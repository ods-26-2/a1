# Evidências — atividades 23 e 24

Base A1: `a196766a0b9839da3ae9d1e14e4280b5393a161b`. Contratos/implementação S5 consultados: `77483834790e7d0d34b5b296f810fa698bdacddb`. Data: 06/11/2026.

## Resultado local em Docker

- Seleção focada: **70 aprovados**, sendo **28 S5 novos e 42 P7 existentes**. Relatório `focados.xml`.
- Regressão completa: **310 Python e 14 frontend aprovados**, zero falhas e zero ignorados. Relatório Python `regressao.xml`.
- Os 70 estão incluídos nos 310; não somar como testes distintos.
- Validador de contratos I8/A1 aprovado para os quatro resultados existentes.
- PostgreSQL 17 real em container isolado; S5/P7 simulados explicitamente. Sem Kafka, portas publicadas, dados industriais, VM ou hardware.
- Aviso de depreciação Starlette/httpx sem falha.

S5: consulta/resposta persistidas sem exigir inspeção; resposta vazia como sucesso; três erros previstos; ID/conteúdo preservados no reenvio após recriar adaptador; filtros e período; ordem/granularidade/tipo da série; contagem incerta; respostas desconhecidas/tardias; timeout; evento duplicado/divergente; versão/produtor/JSON/identidade inválidos; falha de banco impedindo envio.

P7: regressão dos casos já entregues no PR A1 #10: correlação, aceite separado da conclusão, deduplicação/reenvio, ordem das respostas, limites e erros, timeout, falhas de persistência e ciclo do adaptador. Não foi necessário alterar o código P7 para satisfazer a atividade 24.

## Critério de fechamento e limites

A atividade 23 prepara A1 para consultar e receber métricas EVENT por contrato, com transporte injetado. Não há worker Kafka, rota HTTP, tela ou ligação automática nesta entrega. Essa composição será explícita em uma etapa posterior. O adaptador não calcula defeitos, não converte I8 em S2, não fabrica métricas S5 e não mistura contagens de janelas.

A atividade 24 já foi integrada na main e foi revalidada. A atividade 25 continua separada e depende da bancada/contrato físico. Os testes não comprovam disponibilidade dos serviços reais, deduplicação física, alimentação industrial S5 ou fluxo VER-1 completo.

[Funções, exemplo, critérios e comandos Docker](../../sprints/atividades-23-24-fechamento.md). O workflow `testes-s5-p7.yml` repete as provas e conserva XML/log por 30 dias.
