import { inspectionSearchOptions } from "./inspectionSearch.js";
import { validateInspectionView } from "./inspectionView.js";
import { A1ApiError, API_ERROR_KINDS } from "./apiError.js";

export function reportOptions(options = {}) {
  const { limit, offset, ...filters } = inspectionSearchOptions(options);
  if (!filters.captured_from || !filters.captured_to || Date.parse(filters.captured_to) - Date.parse(filters.captured_from) > 31 * 86400000) throw new Error("Relatório exige início e fim UTC com período máximo de 31 dias.");
  return filters;
}

export function validateCause(cause) {
  if (!cause || cause.status !== "OPERATOR_REPORTED" ||
      ["cause_id", "inspection_id", "operator", "cause", "basis", "recorded_at"].some((key) => typeof cause[key] !== "string" || !cause[key].trim()) ||
      !Number.isFinite(Date.parse(cause.recorded_at))) throw new A1ApiError(API_ERROR_KINDS.CONTRACT, "Causa declarada fora do contrato.");
  return cause;
}

export function validateReport(report, kind) {
  const fail = () => { throw new A1ApiError(API_ERROR_KINDS.CONTRACT, "Relatório A1 fora do contrato."); };
  if (!report || report.report_version !== "1.0" || report.kind !== kind || !Number.isFinite(Date.parse(report.generated_at))) fail();
  if (kind === "inspection") {
    validateInspectionView(report.inspection);
    if (!report.history || report.history.inspection_id !== report.inspection.inspection_id ||
        [report.history.events, report.history.reviews, report.causes].some((items) => !Array.isArray(items) || items.length > 5000)) fail();
    report.causes.forEach((cause) => { validateCause(cause); if (cause.inspection_id !== report.inspection.inspection_id) fail(); });
    for (const event of report.history.events) if (!["event_type", "actor", "occurred_at"].every((key) => typeof event[key] === "string" && event[key]) || !Number.isFinite(Date.parse(event.occurred_at)) || !event.details || typeof event.details !== "object") fail();
  } else {
    if (!Number.isInteger(report.total_inspections) || report.total_inspections < 0 || report.total_inspections > 5000 || !Array.isArray(report.items) || report.items.length > 5000) fail();
    try { reportOptions(Object.fromEntries(Object.entries(report.filters).filter(([, value]) => value !== null))); } catch { fail(); }
    let sum = 0;
    for (const item of report.items) {
      if (!Number.isInteger(item.count) || item.count <= 0) fail();
      sum += item.count;
      if (kind === "recurrence") {
        if (["source_id", "taxonomy_version", "defect_class"].some((key) => typeof item[key] !== "string") || item.recurring !== (item.count >= 2) || !Number.isFinite(item.rate) || Math.abs(item.rate - item.count / report.total_inspections) > 1e-12) fail();
      } else if (!((item.status === "NOT_RECORDED" && item.cause === null) || (item.status === "OPERATOR_REPORTED" && typeof item.cause === "string" && item.cause.trim()))) fail();
    }
    if (sum > report.total_inspections || (kind === "causes" && sum !== report.total_inspections)) fail();
  }
  return report;
}

export function aggregateFakeReport(kind, views, causes, filters, generatedAt) {
  const groups = new Map();
  for (const view of views) {
    if (kind === "recurrence" && view.analysis.result !== "NON_CONFORMING") continue;
    const key = kind === "recurrence" ? [view.origin.source_id, view.versions.taxonomy, view.analysis.defect.defect_class] : (causes.get(view.inspection_id)?.at(-1)?.cause ?? null);
    const id = JSON.stringify(key), previous = groups.get(id);
    groups.set(id, { key, count: (previous?.count ?? 0) + 1 });
  }
  const sorted = [...groups.values()].sort((a, b) => b.count - a.count || (a.key === null ? 1 : b.key === null ? -1 : JSON.stringify(a.key) < JSON.stringify(b.key) ? -1 : 1));
  const items = sorted.map(({ key, count }) => kind === "recurrence" ? { source_id: key[0], taxonomy_version: key[1], defect_class: key[2], count, rate: count / views.length, recurring: count >= 2 } : { cause: key, count, status: key === null ? "NOT_RECORDED" : "OPERATOR_REPORTED" });
  return { report_version: "1.0", kind, generated_at: generatedAt, filters: { captured_from: filters.captured_from, captured_to: filters.captured_to, result: filters.result ?? null, source_id: filters.source_id ?? null, defect_class: filters.defect_class ?? null }, total_inspections: views.length, items };
}

export function reportExport(report, format) {
  const stable = (value) => JSON.stringify(value, (_, item) => item && !Array.isArray(item) && typeof item === "object" ? Object.fromEntries(Object.keys(item).sort().map((key) => [key, item[key]])) : item);
  if (!["json", "csv"].includes(format)) throw new Error("Formato inválido.");
  let text;
  if (format === "json") text = stable(report);
  else {
    const cell = (value) => {
      let text = String(value);
      if (/^[\s\uFEFF]*[=+\-@]/u.test(text)) text = "'" + text;
      return `"${text.replaceAll('"', '""')}"`;
    };
    const rows = [["section", "record_json"]];
    for (const key of Object.keys(report).sort()) for (const value of Array.isArray(report[key]) ? report[key] : [report[key]]) rows.push([key, stable(value)]);
    text = "\ufeff" + rows.map((row) => row.map(cell).join(",")).join("\r\n") + "\r\n";
  }
  const blob = new Blob([text], { type: format === "json" ? "application/json;charset=utf-8" : "text/csv;charset=utf-8" });
  if (blob.size > 10 * 1024 * 1024) throw new Error("Exportação excede 10 MiB; reduza o período/filtros.");
  return blob;
}
