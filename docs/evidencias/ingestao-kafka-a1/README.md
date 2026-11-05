# Sprint 3 — Ingestão Kafka A1: consumidor, fake e saúde

Correção implementada e verificada localmente, agora publicada em PR de rascunho. A proposta de contrato Kafka I8/A1 foi aceita por Ícaro; o acordo externo com TRA-1 permanece pendente. Nenhum evento foi enviado ao broker compartilhado e nenhum merge foi realizado.

## Comportamento corrigido

### Consumo e integridade dos dados

O consumidor desabilita `enable.auto.commit` e `enable.auto.offset.store`. O offset da mensagem é confirmado com `commit(message=msg, asynchronous=False)` somente depois de `IngestionService` retornar um resultado durável: ACCEPTED, DUPLICATE ou REJECTED.

Rejeições de contrato passam pelo serviço de ingestão, que registra a falha no banco. JSON inválido, encoding inválido, tombstone e números JSON não permitidos usam `reject_transport_message`, acrescentado ao mesmo serviço. O motivo registra tópico, partição e offset. Nenhuma mensagem inválida é descartada apenas em memória antes do commit.

O processamento mantém uma única mensagem em andamento. Falha de persistência repete essa mensagem com espera progressiva. Falha de commit repete somente o commit, preservando a gravação já concluída. Nenhuma mensagem posterior pode ultrapassar uma mensagem pendente. Se as tentativas esgotarem, o trabalhador encerra, o offset permanece sem confirmação e o health fica DOWN. Após corrigir a causa, reiniciar o backend permite reentrega; a deduplicação existente protege os efeitos já persistidos.

Isso implementa consumo com possibilidade de reentrega e persistência idempotente; não constitui transação distribuída Kafka/PostgreSQL nem promessa de entrega exatamente uma vez em todos os cenários.

### Saúde e encerramento

O health não considera uma chamada a `subscribe` suficiente para declarar o assinante UP. A saúde depende de metadados acessíveis do broker/tópico, participação no grupo, trabalhador ativo e ausência de retry pendente, falha fatal ou encerramento. Callbacks de erro, atribuição e revogação atualizam o estado. O endpoint HTTP lê esse estado sem executar chamadas Kafka.

O estado global A1 fica DEGRADED quando banco ou assinante estão DOWN. A indicação de S4 indisponível permanece, pois o adaptador ainda pertence ao escopo de evidência S4. O healthcheck Docker também verifica `status == ONLINE`; receber HTTP 200 com corpo DEGRADED passa a resultar em falha do healthcheck.

No encerramento, a aplicação sinaliza parada e aguarda o trabalhador terminar antes de fechar o pool PostgreSQL. Uma mensagem já em persistência pode concluir e confirmar seu offset. Se o trabalhador não terminar dentro do prazo, o shutdown relata erro e mantém o pool aberto, evitando fechá-lo durante uma gravação ativa. O consumidor não perde uma parada solicitada antes do agendamento da thread.

### Produtor fake

O fake usa tópico e broker configuráveis. Os quatro exemplos padrão são da candidata 1.1; `--schema-version 1.0` permite exercitar compatibilidade. Eventos são validados pelo contrato estrito antes de construir o produtor, exceto quando `--invalid` foi solicitado explicitamente.

`--fresh` regenera IDs, sessão e sequência, deslocando os horários das fixtures por um mesmo intervalo. Preserva as diferenças entre captura, análise e publicação. Os horários continuam sintéticos; não representam medições de inferência. Campos ausentes e valores inválidos de fixtures negativas não são reparados silenciosamente.

O produtor usa callbacks de entrega, timeout de fila e `flush` limitado. Só informa sucesso quando todas as mensagens têm confirmação. Erro de callback, mensagens pendentes, confirmação ausente ou fila permanentemente cheia produzem status de saída diferente de zero. A idempotência do produtor foi habilitada; ela não substitui a deduplicação A1 por `message_id`.

## Configuração

Foi incluído `.env.kafka.example`. O fallback do código é `localhost:9092`, evitando uma conexão implícita à nuvem. Dentro de um container, esse endereço aponta para o próprio container: configurar explicitamente um broker alcançável pela rede da composição. A composição integrada com I8 e Kafka permanece no escopo de composição S3-12.

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

### Reteste do alvo Docker original, sem montagem adicional

A atualização remove a exclusão de `Dockerfile` em `.dockerignore`. O alvo `tests` passa a receber o arquivo inspecionado por dois testes de saúde. Não foi necessário ignorar testes, modificar o comando de teste ou montar `/app/Dockerfile` por volume.

Comando executado na raiz A1, com projeto de banco descartável isolado:

