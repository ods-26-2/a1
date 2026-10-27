// Indicador de conectividade do cabeçalho. "Online" só aparece depois de uma
// resposta válida de GET /health; a API fake é identificada como tal.
import { formatTime } from "./format.js";

const CONNECTIVITY_PRESENTATION = Object.freeze({
  CHECKING: Object.freeze({ label: "VERIFICANDO API", className: "system-state--checking" }),
  ONLINE: Object.freeze({ label: "SISTEMA ONLINE", className: "system-state--online" }),
  DEGRADED: Object.freeze({ label: "INTEGRAÇÃO DEGRADADA", className: "system-state--degraded" }),
  OFFLINE: Object.freeze({ label: "API A1 OFFLINE", className: "system-state--offline" }),
});

const CONNECTIVITY_CLASSES = Object.values(CONNECTIVITY_PRESENTATION).map(
  ({ className }) => className,
);

export function cacheConnectivityElements(root = document) {
  return {
    container: root.querySelector("#system-state"),
    label: root.querySelector("#system-state-label"),
    detail: root.querySelector("#system-state-detail"),
  };
}

function describe({ state, health, error }) {
  if (state === "CHECKING") {
    return "Consultando saúde do backend A1";
  }
  if (state === "OFFLINE") {
    return error?.message ?? "Sem resposta do backend A1";
  }
  const mode = health.mode === "FAKE" ? "API fake" : "API real";
  const down = health.components
    .filter(({ status }) => status === "DOWN")
    .map(({ name }) => name.toUpperCase());
  const suffix = down.length ? ` · falha: ${down.join(", ")}` : "";
  return `${mode} · verificado às ${formatTime(health.checked_at)}${suffix}`;
}

export function renderConnectivity(result, elements) {
  const presentation =
    CONNECTIVITY_PRESENTATION[result.state] ?? CONNECTIVITY_PRESENTATION.OFFLINE;
  const label =
    result.state === "ONLINE" && result.health?.mode === "FAKE"
      ? `${presentation.label} · FAKE`
      : presentation.label;

  elements.container.classList.remove(...CONNECTIVITY_CLASSES);
  elements.container.classList.add(presentation.className);
  elements.label.textContent = label;
  elements.detail.textContent = describe(result);
}
