# Sprint 3 — Corrigir mensagem que bloqueia a ingestão A1

Uma mensagem com número maior que o banco suporta passava no contrato e fazia
o consumidor repetir uma gravação impossível. Ao esgotar as tentativas, ele
parava e deixava a próxima mensagem pendente.

Agora o A1 verifica seus limites de armazenamento antes de gravar. O evento é
registrado em `ingestion_failures`; só depois o consumidor confirma a mensagem
e segue para a próxima. Se o registro da rejeição falhar, a mensagem continua
pendente, preservando o mecanismo de recuperação.

Os schemas compartilhados e o banco não foram alterados. A verificação é local
à ingestão do A1, após validar o contrato. Ela cobre `sequence`, `frame_index`,
`detection_id` e as quatro coordenadas de `bbox`, conforme os tipos PostgreSQL
existentes. Os maiores números suportados continuam sendo aceitos.

## Prova em Docker — 05/11/2026

Base A1: `f4141bb43a2d13127cf2dcc380d991322be7ad35`.
Branch: `fix/ingestao-limites-inteiros`. Resultados obtidos antes do commit de
publicação, com PostgreSQL 17 real e cliente Kafka substituído por double.

- [Antes](antes.txt): o teste novo falhou; nenhuma mensagem foi confirmada e a próxima ficou pendente.
- [Após a correção, testes focados](focados.txt): 74 aprovados.
- [Suíte completa](suite-completa.txt): 179 testes Python e 14 frontend aprovados, sem testes ignorados.

Foram acrescentados 17 casos: sete campos/posições acima do limite nas duas
versões de contrato, dois casos de máximos aceitos e um caso de falha ao registrar
a rejeição. Os testes verificam no banco a rejeição antes da confirmação, o
processamento da mensagem válida seguinte e a preservação do evento recusado.
O aviso de descontinuação Starlette/httpx é preexistente; não houve falha na suíte final.

Para reproduzir na raiz A1:

```bash
docker compose -p ver1-a1-bounds run --rm --build tests
docker compose -p ver1-a1-bounds down -v
```

O projeto Docker local foi encerrado com `down -v`. Não houve acesso ao broker
compartilhado. A prova específica dos números fora do limite usa PostgreSQL
real e o consumidor real com cliente Kafka substituído; não é uma nova prova
de inferência I8 ou do fluxo industrial completo.
