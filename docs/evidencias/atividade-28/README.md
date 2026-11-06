# Atividade 28 — evidência da composição local

Em 06/11/2026, a composição foi executada em Docker com Kafka 3.9.1,
PostgreSQL 17, frontend nginx, backend A1 e publisher I8 real.

`resultado-local.json` registra a prova: quatro eventos sintéticos, reenvio
dos mesmos quatro, oito offsets confirmados e quatro inspeções persistidas.
O reinício do backend preservou o resultado. HTML, JavaScript e leitura da
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
fechamento coletivo das atividades 28/29/30.
