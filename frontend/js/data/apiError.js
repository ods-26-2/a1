export const API_ERROR_KINDS = Object.freeze({
  NETWORK: "NETWORK",
  TIMEOUT: "TIMEOUT",
  HTTP: "HTTP",
  CONTRACT: "CONTRACT",
});

export class A1ApiError extends Error {
  constructor(kind, message, { status = null, cause } = {}) {
    super(message, cause ? { cause } : undefined);
    this.name = "A1ApiError";
    this.kind = kind;
    this.status = status;
  }
}
