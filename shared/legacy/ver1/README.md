# Legado ods.ver1 (Sprint 1)

Contratos, mocks e taxonomia anteriores à migração 6c. Preservados apenas como
registro histórico; nenhum código do A1 os consome.

- `schemas/i8-piece-analyzed.schema.json` → substituído por
  `shared/schemas/6c/i8-piece-analysis.*.schema.json`;
- `schemas/a1-triage-result.schema.json` → decisão agora é exposta pela API A1
  (`shared/schemas/a1-api/`);
- `defect-categories.json` → substituído pelo artefato versionado
  `shared/artifacts/defect-taxonomy/` e pela política
  `shared/policies/triage/`;
- `mocks/` → substituídos por `shared/mocks/6c/` e `shared/mocks/a1-api/`.
