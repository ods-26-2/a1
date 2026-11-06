import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { it } from "node:test";
import { createInspectionDataSource } from "../js/data/inspectionDataSource.js";
import { aggregateFakeReport, reportExport, reportOptions, validateReport } from "../js/data/reports.js";

const period = { captured_from: "2026-10-01T00:00:00Z", captured_to: "2026-11-01T00:00:00Z" };
async function fileFetch(url) { return { ok: true, status: 200, json: async () => JSON.parse(await readFile(fileURLToPath(url), "utf8")) }; }

it("causas fake são explícitas, preservam histórico e não alteram análise/revisão", async () => {
  const source = createInspectionDataSource({ mode: "FAKE" }, { fetchImpl: fileFetch });
  const view = (await source.searchInspections({ result: "NON_CONFORMING" })).items[0];
  const first = await source.recordCause(view.inspection_id, { operator: " op ", cause: "Alinhamento observado", basis: "Posição medida manualmente" });
  await source.recordCause(view.inspection_id, { operator: "op", cause: "Outra hipótese", basis: "Nova observação" });
  const report = await source.loadReport("inspection", {}, view.inspection_id);
  assert.equal(first.operator, "op");
  assert.equal(report.causes.length, 2);
  assert.equal(report.history.events.length, 2);
  assert.equal(report.inspection.analysis.defect.defect_class, "AMASSADO");
  assert.equal(report.inspection.final_decision, null);
  const at = new Date(view.times.captured_at);
  const filters = { captured_from: new Date(at.getTime()-1000).toISOString(), captured_to: new Date(at.getTime()+1000).toISOString() };
  const causes = await source.loadReport("causes", filters);
  assert.ok(causes.items.some((item) => item.cause === "Outra hipótese"));
  assert.ok(!causes.items.some((item) => item.cause === "Alinhamento observado"));
  const fresh = createInspectionDataSource({ mode: "FAKE" }, { fetchImpl: fileFetch });
  assert.equal((await fresh.loadReport("inspection", {}, view.inspection_id)).causes.length, 0);
});

it("recorrência determinística separa origem e taxonomia e usa denominador filtrado", async () => {
  const source = createInspectionDataSource({ mode: "FAKE" }, { fetchImpl: fileFetch });
  const view = (await source.searchInspections({ result: "NON_CONFORMING" })).items[0];
  const b = structuredClone(view), c = structuredClone(view);
  c.origin.source_id = "outra";
  const at = "2026-11-06T12:00:00.000Z";
  const report = aggregateFakeReport("recurrence", [view, b, c], new Map(), period, at);
  assert.equal(validateReport(report, "recurrence"), report);
  assert.equal(report.items[0].count, 2);
  assert.equal(report.items[0].rate, 2/3);
  assert.equal(report.items[0].recurring, true);
  assert.deepEqual(report, aggregateFakeReport("recurrence", [c, b, view], new Map(), period, at));
});

it("limites, dados inconsistentes e causa vazia são recusados", async () => {
  for (const filters of [{}, { captured_from: period.captured_from }, { ...period, captured_to: "2026-12-01T00:00:00Z" }]) assert.throws(() => reportOptions(filters));
  const bad = { report_version: "1.0", kind: "recurrence", generated_at: "2026-11-06T12:00:00Z", filters: period, total_inspections: 1, items: [{ source_id: "A", taxonomy_version: "t", defect_class: "F", count: 1, recurring: false }] };
  assert.throws(() => validateReport(bad, "recurrence"), { kind: "CONTRACT" });
  const source = createInspectionDataSource({ mode: "FAKE" }, { fetchImpl: fileFetch });
  await assert.rejects(source.recordCause("one", { operator: "op", cause: " ", basis: "x" }));
  await assert.rejects(source.recordCause("", { operator: "op", cause: "x", basis: "y" }));
});

it("exportação local retém JSON completo, UTF-8 e células CSV sem fórmula executável", async () => {
  const report = { kind: "causes", report_version: "1.0", generated_at: "2026-11-06T12:00:00Z", filters: period, total_inspections: 1, items: [{ cause: '=HYPERLINK("x")\nvírgula, aspas"', status: "OPERATOR_REPORTED", count: 1 }] };
  const json = reportExport(report, "json");
  assert.match(json.type, /application\/json/);
  assert.deepEqual(JSON.parse(await json.text()), report);
  const csv = reportExport(report, "csv"), bytes = new Uint8Array(await csv.arrayBuffer());
  assert.deepEqual([...bytes.slice(0, 3)], [239,187,191]);
  assert.match(csv.type, /text\/csv/);
  assert.equal(await csv.text(), await reportExport(report, "csv").text());
  assert.ok((await csv.text()).includes('"section","record_json"'));
  assert.throws(() => reportExport({ ...report, data: "a".repeat(10*1024*1024) }, "json"), /10 MiB/);
});

it("adaptador HTTP envia relatórios e registro de causa pelos endpoints A1", async () => {
  const calls = [];
  const source = createInspectionDataSource({ mode: "REAL", baseUrl: "https://a1.test/api/v1/" }, { fetchImpl: async (url, options) => {
    calls.push([url, options]);
    const report = { report_version: "1.0", kind: "causes", generated_at: "2026-11-06T12:00:00Z", filters: period, total_inspections: 0, items: [] };
    return { ok: true, status: 200, json: async () => options.method === "POST" ? { cause_id: "c", inspection_id: "one", ...JSON.parse(options.body), status: "OPERATOR_REPORTED", recorded_at: report.generated_at } : report };
  } });
  await source.loadReport("causes", { ...period, source_id: "cam & +" });
  assert.equal(calls[0][0].pathname, "/api/v1/reports/causes");
  assert.equal(calls[0][0].searchParams.get("source_id"), "cam & +");
  assert.equal(calls[0][0].searchParams.has("limit"), false);
  await source.recordCause("one", { operator: "op", cause: "Hipótese", basis: "Observação" });
  assert.equal(calls[1][0].pathname, "/api/v1/inspections/one/causes");
  assert.equal(calls[1][1].method, "POST");
});
