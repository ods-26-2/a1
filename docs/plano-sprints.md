# Plano de Desenvolvimento

# Sprint 1 — Base e Contratos

## Samuel

### Taxonomia de defeitos

Entregável:
- defect-categories.json

Critério de conclusão:
- categorias definidas;
- descrição;
- severidade;
- consequência;
- arquivo versionado.

### Contrato I8 → A1

Responsáveis:
Samuel / Ícaro

Entregável:
- schema do evento;
- payloads de exemplo;
- mocks.

### Front v1

Entregável:
- tela de inspeção;
- dados mockados;
- estados Aprova/Reprova/Dúvida.

## João

### Modelagem do normal

Entregável:
- modelo inicial de representação da peça correta.

---

# Sprint 2 — Integração Funcional

## João

- Classificação de tipos
- Integração I11/P2

## Ícaro

- Similaridade
- Motor de triagem
- Integração P7

## Samuel

- Persistência
- Auditoria
- Front v2 integrado ao A1
- Revisão humana

## Critério de conclusão

Deve existir pelo menos:

I8/mock
↓
evento
↓
A1
↓
triagem
↓
persistência
↓
frontend

---

# Sprint 3 — Relatórios e Calibração

## Samuel

- Relatório de causa
- Relatório de inspeção

## João / Ícaro

- Ajuste dos limiares
- Calibração do modelo

## Equipe

- testes integrados;
- latência;
- regressões;
- validação ponta a ponta.
