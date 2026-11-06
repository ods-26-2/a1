# Sprint 3 - P2/I8 até o banco do A1

## O que mudou

A composição agora fixa o I8 em `051851f8c7889aba4da8422293c911aa84579da4`, merge do PR I8 #10. O P2 fica em `fddf028c025b4a9be22d3a67696a13c0c65b9b0e`.

O laboratório original continua enviando quatro eventos sintéticos prontos. O novo ensaio acrescenta o trecho que faltava: **imagens sintéticas passam pela inferência P2 real e o replay oficial do I8 publica os eventos no Kafka; A1 e PostgreSQL recebem e preservam os resultados**.

Essa prova avança as atividades 17, 18 e 28. Não encerra a demonstração de quatro resultados reais da atividade 15 nem a validação industrial da 18.

## Como testar no Linux

Pré-requisitos: Docker com Compose/BuildKit, Git e Python 3 no host. Execute na raiz do A1:

```bash
bash composicao-ver1/testar-p2.sh
```

O script obtém as revisões fixadas, reaproveita o Dockerfile.p2 do I8, constrói o pacote ONNX e executa a composição. A primeira construção precisa de rede para dependências e pesos oficiais. Os serviços de execução usam rede Docker interna: nenhum broker compartilhado é acessado. A porta local padrão é 5502; `VER1_P2_PORT` permite selecionar outra porta livre.

Ao terminar, inclusive quando uma etapa falha, o script executa `down -v --remove-orphans` somente no projeto `ver1-sprint3-p2`. Os arquivos de evidência permanecem no host. Não inicie este laboratório ao usar o broker externo da disciplina; siga a orientação operacional de encerrar o Kafka local antes de alternar ambientes.

Para repetir, primeiro preserve ou renomeie `composicao-ver1/evidencias-p2`. O script recusa sobrescrever essa pasta. Se uma interrupção impedir o encerramento, depois de preservar os arquivos use:

```bash
docker compose --project-name ver1-sprint3-p2 \
  --env-file composicao-ver1/.env.example \
  -f composicao-ver1/compose.yml -f composicao-ver1/compose-p2.yml \
  down -v --remove-orphans
```

Esse comando apaga somente o banco de ensaio desse projeto. O laboratório original continua disponível por `bash composicao-ver1/executar.sh testar`, com seu próprio projeto e evidências.

## Como a prova funciona

1. Gera três imagens RGB de ruído, com sementes 1, 2 e 3. Não usa imagens industriais nem modifica o dataset.
2. Exporta a ResNet18 com pesos oficiais e prepara o pacote P2 FP32/CPU. Usa os modelos normal/classificador/política históricos do I8 e a taxonomia real do A1, sem doubles de inferência ou taxonomia.
3. Calcula a referência Torch com o mesmo pré-processamento e recorte. Os resultados P2 devem manter decisão/classe e proximidade numérica, com `atol=5e-5` e `rtol=1e-4`.
4. Tenta uma engine inexistente. O replay precisa falhar antes de criar journal, publicar mensagens ou criar inspeções/comandos. Não há fallback silencioso para Torch.
5. Chama `python -m scripts.replay --p2-engine ... --kafka`. O replay faz correlação, inferência, journal e confirmação de entrega reais.
6. Confere os recibos, offsets, eventos originais em PostgreSQL e leituras pela API A1. Verifica hashes de imagens, frames, modelos, engine e taxonomia.
7. Reenvia o journal pelo publisher I8, sem refazer a inferência ou regenerar IDs. Seis entregas devem manter três inspeções, três comandos e três registros INGESTED.
8. Reinicia o backend e repete a conferência. Encerra os contêineres, rede e volume locais.

O resultado não é forçado para cobrir quatro classes. Na primeira execução local, as três imagens produziram `UNCERTAIN`; isso é resultado da política histórica sobre ruído, não medida de qualidade industrial.

## Onde conferir

- `composicao-ver1/evidencias-p2/resultado.json`: aceite por fase, contagens, offsets, IDs, versões e limites.
- `preparacao.json`: sementes, hashes e previsões de referência.
- `frames.jsonl`, `eventos.jsonl` e recibos: correlação e conteúdo efetivamente enviado.
- `engine-ausente.json` e seu log: falha fechada antes da publicação.
- `containers.log` e `encerramento.log`: execução e remoção do laboratório.
- Workflow `integracao-p2-a1.yml`: repete a prova em Docker e conserva os arquivos por 30 dias. Os pacotes grandes ONNX ficam no artefato da execução, não no Git.

O registro de origem distingue um checkout limpo de alterações locais; a primeira prova de desenvolvimento teve `a1_working_tree_modified=true`. Não atribua esse resultado a uma revisão limpa diferente. As evidências do CI identificam o commit executado.

## Limites e decisões

- CPU ONNX Runtime FP32; não TensorRT/Jetson, câmera ou captura P4/I1/P6 operacional.
- Modelos e inferência são reais, mas as imagens são sintéticas e os artefatos de classificação são históricos. Não houve novo treino, calibração, homologação ou avaliação do dataset.
- O resultado não comprova quatro saídas industriais, precisão por classe, SLA de 200 ms ou latência até commit. `persistence_latency_measured=false` permanece explícito.
- S4, S5 e P7 reais não são exercitados. Seus bloqueios e o aceite TRA-1/B2 permanecem separados.
- O manifesto da atividade 26 permanece histórico e imutável. O novo registro identifica os hashes efetivamente usados neste ensaio.
- O preparo de dependências recusa checkouts modificados e atualiza apenas as cópias ignoradas em `.dependencias`, para revisões fixadas. Não altera a instalação do usuário.
- A imagem fina do laboratório reaproveita o Dockerfile P2 do I8. Apenas disponibiliza os pesos já baixados para execução sem root e acrescenta o condutor do ensaio; não mantém outro algoritmo de inferência.
- Este incremento reproduz o ajuste de preparação de vídeo já aprovado no A1 #25, ainda não integrado à main. Isso evita reintroduzir o cancelamento daquele job enquanto os PRs são revisados em paralelo.

Atualização: 06/11/2026. Próximo marco industrial: selecionar imagens e artefatos rastreáveis com João, testar captura/runtime no alvo e completar a atividade 18. Registro adicional: `[Inserir atualização aqui: horário, execução, resultado e limite removido]`.
