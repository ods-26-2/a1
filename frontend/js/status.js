// Vocabulário de apresentação. Converte códigos da API A1 em rótulos e
// classes visuais; não decide triagem.
const TRIAGE_PRESENTATION = Object.freeze({
  APPROVED: Object.freeze({
    label: "APROVADA",
    icon: "✓",
    className: "status-banner--approved",
  }),
  REJECTED: Object.freeze({
    label: "REPROVADA",
    icon: "×",
    className: "status-banner--rejected",
  }),
  REVIEW: Object.freeze({
    label: "REVISÃO NECESSÁRIA",
    icon: "?",
    className: "status-banner--review",
  }),
});

const RESULT_PRESENTATION = Object.freeze({
  CONFORMING: Object.freeze({
    label: "CONFORME",
    className: "result-badge--conforming",
    heading: "Sem defeito",
    description: "Peça dentro da referência do normal; nenhuma classe de defeito atribuída.",
  }),
  NON_CONFORMING: Object.freeze({
    label: "NÃO CONFORME",
    className: "result-badge--non-conforming",
    heading: null,
    description: null,
  }),
  ANOMALY: Object.freeze({
    label: "ANOMALIA",
    className: "result-badge--anomaly",
    heading: "Desvio sem classe conhecida",
    description:
      "O I8 detectou desvio em relação ao normal sem correspondência com as classes da taxonomia.",
  }),
  UNCERTAIN: Object.freeze({
    label: "INCERTO",
    className: "result-badge--uncertain",
    heading: "Classe não determinada",
    description: "A inferência não teve certeza suficiente para decidir; nenhuma classe foi atribuída.",
  }),
});

const SEVERITY_LABELS = Object.freeze({
  LOW: "BAIXA · LOW",
  MEDIUM: "MÉDIA · MEDIUM",
  HIGH: "ALTA · HIGH",
});

const STATUS_CLASSES = Object.values(TRIAGE_PRESENTATION).map(({ className }) => className);
const RESULT_CLASSES = Object.values(RESULT_PRESENTATION).map(({ className }) => className);

function lookup(table, code, label) {
  const presentation = table[code];
  if (!presentation) {
    throw new Error(`${label} sem apresentação: ${code}`);
  }
  return presentation;
}

export function getStatusPresentation(status) {
  return lookup(TRIAGE_PRESENTATION, status, "Estado de triagem");
}

export function getResultPresentation(result) {
  return lookup(RESULT_PRESENTATION, result, "Resultado I8");
}

export function getSeverityLabel(severity) {
  return SEVERITY_LABELS[severity] ?? severity;
}

export function renderStatus(status, elements) {
  const presentation = getStatusPresentation(status);

  elements.banner.classList.remove(...STATUS_CLASSES);
  elements.banner.classList.add(presentation.className);
  elements.text.textContent = presentation.label;
  elements.icon.textContent = presentation.icon;
  elements.banner.setAttribute("aria-label", `Resultado da triagem: ${presentation.label}`);
}

export function renderResultBadge(result, element) {
  const presentation = getResultPresentation(result);

  element.classList.remove(...RESULT_CLASSES);
  element.classList.add(presentation.className);
  element.textContent = `${presentation.label} · ${result}`;
}
