# A1 — Aplicação de Inspeção

Aplicação responsável por transformar os resultados de inferência do I8 em
decisões de triagem, revisão humana, histórico, auditoria e visualização para o
operador.

## Conteúdo deste repositório

- `frontend/`: interface web da inspeção;
- `backend/`: API v1, persistência PostgreSQL, ingestão 6c e auditoria do A1;
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

## Executar com Docker

Requer Docker com Compose. Na raiz deste repositório:

```powershell
docker compose up --build
```

O frontend fica em <http://localhost:5500/frontend/>, servido por nginx com
`frontend/` e `shared/`, e usa a API real em `/api/v1` (o nginx repassa `/api/`
ao backend). `?api=fake` volta para a API fake. Depois de editar arquivos, rode
o comando de novo: a imagem copia os arquivos no build.

O mesmo comando sobe o backend (`backend`, porta 8000 só em `127.0.0.1`), o
PostgreSQL 17 (serviço `db`, banco e usuário `a1`).O consumo de eventos é feito
diretamente via Kafka (configurado pela variável `KAFKA_BROKER_URL`).
O banco não publica porta no host. A senha local padrão é `a1-local`; no servidor, 
defina `POSTGRES_PASSWORD` no arquivo `.env`, que não é versionado. A porta do frontend muda com `A1_PORT`.

Para simular o I8 a enviar inspeções via Kafka, use o produtor fake:

```powershell
docker compose exec backend python -m backend.fake_producer --fresh
```

Para validar os contratos 6c e rodar `pytest` (com os testes de banco) e
`npm test` no container:

```powershell
docker compose run --rm tests
```

### Servidor (GCP)

O A1 roda numa VM do Compute Engine com HTTPS. O serviço `caddy` (profile
`https`) emite o certificado Let's Encrypt para `A1_DOMAIN` e repassa para o
frontend. Sem domínio próprio, usa-se `<ip-com-hifens>.sslip.io`.

`docker/gcp-startup.sh` é o startup-script da VM: a cada boot instala Docker,
atualiza o código em `/opt/a1`, completa o `.env` (`POSTGRES_PASSWORD`,
`A1_DOMAIN`, `A1_PORT` e `COMPOSE_PROFILES=https`) e sobe o compose. O
`KAFKA_BROKER_URL` deve ser configurado no mesmo arquivo. Para publicar
uma nova versão depois do push, reinicie a VM ou rode o script de novo nela.

Endereços do frontend, API, banco, Kafka e comandos de verificação estão em
[`docs/hospedagem.md`](docs/hospedagem.md). O endereço público exato não é
versionado; ele deve ser consultado em `A1_DOMAIN` no `/opt/a1/.env` da VM.

O `Dockerfile` tem os alvos `frontend` (padrão), `backend` e `tests`.

O `.gitattributes` impede a conversão de fim de linha em `shared/artifacts/`,
porque o descritor guarda o SHA-256 dos bytes de `content.json`. Em um clone
antigo no Windows com `core.autocrlf=true`, restaure esses arquivos uma vez:

```powershell
git rm --cached -r -q shared/artifacts
git checkout HEAD -- shared/artifacts
```

## Estado atual

O frontend consome a API A1 real (`docs/contratos/a1-api.md`) servida pelo
backend de S3-07, com persistência em PostgreSQL. A ingestão escuta ativamente o
barramento Kafka no tópico `ods.industria.defeito_classificado` para receber as
inspeções do I8 em tempo real. A evidência S4 fica pendente até S3-09.

## Sprint 3 — contratos 6c e taxonomia

S3-01 e S3-02 estão implementados como uma fronteira contratual independente da
API futura: contrato Kafka final `ods.industria.defeito_classificado` 2.0,
leitura temporária do legado `ods.i8.piece_analysis` 1.0, quatro resultados
válidos, exemplos inválidos e catálogo versionado
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

## Sprint 3 — S3-07, backend, banco e auditoria

- API v1 em `backend/app.py`, com rota nova de histórico
  (`/inspections/{id}/history`);
- PostgreSQL com resultado automático imutável, revisões e eventos de auditoria
  só de inserção (o banco recusa `UPDATE`/`DELETE`/`TRUNCATE`);
- deduplicação por `message_id` e recusa de contexto repetido por outra
  mensagem;
- pedido de snapshot S4 registrado como comando pendente;
- produtor fake 6c em `backend/fake_producer.py`.

Verificação (`tests/test_backend.py`, contra PostgreSQL real):

```powershell
docker compose run --rm tests
```

Evidências: `docs/evidencias/s3-07/README.md`.
