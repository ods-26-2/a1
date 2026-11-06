import { HEALTH_INTERVAL_MS, INSPECTION_POLL_MS, resolveApiConfig } from "./config.js";
import { API_ERROR_KINDS } from "./data/apiError.js";
import { createInspectionDataSource } from "./data/inspectionDataSource.js";
import { cacheInspectionElements, renderInspection } from "./inspection.js";
import { getStatusPresentation } from "./status.js";
import { cacheConnectivityElements, renderConnectivity } from "./ui/connectivity.js";
import { cacheEvidenceElements } from "./ui/evidence.js";
import { formatTime } from "./ui/format.js";
import { cacheViewStateElements, setViewState } from "./ui/viewState.js";
import { setupInspectionHistory } from "./history.js";

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
const correctButton = document.querySelector("#correct-result");
const reasonInput = document.querySelector("#review-reason");
const statusInput = document.querySelector("#review-status");
const classInput = document.querySelector("#review-class");
const historyList = document.querySelector("#review-history");
const queueItems = document.querySelector("#queue-items");
const queueSummary = document.querySelector("#queue-summary");
const retryButton = document.querySelector("#retry-load");
const actionFeedback = document.querySelector("#action-feedback");
const persistenceTag = document.querySelector("#persistence-tag");
const apiModeTag = document.querySelector("#api-mode-tag");
const demoPanel = document.querySelector("#demo-panel");

let dataSource;
let currentView = null;
let loadToken = 0;
let selectedInspectionId = null;
let queueOffset = 0;
let editing = false;
let reviewBusy = false;
let detailsToken = 0;

async function refreshQueue() {
  try {
    const queue = await dataSource.loadReviewQueue({ limit: 20, offset: queueOffset });
    if (queueOffset && !queue.items.length) { queueOffset = Math.max(0, queueOffset - 20); return refreshQueue(); }
    queueSummary.textContent = `${queue.total} inspeção(ões) aguardando revisão${dataSource.mode === "FAKE" ? " · demonstração sem persistência" : ""}.`;
    queueItems.replaceChildren();
    for (const view of queue.items) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `${view.inspection_id} · ${view.origin.source_id} · ${view.analysis.result}`;
      button.addEventListener("click", async () => {
        if (reviewBusy) return;
        selectedInspectionId = view.inspection_id;
        editing = false;
        reasonInput.value = "";
        await loadCurrentInspection();
      });
      queueItems.append(button);
    }
    document.querySelector("#queue-previous").disabled = queueOffset === 0;
    document.querySelector("#queue-next").disabled = queueOffset + queue.limit >= queue.total;
  } catch (error) { queueSummary.textContent = `Fila não disponível: ${error.message}`; }
}

async function refreshReviewDetails(view) {
  const token = ++detailsToken;
  correctButton.disabled = true;
  try {
    const [options, history] = await Promise.all([
      dataSource.loadReviewOptions(view.inspection_id), dataSource.loadHistory(view.inspection_id),
    ]);
    if (token !== detailsToken || currentView?.inspection_id !== view.inspection_id) return;
    classInput.replaceChildren(new Option("Sem classe conhecida", ""));
    for (const item of options.classes) classInput.add(new Option(`${item.name} (${item.defect_class})`, item.defect_class));
    const final = view.final_decision;
    statusInput.value = (final ?? view.triage).status;
    classInput.value = final ? final.defect_class ?? "" : view.analysis.defect?.defect_class ?? "";
    classInput.disabled = statusInput.value === "APPROVED";
    if (classInput.disabled) classInput.value = "";
    historyList.replaceChildren();
    for (const entry of history.reviews) {
      const item = document.createElement("li");
      item.textContent = `${formatTime(entry.decided_at)} · ${entry.decided_by} · ${entry.status} · ${entry.defect_class ?? "sem classe"} · ${entry.reason}`;
      historyList.append(item);
    }
    if (!history.reviews.length) historyList.textContent = "Nenhuma revisão registrada.";
    correctButton.disabled = reviewBusy;
  } catch (error) { historyList.textContent = `Não foi possível carregar revisões/classes: ${error.message}`; }
}

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
  refreshReviewDetails(view);
}

