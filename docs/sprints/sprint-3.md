# Sprint 3 — Fechamento VER-1

Este índice organiza a documentação por assunto e pelo plano coletivo de fechamento da Sprint 3. A numeração das sprints em documentos anteriores é mantida como histórico; este índice não redefine o backlog nem cria novos IDs de atividade.

## Contrato Kafka I8/A1 — atividades 01–02

Escopo: tópico/schema funcional, versão final 2.0, captured_at/occurred_at/published_at, validação, fixtures e janela de compatibilidade 1.0.

- [Contrato e decisões](../contratos/kafka-i8-2.0.md).
- [Evidências de contrato](../evidencias/contrato-kafka-2.0/README.md).
- PRs de revisão: [A1 #5](https://github.com/ods-26-2/a1/pull/5) e [I8 #5](https://github.com/ods-26-2/i8/pull/5).

## Ingestão Kafka A1 — atividades 03–05

Escopo: consumidor, confirmação após persistência/rejeição durável, retry, produtor fake, saúde, shutdown e contexto de testes Docker.

- [PR A1 #6](https://github.com/ods-26-2/a1/pull/6).
- [Correção de números fora do limite de armazenamento](../evidencias/limites-armazenamento-a1/README.md).
- [Evidências da ingestão](https://github.com/ods-26-2/a1/blob/fix/consumidor-kafka-confiavel/docs/evidencias/ingestao-kafka-a1/README.md).
- [Roteiro Linux e laboratório](https://github.com/ods-26-2/a1/blob/fix/consumidor-kafka-confiavel/validacao-local/README.md).

As evidências distinguem testes unitários com Kafka simulado de uma prova local com broker e banco reais. A prova usa eventos sintéticos; não comprova inferência industrial I8.

## Publicação I8 — atividade 06

O publisher Kafka I8 continua fora deste incremento, conforme decisão da equipe. A prova A1 usa o produtor fake e não declara inferência I8.

## Provas A1 — atividades 07–09

Transporte fake, deduplicação, reinício, falha do PostgreSQL e regressão da S3-08 foram aprovados com Kafka e PostgreSQL reais.

- [Evidências das etapas 07–09](../evidencias/etapas-07-09/README.md).
- [Execução automatizada](https://github.com/ods-26-2/a1/actions/runs/42031483908).
- [PR A1 #7](https://github.com/ods-26-2/a1/pull/7).

## Outros escopos do fechamento

- Unificação de extração e similaridade, S3-04: atividade 10.
- Dataset, artefatos, calibração e avaliação: atividades 11–16.
- Entrada/runtime I8, S3-06, e fluxo real: atividades 17–18.
- Evidência S4, histórico, relatórios e métricas S5: atividades 19–23.
- Atuação P7, taxonomia e componentes B6: atividades 24–27.
- Composição S3-12, regressão, desempenho, evidências e consolidação: atividades 28–32.

Fonte de numeração: plano_fechamento_sprint3_dependencias.pdf fornecido pela equipe. Datas e aceites devem ser confirmados pelo grupo. Publicar uma branch ou um PR de rascunho não encerra uma atividade nem comprova uma dependência externa.

## Adaptador P7 com simulador — atividade 24

Pedido durável, reenvio com mesmo ID, correlação de reply/state, aceite separado da conclusão, limites e prazo explícito. Consulte o [resumo e roteiro Docker](atividade-24-resumo.md). A integração física continua na atividade 25; o driver publicado ainda exige alinhamento com SIS-2.
