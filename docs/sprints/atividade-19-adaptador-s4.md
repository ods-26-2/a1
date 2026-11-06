# Sprint 3 — atividade 19: evidência S4 no A1

A1 já registrava um pedido de snapshot para cada inspeção, mas a evidência permanecia pendente. Este incremento reutiliza esses pedidos e acrescenta envio, respostas e atualização da API.

## Arquitetura em palavras simples

1. I8 entrega a análise; A1 guarda inspeção, pedido S4 e auditoria juntos.
2. O adaptador guarda o comando de barramento antes de enviar. O ID e o conteúdo permanecem iguais nos reenvios.
3. A reply `OK` confirma o pedido, mas a imagem ainda fica pendente.
4. O evento `ods.s4.clip` fornece o descritor. A1 confere fonte, sessão, comando/evento, ID da mídia e instante exato do snapshot.
5. A evidência fica disponível pela API somente com referência HTTP(S) válida e ainda não expirada. A interface existente já representa os estados.

A1 guarda metadados e referência, sem capturar, recortar ou armazenar mídia. O hash do descritor é validado como SHA-256; A1 não baixa automaticamente o arquivo para comprovar seu conteúdo. A prova do laboratório verifica os bytes da imagem sintética separadamente.

## Estados e falhas

- `PENDING`: aguardando reply/descritor.
- `AVAILABLE`: descritor correlacionado e URL HTTP(S) não expirada.
- `UNAVAILABLE`: recusa S4, timeout de conclusão ou referência que exige acesso ainda não disponível.
- `EXPIRED`: terminou a validade da mídia. A API oculta o link imediatamente, mesmo antes do próximo ciclo do worker.

O prazo de conclusão é 30 segundos a partir do registro do pedido. O reenvio usa intervalo de 5 segundos e conserva ID, horário e payload. Timeout não comprova que a captura deixou de acontecer. Não há criação automática de outro comando após timeout.

Respostas duplicadas não repetem a atualização/auditoria; descritor pode chegar antes da reply. Conteúdo de outra inspeção é recusado e registrado. Kafka confirma offsets somente após persistência, rejeição durável ou identificação de mensagem não aplicável. Falha de banco ou de commit interrompe o consumidor S4 com saúde degradada; após corrigir a causa, reinicie o backend para reprocessar os offsets pendentes. Falhas transitórias de transporte/broker são sondadas novamente.

## Ativação

O padrão é **desativado**, preservando a execução atual. `S4_ENABLED=1` inicia o adaptador no backend, usando `KAFKA_BROKER_URL` e grupo `S4_GROUP_ID` (padrão `a1-s4-v1`). Crie explicitamente os tópicos `ods.s4.capture.command`, `ods.s4.capture.reply` e `ods.s4.clip`; o adaptador não os cria.

O health do componente `s4` informa a prontidão do adaptador/transportes. Broker acessível não homologa o serviço S4 nem comprova mídia real. O laboratório habilita o adaptador somente no Compose isolado. Não habilite na composição real antes de resolver os pontos da atividade 20 abaixo.

## Testar no Linux com Docker

Na raiz desta branch A1:

```bash
mkdir -p validacao-local/evidencias-s4
docker compose -p ver1-s4 -f validacao-local/compose-s4.yml run --rm --build testes
docker compose -p ver1-s4 -f validacao-local/compose-s4.yml down -v
bash validacao-local/executar_s4.sh
```

O primeiro comando de testes executa a seleção S4 com PostgreSQL real. O script seguinte usa Kafka/PostgreSQL/API reais e S4/imagem simulados. Ele verifica quatro inspeções, reenvio, offsets dos dois tópicos, conteúdo da mídia sintética por hash e persistência após reiniciar o A1. Ao terminar, executa `compose down -v`, inclusive se houver falha. Logs e relatórios ficam em `validacao-local/evidencias-s4/`.

Regressão completa:

```bash
docker compose -p ver1-s4 -f validacao-local/compose-s4.yml run --rm --build testes sh -c 'python scripts/validate_contracts.py && python -m pytest -q --junitxml=/evidencias/regressao.xml && npm test'
docker compose -p ver1-s4 -f validacao-local/compose-s4.yml down -v
```

O workflow `testes-s4.yml` repete essas provas e publica XML/JSON/log por 30 dias. O simulador mantém deduplicação somente durante sua instância; isso não certifica reinício/deduplicação do serviço S4 real. A imagem é um PNG sintético de um pixel, sem relação com peças industriais. Não foi feita inspeção visual do frontend em navegador neste incremento.

## Atividade 20 — integração real ainda bloqueada

Consulta ao [handler S4](https://github.com/ods-26-2/s4/blob/57ea2cc226b2a8cf47a134d1f7490060d2033027/src/infrastructure/b3_bus/handlers/capture_command_handler.cpp) e aos [schemas B1](https://github.com/ods-26-2/b1/tree/fdaeb80bc46014d14649f7ba0c14cd8a3533eb96/S4):

- O handler escolhe o quadro mais recente e não usa `payload.at`/janela pedida. A1 exige o instante da inspeção para evitar associar outra peça.
- O contrato descreve `start_at=end_at` em SNAPSHOT; o handler atual usa uma janela em torno do quadro e um arquivo `.mp4`. A mídia precisa ser compatível com a exibição de snapshot do A1.
- O handler gera novo `clip_id` a cada comando, sem deduplicação visível por `message_id`. Reenvio não pode criar outra captura.
- A URI publicada é `s4://clips/...`; falta confirmar o acesso HTTP(S) controlado à mídia. A1 não converte essa URI em um endereço inventado.

Esses pontos precisam de alinhamento com MOD-2/S4 e prova com fonte/buffer reais. Não foram alterados arquivos do repositório S4, provisionado broker compartilhado ou acessada VM Google Cloud. Esta entrega cobre o adaptador com simulador; não encerra a atividade 20 nem o fluxo industrial completo.

[Evidências dos testes](../evidencias/atividade-19-s4/README.md).
