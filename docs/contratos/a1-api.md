# Contrato frontend ↔ backend A1 — API v1

Interface interna da aplicação A1 (camada 4). Não é mensagem do barramento 6c:
o frontend conversa somente com o backend A1 e nunca consome eventos Kafka I8,
S4, S5, P7 ou modelos diretamente.

Schemas executáveis: `shared/schemas/a1-api/`. Fixtures da API fake:
`shared/mocks/a1-api/inspections/`.

## Rotas

| Método | Rota | Resposta |
|---|---|---|
| GET | `/api/v1/health` | `Health` (200). Falha de rede ou timeout = OFFLINE no front |
| GET | `/api/v1/inspections` | `InspectionList` (200): busca histórica paginada e filtrada |
| GET | `/api/v1/inspections/current` | `InspectionView` (200) ou `204` sem inspeção |
| GET | `/api/v1/inspections/review-queue?limit=20&offset=0` | `ReviewQueue` com items, total, limit e offset |
| GET | `/api/v1/inspections/{inspection_id}` | `InspectionView` (200) ou `404` |
| GET | `/api/v1/inspections/{inspection_id}/review-options` | Classes da taxonomia da inspeção |
| GET | `/api/v1/inspections/{inspection_id}/history` | `InspectionHistory` (200) ou `404` |
| POST | `/api/v1/inspections/{inspection_id}/reviews` | `ReviewReceipt` (201) ou `404` |

Corpo do POST:

```json
{ "action": "CONFIRM", "operator": "op-samuel", "reason": "Conferência manual concluída." }
```

`action` é `CONFIRM`, `SEND_TO_REVIEW` ou `CORRECT`; `operator` tem de 1 a 64
caracteres e `reason` de 1 a 1000, após remover espaços externos. Campo
desconhecido, ação inválida, operador/motivo vazio ou correção inconsistente
retornam `422`. Cada POST grava uma revisão nova: `CONFIRM` mantém estado e
classe final vigentes, `SEND_TO_REVIEW` mantém a classe e muda para `REVIEW`.
A decisão automática e a análise I8 nunca são alteradas.

Em `CORRECT`, enviar `status` e `defect_class` (ou `null`). Reprovar exige classe
conhecida na versão da inspeção; aprovar exige classe nula. `REVIEW` aceita classe
conhecida ou nula. Estado/classe não são aceitos nas outras ações.

```json
{ "action": "CORRECT", "operator": "op-samuel", "reason": "Furo verificado manualmente.", "status": "REJECTED", "defect_class": "FURADO" }
```

A fila contém inspeções cuja última decisão é `REVIEW`; confirmá-la mantém a
pendência. `limit` aceita 1–100 e `offset` é não negativo. É uma projeção do banco
e sobrevive a reinício. `review-options` retorna `{taxonomy_version, classes}`
com os rótulos daquela versão, sem usar a versão mais recente silenciosamente.

Banco indisponível retorna `503` nas rotas de inspeção; `/health` responde
`DEGRADED` com o componente `database` em `DOWN`.

## InspectionView

O backend entrega a inspeção já resolvida:

- `origin`: identidade da mensagem I8 e contexto de quadro (`source_id`,
  `session_id`, `sequence`, `frame_index`, `detection_id`, `bbox`);
- `times`: captura, publicação e recepção;
- `versions`: modelo (`artifact_version` do I8), taxonomia e política;
- `analysis`: `result` 6c, `confidence`, `similarity` e `defect` com nome,
  descrição e severidade resolvidos pela versão de taxonomia. `defect` só
  existe em `NON_CONFORMING`;
- `triage`: decisão automática, motivo, `decided_by: "AUTO"`; imutável;
- `final_decision`: decisão do operador ou `null`; inclui `defect_class` final
  (possivelmente nula) e `taxonomy_version`, separadas da análise original;
- `evidence`: `AVAILABLE`, `PENDING`, `UNAVAILABLE` ou `EXPIRED`. `url` só
  existe em `AVAILABLE`; nos demais estados o front mostra placeholder
  explícito, nunca a imagem de outra peça.

## InspectionList — histórico pesquisável (S3-10 / atividade 21)

