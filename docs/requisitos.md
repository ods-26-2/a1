# Requisitos do Sistema

# 1. Requisitos Funcionais

## I8 — Inferência

### RF02 — Identificar peça na imagem

O sistema deve identificar a peça presente na imagem recebida.

### RF03 — Analisar conformidade

O sistema deve analisar se a peça está conforme o padrão esperado.

### RF04 — Classificar defeitos conhecidos

O sistema deve identificar defeitos pertencentes à taxonomia conhecida.

### RF05 — Detectar anomalias desconhecidas

O sistema deve ser capaz de identificar diferenças em relação ao padrão
normal mesmo quando não existir uma categoria conhecida.

### RF06 — Calcular similaridade

O sistema deve calcular a similaridade entre a peça analisada
e as referências disponíveis.

### RF07 — Informar confiança

O sistema deve informar o nível de confiança da análise.

---

## A1 — Aplicação

### RF08 — Manter taxonomia de defeitos

Módulo: TaxonomyService

### RF09 — Registrar descrição do defeito

Módulo: TaxonomyService

### RF10 — Registrar severidade

Módulo: TaxonomyService

### RF11 — Associar consequência

Módulo: TaxonomyService

### RF12 — Executar regra de triagem

Módulo: TriageService

### RF13 — Encaminhar casos duvidosos para revisão

Módulo: TriageService / Front

### RF14 — Permitir confirmação humana

Módulo: ReviewController / Front

### RF15 — Registrar resultado da triagem

Módulo: InspectionRepository

### RF16 — Armazenar histórico de inspeções

Módulo: InspectionRepository

### RF17 — Calcular taxa de defeitos

Módulo: ReportService

### RF18 — Identificar defeitos recorrentes

Módulo: ReportService

### RF19 — Associar causa provável

Módulo: ReportService

### RF20 — Gerar relatório de causa

Módulo: ReportService

### RF21 — Gerar relatório de inspeção

Módulo: ReportService

---

# 2. Requisitos Não Funcionais

## RNF01 — Usabilidade

A interface deve ser simples para utilização durante a inspeção.

## RNF02 — Ambiente industrial

A aplicação deve ser adequada à utilização em chão de fábrica.

## RNF03 — Elementos de interação grandes

Botões e controles importantes devem ser grandes e facilmente acionáveis.

## RNF04 — Priorização visual

Aprova, Reprova, Dúvida, defeito e confiança devem possuir destaque.

## RNF05 — Responsividade

A interface deve adaptar-se às resoluções utilizadas no posto.

## RNF06 — Consistência visual

O frontend deve seguir os componentes definidos pelo B6.

## RNF07 — Tempo de processamento

O pipeline deverá respeitar o SLA máximo de 200 ms.

## RNF08 — Explicabilidade

A aplicação deve apresentar informações suficientes para compreender
a decisão do sistema.

## RNF09 — Persistência

Inspeções e decisões devem ser armazenadas.

## RNF10 — Manutenibilidade

A1 deve utilizar separação entre Rotas, Controle,
Serviço e Repositório.
