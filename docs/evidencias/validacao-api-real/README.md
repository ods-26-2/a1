# Sprint 3 — parcela de Ícaro na validação integrada

Resultado em 06/11/2026: **APROVADA_API_REAL_LOCAL**. Foi executado o roteiro
de navegador sobre frontend, API A1, PostgreSQL e Kafka reais em Docker local.
O publisher I8 enviou quatro eventos sintéticos, explicitamente identificados
por `synthetic-transport-proof`. Não houve inferência de imagens.

Base A1: `5d17305048f21914ed46d4fbe0770c81180215eb`.
I8 fixado: `55a808b1351fdd94ea039148b49fba1f478603e1`.
O ensaio usou essa main antes das adições documentais/deste observador; não
houve alteração de código de produto para obter o resultado.

## O que esta prova quita

- Histórico com período, resultado I8, origem e defeito original combinados.
- Correção da inspeção NON_CONFORMING para REJECTED/FURADO, preservando a
  análise original AMASSADO e a triagem original REVIEW.
- Registro explícito de hipótese de causa e auditoria no backend.
- Relatório individual real e recorrência baseada na análise original.
- Exportação JSON/CSV pela interface: ambos representam o mesmo relatório
  carregado, conferido por reimportação e comparação de todas as seções.
- Revisão e causa preservadas após recarregar a página e reiniciar o backend.
- Reabertura em REVIEW devolvendo a inspeção à fila; duas revisões e uma causa
  no banco, com auditoria correspondente e sem outra inspeção criada.
- Navegação por Enter com foco no título e relatório em 390 px sem overflow
  horizontal. Não é ensaio completo de usabilidade com operadores.
- Console do navegador sem erros ou warnings na consulta final.

São dez verificações do roteiro, executadas por automação assistida de
navegador, e uma conferência somente de leitura da API/banco. Esta entrega
não adiciona um teste de navegador automático ao GitHub Actions. Os testes
de produto já publicados continuam sendo evidência separada.

## Evidências

- [Roteiro observado e estado final](browser-check.json).
- [Conferência API/PostgreSQL](api-banco-final.json): quatro inspeções,
  quatro pedidos S4, duas revisões e uma causa. A inspeção escolhida contém
  um INGESTED, dois REVIEW_RECORDED e um CAUSE_RECORDED.
- [JSON exportado](relatorio-browser.json), [CSV exportado](relatorio-browser.csv)
  e [comparação/hash dos arquivos](validacao-exportacoes.json). Os downloads
  ocorreram antes da reabertura; por isso mostram REJECTED e uma revisão,
  enquanto a conferência final mostra REVIEW e duas revisões.
- [Relatório com API real](capturas/02-relatorio-api-real.jpg).
- [Relatório real em 390 px](capturas/05-mobile-api-real.jpg).
- [Console](console.json) e [encerramento Docker](encerramento.log). O log
  versionado remove somente espaços ao fim das linhas; o CSV conserva os
  bytes originais, inclusive BOM UTF-8 e CRLF.

## Repetir no Linux

1. Em um laboratório novo, execute na raiz A1:

   ```bash
   bash composicao-ver1/executar.sh demonstrar
   ```

2. Abra `http://localhost:5501/frontend/` e confira **API REAL**. Filtre o dia
   UTC da captura sintética, NON_CONFORMING, `cam-linha1` e `AMASSADO`. Abra
   a inspeção encontrada no histórico, anotando seu ID completo.
3. Informe operador e motivo de teste; corrija para Reprovar/FURADO. Confira
   a gravação no backend, a saída da fila e a análise original AMASSADO.
4. Em Relatórios, vincule a inspeção ao formulário de causa. Use a hipótese
   `Hipótese sintética para validar persistência` e fundamentação que deixe
   explícito o caráter sintético. Registre e gere o relatório individual.
5. Baixe JSON e CSV do mesmo relatório. Reimporte o CSV como `section` e
   `record_json`, decodificando cada célula JSON, e compare com o download JSON.
   Gere recorrência com os filtros: a classe continua AMASSADO, não FURADO.
6. Recarregue a página, selecione a inspeção no histórico e gere o relatório.
   Confira revisão, causa e trilha. Reinicie somente o backend:

   ```bash
   docker compose --project-name ver1-sprint3-local \
     --env-file composicao-ver1/.env.example -f composicao-ver1/compose.yml restart backend
   docker compose --project-name ver1-sprint3-local \
     --env-file composicao-ver1/.env.example -f composicao-ver1/compose.yml up -d --wait frontend
   ```

7. Após nova leitura, confirme REJECTED/FURADO e a causa anterior. Reabra a
   inspeção usando Enviar para revisão, com operador/motivo. A fila volta a
   quatro inspeções, mantendo o histórico da correção e a análise original.
8. Antes de apagar o volume, execute o observador com o ID anotado, em lugar
   de `INSP-ID-DO-SEU-ENSAIO`:

   ```bash
   docker compose --project-name ver1-sprint3-local \
     --env-file composicao-ver1/.env.example -f composicao-ver1/compose.yml \
     exec -T backend python - INSP-ID-DO-SEU-ENSAIO \
     < validacao-local/conferir_navegador_real.py
   ```

   Ele só lê API/banco e espera exatamente esse cenário sintético. Não deve
   ser usado como verificador genérico de um banco operacional.
9. Confira navegação por Enter e largura 390 px, preservando acesso aos
   controles. Ao terminar, inclusive antes de outro acesso ao broker externo:

   ```bash
   bash composicao-ver1/executar.sh parar
   ```

## Kafka compartilhado: endereços e bloqueio observado

Ícaro informou os endereços atualizados: acesso externo
`200.17.66.56:9093`; serviços na Jetson `172.18.4.56:9092`.
O exemplo `.env.kafka.example` registra essas opções sem ativá-las; a
composição de laboratório continua em `kafka:9092`.

Antes de iniciar o Kafka local deste ensaio, foi feita uma tentativa TCP ao
endpoint público. Resultado: **timeout**. Não foram consultados metadados,
publicadas/consumidas mensagens, criados tópicos ou confirmados offsets.
O IP privado não foi testado desta máquina. [Resultado](kafka-compartilhado.json)
e [script da consulta](prova-broker-compartilhado.py).

O timeout comprova indisponibilidade desse acesso na tentativa, não a causa
nem que o serviço esteja fora do ar. TRA-1 deve confirmar disponibilidade,
rota/firewall, listener externo, autenticação/protocolo e tópico. O cliente
de metadados foi planejado com os padrões sem TLS/SASL dos exemplos do guia;
não chegou a executar porque TCP falhou. Aceite do contrato continua separado.
Não executar a prova sobre a nuvem/Jetson com um Kafka local deixado ativo.

## Limites e próximo passo

Foi quitado o percurso documentado de navegador com API real e dados
persistidos no ambiente local. A evidência S4 ficou PENDING, pois seu worker
está desativado; a indicação de S4 pendente/degradado não homologa esse serviço.

Permanecem pendentes a inferência real da 18, integração operacional da 17,
latência até commit e desempenho no alvo da 30, S4/P7 reais e aceite TRA-1.
O PR I8 #10 continua sob revisão; este ensaio não o mescla nem assume tarefas
de treino/calibração de João. A documentação apoia as atividades 29 e 32.
