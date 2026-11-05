# Parte 1 — contrato Kafka I8 → A1

**Estado:** proposta local aceita por Ícaro; candidata em revisão por PR. O aceite externo de TRA-1 permanece pendente. A publicação do código não ativa o broker nem realiza merge.

## Decisão proposta

| Item | Proposta | Justificativa |
|---|---|---|
| Tópico Kafka | `ods.i8.piece_analysis` | Preserva o nome canônico 6c e iguala tópico e schema, como pede o guia Kafka |
| `schema` | `ods.i8.piece_analysis` | Mantém identidade da interface implementada nos dois componentes |
| `schema_version` | `1.1`, candidata | Acrescenta `occurred_at` sem alterar silenciosamente a publicação estrita `1.0` |
| `message_type` / `producer` | `event` / `I8` | Observação produzida por I8; a decisão industrial permanece em A1 |
| Horários | UTC com milissegundos, `YYYY-MM-DDTHH:mm:ss.SSSZ` | Mesmo formato dos contratos 6c já implementados |
| Payload | Mantido da 6c | Quatro resultados, contexto de quadro/detecção, taxonomia e scores; sem mídia própria e sem decisão A1 |

O guia sugere `ods.industria.defeito_classificado`; a 6c e os contratos executáveis usam `ods.i8.piece_analysis`. A proposta prioriza preservar a interface 6c existente. TRA-1 deve aceitar o nome proposto ou definir outro canônico. Se exigir o domínio `industria`, tópico e schema deverão ser alterados juntos nos dois lados. O híbrido atual, com tópico industrial e schema I8, não deve virar convenção permanente sem um mapeamento formal aceito.

O número `1.1` também depende de confirmação de que não está reservado a outro contrato. Os arquivos usam um identificador de schema com sufixo `candidate`, distinguindo a proposta de uma versão homologada.

## Significado dos três horários

| Campo | Momento representado | Quem fornece |
|---|---|---|
| `captured_at` | Captura original do quadro utilizado | P4/P6; I8 preserva o valor recebido |
| `occurred_at` | Conclusão da análise I8 da detecção, quando o resultado fica disponível | I8, imediatamente após a inferência/decisão de resultado |
| `published_at` | Preparação da primeira publicação do evento | I8, ao montar o envelope para envio |

Essas são definições da **proposta VER-1**; o guia B2 apenas exige `occurred_at`, sem resolver seu significado específico para I8.

Exemplo: captura `13:00:00.000Z`, conclusão da análise `13:00:00.080Z`, publicação inicial `13:00:00.120Z`. Não preencher os três campos com o relógio do fake nem inferir a conclusão da análise a partir de uma captura histórica.

Em retry, preservar evento, `message_id`, sequência e horários. `published_at` não representa a confirmação do broker nem o tempo de cada tentativa. Medir confirmação e recepção separadamente nos logs. Em replay, `captured_at` conserva a origem do quadro e `occurred_at` registra a análise executada no replay.

O contrato valida formato e datas reais. A ordem captura → análise → publicação é uma expectativa operacional, não uma comparação obrigatória entre relógios de máquinas diferentes: sincronização e possível desvio de relógio devem ser registrados na medição. Não corrigir silenciosamente os horários para forçar essa ordem.

## Identidade, payload e versões

- `message_id` e `session_id`: UUID v4; `correlation_id` opcional também usa UUID v4.
- `sequence`: inteiro não negativo, crescente por produtor/sessão, iniciado em zero; retry mantém o valor. O controle da progressão permanece com o chamador.
- Origem e quadro: `source_id`, `session_id`, `frame_index` e `detection_id`; `detection_id` isolado não identifica permanentemente uma peça.
- `bbox`: `[x_min,y_min,x_max,y_max]`, inteiros não negativos nas coordenadas do quadro bruto; runtime exige área positiva.
- `result`: `CONFORMING`, `NON_CONFORMING`, `ANOMALY` ou `UNCERTAIN`.
- `defect_class`: apenas em `NON_CONFORMING`, pertencente à taxonomia carregada; `NORMAL` não é uma classe substituta de CONFORMING.
- `confidence` e `similarity`: números finitos em 0–1. Os valores dos exemplos são sintéticos, sem significado de limiar calibrado ou resultado de modelo real.
- `taxonomy_version`: versão do DEFECT_TAXONOMY A1; `artifact_version`: modelo/composição de inferência efetivamente usados. Não são `schema_version`.
- Mídia/evidência, severidade e consequência de negócio não entram no payload I8. Continuam nos artefatos e serviços responsáveis.

## Compatibilidade e ativação

| Evento | Publicador I8 / publicador estrito A1 candidatos | Consumidor A1 candidato | Prefiltro Kafka da baseline, antes da parte 2 |
|---|---|---|---|
| `1.0` original sem `occurred_at` | Aceito com contrato original | Aceito para histórico/compatibilidade | Recusado; correção na parte 2 |
| `1.1` completa | Aceito com schema novo, idêntico nos dois repositórios | Aceito | Passa na checagem superficial existente |
| `1.1` sem `occurred_at` ou com horário inválido | Recusado | Recusado | Não é validador suficiente; parte 2 deve delegar ao contrato |
| `1.2` aditiva com campos-base `1.1` | Recusado para publicação estrita | Aceito estruturalmente | Não comprova compatibilidade do transporte |
| Major diferente de `1` | Recusado | Recusado | Não usar o prefiltro atual como aceite de versão |

O builder mantém `1.0` como default. Para gerar a candidata, passar explicitamente `schema_version="1.1"` e `occurred_at` real. Não há preenchimento automático desse campo. Os exemplos candidatos estão em diretórios separados dos mocks `1.0` existentes.

