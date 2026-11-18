# Evidências - inferência P2 até A1/PostgreSQL

Execução Docker local de 06/11/2026, sobre checkout limpo do código `e815ddcf3ce452f3891bbb68de2ef04f030c055e`, branch do PR A1 #26. Os arquivos abaixo são cópias dessa execução, não resultados gerados manualmente.

- [Resultado por fase](resultado.json): envio, reenvio e reinício aprovados; seis entregas, três inspeções, três comandos e três eventos INGESTED. `a1_working_tree_modified=false`.
- [Preparação e hashes](preparacao.json): três imagens de ruído com sementes 1/2/3; modelos/política históricos reais I8; referência Torch e engine P2 FP32/CPU.
- [Frames correlacionados](frames.jsonl), [journal efetivamente enviado](eventos.jsonl) e recibos de [envio](recibos-envio.jsonl) e [reenvio](recibos-reenvio.jsonl).
- [Engine ausente](engine-ausente.json): falha antes de journal, publicação, inspeção ou comando.
- [Encerramento](encerramento.log): remoção dos contêineres, rede e volume apenas do laboratório P2.
- [Manifesto dos arquivos](manifesto.json) e [versões fixadas](versoes.json).

Na execução registrada, as três imagens produziram UNCERTAIN. O teste não força quatro resultados. Modelos e inferência reais sobre imagens sintéticas não demonstram precisão industrial, dataset homologado, captura operacional, Jetson, S4/P7 físicos ou latência até commit.

Reprodução: `bash composicao-ver1/testar-p2.sh`, na raiz do A1. Veja o [roteiro e as decisões de arquitetura](../../sprints/integracao-p2-kafka-a1.md).

Os pacotes ONNX e as imagens não são duplicados no Git. Seus hashes e o gerador estão registrados. O workflow publica a saída completa por 30 dias; a prova resumida acima permanece versionada.

CI do mesmo código: [integração P2](https://github.com/ods-26-2/a1/actions/runs/42272467808), [regressão e fechamento](https://github.com/ods-26-2/a1/actions/runs/42272469876). Acompanhe o estado das execuções nos links; a ausência de erro neste texto não substitui a conclusão do job.

Atualizações Recentes: `[Inserir atualização aqui: horário, commit, execução e novo resultado]`.
