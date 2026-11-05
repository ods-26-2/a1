# Sprint 3 — Evidências do contrato Kafka 2.0

Esta alteração fecha o contrato publicado pelo I8 e recebido pelo A1:

```text
topic:          ods.industria.defeito_classificado
schema:         ods.industria.defeito_classificado
schema_version: 2.0
```

## Verificações

- Quatro resultados válidos passam nos validadores reais A1 e I8.
- O schema estrito de publicação é idêntico nos dois repositórios.
- O A1 preserva leitura explícita de `ods.i8.piece_analysis` 1.0.
- A candidata 1.1, combinações híbridas e versões desconhecidas são recusadas.
- `occurred_at` é obrigatório na 2.0 e representa a conclusão da análise.
- Exemplos negativos cobrem campos ausentes, datas, versão, bbox e vocabulário.

Os testes são locais. Eles não comprovam conexão com Kafka, persistência ou
inferência real.

## Reprodução

```bash
python -m pytest -q tests/test_contracts_6c.py tests/test_kafka_contract_2_0.py
python scripts/validar_interoperabilidade_kafka_2_0.py --a1 /caminho/a1 --i8 /caminho/i8
```

Resultados da execução ficam em [RESULTADOS.txt](RESULTADOS.txt).
