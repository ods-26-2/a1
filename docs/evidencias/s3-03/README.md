# Evidências S3-03 — Recuperar e integrar base do front

## Critérios e onde verificar

| Critério | Evidência |
|---|---|
| Navegador sem erro de import | Console sem erros; `frontend/js/data/inspectionDataSource.js` presente e usado por `app.js` |
| Três estados atuais | `01-resultado-*.png`: APROVADA, REPROVADA, REVISÃO NECESSÁRIA |
| Quatro `result` representados | `01-resultado-conforming/non-conforming/anomaly/uncertain.png` |
| Carregamento, erro, evidência, online | `02-*.png` e indicador do cabeçalho |
| API real substitui fake sem mudar regras | `docs/contratos/a1-api.md`; teste "usa as mesmas rotas e a mesma guarda" em `frontend/tests/dataLayer.test.js` |
| Revisão preserva decisão automática | `04-revisao-operador.png` (API fake, sem persistência) |
| Responsividade 390 / 1366 / 1920 | `03-mobile-390-*.png`, `01-*.png` (1366), `03-desktop-1920-*.png` |

## Reproduzir

```powershell
python -m http.server 5500
npm test
python -m pytest -q
node scripts/capture_front_evidence.mjs
```

O último comando regenera as capturas desta pasta com Chrome headless.

## Roteiro da gravação

Gravar a tela em 1366×768 com `http://localhost:5500/frontend/`:

1. Mostrar o console sem erro de import e o selo "API FAKE".
2. Clicar em Conforme, Não conforme, Anomalia e Incerto. Mostrar resultado I8,
   decisão, motivo, versões e estado da evidência.
3. Em Não conforme, informar operador e clicar "Enviar para revisão". Mostrar
   que a decisão automática REJECTED continua no motivo e que nada foi
   persistido.
4. Falhas: API lenta (carregamento), API offline (erro + cabeçalho offline),
   S4 indisponível (placeholder + integração degradada), Contrato inválido
   (resposta recusada pela guarda).
5. Reduzir a janela para largura de celular.

## Limites declarados

- API fake: não há backend, banco nem persistência. Backend real é S3-07;
  revisão auditável é S3-08.
- Mídia "S4" é imagem de demonstração; não há integração S4 (S3-09).
- B6: nenhum pacote de interface do MOD-2 foi publicado até esta entrega. Os
  componentes de estado ficaram isolados em `frontend/js/ui/`
  (conectividade, evidência, estados de tela) para troca pelo pacote B6
  quando existir. Pendência externa, não apresentada como concluída.
- Confiança e similaridade das fixtures são exemplos, não medições do modelo.
