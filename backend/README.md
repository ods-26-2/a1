# Backend A1

API v1 do A1 (`docs/contratos/a1-api.md`) com persistência em PostgreSQL.
Implementa S3-07: ingestão do evento 6c, deduplicação, histórico original/final,
comandos pendentes e trilha de auditoria.

## Camadas

| Módulo | Papel |
|---|---|
| `app.py` | Rotas HTTP da API v1 (FastAPI) |
| `inspections.py` | `InspectionService` (detalhe, atual, histórico) e `ReviewService` |
| `ingestion.py` | `IngestionService`: valida o 6c, aplica a triagem e grava |
| `triage.py` | Política mínima 7.2 (`TriageService`); o motor completo é S3-08 |
| `taxonomy.py` | `TaxonomyCatalog`: resolve rótulos pela versão da inspeção |
| `contracts.py` | Guarda da fronteira I8 → A1 |
| `repository.py` | `InspectionRepository` sobre PostgreSQL |
| `schema.sql` | Esquema do banco, aplicado a cada inicialização |
| `fake_producer.py` | Produtor fake 6c, até o I8 e o transporte B3 chegarem |
| `mqtt_client.py` | Cliente MQTT que escuta os eventos do I8 | 

## Banco

PostgreSQL (serviço `db` do `docker-compose.yml`). Tabelas:

- `inspections`: resultado automático imutável, com contexto de origem,
  versões, tempos e o evento 6c original (`raw_event`);
- `reviews`: revisões do operador, só inserção;
- `audit_events`: trilha da inspeção e da revisão, só inserção;
- `evidence`: estado da evidência S4 (muda em S3-09);
- `commands`: pedidos emitidos pelo A1 (snapshot S4, atuação P7);
- `ingestion_failures`: mensagens recusadas, para diagnóstico.

O banco recusa `UPDATE`, `DELETE` e `TRUNCATE` em `inspections`, `reviews` e
`audit_events`. Mensagem repetida é reconhecida por `message_id` e não grava
nada. Outra mensagem com a mesma fonte, sessão, quadro e detecção é recusada. Imagens
não são gravadas.

Novas inspeções usam `INSP-<message_id completo>` como ID interno para evitar
colisões entre prefixos de sessão ou fontes. IDs históricos continuam válidos.
A inicialização atualiza a chave de observação de bancos S3-07 existentes para
incluir `source_id`, sem reescrever inspeções, revisões ou auditoria.

## Ingestão

O ponto de entrada é `IngestionService.ingest(evento)`, independente de
transporte. O adaptador MQTT (`mqtt_client.py`) escuta o barramento, 
descodifica o evento 6c e chama este método. Resultado: `ACCEPTED`, `DUPLICATE` ou `REJECTED`.

Para testes locais sem hardware, o produtor fake pode ser injetado diretamente 
dentro do contentor do backend:

```powershell
docker compose exec backend python -m backend.fake_producer
docker compose exec backend python -m backend.fake_producer --fresh
docker compose exec backend python -m backend.fake_producer --invalid python -m backend.fake_producer --invalid
```

`--fresh` gera novos `message_id`, sessão e horários (inspeções novas).
`--invalid` inclui as fixtures inválidas, que devem ser recusadas.

## S3-08 — triagem, fila e revisão

A política ativa é `triage-a1-1.1.0`. `minimum_confidence` declara separadamente
os limiares de `CONFORMING` e `NON_CONFORMING`. Um valor `null` significa que a
calibração ainda não foi aceita: a decisão vai para `REVIEW`, sem aprovação ou
reprovação automática. Depois de calibrar, publique uma nova versão da política;
o limite é inclusivo (`confidence >= limiar`). `ANOMALY` e `UNCERTAIN` sempre vão
para revisão. Versão/classe inválida é recusada na ingestão. A política antiga
permanece em `shared/policies/triage/archive/` para referência histórica.

`GET /api/v1/inspections/review-queue?limit=20&offset=0` consulta a fila persistida
em ordem de recebimento. A fila é a projeção da última decisão de cada inspeção,
não uma lista em memória. Uma correção final remove a inspeção da fila; enviar
para revisão a recoloca. Confirmar uma decisão `REVIEW` mantém a pendência.

`GET /api/v1/inspections/{id}/review-options` entrega as classes da versão da
taxonomia usada pela inspeção. `POST .../{id}/reviews` exige `operator` e `reason`
não vazios e aceita:

- `CONFIRM`: preserva a decisão/classe final atual;
- `SEND_TO_REVIEW`: muda o estado final para `REVIEW`, preservando a classe;
- `CORRECT`: exige `status`; `REJECTED` exige classe conhecida, `APPROVED` exige
  classe nula e `REVIEW` admite classe conhecida ou nula.

Cada revisão é uma inserção auditável com motivo, ator, hora, estado e classe.
`analysis` e `triage` nunca mudam. `final_decision` expõe classe e versão usadas
pelo operador; `.../{id}/history` contém todas as revisões. A migração adiciona
colunas sem reescrever revisões antigas ou alterar as proteções S3-07.

A tela inclui fila paginada, motivo, correção, classe e histórico. A API fake
implementa o mesmo fluxo sem persistência; suas fixtures S3-03 são exemplos da
política histórica 1.0, não limiares calibrados da política ativa.

## Pendências externas

- S3-09: adaptador S4 (os pedidos de snapshot ficam em `commands` como
  `PENDING` e a evidência aparece como pendente);
