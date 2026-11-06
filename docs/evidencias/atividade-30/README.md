# Atividade 30 — latência, recursos e ambiente

Critério da página 5 do plano: “Latência ponta a ponta, memória e ambiente
registrados”. A execução reproduzível usa:

Resultado: **MEDICAO_LOCAL_REGISTRADA** na execução GitHub Actions
[#42219871217](https://github.com/ods-26-2/a1/actions/runs/42219871217),
commit de merge testado `04572cd8c6118922b4378fec0aa29478b02a0206`.
No runner observado, quatro mensagens tiveram p50 **4494,177 ms** e p95
**4521,766 ms** desde a invocação do container do publisher até o início da ingestão A1.
Trinta leituras do histórico tiveram p50 **2,836 ms** e p95 **3,699 ms**.
O snapshot dos quatro containers somou **426,074 MiB**. Valores completos,
ambiente e limites ficam no [resultado estruturado](resultado.json) e no
[log resumido](resumo.log).

```bash
bash fechamento-sprint3/medir.sh
```

A latência principal começa imediatamente antes do comando do publisher I8 e
termina no `received_at` registrado ao entrar em `ingest()`, antes de validar o evento
e executar a transação. Ler esse horário depois no PostgreSQL não transforma
o valor em horário de commit. Quatro mensagens são
medidas individualmente. Também são feitas 30 leituras do histórico pela API.
Depois da regressão e do reinício, `docker stats --no-stream` registra memória,
CPU instantânea e processos de banco, Kafka, backend e frontend. O ambiente fixa
commits, imagens, SO, CPU, memória do runner, Docker e Compose.

O workflow publica JSON bruto, resumo, logs, imagens e ambiente como artefato
por 30 dias.

Limite: os eventos são sintéticos. Esta prova mede publisher, Kafka, A1 e banco,
não inferência de imagem. O fluxo real da atividade 18 permanece bloqueado;
quatro eventos e um snapshot de recursos não representam carga industrial.

## Correção da definição da métrica

O campo antigo publisher_invocation_to_database_ms foi substituído por
publisher_invocation_to_a1_ingestion_ms. O marcador sintético segue a mesma
terminação, com nome synthetic_published_marker_to_a1_ingestion_ms. O resultado
indica persistence_latency_measured=false. Nenhum desses intervalos inclui
a validação e a transação posteriores à chegada. API e memória mantêm sua
metodologia anterior.

Os valores publicados acima são da execução histórica identificada, sem nova
medição numérica. Seus rótulos foram corrigidos no resultado e no resumo.
Os arquivos originais estão preservados em [historico/resultado.json](historico/resultado.json)
e [historico/resumo.log](historico/resumo.log), incluindo o nome antigo incorreto,
para rastrear a correção. Eles não constituem prova de latência até persistência.

A latência até commit/visibilidade após commit e a latência industrial completa
continuam pendentes de uma instrumentação apropriada e do fluxo real da 18.
Não é necessário alterar a ingestão A1 ou seu contrato para esta correção.

## Validação da correção

O teste de regressão novo falhou no código anterior e passou após a correção.
Sete testes focados de métricas/consolidação passaram em Docker sem rede.
O runner completo de medição também passou em Docker local, produzindo os
novos nomes e persistence_latency_measured=false; seu laboratório foi
encerrado com compose down -v. Essa execução de validação não substitui os
valores históricos publicados acima. A atualização do PR repete os workflows.
