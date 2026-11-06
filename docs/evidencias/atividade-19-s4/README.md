# Evidências — Sprint 3, atividade 19: adaptador S4

Base A1: `908129c7787012bba63403a7d861b09a8bb7f261`. Schemas B1: `fdaeb80bc46014d14649f7ba0c14cd8a3533eb96`. S4 consultado: `57ea2cc226b2a8cf47a134d1f7490060d2033027` (master). Data local: 06/11/2026.

## Testes executados em Docker

- Primeira seleção: **34 testes S4 aprovados** com PostgreSQL/API reais.
- Regressão final: **282 Python aprovados e 14 frontend aprovados**, zero testes ignorados. Inclui **38 testes S4** após acrescentar shutdown, erro após aceite e identificadores incompatíveis com PostgreSQL. Não somar as seleções.
- Relatório de todos os casos Python: `regressao.xml`.
- Contratos I8/A1 existentes aprovados para os quatro resultados.
- Aviso Starlette/httpx de depreciação, sem falha.

Cobertura S4: reply distinta da conclusão, fonte/sessão/instante/ID, descritor antes da reply, reenvio idêntico após recriar o adaptador, três erros previstos, timeout, expiração imediata da URL na API, URI s4:// sem gateway, duplicatas divergentes, rejeição durável, falha de DB impedindo envio/commit, offset após persistência e shutdown antes do fechamento do pool.

## Prova com Kafka real

`resultado-s4.json` registra execução com Kafka 3.9.1, PostgreSQL 17 e backend/API A1 reais. S4 e a imagem são **simulados**. A imagem é um PNG sintético de um pixel; não comprova captura industrial.

- Quatro eventos I8 sintéticos válidos, quatro inspeções e quatro pedidos S4 concluídos.
- Quatro descritores disponíveis na API; leitura HTTP da mídia sintética e comparação de SHA-256.
- Reenvio dos mesmos quatro comandos: permanecem quatro inspeções, quatro comandos e quatro registros S4_AVAILABLE.
- Reply e clip: cada tópico chegou a oito mensagens, todas confirmadas pelo grupo A1 S4 (offset 8/8).
- Reinício do backend: as mesmas quatro evidências e auditorias permanecem disponíveis.
- Saúde ONLINE refere-se ao backend/transportes do laboratório, sem homologar o S4 real.
- Script terminou com código zero e removeu containers, rede e volume com `compose down -v`.

Duas primeiras execuções do roteiro falharam antes de concluir a prova: escape de `$topic` no Compose e seleção de fixtures que incluía casos inválidos. Ambos foram corrigidos no laboratório; a prova final acima passou. Não foram relaxadas verificações do adaptador.

## Limites

O worker fica desativado por padrão. Não foi acessado broker compartilhado, VM ou fonte real. O simulador não prova deduplicação do S4 após reiniciar seu processo. A API valida o hash declarado, mas não baixa automaticamente a mídia para verificar os bytes. Não houve teste visual em navegador. A atividade 20 depende de resolver instante/forma do snapshot, deduplicação e acesso HTTP(S) no S4 real.

[Arquitetura, ativação e comandos Docker](../../sprints/atividade-19-adaptador-s4.md).
