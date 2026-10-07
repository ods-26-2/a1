const TAXONOMY_URL = new URL(
  "../../shared/defect-categories.json",
  import.meta.url,
);

const pieceAnalyzedEvent = Object.freeze({
  pieceId: "P000123",
  timestamp: "2026-09-18T10:30:00-03:00",
  classification: "AMASSADO",
  confidence: 0.91,
  similarity: 0.28,
  imagePath: "./assets/images/mock-piece-defective.png",
});

const DEMO_STATUSES = Object.freeze(["APPROVED", "REJECTED", "REVIEW"]);

function parseExistingTaxonomy(rawTaxonomy) {
  // O arquivo compartilhado é a fonte de verdade. A normalização tolera vírgula
  // final sem alterar o artefato já concluído da taxonomia.
  const normalizedJson = rawTaxonomy.replace(/,\s*([}\]])/g, "$1");
  return JSON.parse(normalizedJson);
}

async function loadClassification(classificationId) {
  const response = await fetch(TAXONOMY_URL);

  if (!response.ok) {
    throw new Error(`Falha ao carregar taxonomia: ${response.status}`);
  }

  const taxonomy = parseExistingTaxonomy(await response.text());
  const classification = taxonomy.categories.find(
    (category) => category.id === classificationId,
  );

  if (!classification) {
    throw new Error(`Classificação não encontrada: ${classificationId}`);
  }

  return classification;
}

export async function getMockInspection() {
  const classification = await loadClassification(
    pieceAnalyzedEvent.classification,
  );

  return {
    event: { ...pieceAnalyzedEvent },
    classification,
    status: "REJECTED",
  };
}

export function getDemoStatuses() {
  return [...DEMO_STATUSES];
}
