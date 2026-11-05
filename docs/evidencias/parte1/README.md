# Parte 1 — testes do contrato Kafka 1.1

Esta alteração prepara o contrato que I8 publica e A1 recebe. Não implementa o publisher Kafka nem conclui a integração com broker real. O aceite externo de TRA-1 permanece pendente.

## O que foi verificado

- No A1, os testes de contratos existentes e os novos exemplos passaram: **24 testes**.
- A verificação conjunta A1/I8 passou: **13 testes**, com quatro resultados válidos e oito exemplos negativos.
- Os schemas novos de publicação são idênticos nos dois componentes.
- A versão 1.0 continua aceita; a candidata 1.1 exige occurred_at explícito.
- Campos ausentes, datas inválidas, classes/taxonomias desconhecidas e versões incompatíveis são exercitados.

Os resultados são locais e estão em [RESULTADOS.txt](RESULTADOS.txt). Eles não representam uma execução de GitHub Actions. O script conjunto valida contrato e taxonomia sem importar Torch ou abrir conexão de banco/Kafka.

## Como reproduzir

Na raiz deste repositório, com pytest e jsonschema instalados:

```bash
python -m pytest -q tests/test_contracts_6c.py tests/test_kafka_contract_1_1_candidate.py
```

Para verificar A1 e I8 juntos, usar o script publicado na branch de contrato do A1, apontando para as duas cópias das branches de contrato:

```bash
python scripts/validar_interoperabilidade_kafka_1_1.py --a1 /caminho/a1 --i8 /caminho/i8
```

## Como revisar pelo GitHub

Leia primeiro a descrição do PR. Depois abra **Files changed** para ver o código, os exemplos e os testes. A aba **Checks** mostra apenas testes automáticos do GitHub, quando houver uma execução. Não é necessário usar o Codex para ler esses resultados.

A suíte completa de inferência com Torch não foi executada para esta alteração de contrato. A suíte completa de backend A1 e os testes de transporte pertencem ao PR separado da parte 2.
