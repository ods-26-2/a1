import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

import { createFakeA1Api, FAKE_SCENARIOS } from "../js/data/fakeA1Api.js";
import { createHttpA1Api } from "../js/data/httpA1Api.js";
import { createInspectionDataSource } from "../js/data/inspectionDataSource.js";
import { validateInspectionView } from "../js/data/inspectionView.js";

const ROOT = new URL("../../", import.meta.url);

// fetch de arquivos locais para a API fake fora do navegador.
async function fileFetch(url) {
  try {
    const text = await readFile(fileURLToPath(url), "utf-8");
    return { ok: true, status: 200, json: async () => JSON.parse(text) };
  } catch {
    return { ok: false, status: 404, json: async () => null };
  }
}

function jsonResponse(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

async function readFixture(name) {
  const url = new URL(`shared/mocks/a1-api/inspections/${name}`, ROOT);
  return JSON.parse(await readFile(fileURLToPath(url), "utf-8"));
}

function fakeSource(options = {}) {
  return createInspectionDataSource(
    { mode: "FAKE", scenario: options.scenario, fault: options.fault },
    { fetchImpl: fileFetch },
  );
}

describe("guarda de contrato InspectionView", () => {
  it("aceita as quatro fixtures da API fake", async () => {
    for (const { fixture } of FAKE_SCENARIOS) {
      const view = await readFixture(fixture);
      assert.equal(validateInspectionView(view), view, fixture);
    }
  });

  it("recusa vocabulário legado e defeito fora de NON_CONFORMING", async () => {
    const view = await readFixture("conforming.json");
    assert.throws(
      () => validateInspectionView({ ...view, analysis: { ...view.analysis, result: "APPROVED" } }),
      { kind: "CONTRACT" },
    );
    const anomaly = await readFixture("anomaly.json");
    const withDefect = structuredClone(anomaly);
    withDefect.analysis.defect = {
      defect_class: "AMASSADO",
      name: "Amassado",
      description: "x",
      severity: "HIGH",
    };
    assert.throws(() => validateInspectionView(withDefect), /analysis\.defect/);
  });

  it("exige placeholder sem URL quando a evidência não está disponível", async () => {
    const view = await readFixture("anomaly.json");
    view.evidence.url = "frontend/assets/images/mock-piece-approved.png";
    assert.throws(() => validateInspectionView(view), /evidence\.url/);
  });

  it("recusa confiança fora de 0–1", async () => {
    const view = await readFixture("uncertain.json");
    view.analysis.confidence = 1.2;
    assert.throws(() => validateInspectionView(view), /confidence/);
  });
});

describe("API fake", () => {
  it("representa os quatro result e os três estados de triagem", async () => {
    const source = fakeSource();
    const results = new Set();
    const statuses = new Set();

    for (const { id } of FAKE_SCENARIOS) {
      source.demo.selectScenario(id);
      const view = await source.loadCurrentInspection();
      results.add(view.analysis.result);
      statuses.add(view.triage.status);
    }

    assert.deepEqual([...results].sort(), ["ANOMALY", "CONFORMING", "NON_CONFORMING", "UNCERTAIN"]);
    assert.deepEqual([...statuses].sort(), ["APPROVED", "REJECTED", "REVIEW"]);
  });

  it("simula API offline, S4 indisponível e contrato inválido", async () => {
    const offline = fakeSource({ fault: "OFFLINE" });
    assert.equal((await offline.checkHealth()).state, "OFFLINE");
    await assert.rejects(offline.loadCurrentInspection(), { kind: "NETWORK" });

    const s4 = fakeSource({ scenario: "NON_CONFORMING", fault: "S4_UNAVAILABLE" });
    assert.equal((await s4.checkHealth()).state, "DEGRADED");
    const view = await s4.loadCurrentInspection();
    assert.equal(view.evidence.state, "UNAVAILABLE");
    assert.equal(view.evidence.url, null);

    const invalid = fakeSource({ fault: "INVALID_CONTRACT" });
    await assert.rejects(invalid.loadCurrentInspection(), { kind: "CONTRACT" });
  });

  it("registra revisão sem apagar a decisão automática e sem persistir", async () => {
    const source = fakeSource({ scenario: "NON_CONFORMING" });
    const view = await source.loadCurrentInspection();
    const receipt = await source.submitReview(view.inspection_id, {
      action: "SEND_TO_REVIEW",
      operator: " op-1 ",
    });

    assert.equal(receipt.persisted, false);
    assert.equal(receipt.inspection.triage.status, "REJECTED");
    assert.equal(receipt.inspection.final_decision.status, "REVIEW");
    assert.equal(receipt.inspection.final_decision.decided_by, "op-1");
    await assert.rejects(
      source.submitReview(view.inspection_id, { action: "CONFIRM", operator: "" }),
      /operador/,
    );
  });

  it("resolve a URL da evidência a partir da raiz do repositório", async () => {
    const view = await fakeSource().loadCurrentInspection();
    assert.equal(
      view.evidence.url,
      new URL("frontend/assets/images/mock-piece-approved.png", ROOT).href,
    );
  });
});

describe("API real (HTTP)", () => {
  it("usa as mesmas rotas e a mesma guarda que a API fake", async () => {
    const fixture = await readFixture("non-conforming.json");
    const calls = [];
    const fetchImpl = async (url, init) => {
      calls.push(`${init.method} ${new URL(url).pathname}`);
      if (url.pathname.endsWith("/health")) {
        return jsonResponse(200, {
          status: "ONLINE",
          mode: "REAL",
          checked_at: "2026-10-27T12:00:00.000Z",
          components: [{ name: "database", status: "UP", detail: "" }],
        });
      }
      return jsonResponse(200, fixture);
    };
    const source = createInspectionDataSource(
      { mode: "REAL", baseUrl: "http://a1.test/api/v1" },
      { fetchImpl },
    );

    assert.equal((await source.checkHealth()).state, "ONLINE");
    assert.equal((await source.loadCurrentInspection()).inspection_id, fixture.inspection_id);
    assert.deepEqual(calls, ["GET /api/v1/health", "GET /api/v1/inspections/current"]);
  });

  it("trata 204 como ausência de inspeção e erro de rede como OFFLINE", async () => {
    const empty = createInspectionDataSource(
      { mode: "REAL", baseUrl: "http://a1.test/api/v1/" },
      { fetchImpl: async () => jsonResponse(204, null) },
    );
    assert.equal(await empty.loadCurrentInspection(), null);

    const down = createInspectionDataSource(
      { mode: "REAL", baseUrl: "http://a1.test/api/v1/" },
      {
        fetchImpl: async () => {
          throw new TypeError("fetch failed");
        },
      },
    );
    assert.equal((await down.checkHealth()).state, "OFFLINE");
    await assert.rejects(down.loadCurrentInspection(), { kind: "NETWORK" });
  });

  it("converte HTTP de erro em A1ApiError", async () => {
    const api = createHttpA1Api({
      baseUrl: "http://a1.test/api/v1/",
      fetchImpl: async () => jsonResponse(500, {}),
    });
    await assert.rejects(api.getCurrentInspection(), { kind: "HTTP", status: 500 });
  });
});