O consumidor A1 mantém extensão aditiva de payload/envelope para `1.x`, mas exige o campo-base `occurred_at` a partir da candidata `1.1`. O schema estrito de publicação aceita apenas os campos declarados. O teste existente de extensão aditiva foi ajustado para fornecer esse novo campo-base.

Foram acrescentadas verificações explícitas de datas reais e números finitos no runtime A1: a validação de `date-time` pelo pacote jsonschema pode depender de extras opcionais. Não deixar datas impossíveis passarem apenas por corresponderem a uma expressão regular.

**Ativação proposta:** validar nome/tempos/versão com TRA-1; implantar consumidor atualizado preservando `1.0`; depois ativar publicação `1.1` e migrar fake. A configuração efetiva do tópico, offsets, retry, health, shutdown e confirmação de entrega pertencem à parte 2 e à publicação da parte 3. Nenhuma dessas mudanças de transporte foi aplicada aqui.

## Fonte compartilhada e arquivos preparados

O schema candidato é o mesmo byte a byte em:

- A1: `shared/schemas/6c/i8-piece-analysis.publish.1.1.schema.json`.
- I8: `shared/schemas/6c/i8-piece-analysis.1.1.schema.json`.

Este pacote contém uma cópia canônica em `i8-piece-analysis.1.1.schema.json`. A comparação de bytes faz parte da verificação de interoperabilidade. Mudanças futuras devem atualizar essa fonte e as duas cópias no mesmo incremento; o pacote não cria um registro B1/B5 nem uma terceira fonte oficial remota.

Incluídos: alterações do runtime I8 e do seletor/schema consumidor A1; quatro exemplos válidos e oito inválidos idênticos nos dois lados; documentação candidata; patches separados por repositório; verificador de interoperabilidade. Aplicação dos patches deve ser feita nas baselines indicadas em `MANIFESTO.json`, em branches de trabalho.

## Fronteiras S4, S5 e P7

| Interface | Contrato de referência | Definição ainda necessária |
|---|---|---|
| S4 | `ods.s4.capture.command`, reply, `ods.s4.clip` e consulta de descritor | Transporte real de comando/reply, correlação e suporte a recorte; não acrescentar bbox unilateralmente |
| S5 | `ods.s5.event_metrics`, `ods.s5.metrics.query` e reply | Transporte query/reply e como os eventos industriais alimentam métricas; o mapa 6c não estabelece aresta direta I8/A1 → S5 |
| P7 | `ods.p7.move.command`, reply e `ods.p7.state` | Transporte/correlação operacional; manter pan-tilt e distinguir aceite de conclusão |

O guia fornecido descreve Kafka para eventos. Isso não basta para afirmar que comandos e queries dessas interfaces usam o mesmo mecanismo ou que seus tópicos já existem. Seus schemas não foram modificados nesta candidata.

## Verificação e limites

Resultados detalhados em `RESULTADOS.txt`. Verificações realizadas nas cópias locais dos commits de referência, sem Torch, banco, broker ou hardware:

1. Contratos A1 existentes + candidata: 24 testes aprovados.
2. Contratos I8 existentes + candidata: 87 testes aprovados.
3. Interoperabilidade candidata: 13 testes aprovados, com subcasos para quatro resultados, campos ausentes, versão, horários, valores inválidos, classe/taxonomia e compatibilidade.

O verificador publicado usa os validadores reais A1/I8 e os catálogos reais de taxonomia. Ele não carrega Torch, não constrói cliente Kafka e não acessa banco ou broker. Passar na validação do JSON não prova roteamento, persistência ou confirmação de offsets; essas verificações pertencem às partes 2 e 3.

Reprodução após aplicar os patches nas baselines:

```bash
python -m pip install jsonschema pytest
python scripts/validar_interoperabilidade_kafka_1_1.py --a1 /caminho/a1 --i8 /caminho/i8
# Na raiz de cada componente:
python -m pytest -q tests/test_contracts_6c.py tests/test_kafka_contract_1_1_candidate.py
```

## Perguntas técnicas para TRA-1 — texto preparado, não enviado

> VER-1 está fechando o contrato I8 → A1. Propomos tópico = schema `ods.i8.piece_analysis`, preservando a 6c, e versão candidata `1.1` com `occurred_at` obrigatório. Para esse evento, `captured_at` é a captura do quadro, `occurred_at` a conclusão da análise I8 e `published_at` a preparação da primeira publicação. O payload 6c permanece igual. Podemos adotar esse nome e essa semântica? O número 1.1 está disponível? Há schema/validador B1 atualizado que deva prevalecer? Qual é o transporte acordado de comandos/queries/replies S4/S5/P7 e como são tratados seus tópicos e correlações?

## Aceite externo pendente

Ícaro aceitou a proposta local de **tópico/schema `ods.i8.piece_analysis`, candidata `1.1` e `occurred_at` como conclusão da análise**. Esse aceite permite seguir a implementação interna com a hipótese explícita; não substitui a homologação externa. A parte 1 está tecnicamente preparada e testada localmente, mas o contrato compartilhado só pode ser considerado fechado após o aceite dos participantes.


## Revisão no GitHub

Este documento registra a parte 1. Os resultados locais estão em `docs/evidencias/parte1/README.md`. No A1, o script `scripts/validar_interoperabilidade_kafka_1_1.py` verifica os contratos dos dois repositórios sem carregar Torch ou conectar ao Kafka. O transporte Kafka e sua configuração são tratados separadamente na parte 2.
