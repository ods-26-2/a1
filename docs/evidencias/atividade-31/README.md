# Atividade 31 — vídeos e evidências

Critério da página 5 do plano: “Vídeos, capturas, logs e comandos
publicados”. Resultado: **EVIDENCIAS_PUBLICADAS**.

- [Vídeo da demonstração frontend](videos/demonstracao-frontend.mp4).
- [Histórico filtrado](capturas/01-historico-filtrado.png).
- [Recorrência](capturas/02-recorrencia.png).
- [Inspeção com causa declarada](capturas/03-inspecao-causa.png).
- [Relatório em 390 px](capturas/04-mobile-relatorio.png).
- [Comandos reproduzíveis e logs](comandos.md).
- [Manifesto com hashes](manifesto.json) e [aceite do navegador](browser-check.json).

O vídeo e as capturas mostram a interface real com API fake explícita, porque
o computador executor não possui Docker. Os logs versionados das atividades 29
e 30 provêm do GitHub Actions com publisher I8 fixado, Kafka, PostgreSQL e A1.
Essa separação evita apresentar dados simulados como prova de integração.

Limites: a demonstração visual não persiste causas, não executa inferência de
imagem e não homologa S4 real ou P7 físico. Os artefatos integrais dos runners
expiram em 30 dias; resultados, resumos, comandos, capturas, vídeo e hashes
essenciais permanecem no repositório.

Os resultados da atividade 30 tiveram seus rótulos corrigidos: medem chegada
ao início da ingestão A1, e não o commit no banco. Números históricos foram
preservados, com originais arquivados; os hashes dos dois arquivos afetados
foram atualizados neste manifesto. Vídeo e capturas permanecem iguais.
