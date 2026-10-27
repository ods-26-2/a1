// Guarda de contrato do frontend para a API A1 v1.
// Espelha as regras de shared/schemas/a1-api/*.schema.json que a tela precisa
// para renderizar com segurança. Não aplica política de triagem.
import { A1ApiError, API_ERROR_KINDS } from "./apiError.js";

export const RESULTS = Object.freeze([
  "CONFORMING",
  "NON_CONFORMING",
  "ANOMALY",
  "UNCERTAIN",
]);
export const TRIAGE_STATUSES = Object.freeze(["APPROVED", "REJECTED", "REVIEW"]);
export const EVIDENCE_STATES = Object.freeze([
  "AVAILABLE",
  "PENDING",
  "UNAVAILABLE",
  "EXPIRED",
]);
export const SEVERITIES = Object.freeze(["LOW", "MEDIUM", "HIGH"]);
export const HEALTH_STATUSES = Object.freeze(["ONLINE", "DEGRADED"]);
export const API_MODES = Object.freeze(["REAL", "FAKE"]);
export const REVIEW_ACTIONS = Object.freeze(["CONFIRM", "SEND_TO_REVIEW"]);

function fail(path, message) {
  throw new A1ApiError(
    API_ERROR_KINDS.CONTRACT,
    `Resposta da API A1 fora do contrato: ${path} ${message}.`,
  );
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireObject(value, path) {
  if (!isObject(value)) {
    fail(path, "deve ser um objeto");
  }
  return value;
}

function requireString(value, path) {
  if (typeof value !== "string" || value.length === 0) {
    fail(path, "deve ser texto não vazio");
  }
  return value;
}

function requireNullableString(value, path) {
  if (value !== null) {
    requireString(value, path);
  }
}

function requireDateTime(value, path) {
  requireString(value, path);
  if (Number.isNaN(Date.parse(value))) {
    fail(path, "deve ser data-hora ISO 8601");
  }
}

function requireNullableDateTime(value, path) {
  if (value !== null) {
    requireDateTime(value, path);
  }
}

function requireEnum(value, allowed, path) {
  if (!allowed.includes(value)) {
    fail(path, `deve ser ${allowed.join(", ")} (recebido ${JSON.stringify(value)})`);
  }
}

function requireInteger(value, path) {
  if (!Number.isInteger(value) || value < 0) {
    fail(path, "deve ser inteiro não negativo");
  }
}

function requireRatio(value, path) {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    fail(path, "deve ser número entre 0 e 1");
  }
}

function requireKeys(value, keys, path) {
  const missing = keys.find((key) => !(key in value));
  if (missing) {
    fail(`${path}.${missing}`, "ausente");
  }
}

function validateDecision(decision, path) {
  requireObject(decision, path);
  requireKeys(decision, ["status", "reason", "decided_by", "decided_at"], path);
  requireEnum(decision.status, TRIAGE_STATUSES, `${path}.status`);
  requireString(decision.reason, `${path}.reason`);
  requireString(decision.decided_by, `${path}.decided_by`);
  requireDateTime(decision.decided_at, `${path}.decided_at`);
}

export function validateInspectionView(view) {
  requireObject(view, "$");
  requireKeys(
    view,
    [
      "inspection_id",
      "origin",
      "times",
      "versions",
      "analysis",
      "triage",
      "final_decision",
      "evidence",
    ],
    "$",
  );
  requireString(view.inspection_id, "inspection_id");

  const origin = requireObject(view.origin, "origin");
  requireString(origin.message_id, "origin.message_id");
  if (origin.schema !== "ods.i8.piece_analysis" || origin.producer !== "I8") {
    fail("origin", "deve referenciar ods.i8.piece_analysis produzido por I8");
  }
  requireString(origin.source_id, "origin.source_id");
  requireString(origin.session_id, "origin.session_id");
  ["sequence", "frame_index", "detection_id"].forEach((field) =>
    requireInteger(origin[field], `origin.${field}`),
  );
  if (!Array.isArray(origin.bbox) || origin.bbox.length !== 4) {
    fail("origin.bbox", "deve ter quatro inteiros");
  }
  origin.bbox.forEach((value, index) => requireInteger(value, `origin.bbox[${index}]`));

  const times = requireObject(view.times, "times");
  ["captured_at", "published_at", "received_at"].forEach((field) =>
    requireDateTime(times[field], `times.${field}`),
  );

  const versions = requireObject(view.versions, "versions");
  ["model", "taxonomy", "policy"].forEach((field) =>
    requireString(versions[field], `versions.${field}`),
  );

  const analysis = requireObject(view.analysis, "analysis");
  requireEnum(analysis.result, RESULTS, "analysis.result");
  requireRatio(analysis.confidence, "analysis.confidence");
  requireRatio(analysis.similarity, "analysis.similarity");
  if (analysis.result === "NON_CONFORMING") {
    const defect = requireObject(analysis.defect, "analysis.defect");
    ["defect_class", "name", "description"].forEach((field) =>
      requireString(defect[field], `analysis.defect.${field}`),
    );
    requireEnum(defect.severity, SEVERITIES, "analysis.defect.severity");
  } else if (analysis.defect !== null) {
    fail("analysis.defect", `deve ser null quando result é ${analysis.result}`);
  }

  validateDecision(view.triage, "triage");
  if (view.final_decision !== null) {
    validateDecision(view.final_decision, "final_decision");
  }

  const evidence = requireObject(view.evidence, "evidence");
  requireEnum(evidence.state, EVIDENCE_STATES, "evidence.state");
  requireNullableString(evidence.clip_id, "evidence.clip_id");
  requireNullableString(evidence.url, "evidence.url");
  requireNullableDateTime(evidence.expires_at, "evidence.expires_at");
  requireString(evidence.detail, "evidence.detail");
  if (evidence.state === "AVAILABLE") {
    requireString(evidence.clip_id, "evidence.clip_id");
    requireString(evidence.url, "evidence.url");
  } else if (evidence.url !== null) {
    fail("evidence.url", `deve ser null quando state é ${evidence.state}`);
  }

  return view;
}

export function validateHealth(health) {
  requireObject(health, "$");
  requireEnum(health.status, HEALTH_STATUSES, "status");
  requireEnum(health.mode, API_MODES, "mode");
  requireDateTime(health.checked_at, "checked_at");
  if (!Array.isArray(health.components)) {
    fail("components", "deve ser uma lista");
  }
  health.components.forEach((component, index) => {
    const path = `components[${index}]`;
    requireObject(component, path);
    requireString(component.name, `${path}.name`);
    requireEnum(component.status, ["UP", "DOWN", "SIMULATED"], `${path}.status`);
    if (typeof component.detail !== "string") {
      fail(`${path}.detail`, "deve ser texto");
    }
  });
  return health;
}

export function validateReviewReceipt(receipt) {
  requireObject(receipt, "$");
  requireString(receipt.review_id, "review_id");
  requireEnum(receipt.action, REVIEW_ACTIONS, "action");
  requireDateTime(receipt.recorded_at, "recorded_at");
  if (typeof receipt.persisted !== "boolean") {
    fail("persisted", "deve ser booleano");
  }
  validateInspectionView(receipt.inspection);
  return receipt;
}
