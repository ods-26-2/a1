# Etapa 16 — política A1 candidata e provisória

Versão: `triage-a1-1.2.0-candidate`. Estado: **provisória, não ativada**.
O catálogo padrão permanece em `triage-a1-1.1.0`, com revisão humana nos quatro resultados. Não há alteração de banco, VM, publicação Kafka, política I8 ou inspeções históricas.

## Origem e integridade

O pacote em `shared/policies/triage/candidates/triage-a1-1.2.0-candidate/` contém:

- `policy/content.json`: consequências A1 existentes e limiares candidatos.
- `source-i8-policy.json`: snapshot do artefato `models/policy-caixa_papelao-policy-csv-001.json` do I8, com finais de linha CRLF normalizados para LF, sem alterar campos ou valores.
- `descriptor.json`: repositório, commit completo de `origin/main` no momento da preparação, caminho, versões de modelo/classificador/taxonomia e SHA-256 dos dois conteúdos.

O commit é fixado no descritor, não consultado pela rede durante execução. O descritor distingue o SHA-256 do blob Git original (CRLF) e do snapshot local (LF); o carregador verifica ambos, reconstruindo os finais de linha originais. Hashes detectam alterações nas cópias; não equivalem a assinatura, homologação ou validação industrial da origem. `.gitattributes` preserva os bytes locais contra conversão CRLF.

## Mapeamento e limites

| Resultado I8 | Candidata A1 |
|---|---|
| CONFORMING | REVIEW: não existe limiar calibrado de confiança de conformidade na origem |
| NON_CONFORMING | confiança menor que 0,8: REVIEW; a partir de 0,8: consequência existente da classe (REJECTED nas três classes atuais) |
| ANOMALY | REVIEW, sem atribuir classe conhecida |
| UNCERTAIN | REVIEW |

`known_confidence=0.8` vem do artefato I8 e ainda é provisório. `conforming_similarity=0.2354041860284747` e `anomaly_similarity=0.09153255441789314` medem similaridade; **não são confiança** e não são copiados para `minimum_confidence`. A margem I8 0,05 também não é margem da triagem A1.

O produto de origem é `caixa_papelao`. O catálogo A1 atual seleciona por taxonomia, não produto/modelo. Por isso esta candidata só pode ser avaliada offline: não deve ser ativada globalmente em uma instalação com origens/produtos não delimitados. A avaliação I8 ainda tem suporte zero de ANOMALY e desempenho limitado em algumas classes; esta etapa não corrige nem homologa o modelo.

## Revisão explícita, compatibilidade e rollback

```python
from backend.taxonomy import TaxonomyCatalog
from backend.triage import PolicyCatalog, TriageService

policies = PolicyCatalog.from_candidate(
    "shared/policies/triage/candidates/triage-a1-1.2.0-candidate"
)
review_service = TriageService(policies, TaxonomyCatalog())
# review_service.decide(payload_validado) executa apenas a candidata offline.
```

O carregador verifica hashes, versões, origem e mapeamento antes de reutilizar o motor existente. `build_services` continua usando `PolicyCatalog()`; nenhuma variável de ambiente ativa a candidata. O diretório padrão não é recursivo, portanto a candidata não disputa a taxonomia com a política anterior.

Rollback da avaliação: voltar a `PolicyCatalog()`/`triage-a1-1.1.0`, sem mover arquivos nem migrar dados. A política anterior e seu arquivo permanecem intactos; a versão histórica 1.0 continua arquivada. Inspeções já gravadas conservam decisão e versão originais. Uma futura ativação exige aceite dos limiares, delimitação de produto/modelo e revisão separada; não deve reescrever o histórico.

## Verificação

```bash
python -m pytest -q tests/test_triage.py tests/test_candidate_triage_policy.py
```

Testes cobrem quatro resultados, fronteira inclusiva, classes, ausência de aprovação CONFORMING, origem/hashes alterados, política padrão e rollback. Eles não treinam nem calibram I8, não executam Kafka/banco e não são prova de qualidade industrial.

Verificação local deste incremento: **37 testes focados aprovados** (14 existentes e 23 novos); regressão Python **151 aprovados e 93 ignorados**, pois `A1_TEST_DATABASE_URL` não está definida. O validador de contratos 6c e `git diff --check` passaram. Os testes com fixtures temporárias precisaram executar fora da restrição de acesso do sandbox; nenhum teste foi alterado para contornar essa restrição. Não houve execução PostgreSQL, Kafka ou VM. Os avisos pytest-asyncio e Starlette/httpx são de depreciação, sem falha.
