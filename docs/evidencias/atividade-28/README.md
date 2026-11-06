# Atividade 28 — composição local concluída

Resultado: **APROVADA_COMPOSICAO_LOCAL**. O critério da página 5 do plano é
“A1, I8, Kafka e PostgreSQL configurados por ambiente”. A PR A1
[#16](https://github.com/ods-26-2/a1/pull/16) foi mesclada em
`ace5585f7db0e5e7463d35444f96ab336970e421`; o workflow da composição passou
na execução
[#42176495483](https://github.com/ods-26-2/a1/actions/runs/42176495483). O
[manifesto de aceite](manifesto.json) fixa critério, componentes, commits,
configuração e limites.

Em 06/11/2026, a composição foi executada em Docker com Kafka 3.9.1,
PostgreSQL 17, frontend nginx, backend A1 e publisher I8 real.

`resultado-local.json` registra a prova: quatro eventos sintéticos, reenvio
dos mesmos quatro, oito offsets confirmados e quatro inspeções persistidas.
O reinício do backend preservou o resultado. A prova foi repetida após
integrar a main a0c7a1d (atividades 20 e 21), incluindo consultas do histórico
e filtro por cada resultado, através do proxy nginx. HTML, JavaScript e leitura da
API pelo proxy do frontend foram conferidos. O modo testar encerrou os
containers e removeu o volume com `compose down -v`.
O modo `demonstrar` também passou e manteve os serviços após o sucesso;
o encerramento explícito é executado com o comando `parar`.

A execução local usou o checkout A1 baseado no commit registrado, com as
alterações desta entrega presentes. Não corresponde a um teste da main
sem alterações. A execução do GitHub Actions identifica o commit do PR
e disponibiliza relatório completo, recibos, logs e versões em artefato.

Reprodução e limites: [guia curto](../../../composicao-ver1/README.md).
Não comprova inferência real, integração S4/S5/P7, ambiente final ou
fechamento coletivo das atividades 29/30. A regressão da atividade 29 deve
repetir a prova sobre a `main` consolidada, porque a evidência inicial precede
as atividades 22–27.
