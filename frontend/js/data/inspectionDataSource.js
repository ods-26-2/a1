const SHARED_ROOT = new URL("../../../shared/", import.meta.url);

export const DEMO_SCENARIOS = Object.freeze({
  APPROVED: Object.freeze({
    inference: "mocks/i8-piece-approved.json",
    triage: "mocks/a1-triage-approved.json",
  }),
  REJECTED: Object.freeze({
    inference: "mocks/i8-piece-defective.json",
    triage: "mocks/a1-triage-rejected.json",
  }),
  REVIEW: Object.freeze({
    inference: "mocks/i8-piece-uncertain.json",
    triage: "mocks/a1-triage-review.json",
  }),
});

async function fetchJson(relativePath, label) {
  const response = await fetch(new URL(relativePath, SHARED_ROOT));

  if (!response.ok) {
    throw new Error(`${label} não pôde ser carregado (HTTP ${response.status}).`);
  }

  try {
    return await response.json();
  } catch (error) {
    throw new Error(`${label} não contém JSON válido.`, { cause: error });
  }
}

function validateEnvelope(event, expectedProducer, expectedSchema) {
  if (!event || typeof event !== "object" || Array.isArray(event)) {
    throw new Error("O evento B1 deve ser um objeto JSON.");
  }

  const requiredFields = [
    "message_type",
    "schema",
    "schema_version",
    "producer",
    "published_at",
    "payload",
  ];
  const missingField = requiredFields.find((field) => event[field] == null);

  if (missingField) {
    throw new Error(`Evento B1 inválido: campo ${missingField} ausente.`);
  }

  if (
    event.message_type !== "event" ||
    event.schema_version !== "1.0" ||
    event.producer !== expectedProducer ||
    event.schema !== expectedSchema
  ) {
    throw new Error(`Evento B1 incompatível com ${expectedSchema}.`);
  }

  if (!event.payload || typeof event.payload !== "object" || Array.isArray(event.payload)) {
    throw new Error("Evento B1 inválido: payload ausente ou inválido.");
  }
}

function validateRatio(value, field) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new Error(`Evento I8 inválido: ${field} deve estar entre 0 e 1.`);
  }
}

function validateScenario(inferenceEvent, triageEvent) {
  validateEnvelope(inferenceEvent, "I8", "ods.ver1.i8_piece_analyzed");
  validateEnvelope(triageEvent, "A1", "ods.ver1.a1_triage_result");

  const inference = inferenceEvent.payload;
  const triage = triageEvent.payload;
  const classificationId = inference.classification?.id;

  if (!inference.piece_id || !classificationId) {
    throw new Error("Evento I8 inválido: peça ou classificação ausente.");
  }

  validateRatio(inference.confidence, "confidence");
  validateRatio(inference.similarity, "similarity");

  if (inference.piece_id !== triage.piece_id) {
    throw new Error("Mocks I8 e A1 referem-se a peças diferentes.");
  }

  if (!["APPROVED", "REJECTED", "REVIEW"].includes(triage.status)) {
    throw new Error(`Evento A1 inválido: status ${triage.status ?? "ausente"}.`);
  }

  if (triage.review_required !== (triage.status === "REVIEW")) {
    throw new Error("Evento A1 inválido: review_required não corresponde ao status.");
  }

  if (triage.defect_id !== null && triage.defect_id !== classificationId) {
    throw new Error("Resultado A1 não corresponde à classificação do I8.");
  }
}

export async function loadInspectionScenario(status) {
  const scenario = DEMO_SCENARIOS[status];

  if (!scenario) {
    throw new Error(`Cenário de demonstração desconhecido: ${status}.`);
  }

  const [inferenceEvent, triageEvent, taxonomy] = await Promise.all([
    fetchJson(scenario.inference, "Mock de inferência"),
    fetchJson(scenario.triage, "Mock de triagem"),
    fetchJson("defect-categories.json", "Taxonomia"),
  ]);

  validateScenario(inferenceEvent, triageEvent);
  return { inferenceEvent, triageEvent, taxonomy };
}