`GET /api/v1/inspections` consulta registros persistidos, com filtros opcionais
combinados por **AND**. A resposta usa `inspection-list.schema.json`:
`{items: InspectionView[], total, limit, offset}`. Resultado vazio ou página além
do fim retorna `200`, `items: []` e total preservado.

| Parâmetro | Semântica |
|---|---|
| `captured_from` | `times.captured_at >= início` (inclusivo) |
| `captured_to` | `times.captured_at < fim` (exclusivo) |
| `result` | Resultado automático I8: CONFORMING, NON_CONFORMING, ANOMALY ou UNCERTAIN |
| `source_id` | Origem exata, sensível a maiúsculas, até 256 caracteres; sem NUL ou texto vazio |
| `defect_class` | Código original I8, até 128 caracteres, padrão `[A-Z][A-Z0-9_]*` |
| `limit` | Inteiro de 1 a 100; padrão 50 |
| `offset` | Inteiro não negativo; padrão 0 |

Datas exigem ISO 8601 com `T` e fuso explícito (`Z` ou offset); são comparadas
em UTC. O início deve ser estritamente anterior ao fim. Campos desconhecidos,
datas inválidas/sem fuso, códigos malformados e paginação inválida retornam
`422`. Código de defeito ou origem bem formado sem registros retorna vazio,
inclusive quando pertence a outra versão histórica da taxonomia. Combinação
incompatível (por exemplo ANOMALY + AMASSADO) retorna vazio.

Filtros de resultado e defeito consultam a **análise original imutável**, não
o estado final APPROVED/REJECTED/REVIEW nem a classe corrigida pelo operador.
Cada item continua expondo ambos em `analysis` e `final_decision`. A auditoria
por ID permanece em `/inspections/{id}/history`, com contrato inalterado.

Ordem fixa: `captured_at DESC, inspection_id DESC`; desempate determinístico,
paginação `limit/offset` compatível com a fila existente. Total e itens usam
a mesma transação PostgreSQL de leitura com snapshot repetível. Requisições
sucessivas têm snapshots independentes: novas inspeções podem deslocar páginas;
para uma consulta delimitada, fixe período e repita a busca quando necessário.
Não há promessa de exportação ou snapshot entre páginas nesta atividade.

```text
/api/v1/inspections?captured_from=2026-11-01T00%3A00%3A00Z&captured_to=2026-11-07T00%3A00%3A00Z&result=NON_CONFORMING&source_id=cam-linha1&defect_class=AMASSADO&limit=20&offset=0
```

Na tela, campos de período são explicitamente UTC, limite fixo de 20,
anterior/próximas e botão de limpar filtros. Clique em um registro abre os
detalhes/revisões existentes. Modo fake aplica as mesmas regras às quatro
fixtures, sem persistência; modo real consulta somente a API A1.

## InspectionHistory

Trilha de auditoria (`shared/schemas/a1-api/inspection-history.schema.json`):

- `triage`: decisão automática original;
- `final_decision`: última revisão ou `null`;
- `reviews`: todas as revisões em ordem, incluindo motivo, operador, classe e versão;
- `events`: `INGESTED`, `TRIAGED`, `EVIDENCE_REQUESTED` e `REVIEW_RECORDED`,
  com ator, instante e detalhes (por exemplo, status anterior da revisão).

## Health

`status` é `ONLINE` ou `DEGRADED`; `mode` é `REAL` ou `FAKE`. Componentes com
`DOWN` aparecem no indicador do cabeçalho. "SISTEMA ONLINE" só é exibido após
uma resposta válida desta rota.

## Seleção do adaptador no frontend

- `frontend/?api=fake` (padrão): API fake, painel de cenários visível;
- `frontend/?api=http://localhost:8000/api/v1`: API real;
- `<meta name="a1-api-base">` em `index.html`: API real da implantação. No
  Docker, o nginx preenche o meta com `A1_API_BASE` (padrão `/api/v1`) e
  repassa `/api/` ao backend; `A1_API_BASE=fake` mantém a API fake.

Os dois adaptadores (`frontend/js/data/fakeA1Api.js` e `httpA1Api.js`) têm a
mesma interface e passam pela mesma guarda (`inspectionView.js`). Trocar o fake
pela API real não altera regra do frontend: o front não aplica política de
triagem nem resolve rótulos.
