# A1 — Aplicação de Inspeção

Aplicação responsável por transformar os resultados de inferência do I8 em
decisões de triagem, revisão humana, histórico, auditoria e visualização para o
operador.

## Conteúdo deste repositório

- `frontend/`: interface web da inspeção;
- `backend/`: local reservado para a API, persistência e serviços do A1;
- `shared/defect-categories.json`: fonte de verdade da taxonomia de defeitos;
- `shared/schemas/`: contratos JSON recebidos do I8 e publicados pelo A1;
- `shared/mocks/`: cenários usados pelo frontend na demonstração;
- `docs/`: requisitos, arquitetura, histórias e contratos de integração.

O código Python de inferência não pertence a este repositório; ele está no
repositório I8.

## Executar o frontend

Na raiz deste repositório, execute:

```powershell
python -m http.server 5500
```

Depois acesse <http://localhost:5500/frontend/>. O frontend deve ser servido por
HTTP porque carrega os JSON de `shared/` com `fetch`.

## Estado atual

O frontend e os dados de demonstração da Sprint 1 estão presentes. O diretório
`backend/` documenta os módulos planejados, mas a implementação da API e da
persistência ainda pertence às próximas entregas.

## Sprint 3 — contratos 6c e taxonomia

S3-01 e S3-02 estão implementados como uma fronteira contratual independente da
API futura: schemas de publicação/consumo de `ods.i8.piece_analysis`, quatro
resultados válidos, exemplos inválidos, catálogo versionado
`DEFECT_TAXONOMY`, descritor com hash e anúncio local. A consequência de negócio
permanece em uma política A1 separada do artefato consumido pelo I8.

Os arquivos de demonstração `ods.ver1.*` foram preservados para não antecipar a
migração do frontend de S3-03. Consulte `docs/contratos/migracao-6c.md` e valide
o pacote com:

```powershell
python -m pip install -r requirements-contracts.txt
python scripts/validate_contracts.py
python -m pytest -q
```
