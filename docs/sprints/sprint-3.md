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

- [Etapa 16: política candidata A1, origem/hash e rollback](atividade-16-politica-candidata.md). Provisória e não ativada; política padrão preservada.

- Unificação de extração e similaridade, S3-04: atividade 10.
- Dataset, artefatos, calibração e avaliação: atividades 11–16.
- Entrada/runtime I8, S3-06, e fluxo real: atividades 17–18.
- Evidência S4, histórico, relatórios e métricas S5: atividades 19–23.
- Atuação P7, taxonomia e componentes B6: atividades 24–27.
- Composição S3-12, regressão, desempenho, evidências e consolidação: atividades 28–32.

Fonte de numeração: plano_fechamento_sprint3_dependencias.pdf fornecido pela equipe. Datas e aceites devem ser confirmados pelo grupo. Publicar uma branch ou um PR de rascunho não encerra uma atividade nem comprova uma dependência externa.

## Adaptador P7 com simulador — atividade 24

Pedido durável, reenvio com mesmo ID, correlação de reply/state, aceite separado da conclusão, limites e prazo explícito. Consulte o [resumo e roteiro Docker](atividade-24-resumo.md). A integração física continua na atividade 25; o driver publicado ainda exige alinhamento com SIS-2.

## Evidência S4 — atividade 19

[Adaptador, arquitetura, comandos Docker e bloqueios da atividade 20](atividade-19-adaptador-s4.md). Reutiliza pedidos já persistidos; ativação explícita, correlação, timeout e expiração. O laboratório usa S4/mídia simulados e Kafka/PostgreSQL/A1 reais.

## Validação S4 real — atividade 20

Resultado: **BLOQUEADA_EXTERNAMENTE**, alternativa prevista no plano. O [registro de bloqueio e roteiro de retomada](../evidencias/atividade-20-s4-real/README.md) e o [manifesto rastreável](../evidencias/atividade-20-s4-real/manifesto.json) fixam as versões A1/S4, cinco impedimentos, responsáveis e critérios para a próxima validação. Não houve captura real nem homologação do serviço nesta atividade.

## Histórico e filtros — atividade 21 / S3-10

[Contrato da busca histórica](../contratos/a1-api.md#inspectionlist--histórico-pesquisável-s3-10--atividade-21) e [evidências/roteiro](../evidencias/atividade-21-historico/README.md). API PostgreSQL e tela com período de captura, resultado I8, origem e defeito originais combináveis, ordenação estável e paginação. Auditoria por ID e revisões existentes preservadas; relatórios e recorrência ficam na atividade 22.

## Recorrência, causas e relatórios locais — atividade 22

[Semântica, limites, exportações e evidências](../evidencias/atividade-22-relatorios/README.md). Agregações determinísticas dos filtros21; causa operacional somente declarada por operador com fundamentação e auditoria, separada do defeito e da revisão; relatório integral de inspeção e downloads locais JSON/CSV. Sem causalidade automática ou dependência externa nova.

## Preparação S5 e revalidação P7 — atividades 23 e 24

[Critérios, funções, comandos Docker e limites](atividades-23-24-fechamento.md). A integração S5 EVENT é preparada por contrato com simulador; P7 com fake já estava na main e é revalidado. A prova física da atividade 25 continua separada.

## Prova física P7 — atividade 25

Resultado: **BLOQUEADA_EXTERNAMENTE**, alternativa prevista no plano. O [registro e roteiro acompanhado](../evidencias/atividade-25-p7-fisico/README.md) e o [manifesto rastreável](../evidencias/atividade-25-p7-fisico/manifesto.json) fixam A1/P7, dependência de bancada, coordenadas, homing, limites, transporte, idempotência, riscos e parada segura. Nenhum driver foi executado e não houve movimento físico nesta atividade.

## Taxonomia final A1/I8 — atividade 26

[Verificação executável e proveniência](../evidencias/atividade-26-taxonomia/README.md) e [manifesto com commits/descritor/hashes](../evidencias/atividade-26-taxonomia/manifesto.json). Resultado local: **VERIFICADA_REFERENCIA_COMPARTILHADA**, com loaders A1/I8 consumindo os mesmos bytes e recusando divergências. I8 referencia o pacote A1; implantação e hash da taxonomia no treino histórico não estão comprovados por essa igualdade local.

## Componentes B6 — atividade 27

[Avaliação individual, licença/proveniência e evidências](../evidencias/atividade-27-b6/README.md), com [manifesto fixado](../evidencias/atividade-27-b6/manifesto.json). Comportamento útil de navegação AppShell incorporado em implementação vanilla original A1, sem copiar fonte B6. AlertConsole, OverlayPlayer e ZoneEditor não incorporados, com incompatibilidades de domínio/contrato justificadas. Sem dependência de build ou mudança na API.
