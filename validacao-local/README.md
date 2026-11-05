# Testar as partes 1 e 2 no Linux

Este laboratório executa Kafka, PostgreSQL e A1 reais em Docker. Os eventos são sintéticos; o modelo de inferência I8 não é executado. O broker compartilhado da turma não é acessado.

## Preparar

É necessário ter Git e Docker com o plugin Docker Compose funcionando. Verifique `docker info` e `docker compose version`.

Em uma pasta nova:

```bash
git clone --single-branch --branch fix/consumidor-kafka-confiavel https://github.com/ods-26-2/a1.git a1
git clone --single-branch --branch feat/contrato-kafka-1-1 https://github.com/ods-26-2/i8.git i8
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

Resultado verificado: **149 testes Python e 13 testes do frontend aprovados**. Consulte [a saída registrada](../docs/evidencias/parte2/testes-docker.txt).

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

Resultados da prova anterior: **87 testes de contratos I8** e **13 testes de interoperabilidade** aprovados. As branches de contrato dos dois repositórios são necessárias para a segunda verificação.

## Executar Kafka, A1 e PostgreSQL

```bash
docker compose -p ver1-lab -f validacao-local/compose.yml up -d --build backend frontend
docker compose -p ver1-lab -f validacao-local/compose.yml run --rm --build prova
```

A primeira execução pode baixar imagens e dependências. O serviço `kafka-init` cria o tópico e deve terminar com código 0. Banco, Kafka e backend devem ficar saudáveis.

Abra:

- [Interface A1](http://localhost:18080/frontend/).
- [Saúde da API](http://localhost:18000/api/v1/health).

O script publica quatro eventos 1.1, repete os mesmos IDs e publica quatro eventos 1.0 com IDs novos. São **12 publicações e oito inspeções únicas**. Confere que não surgiram comandos ou registros de ingestão duplicados, verifica offsets confirmados e lê as oito inspeções pela API.

O resultado fica em `validacao-local/evidencias/resultado.json`, fora do versionamento. Ele deve indicar `passed-local-real-kafka`. O offset foi 12 na prova com tópico novo; em execuções posteriores ele pode ser maior.

`i8-subscriber: UP` indica o consumidor Kafka A1 ativo; não confirma a execução da inferência I8. A política A1 ainda pode encaminhar os quatro resultados para REVIEW enquanto faltam limiares calibrados. S4 continuará pendente.

## Conferir após reinício

```bash
docker compose -p ver1-lab -f validacao-local/compose.yml restart backend
docker compose -p ver1-lab -f validacao-local/compose.yml run --rm prova --recheck
```

O segundo comando verifica os IDs da execução anterior. O resultado esperado é a preservação das oito inspeções, comandos e registros INGESTED.

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

A prova anterior foi feita no commit `d1ad836138de91c48c6bd97f8be6ee9eb1adb8e4`. A atualização atual corrige o contexto de build e publica o roteiro; não altera a lógica do backend, do consumidor ou do fake. A prova Kafka anterior foi preservada com sua identificação, sem atribuí-la a um commit diferente.

Não estão comprovados aqui: inferência I8 real, P2/P4/I1/P6, serviços S4/S5/P7, queda física durante gravação, latência industrial ou o broker oficial. A candidata de contrato 1.1 ainda depende do aceite de TRA-1.

- [Evidências e limites da parte 2](../docs/evidencias/parte2/README.md).
- [Prova estruturada Kafka](../docs/evidencias/parte2/kafka-real/resultado.json).
- [Kafka em Docker](https://kafka.apache.org/39/getting-started/docker/).
- [Docker Compose](https://docs.docker.com/reference/cli/docker/compose/).
