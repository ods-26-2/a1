import { renderEvidence } from "./ui/evidence.js";
import { clampRatio, formatDateTime, formatPercentage } from "./ui/format.js";
import {
  getResultPresentation,
  getSeverityLabel,
  renderResultBadge,
  renderStatus,
} from "./status.js";

export function cacheInspectionElements(root = document) {
  return {
    inspectionId: root.querySelector("#inspection-id"),
    originSource: root.querySelector("#origin-source"),
    capturedAt: root.querySelector("#captured-at"),
    originFrame: root.querySelector("#origin-frame"),
    originBbox: root.querySelector("#origin-bbox"),
    analysisResult: root.querySelector("#analysis-result"),
    classificationName: root.querySelector("#classification-name"),
    classificationId: root.querySelector("#classification-id"),
    classificationDescription: root.querySelector("#classification-description"),
    severity: root.querySelector("#severity"),
    confidenceValue: root.querySelector("#confidence-value"),
    confidenceBar: root.querySelector("#confidence-bar"),
    confidenceFill: root.querySelector("#confidence-fill"),
    similarityValue: root.querySelector("#similarity-value"),
    versionModel: root.querySelector("#version-model"),
    versionTaxonomy: root.querySelector("#version-taxonomy"),
    versionPolicy: root.querySelector("#version-policy"),
    status: {
      banner: root.querySelector("#status-banner"),
      text: root.querySelector("#status-text"),
      icon: root.querySelector("#status-icon"),
      origin: root.querySelector("#status-origin"),
      reason: root.querySelector("#status-reason"),
    },
  };
}

function renderAnalysis(analysis, elements) {
  const presentation = getResultPresentation(analysis.result);
  const { defect } = analysis;

  renderResultBadge(analysis.result, elements.analysisResult);
  elements.classificationName.textContent = defect?.name ?? presentation.heading;
  elements.classificationDescription.textContent =
    defect?.description ?? presentation.description;
  elements.classificationId.textContent = defect?.defect_class ?? "nenhuma";
  elements.severity.hidden = !defect;
  elements.severity.textContent = defect ? getSeverityLabel(defect.severity) : "";

  const confidence = clampRatio(analysis.confidence);
  elements.confidenceValue.textContent = formatPercentage(confidence);
  elements.confidenceFill.style.width = `${confidence * 100}%`;
  elements.confidenceBar.setAttribute("aria-valuenow", String(Math.round(confidence * 100)));
  elements.similarityValue.textContent = formatPercentage(analysis.similarity);
}

function renderDecision(view, elements) {
  const decision = view.final_decision ?? view.triage;
  const byOperator = view.final_decision !== null;

  renderStatus(decision.status, elements.status);
  elements.status.origin.textContent = byOperator
    ? `DECISÃO DO OPERADOR · ${decision.decided_by}`
    : "DECISÃO AUTOMÁTICA DA TRIAGEM";
  elements.status.reason.textContent = byOperator
    ? `${decision.reason} Automática: ${view.triage.status} — ${view.triage.reason}`
    : decision.reason;
}

export function renderInspection(view, elements, evidenceElements) {
  const { origin } = view;

  elements.inspectionId.textContent = view.inspection_id;
  elements.originSource.textContent = origin.source_id;
  elements.capturedAt.textContent = formatDateTime(view.times.captured_at);
  elements.originFrame.textContent = `${origin.frame_index} · ${origin.detection_id}`;
  elements.originBbox.textContent = `[${origin.bbox.join(", ")}]`;
  elements.versionModel.textContent = view.versions.model;
  elements.versionTaxonomy.textContent = view.versions.taxonomy;
  elements.versionPolicy.textContent = view.versions.policy;

  renderAnalysis(view.analysis, elements);
  renderDecision(view, elements);
  renderEvidence(view.evidence, view.inspection_id, evidenceElements);
}
