# Evidências das etapas 07, 08 e 09

Execução automatizada: [GitHub Actions 42031483908](https://github.com/ods-26-2/a1/actions/runs/42031483908).

Data: 5 de novembro de 2026. Commit testado: `df7cdac`. Ambiente isolado com Kafka 3.9.1, PostgreSQL 17, backend A1 e produtor fake. O publicador e a inferência I8 não participaram desta prova.

## Resultado

Status final: `aprovado-fase-2-kafka-real`.

| Etapa | Prova | Resultado |
|---|---|---|
| 07 | fake → Kafka → A1 → PostgreSQL → API | aprovado |
| 08 | repetição de IDs, reinício e falha/recuperação do banco | aprovado |
| 09 | fila, `CORRECT`, `SEND_TO_REVIEW`, histórico e auditoria após Kafka | aprovado |

## Etapa 07

- Quatro eventos 2.0 geraram quatro inspeções, quatro comandos e quatro eventos `INGESTED`.
- A repetição dos mesmos quatro IDs manteve as contagens em quatro.
- Quatro eventos legados 1.0 com IDs novos elevaram as contagens para oito.
- Foram feitas 12 publicações e persistidas oito inspeções únicas.
- O offset final da primeira fase foi 12, igual ao maior offset do tópico.

## Etapa 08

- Depois do primeiro reinício, as oito inspeções, comandos e auditorias continuaram no PostgreSQL.
- Com o PostgreSQL interrompido, uma mensagem nova elevou o maior offset para 13, mas o grupo permaneceu no offset 12.
- O health registrou `DEGRADED`, banco `DOWN` e consumidor `DOWN` por falha de persistência.
- Depois da restauração, o grupo confirmou o offset 13 e persistiu uma inspeção, um comando e um evento `INGESTED`.
- Uma nova publicação do mesmo ID elevou o tópico ao offset 14, sem criar duplicata.
- Um segundo reinício preservou a mensagem recuperada.

## Etapa 09

- Uma inspeção recebida pelo Kafka entrou na fila de revisão.
- `CORRECT` alterou a decisão final para `REJECTED` sem modificar análise e triagem automáticas.
- `SEND_TO_REVIEW` devolveu a inspeção à fila.
- O histórico registrou dois `REVIEW_RECORDED`, além de `INGESTED`, `TRIAGED` e `EVIDENCE_REQUESTED`.
- Depois do reinício, as duas revisões, os cinco eventos de auditoria, a decisão automática original e a presença na fila permaneceram.

## Suíte

Na máquina local:

- 128 testes Python aprovados;
- 34 testes PostgreSQL ignorados por falta de banco local;
- 14 testes do frontend aprovados.

Na automação, a suíte completa executou contra PostgreSQL 17 real. O relatório JSON e o manifesto da falha estão no artefato `evidencias-fase-2` da execução.

## Limites

A prova usa uma partição e um Kafka local isolado. Ela não comprova publicador I8, inferência real, broker compartilhado, várias partições, S4, S5, P7 ou bancada física. `CONFIRM` e entradas de revisão inválidas permanecem cobertos pelos testes do backend, não pelo roteiro finito desta prova.
