# Atividade 30 — latência, recursos e ambiente

Critério da página 5 do plano: “Latência ponta a ponta, memória e ambiente
registrados”. A execução reproduzível usa:

Resultado: **MEDICAO_LOCAL_REGISTRADA** na execução GitHub Actions
[#42219871217](https://github.com/ods-26-2/a1/actions/runs/42219871217),
commit de merge testado `04572cd8c6118922b4378fec0aa29478b02a0206`.
No runner observado, quatro mensagens tiveram p50 **4494,177 ms** e p95
**4521,766 ms** desde a invocação do container do publisher até persistência.
Trinta leituras do histórico tiveram p50 **2,836 ms** e p95 **3,699 ms**.
O snapshot dos quatro containers somou **426,074 MiB**. Valores completos,
ambiente e limites ficam no [resultado estruturado](resultado.json) e no
[log resumido](resumo.log).

```bash
bash fechamento-sprint3/medir.sh
```

A latência principal começa imediatamente antes do comando do publisher I8 e
termina no `received_at` persistido pelo A1 no PostgreSQL. Quatro mensagens são
medidas individualmente. Também são feitas 30 leituras do histórico pela API.
Depois da regressão e do reinício, `docker stats --no-stream` registra memória,
CPU instantânea e processos de banco, Kafka, backend e frontend. O ambiente fixa
commits, imagens, SO, CPU, memória do runner, Docker e Compose.

O workflow publica JSON bruto, resumo, logs, imagens e ambiente como artefato
por 30 dias.

Limite: os eventos são sintéticos. Esta prova mede publisher, Kafka, A1 e banco,
não inferência de imagem. O fluxo real da atividade 18 permanece bloqueado;
quatro eventos e um snapshot de recursos não representam carga industrial.
