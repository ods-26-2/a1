// Predicado autossuficiente: também é serializado para execução no navegador via CDP.
export function inspectionReady(document) {
  const summary = document.querySelector("#history-summary");
  const inspection = document.querySelector("#inspection-id");
  if (!summary || !inspection) return false;
  const id = inspection.textContent.trim();
  return !summary.textContent.includes("Carregando") && id !== "" && id !== "—";
}
