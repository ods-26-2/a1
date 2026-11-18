import assert from "node:assert/strict";
import test from "node:test";
import vm from "node:vm";
import { inspectionReady } from "../../scripts/capture_readiness.mjs";

for (const [name, summary, inspection, expected] of [
  ["DOM ainda ausente", null, null, false],
  ["DOM parcial", "Histórico carregado", null, false],
  ["histórico carregando", "Carregando histórico", "INSP-123", false],
  ["inspeção ainda ausente", "Histórico carregado", "—", false],
  ["inspeção vazia", "Histórico carregado", "  ", false],
  ["histórico e inspeção disponíveis", "1 inspeção", "INSP-123", true],
]) {
  test(`captura aguarda ${name}`, () => {
    const nodes = {
      "#history-summary": summary === null ? null : { textContent: summary },
      "#inspection-id": inspection === null ? null : { textContent: inspection },
    };
    const document = { querySelector: (selector) => nodes[selector] };
    // Exatamente a serialização usada por Runtime.evaluate, sem closures do Node.
    assert.equal(vm.runInNewContext(`(${inspectionReady.toString()})(document)`, { document }), expected);
  });
}
