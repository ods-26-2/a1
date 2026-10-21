# Migração 6c — S3-01 e S3-02

Este pacote implementa localmente os contratos e o artefato pedidos em S3-01 e
S3-02. Ele não publica no broker nem no registro externo B5; essas integrações
dependem dos acordos com B1/B5.

## I8 para A1

O evento canônico é `ods.i8.piece_analysis`, perfil EV-SINAL. I8 publica por
peça e A1 consome. O payload contém `frame_index`, `detection_id`, `bbox`,
`result`, `taxonomy_version`, `confidence`, `similarity` e, somente em
`NON_CONFORMING`, `defect_class`.

O schema de publicação é estrito para `1.0`. O schema de consumo aceita campos
aditivos de versões `1.x`, mas rejeita campos legados como `piece_id`,
`classification` e `evidence`. O I8 não inclui mídia, consequência de negócio,
nome, descrição ou severidade. O A1 solicita evidência a S4 em outro fluxo.

Os arquivos antigos `ods.ver1.*`, a taxonomia `shared/defect-categories.json` e
os mocks usados pelo frontend permanecem apenas para a demonstração anterior.
Removê-los ou adaptar a tela faz parte de S3-03, não desta migração.

## DEFECT_TAXONOMY

A fonte versionada está em
`shared/artifacts/defect-taxonomy/defects-a1-1.0.0/`. `content.json` contém
somente classes e seus rótulos. Consequências de triagem ficam separadas em
`shared/policies/triage/defects-a1-1.0.0.json`.

O descritor guarda os oito campos 6c e o SHA-256 dos bytes exatos do conteúdo.
`published.json` representa o anúncio `ods.artifact.published`. Uma nova versão
deve ocupar outra pasta; versões existentes são imutáveis para permitir que uma
inspeção histórica resolva o rótulo da versão registrada.

## Limites de integração

- S4 ainda não define `bbox` em `ods.s4.capture.command`; nenhum campo foi
  acrescentado localmente.
- As entradas fechadas de S5 ainda não definem como I8/A1 alimentam métricas de
  inspeção; nenhuma aresta informal foi criada.
- P7 controla pan-tilt, não ejetor ou separador de peças.
- A referência `S2-01` em S3-02 foi tratada como resíduo da renumeração e aponta
  para a migração correspondente S3-01.
- O documento de 16/10 planeja desenvolvimento na Sprint 3, apesar de a revisão
  de 14/10 reservar a Sprint 3 à estabilização. Para os IDs solicitados, foi
  seguida a numeração posterior.

## Verificação

```powershell
python -m pip install -r requirements-contracts.txt
python scripts/validate_contracts.py
python -m pytest -q
```
