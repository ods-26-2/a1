# Atividade 20 — validação S4 real

Resultado em 06/11/2026: **BLOQUEADA_EXTERNAMENTE**. O serviço S4 real não foi homologado. Este registro atende à alternativa “Serviço real validado ou bloqueio externo documentado” do plano de fechamento, página 4. A dependência é a atividade 19 mais serviço S4 disponível e compatível.

O [manifesto rastreável](manifesto.json) fixa o critério, hash SHA-256 do PDF fornecido, versões, responsáveis, evidências e condições de retomada. O PDF é documento fornecido à equipe, não copiado para este repositório. A inspeção foi estática; não houve tentativa de captura real, acesso ao broker compartilhado, VM, fonte/buffer ou contato externo nesta atividade. Disponibilidade do ambiente não verificada não significa serviço comprovadamente fora do ar.

## Base e responsabilidade

| Componente | Commit inspecionado |
|---|---|
| A1 | [`2e59fe3d90070a00db025b86edc83857e5c0ae47`](https://github.com/ods-26-2/a1/tree/2e59fe3d90070a00db025b86edc83857e5c0ae47) |
| S4 | [`57ea2cc226b2a8cf47a134d1f7490060d2033027`](https://github.com/ods-26-2/s4/tree/57ea2cc226b2a8cf47a134d1f7490060d2033027) |

Samuel e Ícaro conduzem a validação A1/S4. A equipe MOD-2/S4 precisa confirmar o responsável nominal pelas correções e o prazo de disponibilização; ambos ainda estão pendentes. Não há prazo ou aceite externo presumido.

A [atividade 19](../../sprints/atividade-19-adaptador-s4.md) já implementa envio durável, correlação, timeout e expiração com simulador. Suas [evidências](../atividade-19-s4/README.md) usam Kafka/PostgreSQL/A1 reais e S4/imagem simulados. Elas constituem a base local, sem comprovar captura industrial. Este incremento altera somente documentação; a ativação do adaptador no ambiente real continua condicionada ao alinhamento e à validação.

## Bloqueios e impacto

| ID | Evidência no S4 fixado | Impacto e condição objetiva de desbloqueio |
|---|---|---|
| S4-20-01 | [Handler, linhas 91–99](https://github.com/ods-26-2/s4/blob/57ea2cc226b2a8cf47a134d1f7490060d2033027/src/infrastructure/b3_bus/handlers/capture_command_handler.cpp#L91-L99): usa quadro mais recente e janela, sem ler `payload.at`. | Pode capturar outra peça. Capturar o instante pedido, com fonte/sessão corretas, ou devolver erro explícito de buffer; nunca substituir silenciosamente pelo quadro mais recente. |
| S4-20-02 | [Handler, linhas 89–99](https://github.com/ods-26-2/s4/blob/57ea2cc226b2a8cf47a134d1f7490060d2033027/src/infrastructure/b3_bus/handlers/capture_command_handler.cpp#L89-L99) gera `.mp4` e janela; [payload, linhas 24–27](https://github.com/ods-26-2/s4/blob/57ea2cc226b2a8cf47a134d1f7490060d2033027/src/infrastructure/b3_bus/clip_payload.cpp#L24-L27) publica os limites. | A1 espera imagem e instante pontual. Demonstrar SNAPSHOT renderizável, MIME e hash corretos, `start_at=end_at=captured_at=payload.at` do comando. A extensão isolada não comprova os bytes gerados. |
| S4-20-03 | [Handler, linhas 47–79](https://github.com/ods-26-2/s4/blob/57ea2cc226b2a8cf47a134d1f7490060d2033027/src/infrastructure/b3_bus/handlers/capture_command_handler.cpp#L47-L79) gera novo `clip_id` por chamada; não há lookup de deduplicação visível nesse caminho. | Reenvio pode criar outra captura. Provar identidade estável e uma única captura para mesmo `message_id`/conteúdo, incluindo reinício S4; recusar ID com conteúdo divergente. |
| S4-20-04 | [URI, linhas 11–12](https://github.com/ods-26-2/s4/blob/57ea2cc226b2a8cf47a134d1f7490060d2033027/src/infrastructure/b3_bus/clip_payload.cpp#L11-L12) é `s4://clips/...`. | A1 mantém `UNAVAILABLE` sem HTTP(S). Disponibilizar acesso controlado compatível com o contrato e navegador A1, com expiração e integridade verificadas. Gateway, se necessário, requer integração explícita. |
| S4-20-05 | [Handler, linhas 64–84](https://github.com/ods-26-2/s4/blob/57ea2cc226b2a8cf47a134d1f7490060d2033027/src/infrastructure/b3_bus/handlers/capture_command_handler.cpp#L64-L84) publica `OK` antes de verificar suporte e buffer; pode retornar sem descritor. | Aceite pode terminar somente em timeout. Provar descritor e mídia após aceite, ou erro explícito de conclusão; reply `OK` e health isolados não homologam captura. |

No A1 fixado, [correlação](https://github.com/ods-26-2/a1/blob/2e59fe3d90070a00db025b86edc83857e5c0ae47/backend/s4.py#L135-L139) exige fonte/sessão/instante exatos, [reenvio](https://github.com/ods-26-2/a1/blob/2e59fe3d90070a00db025b86edc83857e5c0ae47/backend/s4.py#L67-L83) conserva o envelope, [URL](https://github.com/ods-26-2/a1/blob/2e59fe3d90070a00db025b86edc83857e5c0ae47/backend/s4_contracts.py#L65-L70) exige HTTP(S), e a [interface](https://github.com/ods-26-2/a1/blob/2e59fe3d90070a00db025b86edc83857e5c0ae47/frontend/js/ui/evidence.js#L47-L66) usa elemento de imagem. Afrouxar essas verificações não resolve a captura da peça correta.

## Checklist de retomada

- [ ] MOD-2/S4 confirma responsável nominal, versão corrigida, prazo e os cinco pontos acima.
- [ ] Samuel/Ícaro registram commits A1/S4/B1 da nova execução, ambiente, relógios UTC com milissegundos, fonte/sessão reais e retenção do buffer compatível com o pedido.
- [ ] Broker/tópicos `ods.s4.capture.command`, `ods.s4.capture.reply`, `ods.s4.clip`, grupos isolados e acesso autorizado estão disponíveis; não publicar dados reais em laboratório compartilhado sem coordenação operacional.
- [ ] HTTP(S) da mídia está disponível ao navegador A1, com validade e controle de acesso acordados; nenhuma credencial entra nas evidências.
- [ ] Há fonte/buffer reais e uma inspeção A1 correlacionável. Evento sintético, se usado apenas para disparar o pedido, fica identificado como tal e não constitui validação do fluxo real I8 da atividade 18.
- [ ] O roteiro abaixo conclui captura, integridade, renderização, idempotência, falhas e expiração, com logs e revisão de Samuel/Ícaro.

## Roteiro da próxima validação real

1. Criar diretório de evidências da execução, com data/hora, versões completas, comandos exatos, endpoints sem segredos e configuração efetivamente usada. Registrar fonte/sessão, instante de captura, inspeção e IDs de correlação. Separar o banco/grupos de validação dos dados operacionais.
2. Confirmar os cinco desbloqueios na implementação S4 e no ambiente. Reexecutar o laboratório da [atividade 19](../../sprints/atividade-19-adaptador-s4.md#testar-no-linux-com-docker) como regressão separada. O script `validacao-local/executar_s4.sh` cria S4 fake e encerra seu laboratório com `down -v`: ele não é roteiro de captura real e não deve ser reapontado para serviços compartilhados.
3. Usar uma composição real configurada pelos responsáveis, com `KAFKA_BROKER_URL`, `S4_ENABLED=1` e `S4_GROUP_ID` dedicado, somente após disponibilidade e compatibilidade confirmadas. Registrar o comando de inicialização adotado. Não há comando executável universal de S4 real nesta entrega: endereço, fonte, armazenamento e composição continuam dependências externas.
4. Gerar uma inspeção ligada a um quadro real ainda retido pelo S4. Guardar consulta da inspeção e do pedido persistido, envelope enviado e offsets/partições. Comprovar `payload.at` igual ao instante da inspeção. Salvar reply, descritor e IDs completos; reply `OK` deve representar aceite, sem disponibilizar mídia antes do descritor válido.
5. Conferir produtor, versões, fonte, sessão, comando/evento, `clip_id` e instante pontual no descritor. Baixar a mídia pela referência HTTP(S), registrar status e `Content-Type`, calcular SHA-256 dos bytes e comparar com `hash_sha256`. Abrir imagem e inspeção no navegador para comprovar renderização e correspondência à peça; guardar captura da tela e resultado da API. A1 não baixa a mídia automaticamente para conferir o hash.
6. Reenviar o mesmo envelope e simular resposta perdida. Reiniciar A1 e S4 na instância de validação e repetir a mesma identidade. Conferir uma captura/`clip_id`, uma inspeção e ausência de auditoria de conclusão duplicada; registrar contagens e offsets. Reutilização do ID com conteúdo diferente deve ser recusada.
7. Exercitar fonte inexistente, instante fora do buffer e falha de armazenamento suportada pelo contrato; guardar erro explícito e estado `UNAVAILABLE`. Interromper a resposta para observar timeout; resposta tardia não deve ressuscitar o pedido. Descritor de fonte/sessão/instante incompatível deve ser recusado sem aparecer em outra inspeção. Comprovar que a expiração oculta a URL na API e que o serviço respeita a validade prometida.
8. Registrar falhas encontradas, resultados por item, comandos e logs suficientes para repetir a execução. Desativar a configuração temporária conforme o procedimento do ambiente. Samuel/Ícaro revisam a evidência; só então registrar nova decisão, preservando este histórico de bloqueio e apontando os commits efetivamente executados.

## Critério de aceite

O resultado atual é **bloqueio externo documentado**, alternativa prevista na etapa 20. Não significa integração homologada, captura real tentada ou Sprint 3 inteira concluída. A mudança futura para `VALIDADA_REAL` exige todos os itens de retomada e resultados do roteiro real, incluindo mídia, correlação, idempotência, falhas e expiração. Se permanecer bloqueada, acrescentar data, responsável e evidência nova, sem promover status por testes do simulador.

Esta atividade não implementa histórico, relatórios, S5, P7 ou outras tarefas do plano. O manifesto não altera configuração, política, esquema de banco ou comportamento do produto.
