# A1 — Aplicação de Inspeção

Aplicação responsável por transformar os resultados de inferência do I8 em
decisões de triagem, revisão humana, histórico, auditoria e visualização para o
operador.

## Conteúdo deste repositório

- `frontend/`: interface web da inspeção;
- `backend/`: local reservado para a API, persistência e serviços do A1;
- `shared/artifacts/defect-taxonomy/`: taxonomia versionada `DEFECT_TAXONOMY`;
- `shared/policies/triage/`: política de consequência do A1;
- `shared/schemas/6c/`: contratos 6c recebidos do I8;
- `shared/schemas/a1-api/`: contrato da API A1 consumida pelo frontend;
- `shared/mocks/`: eventos 6c e fixtures da API fake;
- `shared/legacy/ver1/`: contratos e mocks da Sprint 1, sem uso;
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

Sem parâmetros, a tela usa a API A1 fake e mostra o painel de cenários. Para a
API real, use `?api=http://localhost:8000/api/v1` ou preencha
`<meta name="a1-api-base">` em `frontend/index.html`.

## Estado atual

O frontend consome a camada de dados da API A1 (`docs/contratos/a1-api.md`),
com API fake até a entrega do backend (S3-07). A implementação da API e da
persistência ainda pertence às próximas entregas.

## Sprint 3 — contratos 6c e taxonomia

S3-01 e S3-02 estão implementados como uma fronteira contratual independente da
API futura: schemas de publicação/consumo de `ods.i8.piece_analysis`, quatro
resultados válidos, exemplos inválidos, catálogo versionado
`DEFECT_TAXONOMY`, descritor com hash e anúncio local. A consequência de negócio
permanece em uma política A1 separada do artefato consumido pelo I8.

Os arquivos de demonstração `ods.ver1.*` foram movidos para
`shared/legacy/ver1/` em S3-03. Consulte `docs/contratos/migracao-6c.md` e valide
o pacote com:

```powershell
python -m pip install -r requirements-contracts.txt
python scripts/validate_contracts.py
python -m pytest -q
```

## Sprint 3 — S3-03, base do frontend

O import ausente foi recuperado e a tela foi migrada para a API A1:

- `frontend/js/data/`: adaptadores fake e HTTP com a mesma interface e a
  mesma guarda de contrato;
- `frontend/js/ui/`: estados de carregamento, erro, vazio, conectividade real
  (`GET /health`) e evidência S4 com placeholder explícito;
- quatro `result` 6c e três decisões A1 nas fixtures
  `shared/mocks/a1-api/inspections/`, com falhas simuladas.

Verificação:

```powershell
npm test
python -m pytest -q
node scripts/capture_front_evidence.mjs
```

Evidências e roteiro de gravação: `docs/evidencias/s3-03/README.md`.
