# Sprint 3 — atividade 24: adaptador P7 com simulador

P7 orienta a câmera por pan-tilt. Esta entrega prepara A1 para pedir uma posição e acompanhar a resposta, sem mover hardware.

## O que muda na arquitetura

O serviço A1 registra o pedido no PostgreSQL antes do envio. O adaptador entrega esse pedido a um transporte fornecido pelo chamador. Nos testes, esse transporte é o simulador `FakeP7`.

- `PENDING`: pedido salvo, ainda não enviado.
- `SENT`: envio tentado; entrega pode ter ocorrido mesmo se houver erro de comunicação.
- `ACCEPTED`: P7 respondeu `OK`. Isso não comprova conclusão.
- `COMPLETED`: chegou `ods.p7.state` com o mesmo comando, mecanismo correto, posição solicitada, `IDLE` e homing concluído.
- `REJECTED`: P7 recusou o pedido, com motivo registrado.
- `FAILED`: P7 informou falha durante o movimento.
- `EXPIRED`: não houve conclusão no prazo. O resultado físico permanece desconhecido.

O chamador fornece um `command_id` estável. Repetir esse ID retorna o pedido existente; trocar sua intenção é erro. O reenvio conserva o envelope completo, inclusive ID e horário. Respostas duplicadas e fora de ordem não reabrem comandos encerrados. A auditoria e o estado mudam na mesma transação.

## Como testar no Linux

Na raiz do repositório A1 desta branch, execute:

```bash
mkdir -p validacao-local/evidencias-p7
docker compose -p ver1-p7 -f validacao-local/compose-p7.yml run --rm --build testes
docker compose -p ver1-p7 -f validacao-local/compose-p7.yml down -v
```

O relatório fica em `validacao-local/evidencias-p7/p7.xml`. Para executar também a regressão Python e frontend:

```bash
docker compose -p ver1-p7 -f validacao-local/compose-p7.yml run --rm testes sh -c 'python scripts/validate_contracts.py && python -m pytest -q && npm test'
docker compose -p ver1-p7 -f validacao-local/compose-p7.yml down -v
```

O laboratório usa PostgreSQL real e P7 simulado. Não inicia Kafka, não publica portas e não acessa dispositivos. O workflow `testes-p7.yml` executa o mesmo teste no GitHub Actions e guarda XML/log por 30 dias.

## Onde continuar a integração

`build_services(...).p7` oferece `request`, `dispatch`, `receive`, `get` e `expire`. O transporte implementa `send(topic, message)` com prazo limitado. O chamador encaminha replies e states a `receive` e chama `expire` ao verificar prazos. Não existe processo de envio automático nesta entrega.

O serviço não cria atuação a partir de uma reprovação industrial. Não foram acrescentados botão, rota HTTP, consumidor Kafka ou ligação com o driver. Essas ligações exigem a composição da aplicação e o transporte acordado com SIS-2/B2.

## Contrato e pendências externas

Os três schemas foram copiados sem alteração do B1, árvore `fdaeb80bc46014d14649f7ba0c14cd8a3533eb96`, pasta [P7](https://github.com/ods-26-2/b1/tree/fdaeb80bc46014d14649f7ba0c14cd8a3533eb96/P7). O adaptador acrescenta verificações do envelope 6c. Não muda o contrato externo.

O contrato usa pan de −90° a 90° e tilt de −45° a 45°. O [driver P7 consultado](https://github.com/ods-26-2/p7/blob/a4698d9e0590db6ecaeb741cfaac15356b6599e2/pantilt_driver.py) usa coordenadas de servo diferentes, aplica clamping e não implementa reply/state. **Não ligar esse driver diretamente ao adaptador.** SIS-2 precisa definir a conversão, o comportamento de recusa e o transporte real.

A deduplicação do simulador dura enquanto sua instância existe. O PostgreSQL preserva o pedido após recriar o adaptador A1; isso não comprova deduplicação após reiniciar o dispositivo real. Essa garantia, os limites calibrados, a bancada e a prova física pertencem à atividade 25. Na operação real, não gerar outro ID automaticamente após timeout: o movimento anterior pode ter ocorrido.

A atividade 24 pode ser revisada com fake. A atividade 25 continua pendente. Não há homologação externa ou prova física nesta entrega.
