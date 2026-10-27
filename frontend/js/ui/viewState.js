// Estados da página: carregando, pronta, vazia (sem inspeção) e erro.
// Em erro a inspeção anterior é ocultada para não ser lida como atual.
const VIEW_STATES = Object.freeze(["loading", "ready", "empty", "error"]);

export function cacheViewStateElements(root = document) {
  return {
    layout: root.querySelector("#inspection-layout"),
    loading: root.querySelector("#loading-state"),
    empty: root.querySelector("#empty-state"),
    error: root.querySelector("#app-error"),
    errorTitle: root.querySelector("#app-error-title"),
    errorMessage: root.querySelector("#app-error-message"),
    actions: [...root.querySelectorAll(".action-buttons button")],
  };
}

export function setViewState(state, elements, { title, message } = {}) {
  if (!VIEW_STATES.includes(state)) {
    throw new Error(`Estado de tela desconhecido: ${state}`);
  }

  elements.layout.dataset.viewState = state;
  elements.layout.setAttribute("aria-busy", String(state === "loading"));
  elements.layout.hidden = state === "empty" || state === "error";
  elements.loading.hidden = state !== "loading";
  elements.empty.hidden = state !== "empty";
  elements.error.hidden = state !== "error";
  elements.actions.forEach((button) => {
    button.disabled = state !== "ready";
  });

  if (state === "error") {
    elements.errorTitle.textContent = title ?? "Falha ao carregar a inspeção";
    elements.errorMessage.textContent = message ?? "Erro desconhecido.";
  }
}
