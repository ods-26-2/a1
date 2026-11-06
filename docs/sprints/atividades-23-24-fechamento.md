# Sprint 3 — fechamento das atividades 23 e 24

Ícaro assumiu a conclusão destas atividades conforme orientação atual do grupo. A numeração e os critérios continuam os do plano coletivo; esta página não redefine o backlog histórico.

| Atividade | Critério do plano | Entrega |
|---|---|---|
| 23 — preparar integração S5 | Adaptador preparado; funcionamento local não depende do S5 real | Serviço S5 EVENT, contratos, consultas/respostas, recebimento de eventos, simulador e testes com PostgreSQL |
| 24 — adaptador P7 com fake | Correlação, idempotência, respostas e limites testados | Já integrado no PR A1 #10; os 42 testes são repetidos no conjunto atual |

Ambas podem ser revisadas sem disponibilidade dos serviços externos. A consulta S5 depende do contrato publicado; P7 depende do contrato publicado e de uma inspeção local para vincular o pedido. Não exigem inferência real, dataset industrial, S4, respostas TRA-1 ou bancada para estes critérios locais.

## O que foi criado para S5

`build_services(...).s5` oferece:

- `request(...)`: registra consulta `ods.s5.metrics.query` para métricas EVENT, período e granularidade. Filtros opcionais: event_type, zone_id e object_class (campo `class` do contrato).
- `dispatch_pending(send)`: entrega consultas ao transporte fornecido pelo chamador. Uma falha incerta conserva o mesmo ID, horário e conteúdo para reenvio explícito.
- `receive(message)`: valida e correlaciona replies 1.0/1.1; grava resposta OK ou os erros INVALID_QUERY, PERIOD_TOO_LONG e UNKNOWN_ZONE. Também recebe `ods.s5.event_metrics` com deduplicação por message_id.
- `get(query_id)`, `expire()` e `events(limit=...)`: consultam o resultado/prazo e os eventos armazenados. O chamador deve executar `expire()`/`dispatch_pending()` no seu ciclo.

As consultas têm estados PENDING, SENT, COMPLETED, REJECTED e EXPIRED, com prazo padrão de 30 segundos. Resposta vazia é sucesso, sem confundir ausência de amostras com serviço indisponível. A primeira resposta válida conclui a consulta; respostas posteriores não substituem esse resultado. Para uma nova leitura, use outro ID. Reutilizar ID com outros filtros é erro.

O adaptador verifica datas, período positivo, máximo de 1000 janelas/pontos, granularidade, filtros, ordem cronológica e contagem incerta menor ou igual ao total. Uma reply ZONE não satisfaz consulta EVENT. Consultas/eventos S5 usam tabelas próprias e não alteram inspeções, triagem, revisão ou evidência S4.

O transporte é injetado e o `FakeS5` usa agregados sintéticos explicitamente fornecidos. O S5 real responde novamente a consultas repetidas, podendo gerar outro message_id de reply; o adaptador correlaciona pelo ID da consulta e não duplica o resultado.

## Exemplo local

Com os serviços A1 já construídos sobre um pool PostgreSQL inicializado:

```python
from uuid import uuid4
from backend.s5_fake import FakeS5

adapter = services.s5
fake = FakeS5(series=[])  # zero dados sintéticos, não resultado industrial real
request = adapter.request(
    query_id=uuid4(),
    period_start_at="2026-11-06T12:00:00.000Z",
    period_end_at="2026-11-06T13:00:00.000Z",
    granularity="1h",
)
adapter.dispatch_pending(fake.send)
adapter.receive(fake.reply(request["query_id"]))
assert adapter.get(request["query_id"])["status"] == "COMPLETED"
```

Este exemplo é uma chamada de biblioteca. Não cria botão, rota HTTP ou worker Kafka automático. A ligação ao transporte/composição e ao produto será uma etapa explícita de integração, sem ativação silenciosa nesta entrega. ZONE, heatmap e perfis de horário não fazem parte do escopo A1 EVENT preparado aqui.

## Testar no Linux com Docker

Na raiz desta branch A1:

```bash
mkdir -p validacao-local/evidencias-s5-p7
docker compose -p ver1-s5-p7 -f validacao-local/compose-s5-p7.yml run --rm --build testes
docker compose -p ver1-s5-p7 -f validacao-local/compose-s5-p7.yml run --rm testes sh -c 'python scripts/validate_contracts.py && python -m pytest -q --junitxml=/evidencias/regressao.xml && npm test'
docker compose -p ver1-s5-p7 -f validacao-local/compose-s5-p7.yml down -v
```

PostgreSQL é real; S5 e P7 são simulados. Não há Kafka, portas publicadas, hardware ou broker Google Cloud neste laboratório. O workflow `testes-s5-p7.yml` executa as mesmas provas e publica XML/log por 30 dias.

## Contrato e pendências fora desses critérios

Schemas S5 copiados sem alteração do [componente S5](https://github.com/ods-26-2/s5/tree/77483834790e7d0d34b5b296f810fa698bdacddb/contracts). As verificações semânticas também seguem seu [caso de uso EVENT](https://github.com/ods-26-2/s5/blob/77483834790e7d0d34b5b296f810fa698bdacddb/src/application/use_cases/query_metrics_use_case.py). A1 não fabrica métricas S5 nem converte I8 em eventos S2. O mapeamento/alimentação industrial depende de acordo com MOD-2/S5.

A atividade 24 já tem [arquitetura e roteiro próprios](atividade-24-resumo.md). A atividade 25 permanece separada: resolver coordenadas/recusas/transporte com SIS-2 e provar na bancada. Os testes com fake não homologam o dispositivo real.

A conclusão dos critérios locais 23/24 não conclui o fluxo VER-1 inteiro, os relatórios da atividade 22 ou a composição final da 28. Após revisão do PR, registrar o aceite da equipe para a atividade 23. A atividade 24 permanece entregue, agora revalidada.

[Evidências dos testes](../evidencias/atividades-23-24/README.md).
