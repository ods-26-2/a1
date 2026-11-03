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
nada. Outra mensagem com a mesma sessão, quadro e detecção é recusada. Imagens
não são gravadas.

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

## Pendências fora de S3-07

- S3-08: motor de triagem completo, motivo obrigatório e correção de classe;
- S3-09: adaptador S4 (os pedidos de snapshot ficam em `commands` como
  `PENDING` e a evidência aparece como pendente);
