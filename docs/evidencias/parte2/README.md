# Parte 2 — consumidor, fake e saúde Kafka A1

Correção implementada e verificada localmente, agora publicada em PR de rascunho. A proposta de contrato da parte 1 foi aceita por Ícaro; o acordo externo com TRA-1 permanece pendente. Nenhum evento foi enviado ao broker compartilhado e nenhum merge foi realizado.

## Comportamento corrigido

### Consumo e integridade dos dados

O consumidor desabilita `enable.auto.commit` e `enable.auto.offset.store`. O offset da mensagem é confirmado com `commit(message=msg, asynchronous=False)` somente depois de `IngestionService` retornar um resultado durável: ACCEPTED, DUPLICATE ou REJECTED.

Rejeições de contrato passam pelo serviço de ingestão, que registra a falha no banco. JSON inválido, encoding inválido, tombstone e números JSON não permitidos usam `reject_transport_message`, acrescentado ao mesmo serviço. O motivo registra tópico, partição e offset. Nenhuma mensagem inválida é descartada apenas em memória antes do commit.

O processamento mantém uma única mensagem em andamento. Falha de persistência repete essa mensagem com espera progressiva. Falha de commit repete somente o commit, preservando a gravação já concluída. Nenhuma mensagem posterior pode ultrapassar uma mensagem pendente. Se as tentativas esgotarem, o trabalhador encerra, o offset permanece sem confirmação e o health fica DOWN. Após corrigir a causa, reiniciar o backend permite reentrega; a deduplicação existente protege os efeitos já persistidos.

Isso implementa consumo com possibilidade de reentrega e persistência idempotente; não constitui transação distribuída Kafka/PostgreSQL nem promessa de entrega exatamente uma vez em todos os cenários.

### Saúde e encerramento

O health não considera uma chamada a `subscribe` suficiente para declarar o assinante UP. A saúde depende de metadados acessíveis do broker/tópico, participação no grupo, trabalhador ativo e ausência de retry pendente, falha fatal ou encerramento. Callbacks de erro, atribuição e revogação atualizam o estado. O endpoint HTTP lê esse estado sem executar chamadas Kafka.

O estado global A1 fica DEGRADED quando banco ou assinante estão DOWN. A indicação de S4 indisponível permanece, pois o adaptador ainda pertence à parte 6 do plano. O healthcheck Docker também verifica `status == ONLINE`; receber HTTP 200 com corpo DEGRADED passa a resultar em falha do healthcheck.

No encerramento, a aplicação sinaliza parada e aguarda o trabalhador terminar antes de fechar o pool PostgreSQL. Uma mensagem já em persistência pode concluir e confirmar seu offset. Se o trabalhador não terminar dentro do prazo, o shutdown relata erro e mantém o pool aberto, evitando fechá-lo durante uma gravação ativa. O consumidor não perde uma parada solicitada antes do agendamento da thread.

### Produtor fake

O fake usa tópico e broker configuráveis. Os quatro exemplos padrão são da candidata 1.1; `--schema-version 1.0` permite exercitar compatibilidade. Eventos são validados pelo contrato estrito antes de construir o produtor, exceto quando `--invalid` foi solicitado explicitamente.

`--fresh` regenera IDs, sessão e sequência, deslocando os horários das fixtures por um mesmo intervalo. Preserva as diferenças entre captura, análise e publicação. Os horários continuam sintéticos; não representam medições de inferência. Campos ausentes e valores inválidos de fixtures negativas não são reparados silenciosamente.

O produtor usa callbacks de entrega, timeout de fila e `flush` limitado. Só informa sucesso quando todas as mensagens têm confirmação. Erro de callback, mensagens pendentes, confirmação ausente ou fila permanentemente cheia produzem status de saída diferente de zero. A idempotência do produtor foi habilitada; ela não substitui a deduplicação A1 por `message_id`.

## Configuração

Foi incluído `.env.kafka.example`. O fallback do código é `localhost:9092`, evitando uma conexão implícita à nuvem. Dentro de um container, esse endereço aponta para o próprio container: configurar explicitamente um broker alcançável pela rede da composição. A composição integrada com I8 e Kafka permanece na parte 8.

