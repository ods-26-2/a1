const STATUS_PRESENTATION = Object.freeze({
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

const STATUS_CLASSES = Object.values(STATUS_PRESENTATION).map(
  ({ className }) => className,
);

export function getStatusPresentation(status) {
  const presentation = STATUS_PRESENTATION[status];

  if (!presentation) {
    throw new Error(`Estado de triagem inválido: ${status}`);
  }

  return presentation;
}

export function renderStatus(status, elements) {
  const presentation = getStatusPresentation(status);

  elements.banner.classList.remove(...STATUS_CLASSES);
  elements.banner.classList.add(presentation.className);
  elements.text.textContent = presentation.label;
  elements.icon.textContent = presentation.icon;
  elements.banner.setAttribute(
    "aria-label",
    `Resultado da triagem: ${presentation.label}`,
  );
}
