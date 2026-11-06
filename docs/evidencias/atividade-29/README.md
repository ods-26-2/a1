# Atividade 29 — regressão completa

Critério da página 5 do plano: “Contratos, banco, Kafka, frontend e reinício
aprovados”. A execução canônica usa:

Resultado: **REGRESSAO_LOCAL_APROVADA** na execução GitHub Actions
[#42218589659](https://github.com/ods-26-2/a1/actions/runs/42218589659),
commit de merge testado `9724856a6ba0ff2fb0d90db14362137933daf9ee`.
Foram aprovados **387 testes Python**, **27 testes frontend**, contratos,
PostgreSQL, Kafka e reinício, sem falhas ou erros. Um teste Python foi ignorado:
a prova isolada do loader I8 exige o repositório I8 local; a composição do
mesmo job executou o publisher I8 fixado e conferiu seus eventos no A1.
O [resultado estruturado](resultado.json) e o [log resumido](resumo.log) ficam
versionados; XML e logs integrais permanecem no artefato da execução.

```bash
bash fechamento-sprint3/regressao.sh
```

O runner executa, no mesmo checkout identificado:

1. validação dos contratos 6c;
2. toda a suíte Python com PostgreSQL 17 real;
3. toda a suíte frontend;
4. publisher I8 fixado, Kafka 3.9.1, A1 e PostgreSQL;
5. envio, reenvio idempotente, leitura pelo frontend e reinício do backend;
6. encerramento com remoção dos volumes dos dois laboratórios.

O workflow `Sprint 3 - fechamento reproduzível` publica XML, logs, comandos,
ambiente e JSON consolidado como artefato por 30 dias.

Limite: a regressão local usa o publisher real do I8 com eventos sintéticos.
Ela não substitui a inferência real pendente da atividade 18, nem homologa S4,
S5, P7 ou escala industrial.
