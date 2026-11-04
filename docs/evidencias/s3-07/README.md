# Evidências S3-07 — backend, banco e auditoria

Verificação local em 03/11/2026 com `docker compose` (backend FastAPI,
PostgreSQL 17.11, nginx). Ingestão pelo produtor fake 6c, não pelo I8 real.

## Critérios de conclusão

| Critério | Teste automatizado | Verificação manual |
|---|---|---|
| Reinício preserva dados | `test_data_survives_restart` | `docker compose down` e `up`: inspeção e revisão continuam na API |
| Mensagem repetida não duplica registro | `test_repeated_message_is_not_duplicated` | segunda execução do produtor fake: 4 × `DUPLICATE` |
| API responde detalhe/histórico | `test_four_results_are_stored_and_served`, `test_review_keeps_automatic_decision_and_history` | `GET /api/v1/inspections/{id}` e `/history` |
| Trilha da inspeção e da revisão | `test_review_keeps_automatic_decision_and_history`, `test_audit_records_are_immutable` | eventos `INGESTED`, `TRIAGED`, `EVIDENCE_REQUESTED`, `REVIEW_RECORDED` |
| Mensagem inválida não vira inspeção | `test_invalid_events_are_rejected_and_logged`, `test_unknown_class_is_rejected` | `--invalid`: 3 × `REJECTED`, gravadas em `ingestion_failures` |

Resultado da suíte no container: 63 testes aprovados, nenhum ignorado.

## Roteiro de demonstração

```powershell
docker compose up -d --build
docker compose exec backend python -m backend.fake_producer --invalid
docker compose exec backend python -m backend.fake_producer
curl http://localhost:5500/api/v1/inspections/INSP-3fbff51e-3e45-433c-b69a-6753e0f4ebd7/history
docker compose down
docker compose up -d
curl http://localhost:5500/api/v1/inspections/INSP-3fbff51e-3e45-433c-b69a-6753e0f4ebd7
docker compose run --rm tests
```

1. Primeira execução do produtor: 4 `ACCEPTED` (um por `result`) e 3
   `REJECTED`.
2. Segunda execução: 4 `DUPLICATE`, sem novas linhas no banco.
3. A tela em <http://localhost:5500/frontend/> mostra "API REAL", a última
   inspeção e "S4 · PENDENTE" com placeholder.
4. Revisão pela tela ("Enviar para revisão" com `op-samuel`): o histórico mostra
   a decisão automática `REVIEW` intacta e a revisão do operador.
5. Depois de `down`/`up`, a inspeção e a revisão continuam na API.

## Limitações registradas

Após a correção de identidade de 03/11, novas inspeções usam o UUID completo da
mensagem. Se a fixture já existia no banco anterior, use o ID retornado pelo
produtor (`DUPLICATE` mantém o ID histórico); a migração não reescreve registros.

- Ingestão pelo produtor fake: o transporte B3 do evento I8 não está integrado.
- S4 não integrado (S3-09): todo pedido de snapshot fica `PENDING` e o
  componente `s4` aparece como `DOWN` no `/health`.
- Triagem baseline da seção 7.2; motor completo, motivo obrigatório e correção
  de classe pertencem a S3-08.
- Classe de defeito fora da taxonomia é recusada na ingestão (vai para
  `ingestion_failures`), porque a `InspectionView` exige rótulo resolvido.
