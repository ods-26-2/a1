import { inspectionSearchOptions } from "./data/inspectionSearch.js";
import { formatDateTime } from "./ui/format.js";

export function readHistoryFilters(form) {
  const values = new FormData(form);
  const filters = { limit: 20, offset: 0 };
  for (const key of ["captured_from", "captured_to", "result", "source_id", "defect_class"]) {
    const value = values.get(key).trim();
    if (value) filters[key] = key.startsWith("captured_") ? `${value}Z` : value;
  }
  return inspectionSearchOptions(filters);
}

export function setupInspectionHistory(dataSource, selectInspection, root = document) {
  const form = root.querySelector("#history-filters");
  const summary = root.querySelector("#history-summary");
  const items = root.querySelector("#history-items");
  const previous = root.querySelector("#history-previous");
  const next = root.querySelector("#history-next");
  let applied = { limit: 20, offset: 0 }, token = 0;

  async function load(filters) {
    const current = ++token;
    previous.disabled = next.disabled = true;
    items.replaceChildren();
    summary.textContent = "Consultando histórico…";
    try {
      const page = await dataSource.searchInspections(filters);
      if (current !== token) return;
      applied = filters;
      summary.textContent = page.total ? `${page.total} inspeção(ões) · exibindo ${page.items.length ? page.offset + 1 : 0}–${page.offset + page.items.length}${dataSource.mode === "FAKE" ? " · demonstração sem persistência" : ""}.` : "Nenhuma inspeção encontrada para estes filtros.";
      for (const view of page.items) {
        const button = root.createElement("button");
        button.type = "button";
        button.textContent = `${formatDateTime(view.times.captured_at)} · ${view.inspection_id} · ${view.origin.source_id} · ${view.analysis.result} · ${view.analysis.defect?.defect_class ?? "sem defeito conhecido"}`;
        button.addEventListener("click", () => selectInspection(view.inspection_id));
        items.append(button);
      }
      previous.disabled = page.offset === 0;
      next.disabled = page.offset + page.limit >= page.total;
    } catch (error) {
      if (current !== token) return;
      summary.textContent = `Histórico não disponível: ${error.message}`;
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      load(readHistoryFilters(form));
    } catch (error) { ++token; items.replaceChildren(); previous.disabled = next.disabled = true; summary.textContent = error.message; }
  });
  form.addEventListener("reset", () => load({ limit: 20, offset: 0 }));
  previous.addEventListener("click", () => load({ ...applied, offset: Math.max(0, applied.offset - applied.limit) }));
  next.addEventListener("click", () => load({ ...applied, offset: applied.offset + applied.limit }));
  return load(applied);
}
