import { HEALTH_INTERVAL_MS, INSPECTION_POLL_MS, resolveApiConfig } from "./config.js";
import { API_ERROR_KINDS } from "./data/apiError.js";
import { createInspectionDataSource } from "./data/inspectionDataSource.js";
import { cacheInspectionElements, renderInspection } from "./inspection.js";
import { getStatusPresentation } from "./status.js";
import { cacheConnectivityElements, renderConnectivity } from "./ui/connectivity.js";
import { cacheEvidenceElements } from "./ui/evidence.js";
import { formatTime } from "./ui/format.js";
import { cacheViewStateElements, setViewState } from "./ui/viewState.js";

const ERROR_TITLES = Object.freeze({
  [API_ERROR_KINDS.NETWORK]: "API A1 inacessível",
  [API_ERROR_KINDS.TIMEOUT]: "API A1 sem resposta",
  [API_ERROR_KINDS.HTTP]: "Erro da API A1",
  [API_ERROR_KINDS.CONTRACT]: "Resposta da API A1 fora do contrato",
});

const inspectionElements = cacheInspectionElements();
const evidenceElements = cacheEvidenceElements();
const connectivityElements = cacheConnectivityElements();
const viewStateElements = cacheViewStateElements();
const operatorInput = document.querySelector("#operator-id");
const confirmButton = document.querySelector("#confirm-result");
const reviewButton = document.querySelector("#send-review");
const retryButton = document.querySelector("#retry-load");
const actionFeedback = document.querySelector("#action-feedback");
const persistenceTag = document.querySelector("#persistence-tag");
const apiModeTag = document.querySelector("#api-mode-tag");
const demoPanel = document.querySelector("#demo-panel");

let dataSource;
let currentView = null;
let loadToken = 0;

function showLoadError(error) {
  currentView = null;
  setViewState("error", viewStateElements, {
    title: ERROR_TITLES[error.kind] ?? "Falha ao carregar a inspeção",
    message: error.message,
  });
  console.error("Falha ao carregar inspeção:", error);
}

function showInspection(view) {
  currentView = view;
  renderInspection(view, inspectionElements, evidenceElements);
  setViewState("ready", viewStateElements);
}

async function refreshHealth() {
  renderConnectivity(await dataSource.checkHealth(), connectivityElements);
}

async function loadCurrentInspection({ silent = false } = {}) {
  const token = ++loadToken;

  if (!silent) {
    setViewState("loading", viewStateElements);
  }

  try {
    const view = await dataSource.loadCurrentInspection();
    if (token !== loadToken) {
      return;
    }
    if (view === null) {
      currentView = null;
      setViewState("empty", viewStateElements);
      return;
    }
    const changed =
      !silent || JSON.stringify(view) !== JSON.stringify(currentView);
    if (changed) {
      showInspection(view);
      if (!silent) {
        actionFeedback.textContent = "Nenhuma ação registrada.";
      }
    }
  } catch (error) {
    if (token === loadToken) {
      showLoadError(error);
    }
  }
}

async function submitReview(action) {
  if (!currentView) {
    return;
  }
  if (!operatorInput.value.trim()) {
    actionFeedback.textContent = "Informe a identificação do operador antes de registrar.";
    operatorInput.focus();
    return;
  }

  confirmButton.disabled = true;
  reviewButton.disabled = true;
  actionFeedback.textContent = "Registrando ação na API A1…";

  try {
    const receipt = await dataSource.submitReview(currentView.inspection_id, {
      action,
      operator: operatorInput.value,
    });
    showInspection(receipt.inspection);
    const label = getStatusPresentation(receipt.inspection.final_decision.status).label;
    const time = formatTime(receipt.recorded_at);
    actionFeedback.textContent = receipt.persisted
      ? `${label} registrada no backend A1 às ${time} (${receipt.review_id}).`
      : `${label} registrada na API fake às ${time} (${receipt.review_id}). Nenhum dado foi persistido.`;
  } catch (error) {
    actionFeedback.textContent = `Ação não registrada: ${error.message}`;
    confirmButton.disabled = false;
    reviewButton.disabled = false;
  }
}

function syncDemoQuery(demo) {
  const url = new URL(window.location.href);
  url.searchParams.set("scenario", demo.scenario);
  url.searchParams.set("fault", demo.fault);
  window.history.replaceState(null, "", url);
}

function buildDemoButtons(container, items, isActive, onSelect) {
  const buttons = items.map((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = item.label;
    button.dataset.demoId = item.id;
    button.addEventListener("click", () => onSelect(item.id));
    container.append(button);
    return button;
  });

  return () =>
    buttons.forEach((button) =>
      button.setAttribute("aria-pressed", String(isActive(button.dataset.demoId))),
    );
}

function setupDemoPanel(demo) {
  demoPanel.hidden = false;
  let refreshScenarioButtons;
  let refreshFaultButtons;

  const refreshButtons = () => {
    refreshScenarioButtons();
    refreshFaultButtons();
    syncDemoQuery(demo);
  };

  refreshScenarioButtons = buildDemoButtons(
    document.querySelector("#demo-scenarios"),
    demo.scenarios,
    (id) => id === demo.scenario,
    (id) => {
      demo.selectScenario(id);
      refreshButtons();
      loadCurrentInspection();
    },
  );
  refreshFaultButtons = buildDemoButtons(
    document.querySelector("#demo-faults"),
    demo.faults,
    (id) => id === demo.fault,
    (id) => {
      demo.selectFault(id);
      refreshButtons();
      refreshHealth();
      loadCurrentInspection();
    },
  );
  refreshButtons();
}

function bindInteractions() {
  confirmButton.addEventListener("click", () => submitReview("CONFIRM"));
  reviewButton.addEventListener("click", () => submitReview("SEND_TO_REVIEW"));
  retryButton.addEventListener("click", () => {
    refreshHealth();
    loadCurrentInspection();
  });
}

function describeMode() {
  const fake = dataSource.mode === "FAKE";
  apiModeTag.textContent = fake ? "API FAKE" : "API REAL";
  apiModeTag.classList.toggle("api-mode-tag--fake", fake);
  persistenceTag.textContent = fake ? "API fake · sem persistência" : "Gravação no backend A1";
}

function initializeApp() {
  try {
    dataSource = createInspectionDataSource(resolveApiConfig());
  } catch (error) {
    showLoadError(error);
    return;
  }

  describeMode();
  bindInteractions();

  if (dataSource.demo) {
    setupDemoPanel(dataSource.demo);
  }

  refreshHealth();
  loadCurrentInspection();
  window.setInterval(refreshHealth, HEALTH_INTERVAL_MS);

  if (dataSource.mode === "REAL") {
    window.setInterval(() => loadCurrentInspection({ silent: true }), INSPECTION_POLL_MS);
  }
}

initializeApp();
