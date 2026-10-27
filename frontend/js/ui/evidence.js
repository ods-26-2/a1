// Evidência S4 da inspeção. Sem mídia disponível, mostra placeholder
// explícito; nunca substitui por imagem de outra peça.
import { formatDateTime } from "./format.js";

const EVIDENCE_PRESENTATION = Object.freeze({
  AVAILABLE: Object.freeze({ tag: "S4 · DISPONÍVEL", icon: "", title: "" }),
  PENDING: Object.freeze({ tag: "S4 · PENDENTE", icon: "…", title: "Evidência pendente" }),
  UNAVAILABLE: Object.freeze({
    tag: "S4 · INDISPONÍVEL",
    icon: "!",
    title: "Evidência indisponível",
  }),
  EXPIRED: Object.freeze({ tag: "S4 · EXPIRADA", icon: "⌛", title: "Evidência expirada" }),
  LOAD_FAILED: Object.freeze({
    tag: "S4 · FALHA",
    icon: "!",
    title: "Falha ao carregar a mídia",
  }),
});

export function cacheEvidenceElements(root = document) {
  return {
    frame: root.querySelector(".evidence-frame"),
    image: root.querySelector("#evidence-image"),
    placeholder: root.querySelector("#evidence-placeholder"),
    placeholderIcon: root.querySelector("#evidence-placeholder-icon"),
    placeholderTitle: root.querySelector("#evidence-placeholder-title"),
    detail: root.querySelector("#evidence-detail"),
    stateTag: root.querySelector("#evidence-state-tag"),
    clip: root.querySelector("#evidence-clip"),
    expires: root.querySelector("#evidence-expires"),
  };
}

function showPlaceholder(state, elements) {
  const presentation = EVIDENCE_PRESENTATION[state];

  elements.image.hidden = true;
  elements.image.removeAttribute("src");
  elements.placeholder.hidden = false;
  elements.placeholderIcon.textContent = presentation.icon;
  elements.placeholderTitle.textContent = presentation.title;
  elements.stateTag.textContent = presentation.tag;
  elements.frame.dataset.evidenceState = state;
}

export function renderEvidence(evidence, inspectionId, elements) {
  elements.detail.textContent = evidence.detail;
  elements.clip.textContent = evidence.clip_id ?? "—";
  elements.expires.textContent = formatDateTime(evidence.expires_at);

  if (evidence.state !== "AVAILABLE") {
    showPlaceholder(evidence.state, elements);
    return;
  }

  elements.stateTag.textContent = EVIDENCE_PRESENTATION.AVAILABLE.tag;
  elements.frame.dataset.evidenceState = "AVAILABLE";
  elements.placeholder.hidden = true;
  elements.image.hidden = false;
  elements.image.alt = `Evidência S4 da inspeção ${inspectionId}`;
  elements.image.onerror = () => {
    elements.image.onerror = null;
    showPlaceholder("LOAD_FAILED", elements);
  };
  elements.image.src = evidence.url;
}
