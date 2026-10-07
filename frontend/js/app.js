import {
  DEMO_SCENARIOS,
  loadInspectionScenario,
} from "./data/inspectionDataSource.js";
import {
  cacheInspectionElements,
  mapEventsToInspection,
  renderInspection,
  updateInspectionStatus,
} from "./inspection.js";
import { getStatusPresentation } from "./status.js";

const inspectionElements = cacheInspectionElements();
const errorMessage = document.querySelector("#app-error");
const confirmButton = document.querySelector("#confirm-result");
const reviewButton = document.querySelector("#send-review");
const actionFeedback = document.querySelector("#action-feedback");
const demoButtons = [...document.querySelectorAll("[data-demo-status]")];

let currentInspection;

function setActiveDemoButton(status) {
  demoButtons.forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.demoStatus === status),
    );
  });
}

function setStatus(status, feedback) {
  updateInspectionStatus(currentInspection, status, inspectionElements);
  setActiveDemoButton(status);
  actionFeedback.textContent = feedback;
}

function showError(error) {
  errorMessage.textContent = error.message;
  errorMessage.hidden = false;
  console.error("Erro ao carregar cenário de inspeção:", error);
}

async function selectScenario(status) {
  errorMessage.hidden = true;

  try {
    const { inferenceEvent, triageEvent, taxonomy } =
      await loadInspectionScenario(status);
    currentInspection = mapEventsToInspection(
      inferenceEvent,
      triageEvent,
      taxonomy,
    );
    renderInspection(currentInspection, inspectionElements);
    setActiveDemoButton(currentInspection.status);
    actionFeedback.textContent = `Mock ${getStatusPresentation(status).label.toLowerCase()} carregado de shared/mocks.`;
  } catch (error) {
    showError(error);
  }
}

function bindInteractions() {
  const allowedStatuses = new Set(Object.keys(DEMO_SCENARIOS));

  demoButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const status = button.dataset.demoStatus;

      if (!allowedStatuses.has(status)) {
        return;
      }

      selectScenario(status);
    });
  });

  confirmButton.addEventListener("click", () => {
    const label = getStatusPresentation(currentInspection.status).label;
    const time = new Intl.DateTimeFormat("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date());

    actionFeedback.textContent = `${label} confirmada localmente às ${time}. Nenhum dado foi persistido.`;
  });

  reviewButton.addEventListener("click", () => {
    setStatus(
      "REVIEW",
      "Peça encaminhada localmente para revisão. Nenhum dado foi persistido.",
    );
  });
}

async function initializeApp() {
  bindInteractions();
  await selectScenario("APPROVED");
}

initializeApp();
