# Sprint 3 — Fechamento VER-1

Este índice organiza a documentação por assunto e pelo plano coletivo de fechamento da Sprint 3. A numeração das sprints em documentos anteriores é mantida como histórico; este índice não redefine o backlog nem cria novos IDs de atividade.

## Contrato Kafka I8/A1 — atividades 01–02

Escopo: tópico/schema, versão candidata 1.1, captured_at/occurred_at/published_at, validação, fixtures e compatibilidade 1.0. Proposta local aceita; homologação externa TRA-1 pendente.

- [Contrato e decisões](../contratos/kafka-i8-1.1-candidato.md).
- [Evidências de contrato](../evidencias/contrato-kafka-1.1/README.md).
- PRs de revisão: [A1 #5](https://github.com/ods-26-2/a1/pull/5) e [I8 #5](https://github.com/ods-26-2/i8/pull/5).

## Ingestão Kafka A1 — atividades 03–05

Escopo: consumidor, confirmação após persistência/rejeição durável, retry, produtor fake, saúde, shutdown e contexto de testes Docker.

- [PR A1 #6](https://github.com/ods-26-2/a1/pull/6).
- [Evidências da ingestão](https://github.com/ods-26-2/a1/blob/fix/consumidor-kafka-confiavel/docs/evidencias/ingestao-kafka-a1/README.md).
- [Roteiro Linux e laboratório](https://github.com/ods-26-2/a1/blob/fix/consumidor-kafka-confiavel/validacao-local/README.md).

As evidências distinguem testes unitários com Kafka simulado de uma prova local com broker e banco reais. A prova usa eventos sintéticos; não comprova inferência industrial I8.

## Publicação e integração I8 — atividade 06 e provas 07–09/18

O publisher Kafka I8 é o próximo incremento de implementação, com João como responsável principal e apoio de Ícaro no transporte. Samuel participa das provas A1. O fluxo real e os testes de recuperação em falhas precisam de aceite próprio.

## Outros escopos do fechamento

- Unificação de extração e similaridade, S3-04: atividade 10.
- Dataset, artefatos, calibração e avaliação: atividades 11–16.
- Entrada/runtime I8, S3-06, e fluxo real: atividades 17–18.
- Evidência S4, histórico, relatórios e métricas S5: atividades 19–23.
- Atuação P7, taxonomia e componentes B6: atividades 24–27.
- Composição S3-12, regressão, desempenho, evidências e consolidação: atividades 28–32.

Fonte de numeração: plano_fechamento_sprint3_dependencias.pdf fornecido pela equipe. Datas e aceites devem ser confirmados pelo grupo. Publicar uma branch ou um PR de rascunho não encerra uma atividade nem comprova uma dependência externa.
