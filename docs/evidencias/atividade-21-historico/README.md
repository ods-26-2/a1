# Atividade 21 — histórico e filtros (S3-10)

Data: 06/11/2026. Base: `efd177323a137914bb8db4136abce8740bfa00fe` (atividade 20). Escopo do plano: consultas por período, resultado, origem e defeito. A implementação é aditiva: `GET /api/v1/inspections`, projeção de InspectionView existente e formulário de busca na tela A1.

## Comportamento verificável

- Período de captura em UTC: início incluso e fim exclusivo, com validação de fuso e ordem.
- Resultado original I8, origem exata e classe original de defeito combinados por AND; valores bem formados sem correspondência retornam vazio.
- Ordem `captured_at DESC, inspection_id DESC`, limite 1–100 e offset; interface usa páginas de 20. Total e página têm snapshot PostgreSQL único por requisição. Inserções entre requisições podem deslocar páginas.
- Selecionar um resultado abre inspeção, decisão original, decisão final e revisões já existentes. Correções não reclassificam silenciosamente o filtro de análise original; nenhuma consulta escreve auditoria ou muda a inspeção.
- Modo fake usa quatro fixtures e deixa explícita a ausência de persistência. Carregamento, vazio e erro têm feedback; resultado antigo é limpo ao buscar. Respostas atrasadas não substituem consulta mais recente.

O [contrato completo](../../contratos/a1-api.md) define nomes, limites e exemplo de URL. O [schema executável](../../../shared/schemas/a1-api/inspection-list.schema.json) preserva InspectionView e os contratos das rotas existentes. O único acréscimo no banco é índice idempotente por captura/ID; bootstrap não reescreve registros. Sua criação pode consumir recursos/bloquear escrita durante bootstrap em base volumosa e deve ser planejada no ambiente de implantação.

## Verificação local deste incremento

Com Python 3.14 e Node disponíveis no Windows:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q -p no:cacheprovider tests/test_inspection_search.py
node --test --test-isolation=none 'frontend/tests/*.test.js'
python scripts/validate_contracts.py
git diff --check
```

Resultado inicial: **19 Python aprovados, 2 PostgreSQL ignorados**, **18 frontend aprovados** (14 existentes + 4 novos); contratos 6c e diff aprovados. Os testes locais não dependem de diretório temporário nem iniciam Kafka. O isolamento do runner Node é desativado localmente porque o sandbox recusa `spawn`; não altera o código/testes da aplicação.

Os 19 testes verificam HTTP/422, normalização UTC, filtros completos, SQL parametrizado, intervalo inclusivo/exclusivo, projeção e schema. Os dois casos PostgreSQL verificam combinação, fronteiras, total fora da página, ordenação com empates, páginas sem sobreposição, análise imutável após revisão e auditoria preservada. Foram ignorados porque `A1_TEST_DATABASE_URL` não está definida; esta evidência local não substitui sua execução. Testes frontend verificam filtros fake, transporte HTTP/encoding, guarda de contrato, seleção, paginação, vazio e erro por controlador com DOM mínimo simulado; não constituem inspeção visual no navegador.

## Reproduzir com PostgreSQL real

Reutiliza o runner/DB isolados existentes, sobrescrevendo a seleção de testes; não aciona S5/P7, Kafka, VM ou bancada:

```bash
mkdir -p validacao-local/evidencias-s5-p7
docker compose -p ver1-historico -f validacao-local/compose-s5-p7.yml run --rm --build testes \
  sh -c 'python -m pytest -q tests/test_inspection_search.py --junitxml=/evidencias/historico.xml && npm test && python scripts/validate_contracts.py'
docker compose -p ver1-historico -f validacao-local/compose-s5-p7.yml run --rm testes \
  python -m pytest -q --junitxml=/evidencias/historico-regressao.xml
docker compose -p ver1-historico -f validacao-local/compose-s5-p7.yml down -v
```

Esperado: os 21 casos históricos passam sem skip e a regressão existente permanece aprovada. O workflow já existente `testes-s5-p7.yml` inclui regressão completa com PostgreSQL em PRs que alteram backend/tests/shared; portanto inclui esta suíte. Guardar XML/logs da execução real como complemento, com commit e ambiente efetivamente testados. Docker não estava disponível no PATH deste agente; não houve execução real de banco neste registro inicial.

## Conferência no navegador

1. Abrir A1 em modo fake; buscar as quatro análises, combinar NON_CONFORMING e AMASSADO, testar período UTC que exclui/inclui o instante, limpar e abrir uma inspeção.
2. Repetir no backend real com registros persistidos; comparar total, fonte, horários e defeito da API com a tela. Navegar entre páginas com empates de horário e conferir ID como desempate.
3. Corrigir defeito em inspeção conhecida, reler histórico e verificar que filtro original encontra a análise original e detalhes mostram também a classe final.
4. Testar vazio, API indisponível, datas invertidas e telas estreitas; registrar capturas, URL, versão e erros, se houver.

Não há relatório, recorrência, exportação, agrupamento de causas ou integração externa nova nesta atividade.
