# Arquitetura do Sistema

## 1. Visão Geral

O sistema possui dois componentes principais:

I8 — Componente de Inferência
A1 — Componente de Aplicação de Inspeção

---

# 2. I8 — Componente de Inferência

## Responsabilidade

Analisar o recorte de uma peça e produzir um resultado estruturado
de inferência.

O I8 não executa diretamente a decisão física da triagem.

## Módulos internos

### Pré-processamento

Recebe e valida o recorte vindo do I11.

### Extração de características

Utiliza modelos como ResNet ou CLIP para gerar vetores de características.

### Classificação

Identifica defeitos conhecidos ou anomalias.

### Similaridade

Calcula a distância da peça analisada em relação às referências.

Pode utilizar:
- Distância Cosseno
- Distância Euclidiana

### Publicação

Cria o evento que será enviado ao A1.

---

# 3. A1 — Aplicação de Inspeção

## Responsabilidade

Transformar os resultados produzidos pelo I8 em:

- decisão de negócio;
- triagem;
- registro auditável;
- interface para o operador;
- comando para atuação física.

## Arquitetura interna

Rotas / Adaptadores
        ↓
Controladores
        ↓
Serviços
        ↓
Repositórios

## Módulos

### TaxonomyService

Responsável pela taxonomia de defeitos.

### TriageService

Responsável pelas decisões:

APROVA
REPROVA
DÚVIDA

### ReportService

Responsável por histórico e relatórios.

### InspectionRepository

Responsável por persistir as inspeções.

### ReviewController

Responsável pela revisão humana.

### Frontend

Responsável pela interação com o operador.

---

# 4. Dependências externas

I11 → fornece recorte da peça

B1 → contratos de eventos

B5 → imagens e artefatos

B6 → kit de interface

P2 → runtime GPU

P7 → atuação física

S4 → evidências/imagens

S5 → histórico e métricas
