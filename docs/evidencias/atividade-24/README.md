# Evidências — Sprint 3, atividade 24

Teste local em Docker, em 05/11/2026 (America/Sao_Paulo), com PostgreSQL 17 real e simulador P7. Base A1 `186ac6284798a556f0b5e3e86c569617ac4bb153`.

- Suíte P7: **42 aprovados**, zero falhas e zero testes ignorados. Relatório: `p7.xml`.
- Regressão Python: **204 aprovados**, zero falhas e zero testes ignorados. Inclui os mesmos 42 P7: não somar. Relatório: `regressao.xml`.
- Frontend: **14 aprovados**. Saída: `regressao-saida.txt` (trecho capturado após início da suíte).
- Contratos I8/A1 existentes: validador aprovado para quatro resultados.
- Aviso existente: depreciação Starlette/httpx; não impediu os testes.

Cobertura P7: persistência e auditoria atômicas, IDs e contexto, reenvio após entrega incerta, recriação do adaptador sobre o mesmo banco, duplicatas, estado antes de reply, aceite separado da conclusão, limite inclusivo, entradas inválidas, quatro códigos de erro, falha durante movimento, fonte/posição divergentes, timeout e falha de persistência impedindo envio.

A primeira rodada teve uma falha no teste: `%` literal de `LIKE` precisava ser escapado para psycopg. A consulta foi corrigida e a suíte completa passou. Não era falha no fluxo P7.

Este laboratório não inicia Kafka e não usa o broker Google Cloud. O simulador conserva a deduplicação apenas durante sua instância. Não comprova firmware, transporte real, movimento físico, reinício do dispositivo ou integração completa VER-1.

[Roteiro para reproduzir e pendências da atividade 25](../../sprints/atividade-24-resumo.md).
