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
