# Contrato frontend ↔ backend A1 — API v1

Interface interna da aplicação A1 (camada 4). Não é mensagem do barramento 6c:
o frontend conversa somente com o backend A1 e nunca consome
`ods.i8.piece_analysis`, S4, S5, P7 ou modelos diretamente.

Schemas executáveis: `shared/schemas/a1-api/`. Fixtures da API fake:
`shared/mocks/a1-api/inspections/`.

## Rotas

| Método | Rota | Resposta |
|---|---|---|
| GET | `/api/v1/health` | `Health` (200). Falha de rede ou timeout = OFFLINE no front |
| GET | `/api/v1/inspections/current` | `InspectionView` (200) ou `204` sem inspeção |
| GET | `/api/v1/inspections/{inspection_id}` | `InspectionView` (200) ou `404` |
| POST | `/api/v1/inspections/{inspection_id}/reviews` | `ReviewReceipt` (201/200) |

Corpo do POST:

```json
{ "action": "CONFIRM", "operator": "op-samuel" }
```

`action` é `CONFIRM` ou `SEND_TO_REVIEW`. Motivo obrigatório e correção de
classe pertencem a S3-08 e entram como campos aditivos.

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
- `final_decision`: decisão do operador ou `null`;
- `evidence`: `AVAILABLE`, `PENDING`, `UNAVAILABLE` ou `EXPIRED`. `url` só
  existe em `AVAILABLE`; nos demais estados o front mostra placeholder
  explícito, nunca a imagem de outra peça.

## Health

`status` é `ONLINE` ou `DEGRADED`; `mode` é `REAL` ou `FAKE`. Componentes com
`DOWN` aparecem no indicador do cabeçalho. "SISTEMA ONLINE" só é exibido após
uma resposta válida desta rota.

## Seleção do adaptador no frontend

- `frontend/?api=fake` (padrão): API fake, painel de cenários visível;
- `frontend/?api=http://localhost:8000/api/v1`: API real;
- `<meta name="a1-api-base">` em `index.html`: API real da implantação.

Os dois adaptadores (`frontend/js/data/fakeA1Api.js` e `httpA1Api.js`) têm a
mesma interface e passam pela mesma guarda (`inspectionView.js`). Trocar o fake
pela API real não altera regra do frontend: o front não aplica política de
triagem nem resolve rótulos.