async function refreshHealth() {
  renderConnectivity(await dataSource.checkHealth(), connectivityElements);
}

async function loadCurrentInspection({ silent = false } = {}) {
  if (reviewBusy || (silent && editing)) return;
  const token = ++loadToken;

  if (!silent) {
    setViewState("loading", viewStateElements);
  }

  try {
    const view = selectedInspectionId ? await dataSource.loadInspection(selectedInspectionId) : await dataSource.loadCurrentInspection();
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
  if (!currentView || reviewBusy) {
    return;
  }
  if (!operatorInput.value.trim()) {
    actionFeedback.textContent = "Informe a identificação do operador antes de registrar.";
    operatorInput.focus();
    return;
  }
  if (!reasonInput.value.trim()) {
    actionFeedback.textContent = "Informe o motivo da revisão antes de registrar.";
    reasonInput.focus();
    return;
  }

  reviewBusy = true;
  ++loadToken;
  confirmButton.disabled = true;
  reviewButton.disabled = true;
  correctButton.disabled = true;
  actionFeedback.textContent = "Registrando ação na API A1…";

  try {
    const receipt = await dataSource.submitReview(currentView.inspection_id, {
      action,
      operator: operatorInput.value,
      reason: reasonInput.value,
      ...(action === "CORRECT" ? { status: statusInput.value, defect_class: classInput.value || null } : {}),
    });
    showInspection(receipt.inspection);
    editing = false;
    reasonInput.value = "";
    const label = getStatusPresentation(receipt.inspection.final_decision.status).label;
    const time = formatTime(receipt.recorded_at);
    actionFeedback.textContent = receipt.persisted
      ? `${label} registrada no backend A1 às ${time} (${receipt.review_id}).`
      : `${label} registrada na API fake às ${time} (${receipt.review_id}). Nenhum dado foi persistido.`;
    try {
      showInspection(await dataSource.loadInspection(receipt.inspection.inspection_id));
    } catch (error) { actionFeedback.textContent += ` Gravação recebida; falha ao reler: ${error.message}`; }
    await refreshQueue();
  } catch (error) {
    actionFeedback.textContent = `Ação não registrada: ${error.message}`;
  } finally {
    reviewBusy = false;
    confirmButton.disabled = !currentView;
    reviewButton.disabled = !currentView;
    if (currentView) refreshReviewDetails(currentView);
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
      selectedInspectionId = null;
      editing = false;
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
  correctButton.addEventListener("click", () => submitReview("CORRECT"));
  for (const input of [operatorInput, reasonInput, statusInput, classInput]) input.addEventListener("input", () => { editing = true; });
  statusInput.addEventListener("change", () => {
    classInput.disabled = statusInput.value === "APPROVED";
    if (classInput.disabled) classInput.value = "";
  });
  document.querySelector("#queue-refresh").addEventListener("click", () => refreshQueue());
  document.querySelector("#queue-previous").addEventListener("click", () => { queueOffset = Math.max(0, queueOffset - 20); refreshQueue(); });
  document.querySelector("#queue-next").addEventListener("click", () => { queueOffset += 20; refreshQueue(); });
  document.querySelector("#show-current").addEventListener("click", () => {
    if (reviewBusy) return;
    selectedInspectionId = null; editing = false; reasonInput.value = ""; loadCurrentInspection();
  });
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
  refreshQueue();
  setupInspectionHistory(dataSource, async (inspectionId) => {
    if (reviewBusy) return;
    selectedInspectionId = inspectionId;
    editing = false;
    reasonInput.value = "";
    await loadCurrentInspection();
  });
  window.setInterval(refreshHealth, HEALTH_INTERVAL_MS);

  if (dataSource.mode === "REAL") {
    window.setInterval(() => { loadCurrentInspection({ silent: true }); refreshQueue(); }, INSPECTION_POLL_MS);
  }
}

initializeApp();
