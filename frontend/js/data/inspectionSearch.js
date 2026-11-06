import { RESULTS, validateInspectionView } from "./inspectionView.js";
import { A1ApiError, API_ERROR_KINDS } from "./apiError.js";

export function inspectionSearchOptions(options = {}) {
  const allowed = ["captured_from", "captured_to", "result", "source_id", "defect_class", "limit", "offset"];
  if (Object.keys(options).some((key) => !allowed.includes(key))) throw new Error("Filtro de histórico desconhecido.");
  const filters = { limit: 50, offset: 0, ...options };
  if (!Number.isInteger(filters.limit) || filters.limit < 1 || filters.limit > 100 ||
      !Number.isInteger(filters.offset) || filters.offset < 0) throw new Error("Paginação inválida (limite 1–100, posição não negativa).");
  for (const key of ["captured_from", "captured_to"]) {
    if (filters[key] !== undefined) {
      const value = filters[key];
      if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) {
        throw new Error("Período exige data-hora ISO 8601 com fuso explícito.");
      }
    }
  }
  if (filters.captured_from && filters.captured_to && Date.parse(filters.captured_from) >= Date.parse(filters.captured_to)) throw new Error("O início deve ser anterior ao fim exclusivo.");
  if (filters.result !== undefined && !RESULTS.includes(filters.result)) throw new Error("Resultado I8 inválido.");
  if (filters.source_id !== undefined && (typeof filters.source_id !== "string" || !filters.source_id.trim() || filters.source_id.length > 256 || /\0|[\uD800-\uDFFF]/u.test(filters.source_id))) throw new Error("Origem inválida (até 256 caracteres).");
  if (filters.defect_class !== undefined && (typeof filters.defect_class !== "string" || !/^[A-Z][A-Z0-9_]{0,127}$/.test(filters.defect_class))) throw new Error("Classe de defeito inválida; use o código em maiúsculas.");
  return filters;
}

export function validateInspectionList(page, requested) {
  const fail = () => { throw new A1ApiError(API_ERROR_KINDS.CONTRACT, "Histórico de inspeções fora do contrato."); };
  if (!page || !Array.isArray(page.items) || !Number.isInteger(page.total) || page.total < 0 ||
      page.limit !== requested.limit || page.offset !== requested.offset ||
      Object.keys(page).some((key) => !["items", "total", "limit", "offset"].includes(key)) ||
      page.items.length !== Math.min(page.limit, Math.max(0, page.total - page.offset))) fail();
  page.items.forEach(validateInspectionView);
  if (new Set(page.items.map((view) => view.inspection_id)).size !== page.items.length) fail();
  for (let index = 1; index < page.items.length; index++) {
    const a = page.items[index - 1], b = page.items[index];
    const difference = Date.parse(a.times.captured_at) - Date.parse(b.times.captured_at);
    if (difference < 0 || (difference === 0 && a.inspection_id < b.inspection_id)) fail();
  }
  return page;
}
