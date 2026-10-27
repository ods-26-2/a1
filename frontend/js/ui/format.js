const percentageFormatter = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  maximumFractionDigits: 0,
});

const dateTimeFormatter = new Intl.DateTimeFormat("pt-BR", {
  dateStyle: "short",
  timeStyle: "medium",
});

const timeFormatter = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export function clampRatio(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? Math.min(1, Math.max(0, numericValue)) : 0;
}

export function formatPercentage(value) {
  return percentageFormatter.format(clampRatio(value));
}

export function formatDateTime(timestamp) {
  if (!timestamp) {
    return "—";
  }
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? "Horário indisponível" : dateTimeFormatter.format(date);
}

export function formatTime(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? "—" : timeFormatter.format(date);
}
