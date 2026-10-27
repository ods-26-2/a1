// API A1 fake: substitui o backend até S3-07 com a mesma interface de
// httpA1Api.js. Os dados vêm de shared/mocks/a1-api/inspections/, derivados dos
// eventos 6c válidos. Nada é persistido e a mídia representa um S4 simulado.
import { A1ApiError, API_ERROR_KINDS } from "./apiError.js";

const REPO_ROOT = new URL("../../../", import.meta.url);
const FIXTURE_DIR = "shared/mocks/a1-api/inspections/";

export const FAKE_SCENARIOS = Object.freeze([
  Object.freeze({ id: "CONFORMING", fixture: "conforming.json", label: "Conforme" }),
  Object.freeze({ id: "NON_CONFORMING", fixture: "non-conforming.json", label: "Não conforme" }),
  Object.freeze({ id: "ANOMALY", fixture: "anomaly.json", label: "Anomalia" }),
  Object.freeze({ id: "UNCERTAIN", fixture: "uncertain.json", label: "Incerto" }),
]);

export const FAKE_FAULTS = Object.freeze([
  Object.freeze({ id: "NONE", label: "Sem falha" }),
  Object.freeze({ id: "SLOW", label: "API lenta" }),
  Object.freeze({ id: "OFFLINE", label: "API offline" }),
  Object.freeze({ id: "S4_UNAVAILABLE", label: "S4 indisponível" }),
  Object.freeze({ id: "INVALID_CONTRACT", label: "Contrato inválido" }),
]);

const SLOW_DELAY_MS = 1800;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function offlineError() {
  return new A1ApiError(
    API_ERROR_KINDS.NETWORK,
    "API A1 inacessível (falha simulada pela API fake).",
  );
}

function findById(list, id, label) {
  const item = list.find((entry) => entry.id === id);
  if (!item) {
    throw new Error(`${label} desconhecido na API fake: ${id}.`);
  }
  return item;
}

export function createFakeA1Api({
  fetchImpl = globalThis.fetch.bind(globalThis),
  rootUrl = REPO_ROOT,
  scenario = "CONFORMING",
  fault = "NONE",
  delayMs = 250,
  now = () => new Date(),
} = {}) {
  const root = new URL(rootUrl);
  const reviews = new Map();
  let reviewCounter = 0;
  let currentScenario = findById(FAKE_SCENARIOS, scenario, "Cenário");
  let currentFault = findById(FAKE_FAULTS, fault, "Falha");

  async function simulateLatency() {
    await wait(currentFault.id === "SLOW" ? SLOW_DELAY_MS : delayMs);
    if (currentFault.id === "OFFLINE") {
      throw offlineError();
    }
  }

  async function loadFixture(entry) {
    const response = await fetchImpl(new URL(FIXTURE_DIR + entry.fixture, root));
    if (!response.ok) {
      throw new A1ApiError(
        API_ERROR_KINDS.HTTP,
        `Fixture ${entry.fixture} não pôde ser carregada (HTTP ${response.status}).`,
        { status: response.status },
      );
    }
    const view = await response.json();
    if (typeof view.evidence?.url === "string") {
      view.evidence.url = new URL(view.evidence.url, root).href;
    }
    return view;
  }

  function applyFault(view) {
    if (currentFault.id === "S4_UNAVAILABLE") {
      view.evidence = {
        state: "UNAVAILABLE",
        clip_id: null,
        url: null,
        expires_at: null,
        detail: "S4 não respondeu ao pedido de snapshot (timeout simulado).",
      };
    }
    if (currentFault.id === "INVALID_CONTRACT") {
      // Vocabulário legado ods.ver1: deve ser recusado pela guarda do front.
      view.analysis.result = "APPROVED";
    }
    return view;
  }

  async function buildCurrentView() {
    const view = await loadFixture(currentScenario);
    view.final_decision = reviews.get(view.inspection_id) ?? null;
    return applyFault(view);
  }

  return Object.freeze({
    mode: "FAKE",

    async getHealth() {
      await wait(0);
      if (currentFault.id === "OFFLINE") {
        throw offlineError();
      }
      const s4Down = currentFault.id === "S4_UNAVAILABLE";
      return {
        status: s4Down ? "DEGRADED" : "ONLINE",
        mode: "FAKE",
        checked_at: now().toISOString(),
        components: [
          { name: "api-a1", status: "SIMULATED", detail: "API fake no navegador." },
          { name: "i8-subscriber", status: "SIMULATED", detail: "Eventos 6c de fixture." },
          {
            name: "s4",
            status: s4Down ? "DOWN" : "SIMULATED",
            detail: s4Down ? "Timeout simulado." : "Mídia de demonstração.",
          },
        ],
      };
    },

    async getCurrentInspection() {
      await simulateLatency();
      return buildCurrentView();
    },

    async getInspection(inspectionId) {
      await simulateLatency();
      for (const entry of FAKE_SCENARIOS) {
        const view = await loadFixture(entry);
        if (view.inspection_id === inspectionId) {
          view.final_decision = reviews.get(inspectionId) ?? null;
          return applyFault(view);
        }
      }
      throw new A1ApiError(API_ERROR_KINDS.HTTP, `Inspeção ${inspectionId} não encontrada.`, {
        status: 404,
      });
    },

    async submitReview(inspectionId, { action, operator }) {
      await simulateLatency();
      const view = await buildCurrentView();
      if (view.inspection_id !== inspectionId) {
        throw new A1ApiError(API_ERROR_KINDS.HTTP, `Inspeção ${inspectionId} não é a atual.`, {
          status: 409,
        });
      }

      const recordedAt = now().toISOString();
      const decision =
        action === "SEND_TO_REVIEW"
          ? {
              status: "REVIEW",
              reason: "Encaminhada para revisão pelo operador.",
              decided_by: operator,
              decided_at: recordedAt,
            }
          : {
              status: (view.final_decision ?? view.triage).status,
              reason: "Decisão confirmada pelo operador.",
              decided_by: operator,
              decided_at: recordedAt,
            };

      reviews.set(inspectionId, decision);
      reviewCounter += 1;
      return {
        review_id: `fake-review-${reviewCounter}`,
        action,
        recorded_at: recordedAt,
        persisted: false,
        inspection: { ...view, final_decision: decision },
      };
    },

    demo: Object.freeze({
      scenarios: FAKE_SCENARIOS,
      faults: FAKE_FAULTS,
      get scenario() {
        return currentScenario.id;
      },
      get fault() {
        return currentFault.id;
      },
      selectScenario(id) {
        currentScenario = findById(FAKE_SCENARIOS, id, "Cenário");
      },
      selectFault(id) {
        currentFault = findById(FAKE_FAULTS, id, "Falha");
      },
    }),
  });
}
