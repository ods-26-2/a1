// Seleção do adaptador da API A1.
//   ?api=fake (padrão)                 -> API fake com fixtures 6c
//   ?api=http://localhost:8000/api/v1  -> API real do backend A1
// <meta name="a1-api-base"> define a API real em uma implantação; o parâmetro
// da URL tem precedência. ?scenario= e ?fault= só valem para a API fake.
export const HEALTH_INTERVAL_MS = 10000;
export const INSPECTION_POLL_MS = 5000;

export function resolveApiConfig(location = window.location, root = document) {
  const params = new URLSearchParams(location.search);
  const metaBase = root.querySelector('meta[name="a1-api-base"]')?.content?.trim();
  const requested = params.get("api") ?? (metaBase || "fake");

  if (requested === "fake") {
    return {
      mode: "FAKE",
      baseUrl: null,
      scenario: params.get("scenario"),
      fault: params.get("fault"),
    };
  }

  return {
    mode: "REAL",
    baseUrl: new URL(requested, location.href).href,
    scenario: null,
    fault: null,
  };
}
