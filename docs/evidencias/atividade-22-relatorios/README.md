# Atividade 22 — recorrência, causas e relatórios locais

Base: `a62debecf2ecda2715d516f6432fa07ddb985359` (atividade 21). Data: 06/11/2026. O critério do plano é “Recorrência, causa, inspeção e exportação funcionando localmente”.

## Diagnóstico e semântica adotada

Os [requisitos RF18–RF21](../../requisitos.md) nomeiam recorrência, associação de causa provável e relatórios. A [arquitetura](../../arquitetura.md) atribui esses serviços ao A1. Os dados anteriores contêm classificação I8, decisão de negócio, motivo de revisão e auditoria; não contêm parâmetros de processo ou vínculo validado entre defeito e causa operacional. Portanto não há causalidade automática neste incremento.

**Recorrência:** contar inspeções NON_CONFORMING por `(source_id, taxonomy_version, defect_class original)`, nos filtros da atividade 21. Duas ou mais inspeções no mesmo grupo/período são recorrentes. Conta inspeções/observações deduplicadas pelo A1, não peças físicas únicas; múltiplas detecções da mesma peça podem ser inspeções diferentes. Taxonomias e origens diferentes não são somadas. Ordem: contagem decrescente e chave crescente. `rate=count/total_inspections` usa como denominador todas as inspeções que passam pelos filtros; filtrar NON_CONFORMING altera esse denominador. Não é automaticamente uma taxa de defeitos da fábrica inteira.

**Causa:** hipótese operacional declarada manualmente pelo operador, com fundamentação obrigatória. Classe de defeito e motivo de revisão não geram hipótese. Registros são append-only, com ID, inspeção, autor, data e evento `CAUSE_RECORDED` na mesma transação. O último `seq` da inspeção é a hipótese vigente nos agregados; o relatório individual preserva todas as hipóteses. O agrupamento usa texto exato, após trim, sensível a maiúsculas; não há catálogo ou normalização semântica automática. Ausência aparece como `NOT_RECORDED`, nunca como classe de defeito ou causa inventada. `OPERATOR_REPORTED` significa relato, não comprovação ou aprovação técnica. Identificação do operador é declarada, como nas revisões atuais; não é assinatura autenticada.

**Inspeção:** relatório reúne InspectionView, histórico de revisões/eventos e histórico de causas no mesmo snapshot PostgreSQL. Preserva análise e triagem originais, decisão final separada, referências/estado da evidência S4 e auditoria, sem baixar a mídia. A URL segue as regras de expiração do A1. Os eventos existentes S4/P7 e o novo evento de causa foram incluídos aditivamente no schema da trilha, para representar registros já persistidos.

## API, limites e exportação

O [contrato](../../contratos/a1-api.md) descreve as novas rotas. Schema: [report.schema.json](../../../shared/schemas/a1-api/report.schema.json) e [cause.schema.json](../../../shared/schemas/a1-api/cause.schema.json).

- `GET /api/v1/reports/recurrence` e `/reports/causes`: filtros de captura/resultado/origem/defeito da 21, combinados por AND. Início inclusivo/fim exclusivo com fuso são obrigatórios; máximo 31 dias. Relatórios não aceitam `limit/offset`: agregam o conjunto filtrado completo ou recusam explicitamente.
- `GET /api/v1/inspections/{id}/report`: relatório completo daquela inspeção, ou 404.
- `POST /api/v1/inspections/{id}/causes`: `{operator, cause, basis}`; máximos 64/200/1000 caracteres, trim, texto não vazio e UTF-8 válido. Registra uma hipótese e sua auditoria atomicamente; não altera análise/revisões/evidências. O alvo da tela é vinculado explicitamente e permanece fixo durante o preenchimento, mesmo se a inspeção exibida mudar.
- Máximo 5000 inspeções por agregado e 5000 entradas em cada trilha individual; o resultado nunca é truncado silenciosamente. Cada comando SQL tem timeout de 5 segundos. Excesso de registros/tamanho retorna 422; timeout retorna 503 e recomenda reduzir filtros.
- `file_format=json` (padrão) ou `csv`: mesma informação do relatório, com nome fixo seguro, `Cache-Control: no-store` e `nosniff`. Máximo de 10 MiB serializados. JSON usa UTF-8 e chaves ordenadas; CSV usa UTF-8 com BOM, CRLF, todas as células entre aspas e proteção de prefixos de fórmula (`=`, `+`, `-`, `@`, inclusive após espaços/controles/BOM).

