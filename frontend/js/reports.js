import { readHistoryFilters } from "./history.js";
import { reportExport } from "./data/reports.js";
import { formatDateTime, formatPercentage } from "./ui/format.js";

export function setupReports(dataSource, selectedInspection, root = document) {
  const status = root.querySelector("#report-summary"), results = root.querySelector("#report-results");
  const kind = root.querySelector("#report-kind"), generate = root.querySelector("#report-generate");
  const json = root.querySelector("#report-json"), csv = root.querySelector("#report-csv");
  const causeForm = root.querySelector("#cause-form"), causeId = root.querySelector("#cause-inspection-id"), causeStatus = root.querySelector("#cause-feedback");
  let report = null, token = 0, causeBusy = false;
  const clear = () => { ++token; report = null; json.disabled = csv.disabled = true; results.replaceChildren(); };
  function line(text) { const item = root.createElement("p"); item.textContent = text; results.append(item); }
  async function load() {
    clear();
    const current = token;
    status.textContent = "Gerando relatório…";
    try {
      const selectedKind = kind.value;
      const id = selectedInspection();
      if (selectedKind === "inspection" && !id) throw new Error("Selecione uma inspeção antes de gerar seu relatório.");
      const filters = selectedKind === "inspection" ? {} : readHistoryFilters(root.querySelector("#history-filters"));
      const value = await dataSource.loadReport(selectedKind, filters, id);
      if (current !== token) return;
      report = value;
      status.textContent = `${selectedKind === "inspection" ? value.inspection.inspection_id : `${value.total_inspections} inspeção(ões) no período`} · ${formatDateTime(value.generated_at)}${dataSource.mode === "FAKE" ? " · demonstração sem persistência" : ""}.`;
      if (selectedKind === "inspection") {
        const view = value.inspection;
        line(`Origem: ${view.origin.source_id} · captura: ${formatDateTime(view.times.captured_at)} · análise I8: ${view.analysis.result} · defeito original: ${view.analysis.defect?.defect_class ?? "sem classe"}`);
        line(`Triagem: ${view.triage.status} · decisão final: ${view.final_decision?.status ?? "sem revisão"} · evidência: ${view.evidence.state}`);
        for (const cause of value.causes) line(`Causa provável declarada: ${cause.cause} · ${cause.operator} · ${formatDateTime(cause.recorded_at)} · fundamento: ${cause.basis}`);
        if (!value.causes.length) line("Causa operacional não registrada.");
        for (const event of value.history.events) line(`${formatDateTime(event.occurred_at)} · ${event.event_type} · ${event.actor}`);
        line("A exportação contém análise, decisões, referências de evidência, revisões, causas e auditoria completas.");
      } else {
        if (!value.items.length) line("Nenhuma ocorrência para estes filtros.");
        for (const item of value.items) line(selectedKind === "recurrence" ?
          `${item.source_id} · ${item.taxonomy_version} · ${item.defect_class} · ${item.count} ocorrência(s) · ${formatPercentage(item.rate)} das inspeções filtradas · ${item.recurring ? "recorrente (2 ou mais)" : "ocorrência única"}` :
          `${item.cause ?? "Causa não registrada"} · ${item.count} inspeção(ões) · ${item.status === "OPERATOR_REPORTED" ? "hipótese declarada por operador" : "sem hipótese registrada"}`);
      }
      json.disabled = csv.disabled = false;
    } catch (error) { if (current === token) status.textContent = `Relatório não disponível: ${error.message}`; }
  }
  generate.addEventListener("click", load);
  kind.addEventListener("change", () => { clear(); status.textContent = "Gere o relatório selecionado."; });
  root.querySelector("#history-filters").addEventListener("input", () => { clear(); status.textContent = "Filtros alterados; gere novamente o relatório."; });
  root.querySelector("#history-filters").addEventListener("reset", () => { clear(); status.textContent = "Filtros limpos; gere novamente o relatório."; });
  for (const [button, format] of [[json, "json"], [csv, "csv"]]) button.addEventListener("click", () => {
    if (!report) return;
    try {
      const url = URL.createObjectURL(reportExport(report, format));
      const link = root.createElement("a"); link.href = url; link.download = `a1-${report.kind}.${format}`;
      root.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { status.textContent = error.message; }
  });
  root.querySelector("#cause-use-current").addEventListener("click", () => {
    if (causeBusy) return;
    const id = selectedInspection();
    if (!id) { causeStatus.textContent = "Selecione uma inspeção."; return; }
    causeId.value = id;
    causeForm.elements.namedItem("cause").value = "";
    causeForm.elements.namedItem("basis").value = "";
    causeStatus.textContent = `Causa será registrada para ${id}; o alvo permanece fixo durante o preenchimento.`;
  });
  causeForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (causeBusy) return;
    causeBusy = true;
    const button = root.querySelector("#cause-submit"), id = causeId.value;
    button.disabled = true;
    try {
      const values = new FormData(causeForm);
      await dataSource.recordCause(id, Object.fromEntries(["operator", "cause", "basis"].map((key) => [key, values.get(key)])));
      clear();
      status.textContent = "Hipótese atualizada; gere novamente o relatório.";
      causeStatus.textContent = `Hipótese registrada para ${id}${dataSource.mode === "FAKE" ? " somente na demonstração, sem persistência" : " e auditada no A1"}. Gere novamente os relatórios.`;
      causeForm.elements.namedItem("cause").value = "";
      causeForm.elements.namedItem("basis").value = "";
    } catch (error) { causeStatus.textContent = `Causa não registrada: ${error.message}`; }
    finally { button.disabled = false; causeBusy = false; }
  });
}
