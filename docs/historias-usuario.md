# Histórias de Usuário

## HU01 — Resultado da inspeção

Como operador,
quero visualizar o resultado da inspeção atual,
para saber rapidamente se está conforme ou precisa de revisão.

Relacionado:
- Front de inspeção

---

## HU02 — Defeito identificado

Como operador,
quero saber qual defeito foi identificado na peça,
para compreender o motivo da reprovação.

Relacionado:
- Front
- Taxonomia

---

## HU03 — Confiança

Como operador,
quero visualizar o nível de confiança da classificação,
para identificar situações que necessitam de revisão humana.

Relacionado:
- Front

---

## HU04 — Revisão humana

Como operador,
quero encaminhar uma peça com resultado duvidoso para revisão humana,
para evitar decisões automáticas incorretas.

Relacionado:
- TriageService
- Front

---

## HU05 — Corrigir classificação

Como responsável pela inspeção,
quero confirmar ou corrigir uma classificação automática,
para garantir que a decisão final represente corretamente
a condição do produto.

Relacionado:
- ReviewController
- Front

---

## HU06 — Histórico

Como operador,
quero consultar inspeções anteriores,
para acompanhar falhas e decisões tomadas ao longo do tempo.

---

## HU07 — Filtrar histórico

Como responsável pela qualidade,
quero filtrar inspeções por período, resultado e tipo de defeito,
para localizar ocorrências relevantes.

---

## HU08 — Detalhes da peça

Como responsável pela qualidade,
quero visualizar os detalhes de um produto defeituoso,
para analisar a ocorrência e sua evidência visual.

---

## HU09 — Taxonomia

Como responsável técnico,
quero manter uma taxonomia padronizada de defeitos,
para garantir consistência na classificação das peças.

---

## HU10 — Anomalias desconhecidas

Como responsável pela qualidade,
quero que o sistema detecte produtos diferentes da referência
mesmo quando o defeito não for conhecido,
para evitar a aprovação incorreta de novas anomalias.

Componente:
- I8
