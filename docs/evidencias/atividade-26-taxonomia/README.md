# Atividade 26 — verificar taxonomia final A1/I8

Data: 06/11/2026. Critério do plano, página 4: “A1 e I8 usam mesma versão, descritor e hash”. Resultado local: **VERIFICADA_REFERENCIA_COMPARTILHADA**. Os dois loaders consumiram o mesmo pacote A1 e concordaram sobre versão, descritor inteiro, classes e SHA-256. O teste não afirma que um processo implantado já esteja configurado com esses arquivos, nem prova os bytes usados no treino histórico I8.

O [manifesto fixado](manifesto.json) registra origem, commits, hashes dos arquivos, descritor integral e limites da evidência. O [verificador executável](../../../scripts/verify_final_taxonomy.py) retorna zero somente quando toda a cadeia passa. Não há normalização de fim de linha, fallback para outra versão, checkout I8, acesso à rede/B5 ou importação de Torch.

## Cadeia de proveniência comprovada

1. **A1 proprietário:** pacote `shared/artifacts/defect-taxonomy/defects-a1-1.0.0/` no commit [`a4ea77a191eddc7726007fcdb1699cb612797c19`](https://github.com/ods-26-2/a1/tree/a4ea77a191eddc7726007fcdb1699cb612797c19/shared/artifacts/defect-taxonomy/defects-a1-1.0.0). A árvore local precisa corresponder byte a byte ao conteúdo, descritor e publicação desse commit. O catálogo A1 existente valida schema, proprietário, versão, classes e hash.
2. **Descritor e publicação:** `published.json.payload` precisa ser exatamente igual a `descriptor.json`, incluindo URI, proprietário, versão, validade e hash. A URI `registry://b5/...` é metadado; nenhum registro B5 foi consultado ou publicado nesta tarefa. Hash do arquivo descritor é separado do hash do conteúdo descrito.
3. **I8 consumidor explícito:** em [`55a808b1351fdd94ea039148b49fba1f478603e1`](https://github.com/ods-26-2/i8/tree/55a808b1351fdd94ea039148b49fba1f478603e1), [inferência, linhas 7–12](https://github.com/ods-26-2/i8/blob/55a808b1351fdd94ea039148b49fba1f478603e1/scripts/infer_image.py#L7-L12) e [publisher, linhas 15–20](https://github.com/ods-26-2/i8/blob/55a808b1351fdd94ea039148b49fba1f478603e1/scripts/publish_events.py#L15-L20) exigem conteúdo, descritor e versão por argumentos. O [roteiro I8](https://github.com/ods-26-2/i8/blob/55a808b1351fdd94ea039148b49fba1f478603e1/docs/evidencias/etapas-11-15/README.md) aponta esses argumentos para o pacote A1 em `../a1/shared/artifacts/...`. A inspeção `git ls-tree -r --name-only origin/main shared/artifacts` não encontrou cópia nesse diretório I8; não existe sincronização automática demonstrada.
4. **Loader real verificado:** [I8, linhas 51–80](https://github.com/ods-26-2/i8/blob/55a808b1351fdd94ea039148b49fba1f478603e1/src/taxonomy/__init__.py#L51-L80) lê os arquivos explícitos, verifica proprietário A1/tipo/versão e SHA-256 dos bytes originais. O verificador extrai somente `src.contracts` e `src.taxonomy` dos blobs Git fixados, confere seus hashes e executa esses dois módulos em subprocesso Python isolado (`-I`), fornecendo os arquivos A1 exatos. Não usa código do checkout I8, que pode estar em outra branch. Compara o resultado completo com o catálogo A1 e relê o pacote para detectar alteração durante a verificação.
5. **Metadados históricos compatíveis, proveniência limitada:** classificador e política em `models/` I8 apontam `taxonomy_version=defects-a1-1.0.0`. Classes AMASSADO, FURADO e FURADO_AMASSADO existem no pacote. Versões de classificador/produto da política também correspondem. Esses artefatos históricos não guardam hash/descritor da taxonomia de treino; coincidência de versão não comprova retrospectivamente igualdade dos bytes. Os [bloqueios de dados I8](https://github.com/ods-26-2/i8/blob/55a808b1351fdd94ea039148b49fba1f478603e1/docs/evidencias/etapas-11-15/README.md) continuam válidos.

## Identidade observada

| Campo | Valor verificado |
|---|---|
| artifact_id | `defect-taxonomy-a1` |
| artifact_version | `defects-a1-1.0.0` |
| owner / kind | `A1` / `DEFECT_TAXONOMY` |
| schema_version | `1.0` |
| valid_from | `2026-10-20T12:00:00.000Z` |
| URI declarada | `registry://b5/a1/defect-taxonomy/defects-a1-1.0.0` |
| SHA-256 do conteúdo original | `324476cf7bbef29de8583807c1eb7b4a3709ef269c2db317a670501da4f7440a` |
| SHA-256 dos bytes de descriptor.json | `e7cf99210f56789c7b0ceb7096dbeaf5e6e1e3f1ae551ff94c45994c67c0ea95` |
| SHA-256 de published.json | `f464869dd2c183eaa0f78f7aab8f4f3d6a5d704d4093dee3ba0d532e1b0c9981` |

Hashes de loader, contratos, CLIs, classificador e política I8 também ficam no manifesto. Eles identificam os arquivos auditados; não substituem assinatura/autenticidade, revisão do manifesto ou homologação industrial.

## Reproduzir e usar como verificação

Na raiz A1, com dependências de contratos instaladas e repositório I8 local contendo os objetos fixados:

```powershell
python scripts/verify_final_taxonomy.py --i8-repo ..\i8
```

O verificador apenas lê arquivos/objetos locais; não faz fetch. Exige que `I8 origin/main` ainda seja o commit fixado no manifesto. Se a referência avançar, falha para solicitar revisão do manifesto; não altera nem baixa a referência. Para revalidar uma entrega nova, revisar primeiro conteúdo/descritor/artefatos dos novos commits e seus limites de proveniência, atualizar manifesto conscientemente e repetir a prova. O código executado do I8 é restrito aos dois módulos identificados e verificados; alterar o manifesto significa alterar a base de confiança, não criar uma assinatura.

Saída aprovada observada nesta atividade: versão/hash da tabela, classes AMASSADO/FURADO/FURADO_AMASSADO, `i8_loader_executed=true`, `torch_imported=false`, `deployment_verified=false` e `historical_training_hash_proven=false`. Arquivo ausente, objeto Git indisponível, `origin/main` divergente, byte modificado, hash/descritor/publicação incompatível, metadado I8 divergente, JSON ambíguo ou erro/timeout do loader retorna **1** e `FALHOU_TAXONOMIA`, sem resultado de sucesso. A checagem é uma ferramenta explícita de revisão, não modifica ingestão ou configuração de runtime.

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q -p no:cacheprovider tests/test_final_taxonomy.py
python scripts/validate_contracts.py
git diff --check
```

Resultado local inicial: **28 testes aprovados**, incluindo execução isolada do loader I8 real e casos negativos de bytes/versão/descritor/publicação/classes/modelo, JSON duplicado/NaN, travessia de caminhos, referência alterada e falha da CLI. Os testes unitários usam metadados sintéticos explícitos; não constituem treino. Em CI sem checkout I8, somente o teste integrado é ignorado com motivo explícito; para aceite integrado é obrigatório fornecer o I8 fixado e executar também a CLI.

## Limites e próxima implantação

O critério de identidade foi verificado localmente por referência compartilhada: os loaders concordam quando consomem o pacote A1 fixado. Não há cópia da taxonomia I8 inventada, sincronização, migração automática, treino, inferência industrial, publicação Kafka/B5 ou implantação neste incremento. Antes de afirmar uso efetivo em um processo implantado, registrar seus argumentos/caminhos e verificar os mesmos bytes naquele ambiente. Para provar proveniência futura de treino, o responsável I8 deve preservar hash do conteúdo, descritor e manifesto do experimento; esta tarefa não reescreve a história dos modelos existentes.
