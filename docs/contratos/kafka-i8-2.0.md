# Sprint 3 — Contrato Kafka final I8/A1

## Decisão final

| Item | Valor |
|---|---|
| Tópico Kafka | `ods.industria.defeito_classificado` |
| `schema` | `ods.industria.defeito_classificado` |
| `schema_version` | `2.0` |
| `message_type` | `event` |
| `producer` | `I8` |

O nome usa domínio funcional e mantém tópico igual ao `schema`. A versão é
major porque a interface 1.0 usa outra identidade e não exige `occurred_at`.
A proposta `ods.i8.piece_analysis` 1.1 nunca foi ativada e foi substituída por
esta decisão antes da publicação.

## Tempos

| Campo | Significado |
|---|---|
| `captured_at` | Captura original do quadro; I8 preserva o valor recebido. |
| `occurred_at` | Conclusão da análise I8. |
| `published_at` | Preparação da primeira publicação. |

Os três campos usam UTC com milissegundos no formato
`YYYY-MM-DDTHH:mm:ss.SSSZ`. Retry preserva `message_id`, sequência e horários.
Não usar a confirmação do broker como `published_at`.

## Envelope e payload

- `message_id`, `session_id` e `correlation_id`, quando presente: UUID v4.
- `sequence`: inteiro não negativo, crescente por produtor e sessão.
- `bbox`: `[x_min,y_min,x_max,y_max]`, com coordenadas não negativas e área positiva.
- `result`: `CONFORMING`, `NON_CONFORMING`, `ANOMALY` ou `UNCERTAIN`.
- `defect_class`: obrigatório somente em `NON_CONFORMING` e resolvido pela taxonomia versionada.
- `confidence` e `similarity`: números finitos entre 0 e 1.
- Mídia, severidade e consequência de negócio não pertencem ao evento I8.

## Janela de compatibilidade

O A1 aceita somente estes pares durante a migração:

| `schema` | `schema_version` | Uso |
|---|---|---|
| `ods.i8.piece_analysis` | `1.0` | Legado temporário e histórico. |
| `ods.industria.defeito_classificado` | `2.0` | Contrato final. |

Combinações híbridas, a candidata 1.1, versões `2.x` não declaradas e majors
desconhecidas são recusadas. O I8 mantém 1.0 apenas para replay controlado e
publica 2.0 explicitamente no fluxo novo.

## Ativação e rollback

1. Implantar primeiro o consumidor A1 com suporte explícito a 1.0 e 2.0.
2. Disponibilizar `ods.industria.defeito_classificado` no Kafka.
3. Ativar o publicador I8 2.0.
4. Verificar validação, persistência, deduplicação e confirmação de offset.
5. Manter o leitor 1.0 até encerrar produtores e mensagens legadas.

Rollback: interromper a publicação 2.0 e manter o consumidor A1 compatível com
1.0. Registros históricos preservam `schema`, versão, identidade e horários
originais. Este PR não remove o leitor legado.

## Fontes executáveis

- A1: `shared/schemas/6c/i8-defeito-classificado.publish.2.0.schema.json`.
- I8: `shared/schemas/6c/i8-defeito-classificado.2.0.schema.json`.
- Exemplos: `shared/mocks/kafka-2.0/`.
- Verificação conjunta: `scripts/validar_interoperabilidade_kafka_2_0.py`.

Os schemas de publicação A1/I8 devem permanecer byte a byte idênticos. O teste
conjunto não prova conexão com broker, banco ou hardware.
