# Sprint 3 — Prova das etapas 07, 08 e 09

Este laboratório executa Kafka, PostgreSQL e A1 reais em Docker. Os eventos são sintéticos. O publicador I8 e seu modelo de inferência não são executados. O broker compartilhado da turma não é acessado.

Escopo comprovado:

- etapa 07: fake → Kafka → consumidor A1 → PostgreSQL → API;
- etapa 08: deduplicação, reinício e recuperação após indisponibilidade do banco;
- etapa 09: fila, correção, histórico e auditoria da S3-08 após a migração Kafka.

## Preparar

É necessário ter Git e Docker com o plugin Docker Compose funcionando. Verifique `docker info` e `docker compose version`.

Em uma pasta nova:

```bash
git clone https://github.com/ods-26-2/a1.git a1
git clone https://github.com/ods-26-2/i8.git i8
cd a1
mkdir -p validacao-local/evidencias
export VER1_UID="$(id -u)" VER1_GID="$(id -g)"
```

Os repositórios A1 e I8 devem ficar lado a lado. Os comandos seguintes são executados na raiz do A1. As variáveis VER1_UID/VER1_GID permitem gravar o relatório com seu usuário Linux.

## Rodar a suíte A1 sem Kafka

```bash
docker compose -p ver1-testes run --rm --build tests
```

Esse é o alvo original do repositório. Inicia somente as dependências necessárias aos testes, usa PostgreSQL real e substitui o cliente Kafka por doubles nos testes de transporte. A correção do `.dockerignore` permite copiar o Dockerfile para o ambiente de teste, sem volume adicional.

O resultado atual deve ser conferido na execução da automação `Validação da fase 2` e no artefato `evidencias-fase-2`.

Depois, encerre o banco descartável desse comando:

```bash
docker compose -p ver1-testes down -v
```

Esse comando apaga somente os volumes do projeto de testes `ver1-testes`.

## Contratos I8 e interoperabilidade

Não é preciso instalar Torch ou baixar modelos:

```bash
docker compose -p ver1-lab -f validacao-local/compose.yml run --rm --build contratos-i8
docker compose -p ver1-lab -f validacao-local/compose.yml run --rm --build interoperabilidade
```

Essas verificações confirmam o contrato. Elas não implementam nem executam o publicador I8, que está fora deste escopo.

## Executar Kafka, A1 e PostgreSQL

```bash
docker compose -p ver1-lab -f validacao-local/compose.yml up -d --build backend frontend
docker compose -p ver1-lab -f validacao-local/compose.yml run --rm --build prova
```

A primeira execução pode baixar imagens e dependências. O serviço `kafka-init` cria o tópico e deve terminar com código 0. Banco, Kafka e backend devem ficar saudáveis.

Abra:

- [Interface A1](http://localhost:18080/frontend/).
- [Saúde da API](http://localhost:18000/api/v1/health).

O script publica quatro eventos finais 2.0, repete os mesmos IDs e publica quatro eventos legados 1.0 com IDs novos. São **12 publicações e oito inspeções únicas**. Ele confere comandos, auditoria, offsets e leitura pela API.

O mesmo ensaio seleciona uma inspeção recebida pelo Kafka, aplica `CORRECT`, confirma sua saída da fila, aplica `SEND_TO_REVIEW` e confirma o retorno. A decisão automática original permanece imutável. Revisões e eventos de auditoria ficam no histórico.

O resultado fica em `validacao-local/evidencias/resultado.json`, fora do versionamento. A prova inicial indica `fluxo-normal-aprovado`. A sequência completa muda o estado para `aprovado-fase-2-kafka-real` após comprovar falha e recuperação do banco. O Compose cria uma partição. Portanto, a prova observa somente a partição zero e não generaliza o resultado para tópicos com várias partições.

`i8-subscriber: UP` indica o consumidor Kafka A1 ativo; não confirma a execução da inferência I8. A política A1 ainda pode encaminhar os quatro resultados para REVIEW enquanto faltam limiares calibrados. S4 continuará pendente.

## Conferir após reinício

```bash
docker compose -p ver1-lab -f validacao-local/compose.yml restart backend
docker compose -p ver1-lab -f validacao-local/compose.yml run --rm prova --recheck
```

O segundo comando verifica os IDs da execução anterior. O resultado esperado é a preservação das oito inspeções, comandos e registros INGESTED.

## Conferir falha e recuperação do PostgreSQL

Execute após a prova normal:

```bash
docker compose -p ver1-lab -f validacao-local/compose.yml stop db
docker compose -p ver1-lab -f validacao-local/compose.yml run --rm --no-deps prova --publish-pending
docker compose -p ver1-lab -f validacao-local/compose.yml up -d --wait db
docker compose -p ver1-lab -f validacao-local/compose.yml restart backend
docker compose -p ver1-lab -f validacao-local/compose.yml up -d --wait backend
docker compose -p ver1-lab -f validacao-local/compose.yml run --rm prova --verify-pending
```

O segundo comando publica uma mensagem enquanto o PostgreSQL está indisponível. Ele exige `--no-deps` para não tentar restaurar o banco automaticamente. O script aguarda o health indicar `DEGRADED` e registrar falha de persistência no consumidor. Só então confirma que o offset permanece pendente. Depois da restauração, a mensagem deve aparecer uma vez no banco. Uma nova publicação do mesmo ID não pode duplicar inspeção, comando ou evento `INGESTED`.

A automação [Validação da fase 2](../.github/workflows/validacao-fase-2.yml) executa a sequência completa e publica os JSON como artefato. A execução de referência foi [aprovada no GitHub Actions](https://github.com/ods-26-2/a1/actions/runs/42031483908).

Para diagnóstico:

```bash
docker compose -p ver1-lab -f validacao-local/compose.yml ps -a
docker compose -p ver1-lab -f validacao-local/compose.yml logs --tail=100 backend kafka
```

O endereço interno do broker é `kafka:9092`. Não se deve substituí-lo por `localhost` dentro dos containers. As portas HTTP 18000 e 18080 são publicadas somente no localhost.

## Encerrar

```bash
docker compose -p ver1-lab -f validacao-local/compose.yml down
```

Para apagar também os dados **somente desse laboratório**, acrescente `-v`. Não use `--recheck` depois de apagar o banco sem executar a prova normal primeiro.

## Limites e referências

Não estão comprovados aqui: publicador e inferência I8 reais, P2/P4/I1/P6, serviços S4/S5/P7, queda física, latência industrial, várias partições, broker compartilhado ou navegação automatizada no frontend. A prova S3-08 cobre `CORRECT` e `SEND_TO_REVIEW`; `CONFIRM` e entradas inválidas permanecem cobertos pela suíte do backend. O roteiro usa o contrato final 2.0 e testa também a leitura temporária do legado 1.0.

- [Evidências e limites da ingestão Kafka A1](../docs/evidencias/ingestao-kafka-a1/README.md).
- [Prova estruturada Kafka](../docs/evidencias/ingestao-kafka-a1/kafka-real/resultado.json).
- [Kafka em Docker](https://kafka.apache.org/39/getting-started/docker/).
- [Docker Compose](https://docs.docker.com/reference/cli/docker/compose/).


## Referência de planejamento

Este escopo integra a Sprint 3 do plano coletivo de fechamento. O [índice da Sprint 3](../docs/sprints/sprint-3.md) relaciona os assuntos e as atividades do plano.
