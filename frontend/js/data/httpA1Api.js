// Adaptador HTTP da API A1 v1 (docs/contratos/a1-api.md).
// Devolve JSON bruto; a validação do contrato fica em inspectionDataSource.js.
import { A1ApiError, API_ERROR_KINDS } from "./apiError.js";

const DEFAULT_TIMEOUT_MS = 5000;

export function createHttpA1Api({
  baseUrl,
  fetchImpl = globalThis.fetch.bind(globalThis),
  timeoutMs = DEFAULT_TIMEOUT_MS,
}) {
  const root = new URL(baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`);

  async function request(path, { method = "GET", body } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let response;

    try {
      response = await fetchImpl(new URL(path, root), {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });
    } catch (error) {
      if (error?.name === "AbortError") {
        throw new A1ApiError(
          API_ERROR_KINDS.TIMEOUT,
          `API A1 não respondeu em ${timeoutMs} ms.`,
          { cause: error },
        );
      }
      throw new A1ApiError(
        API_ERROR_KINDS.NETWORK,
        "API A1 inacessível. Verifique se o backend está em execução.",
        { cause: error },
      );
    } finally {
      clearTimeout(timer);
    }

    if (response.status === 204) {
      return null;
    }

    if (!response.ok) {
      throw new A1ApiError(
        API_ERROR_KINDS.HTTP,
        `API A1 respondeu HTTP ${response.status} em ${method} ${path}.`,
        { status: response.status },
      );
    }

    try {
      return await response.json();
    } catch (error) {
      throw new A1ApiError(
        API_ERROR_KINDS.CONTRACT,
        `API A1 devolveu JSON inválido em ${method} ${path}.`,
        { cause: error },
      );
    }
  }

  return Object.freeze({
    mode: "REAL",
    demo: null,
    getHealth: () => request("health"),
    getCurrentInspection: () => request("inspections/current"),
    getInspection: (inspectionId) =>
      request(`inspections/${encodeURIComponent(inspectionId)}`),
    submitReview: (inspectionId, review) =>
      request(`inspections/${encodeURIComponent(inspectionId)}/reviews`, {
        method: "POST",
        body: review,
      }),
  });
}