CSV tem duas colunas, `section` e `record_json`: cada registro de seção mantém sua estrutura como JSON dentro da célula. Isso preserva decisões/evidência/auditoria aninhadas, inclusive vírgulas, aspas e quebras de linha. Strings do operador são conteúdo JSON dentro da célula; não fórmulas. Reimportar com parser CSV e `json.loads(record_json)`, sem executar o conteúdo.

A interface exporta o **relatório já carregado** como Blob local JSON/CSV; não refaz a consulta ao clicar em baixar. O servidor oferece os mesmos formatos para reprodução por API. Mesmo objeto exportado tem ordem estável; nova consulta pode mudar `generated_at`, causas, revisões e estado de expiração. Guardar o artefato original, filtros, instante e versão executada permite repetir a análise; não se promete identidade de bytes entre consultas novas ou entre serializadores Python/JavaScript. Relatórios não enviam dados a serviços externos.

## Verificação local inicial

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q -p no:cacheprovider tests/test_reports.py tests/test_inspection_search.py tests/test_review_service.py
node --test --test-isolation=none 'frontend/tests/*.test.js'
python scripts/validate_contracts.py
git diff --check
```

Resultado inicial: **52 Python aprovados e 4 PostgreSQL ignorados**, **23 frontend aprovados**, contratos 6c e diff aprovados. Os testes novos cobrem agrupamento determinístico, separação origem/taxonomia, ausência de inferência causal, schema, período/limites, SQL parametrizado, erro/timeout, CSV com conteúdo hostil, integridade de JSON/UTF-8 e tamanho máximo. Testes frontend cobrem causas fake/última hipótese/histórico, validação, endpoints e exportação local. Modo fake conserva dados somente na instância do navegador e não comprova persistência.

Os quatro skips correspondem aos dois testes PostgreSQL da 21 e dois da 22; dependem de `A1_TEST_DATABASE_URL`. Os novos casos reais verificam recorrência, filtros, última hipótese no agregado, histórico integral, análise/decisão/evidência preservadas, auditoria, imutabilidade e rollback quando auditoria falha. Este registro inicial não afirma que rodaram com banco real nem que houve inspeção visual no navegador. Não há Docker no PATH do agente executor.

Seleção de regressão ampliada (incluindo fixtures API, lifecycle Kafka e S4): **77 aprovados e 42 PostgreSQL ignorados**. Novos testes frontend de relatórios reexecutados após reforçar as guardas: **5 aprovados**. Schemas JSON, sintaxe Python, links locais e `git diff --check` passaram.

## Reproduzir PostgreSQL e conferir a tela

Reutiliza o runner isolado existente, sobrescrevendo a seleção, sem acionar S5/P7:

```bash
mkdir -p validacao-local/evidencias-s5-p7
docker compose -p ver1-relatorios -f validacao-local/compose-s5-p7.yml run --rm --build testes \
  sh -c 'python -m pytest -q tests/test_reports.py tests/test_inspection_search.py --junitxml=/evidencias/relatorios.xml && npm test && python scripts/validate_contracts.py'
docker compose -p ver1-relatorios -f validacao-local/compose-s5-p7.yml run --rm testes \
  python -m pytest -q --junitxml=/evidencias/relatorios-regressao.xml
docker compose -p ver1-relatorios -f validacao-local/compose-s5-p7.yml down -v
```

Esperado: os 47 casos focados (26 da 22 e 21 da 21) passam sem skip, além da regressão. Registrar XML/logs, commit, ambiente e resultados efetivamente obtidos. A regressão PostgreSQL do workflow existente já inclui os novos testes.

Na tela: preencher período UTC no histórico, gerar recorrência e causas, selecionar inspeção e gerar relatório individual. Vincular explicitamente a inspeção ao formulário de causa; registrar operador/hipótese/fundamentação; gerar novamente e verificar causa/auditoria, mantendo classificação original. Baixar JSON/CSV, reimportar e comparar dados com relatório carregado. Testar período inválido/vazio, erro da API, texto com `=`, vírgulas/aspas, mudança da inspeção enquanto escreve a causa e largura de celular. A causa deve permanecer no ID vinculado. Registros reais permanecem após reiniciar A1; nenhum serviço externo é necessário para essas funções locais.

Limites de escopo: não há inferência automática de causa, confirmação industrial de hipótese, relatório S5, atuação P7 ou alterações de tarefas 25+.
