// Camada de dados da tela. Escolhe o adaptador (API real ou fake) e aplica a
// mesma guarda de contrato aos dois, de modo que trocar o fake pela API real
// não altera nenhuma regra do frontend.
import { createFakeA1Api } from "./fakeA1Api.js";
import { createHttpA1Api } from "./httpA1Api.js";
import {
  REVIEW_ACTIONS,
  validateHealth,
  validateInspectionView,
  validateReviewReceipt,
} from "./inspectionView.js";

export function createInspectionDataSource(config, { fetchImpl } = {}) {
  const api =
    config.mode === "REAL"
      ? createHttpA1Api({ baseUrl: config.baseUrl, fetchImpl })
      : createFakeA1Api({
          fetchImpl,
          scenario: config.scenario ?? undefined,
          fault: config.fault ?? undefined,
        });

  return Object.freeze({
    mode: api.mode,
    demo: api.demo,

    async checkHealth() {
      try {
        const health = validateHealth(await api.getHealth());
        return { state: health.status, health, error: null };
      } catch (error) {
        return { state: "OFFLINE", health: null, error };
      }
    },

    async loadCurrentInspection() {
      const view = await api.getCurrentInspection();
      return view === null ? null : validateInspectionView(view);
    },

    async loadInspection(inspectionId) {
      return validateInspectionView(await api.getInspection(inspectionId));
    },

    async submitReview(inspectionId, { action, operator }) {
      if (!REVIEW_ACTIONS.includes(action)) {
        throw new Error(`Ação de revisão desconhecida: ${action}.`);
      }
      if (typeof operator !== "string" || operator.trim() === "") {
        throw new Error("Informe a identificação do operador.");
      }
      return validateReviewReceipt(
        await api.submitReview(inspectionId, { action, operator: operator.trim() }),
      );
    },
  });
}
