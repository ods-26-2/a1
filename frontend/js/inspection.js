import { renderStatus } from "./status.js";
import { getCategoryById } from "./taxonomy.js";

const percentageFormatter = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  maximumFractionDigits: 0,
});

const dateFormatter = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "medium",
});

const severityLabels = Object.freeze({
  NONE: "NENHUMA · NONE",
  LOW: "BAIXA · LOW",
  MEDIUM: "MÉDIA · MEDIUM",
  HIGH: "ALTA · HIGH",
});

function clampRatio(value) {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return 0;
  }

  return Math.min(1, Math.max(0, numericValue));
}

function formatPercentage(value) {
  return percentageFormatter.format(clampRatio(value));
}

function formatTimestamp(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? "Horário indisponível" : dateFormatter.format(date);
}

export function cacheInspectionElements(root = document) {
  return {
    eventId: root.querySelector("#event-id"),
    pieceId: root.querySelector("#piece-id"),
    inspectionTime: root.querySelector("#inspection-time"),
    evidenceImage: root.querySelector("#evidence-image"),
    classificationName: root.querySelector("#classification-name"),
    classificationId: root.querySelector("#classification-id"),
    classificationDescription: root.querySelector("#classification-description"),
    severity: root.querySelector("#severity"),
    confidenceValue: root.querySelector("#confidence-value"),
    confidenceBar: root.querySelector("#confidence-bar"),
    confidenceFill: root.querySelector("#confidence-fill"),
    similarityValue: root.querySelector("#similarity-value"),
    status: {
      banner: root.querySelector("#status-banner"),
      text: root.querySelector("#status-text"),
      icon: root.querySelector("#status-icon"),
    },
  };
}

export function renderInspection(inspection, elements) {
  const { classification, status } = inspection;
  const confidence = clampRatio(inspection.confidence);

  elements.eventId.textContent = inspection.pieceId;
  elements.pieceId.textContent = inspection.pieceId;
  elements.inspectionTime.textContent = formatTimestamp(inspection.timestamp);
  elements.evidenceImage.src = inspection.imagePath;
  elements.evidenceImage.onerror = () => {
    elements.evidenceImage.onerror = null;
    elements.evidenceImage.src = "./assets/images/mock-piece-approved.png";
  };
  elements.evidenceImage.alt = `Evidência simulada da peça ${inspection.pieceId} com ${classification.name.toLowerCase()}`;
  elements.classificationName.textContent = classification.name;
  elements.classificationId.textContent = classification.id;
  elements.classificationDescription.textContent = classification.description;
  elements.severity.textContent = severityLabels[classification.severity] ?? classification.severity;
  elements.confidenceValue.textContent = formatPercentage(confidence);
  elements.confidenceFill.style.width = `${confidence * 100}%`;
  elements.confidenceBar.setAttribute(
    "aria-valuenow",
    String(Math.round(confidence * 100)),
  );
  elements.similarityValue.textContent = formatPercentage(inspection.similarity);

  renderStatus(status, elements.status);
}

export function mapEventsToInspection(inferenceEvent, triageEvent, taxonomy) {
  const payload = inferenceEvent.payload;
  const classification = getCategoryById(taxonomy, payload.classification.id);

  return {
    pieceId: payload.piece_id,
    timestamp: inferenceEvent.published_at,
    classification,
    confidence: payload.confidence,
    similarity: payload.similarity,
    imagePath: payload.evidence?.image_url ?? "./assets/images/mock-piece-approved.png",
    status: triageEvent.payload.status,
  };
}

export function updateInspectionStatus(inspection, status, elements) {
  inspection.status = status;
  renderStatus(status, elements.status);
}