```bash
docker compose -p ver1-pr6-test run --rm --build tests
```

Resultado: **149 testes Python e 13 testes do frontend aprovados**. O alvo também executou o validador de contratos, conforme seu comando padrão. O PostgreSQL foi real, dentro de um container descartável. Os testes de transporte dessa suíte continuam usando doubles Kafka.

A saída está em [testes-docker.txt](testes-docker.txt), o resumo em [RESULTADOS.txt](RESULTADOS.txt) e as versões Python do container em [dependencias-docker.txt](dependencias-docker.txt). A configuração do [roteiro Linux](../../../validacao-local/README.md) foi validada com `docker compose config --quiet`.

### Prova anterior com Kafka e PostgreSQL reais

A prova estruturada em [kafka-real/resultado.json](kafka-real/resultado.json) foi executada no commit `d1ad836138de91c48c6bd97f8be6ee9eb1adb8e4`, anterior a esta correção de contexto. A lógica do consumidor, fake e backend não foi alterada na atualização atual, portanto a evidência foi preservada com sua identificação original.

Foram **12 publicações de eventos sintéticos, oito inspeções únicas e offset final confirmado em 12**. O reenvio de quatro IDs não criou inspeções, comandos S4 ou registros INGESTED adicionais. Depois de reiniciar normalmente o backend, as oito inspeções e seus registros permaneceram disponíveis; o offset continuou em 12.

Esse teste usa broker Kafka 3.9.1 e PostgreSQL 17 reais em Docker, além da API A1. Não executa inferência I8. O roteiro e o script finito estão em [validacao-local](../../../validacao-local/README.md); os relatórios gerados pelo usuário nesse diretório ficam fora do versionamento.

### Limites e histórico

- Os resultados publicados são **locais**, não execuções de GitHub Actions.
- Os testes anteriores no host registraram 147 aprovações e depois seis testes focados, incluindo dois novos. O novo reteste Docker executou os **149 juntos**, além dos 13 Node.
- A primeira tentativa Docker anterior à correção falhou em dois testes por ausência de `/app/Dockerfile`. A montagem somente leitura usada no laboratório anterior não é mais necessária após esta correção.
- O banco prova persistência, deduplicação, revisão, auditoria e reinício normal. As falhas de repositório dos testes unitários foram injetadas.
- Não houve ensaio de queda física do banco/broker durante gravação ou falha entre persistência e commit.
- O broker compartilhado, a inferência real, P2/P4/I1/P6, S4/S5/P7 e desempenho industrial permanecem fora desta prova.
- O aviso Starlette/httpx de depreciação apareceu, sem falhas; não foi alterado o conjunto de dependências para suprimi-lo.
- Os containers e volumes descartáveis dos testes foram encerrados. Não foram versionados imagens, volumes, caches ou dados locais de desenvolvimento.

## Aplicação e revisão

Este PR compara `fix/consumidor-kafka-confiavel` com `feat/contrato-kafka-1-1` no A1. Assim, a aba **Files changed** mostra somente a correção da ingestão Kafka A1; o contrato Kafka I8/A1 está na branch base e tem seu próprio PR.

Para conferir sem usar o Codex:

1. Abra a descrição do PR e leia os resultados de testes.
2. Na aba **Files changed**, consulte `backend/kafka_client.py` e os três arquivos novos de testes Kafka.
3. Abra `docs/evidencias/ingestao-kafka-a1/RESULTADOS.txt` para o resumo, `testes-docker.txt` para a saída e `dependencias-docker.txt` para as versões do reteste.
4. A aba **Checks** mostra somente execuções automáticas do GitHub. Os resultados locais descritos aqui não devem ser confundidos com um workflow aprovado.

Este incremento de ingestão não altera a implementação I8. A reconciliação main/develop da similaridade continua no escopo de unificação da extração e similaridade (S3-04). As branches main e develop não foram alteradas. Este PR permanece em rascunho para revisão; não houve merge.

## Próximo aceite

A ingestão Kafka A1 está publicada para revisão. O escopo de publicação e integração I8 deverá conectar o publisher Kafka e demonstrar o fluxo de inferência real, além de ampliar a prova de recuperação em falhas no ambiente escolhido. A disponibilidade presumida das dependências não foi tratada como evidência de integração concluída.

Referências de API utilizadas: [cliente Python Confluent](https://docs.confluent.io/kafka-clients/python/current/overview.html) e [API Consumer/Producer](https://docs.confluent.io/platform/8.0/clients/confluent-kafka-python/html/index.html).


## Referência de planejamento

Este escopo integra a Sprint 3 do plano coletivo de fechamento. O [índice da Sprint 3](../../sprints/sprint-3.md) relaciona os assuntos e as atividades do plano.
