import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { it } from "node:test";
import { createInspectionDataSource } from "../js/data/inspectionDataSource.js";
import { createFakeA1Api } from "../js/data/fakeA1Api.js";
import { inspectionSearchOptions, validateInspectionList } from "../js/data/inspectionSearch.js";
import { setupInspectionHistory } from "../js/history.js";

async function fileFetch(url) {
  return { ok: true, status: 200, json: async () => JSON.parse(await readFile(fileURLToPath(url), "utf8")) };
}

it("histórico fake combina todos os filtros e conserva análise após correção", async () => {
  const api = createFakeA1Api({ fetchImpl: fileFetch, delayMs: 0 });
  const all = await api.searchInspections({ limit: 100 });
  assert.equal(all.total, 4);
  const view = all.items.find((item) => item.analysis.result === "NON_CONFORMING");
  const filters = { captured_from: view.times.captured_at, captured_to: "2100-01-01T00:00:00Z", result: "NON_CONFORMING", source_id: view.origin.source_id, defect_class: view.analysis.defect.defect_class };
  await api.submitReview(view.inspection_id, { action: "CORRECT", operator: "op", reason: "Conferido", status: "REJECTED", defect_class: "FURADO" });
  const page = await api.searchInspections(filters);
  assert.equal(page.total, 1);
  assert.equal(page.items[0].analysis.defect.defect_class, "AMASSADO");
  assert.equal(page.items[0].final_decision.defect_class, "FURADO");
  assert.equal((await api.searchInspections({ ...filters, captured_to: view.times.captured_at, captured_from: "2000-01-01T00:00:00Z" })).total, 0);
  assert.equal((await api.searchInspections({ ...filters, source_id: "missing" })).total, 0);
  assert.deepEqual((await api.searchInspections({ ...filters, offset: 20 })).items, []);
  const paged = [];
  for (let offset = 0; offset < 4; offset++) paged.push((await api.searchInspections({ limit: 1, offset })).items[0].inspection_id);
  assert.deepEqual(paged, all.items.map((item) => item.inspection_id));
});

it("HTTP codifica filtros, preserva fuso e aplica guarda à página recebida", async () => {
  const fixture = await (await fileFetch(new URL("../../shared/mocks/a1-api/inspections/non-conforming.json", import.meta.url))).json();
  let requested;
  const source = createInspectionDataSource({ mode: "REAL", baseUrl: "https://a1.test/api/v1/" }, { fetchImpl: async (url) => {
    requested = url;
    return { ok: true, status: 200, json: async () => ({ items: [fixture], total: 1, limit: 20, offset: 0 }) };
  } });
  const options = { limit: 20, offset: 0, source_id: "cam & +/?", captured_from: "2026-01-01T09:00:00-03:00", result: "NON_CONFORMING", defect_class: "AMASSADO" };
  assert.equal((await source.searchInspections(options)).items[0].inspection_id, fixture.inspection_id);
  assert.equal(requested.pathname, "/api/v1/inspections");
  for (const [key, value] of Object.entries(options)) assert.equal(requested.searchParams.get(key), String(value));
  assert.throws(() => validateInspectionList({ items: [], total: 1, limit: 20, offset: 0 }, options), { kind: "CONTRACT" });
  assert.throws(() => validateInspectionList({ items: [fixture, fixture], total: 2, limit: 20, offset: 0 }, options), { kind: "CONTRACT" });
  const bad = structuredClone(fixture); bad.analysis.result = "APPROVED";
  assert.throws(() => validateInspectionList({ items: [bad], total: 1, limit: 20, offset: 0 }, options), { kind: "CONTRACT" });
});

it("validação dos filtros recusa período sem fuso, ordem, paginação e códigos inválidos", () => {
  for (const filters of [{ captured_from: "2026-01-01" }, { captured_to: "2026-01-01T12:00:00" },
    { captured_from: "2026-01-02T00:00:00Z", captured_to: "2026-01-01T00:00:00Z" },
    { result: "APPROVED" }, { source_id: " " }, { source_id: "x\0y" }, { defect_class: "furado" }, { limit: 101 }, { offset: -1 }, { unknown: "x" }]) {
    assert.throws(() => inspectionSearchOptions(filters));
  }
});

function fakeDocument() {
  const make = () => ({ textContent: "", disabled: false, children: [], handlers: {},
    replaceChildren() { this.children = []; }, append(value) { this.children.push(value); },
    addEventListener(event, callback) { this.handlers[event] = callback; } });
  const elements = Object.fromEntries(["history-filters", "history-summary", "history-items", "history-previous", "history-next"].map((id) => [id, make()]));
  return { elements, querySelector: (selector) => elements[selector.slice(1)], createElement: make };
}

it("controle da tela renderiza seleção, paginação, vazio e erro sem resultados antigos", async () => {
  const root = fakeDocument(), calls = [], selected = [];
  const view = { inspection_id: "inspection-1", times: { captured_at: "2026-01-01T12:00:00Z" }, origin: { source_id: "camera-A" }, analysis: { result: "ANOMALY", defect: null } };
  const source = { mode: "REAL", searchInspections: async (filters) => {
    calls.push(filters);
    if (calls.length === 3) throw new Error("API offline");
    return { items: filters.offset ? [] : [view], total: filters.offset ? 0 : 21, limit: 20, offset: filters.offset };
  } };
  await setupInspectionHistory(source, (id) => selected.push(id), root);
  assert.equal(root.elements["history-next"].disabled, false);
  root.elements["history-items"].children[0].handlers.click();
  assert.deepEqual(selected, ["inspection-1"]);
  await root.elements["history-next"].handlers.click();
  assert.equal(calls[1].offset, 20);
  assert.match(root.elements["history-summary"].textContent, /Nenhuma inspeção/);
  await root.elements["history-previous"].handlers.click();
  assert.match(root.elements["history-summary"].textContent, /API offline/);
  assert.equal(root.elements["history-items"].children.length, 0);
});