| Variável | Default |
|---|---|
| `KAFKA_BROKER_URL` | `localhost:9092` |
| `KAFKA_TOPIC` | `ods.i8.piece_analysis` |
| `KAFKA_GROUP_ID` | `VER-1-A1-Consumer` |
| `KAFKA_RETRY_ATTEMPTS` | `5` tentativas totais por operação |
| `KAFKA_RETRY_INITIAL` | `0.25` segundo |
| `KAFKA_RETRY_MAX` | `4` segundos |
| `KAFKA_SHUTDOWN_TIMEOUT` | `15` segundos |

O Compose repassa essas variáveis. Para testes B2 compartilhados, o endereço temporário do guia deve ser informado explicitamente. Não foi exercitado nesta etapa. É possível selecionar o tópico industrial anterior por configuração, mas isso não elimina a necessidade de homologar o nome canônico com TRA-1.

Após falha permanente do processamento, o backend continua disponível para consulta histórica e informa degradação. Um container unhealthy não é reiniciado automaticamente apenas por `restart: unless-stopped`; o operador deve corrigir a causa e reiniciar o serviço.

## Evidências de verificação

- A suíte Python A1 completa passou: **147 testes**, sem testes ignorados, com PostgreSQL 17 descartável no localhost.
- Após o ajuste final do healthcheck Docker, sua camada afetada foi revalidada: **6 testes de health/shutdown passaram**, incluindo dois testes novos do comando Docker. Há **149 testes distintos aprovados** considerando os dois conjuntos; a suíte completa não foi repetida depois dessa alteração isolada.
- A prova de banco usa PostgreSQL real para persistência, deduplicação, revisão, auditoria e reinício da aplicação. As falhas transitórias/permanentes de repositório foram injetadas nos testes; não se afirma um ensaio de queda física da rede ou do servidor PostgreSQL.
- Os testes de transporte usam doubles Kafka. Verificam ordem de persistência/commit, retry, falha de confirmação, rejeição durável, parada e callbacks. Não comprovam roteamento ou offsets em um broker real.
- O PostgreSQL temporário foi encerrado e removido ao terminar os testes.
- Ambiente de teste: Python 3.13.5; versões resolvidas em `dependencias-testadas.txt`. O build Docker completo em Python 3.11 não foi executado nesta etapa.
- Houve um aviso de depreciação do TestClient Starlette/httpx, sem falhas. Não foi alterado o conjunto de dependências da aplicação para suprimir esse aviso.

As fixtures de banco/API deixaram de referenciar a classe inexistente `A1IngestionClient`; elas injetam um assinante offline, sem construir cliente da nuvem.

Comando principal, na raiz A1:

```bash
# Definir A1_TEST_DATABASE_URL para um banco de teste descartável.
python -m pytest -q
# Verificação focada posterior ao ajuste Docker:
python -m pytest -q tests/test_kafka_lifecycle.py
```

## Aplicação e revisão

Este PR compara `fix/consumidor-kafka-confiavel` com `feat/contrato-kafka-1-1` no A1. Assim, a aba **Files changed** mostra somente a correção da parte 2; o contrato da parte 1 está na branch base e tem seu próprio PR.

Para conferir sem usar o Codex:

1. Abra a descrição do PR e leia os resultados de testes.
2. Na aba **Files changed**, consulte `backend/kafka_client.py` e os três arquivos novos de testes Kafka.
3. Abra `docs/evidencias/parte2/RESULTADOS.txt` para os resultados locais e `dependencias-testadas.txt` para as versões utilizadas.
4. A aba **Checks** mostra somente execuções automáticas do GitHub. Os resultados locais descritos aqui não devem ser confundidos com um workflow aprovado.

I8 não recebeu alterações novas nesta parte. A reconciliação main/develop da similaridade continua na parte 4. As branches main e develop não foram alteradas. Este PR permanece em rascunho para revisão; não houve merge.

## Próximo aceite

A parte 2 está pronta para revisão local. A parte 3 deverá integrar o publisher Kafka do I8 e demonstrar o fluxo com broker, confirmando reentrega e deduplicação no ambiente escolhido. A disponibilidade presumida das dependências não foi tratada como evidência de integração concluída.

Referências de API utilizadas: [cliente Python Confluent](https://docs.confluent.io/kafka-clients/python/current/overview.html) e [API Consumer/Producer](https://docs.confluent.io/platform/8.0/clients/confluent-kafka-python/html/index.html).
