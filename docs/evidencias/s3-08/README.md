# S3-08 — política, fila e revisão

## Cenário reproduzível

1. Com o backend e PostgreSQL da composição existentes, publique os quatro eventos
   do produtor fake 6c. A política ativa sem calibração mantém todos em REVIEW.
2. Abra o front com API real. A fila lista as inspeções e permite abrir qualquer
   pendência sem substituir a inspeção escolhida pelo polling da inspeção atual.
3. Preencha operador e motivo. Corrija a decisão para REJECTED com classe FURADO.
   A confirmação deve mostrar gravação, classe final e nova leitura da API.
4. Atualize a tela: a inspeção saiu da fila, a análise I8 e a triagem original
   continuam iguais, e o histórico mostra motivo, ator e classe corrigida.
5. Envie a inspeção para revisão: ela retorna à fila. Confirmar REVIEW mantém a
   pendência. Aprovar exige classe nula; reprovar exige classe da taxonomia da peça.
6. Reinicie o backend: decisões, fila e histórico continuam no banco.

O mesmo fluxo pode ser ensaiado com a API fake, identificada como não persistente.
As fixtures fake históricas cobrem os quatro result e os três estados originais.

## Verificações

- `tests/test_triage.py`: quatro result, versão/classe inválidas, política sem
  calibração e fronteiras de limiar configurado exclusivamente para testes.
- `tests/test_review_service.py`: correção/confirmar/reabrir, motivo obrigatório,
  classe válida, original preservado e contrato da visão final, sem transporte.
- `tests/test_backend.py`: fila, API, consulta após correção, auditoria imutável,
  contexto único S3-07 e reinício sobre PostgreSQL real.
- `frontend/tests/dataLayer.test.js`: motivo, classe, fila, nova leitura e histórico
  no fake, com o mesmo adaptador HTTP disponível para a API real.

Os testes de banco requerem `A1_TEST_DATABASE_URL`. Os testes de negócio isolam
o MQTT já existente; este incremento não implementa ou valida Kafka, S4, S5 ou P7.

Não há limiar industrial inventado: `minimum_confidence=null` exige revisão até
a calibração ser aceita e publicada em uma nova versão de política.

## Evidências locais em 04/11/2026

- Python: 62 aprovados; 29 casos de PostgreSQL ignorados por ausência de
  `A1_TEST_DATABASE_URL`. Esta execução não prova migração/reinício em banco real.
- Frontend: 13 testes aprovados; contratos 6c validados.
- Chrome headless: 9 verificações do fluxo fake aprovadas, sem exceções de
  JavaScript ou overflow em 390px. Capturas `01-fila-desktop.png`,
  `02-correcao-desktop.png`, `03-revisao-mobile.png` e resumo `browser-check.json`.
- Reprodução visual: `node scripts/capture_review_evidence.mjs` (Chrome instalado).
