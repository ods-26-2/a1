# Atividade 27 — avaliação e incorporação útil do B6

Critério do plano, página 4: “Componentes úteis incorporados; demais justificados”. Data: 06/11/2026. Resultado: **AVALIADOS_COM_NAVEGACAO_INCORPORADA**. A necessidade concreta é navegar rapidamente entre inspeção, histórico, relatórios e fila na página A1 que cresceu com os recursos locais existentes.

O [manifesto](manifesto.json) registra decisões individuais, hashes, licença observada e validação. Base A1: [`070b153fa0a3199a8682a6435278ebd52b4739ba`](https://github.com/ods-26-2/a1/tree/070b153fa0a3199a8682a6435278ebd52b4739ba). B6 main/origin-main auditados: [`61a9658b7c36e8abc016eff79ce9f5237d92aa64`](https://github.com/ods-26-2/b6/tree/61a9658b7c36e8abc016eff79ce9f5237d92aa64). Foram lidos o [README B6](https://github.com/ods-26-2/b6/blob/61a9658b7c36e8abc016eff79ce9f5237d92aa64/README.md), os quatro componentes e os testes pertinentes. Os hashes se referem aos blobs Git originais, sem normalização.

## Decisão por componente

| Componente | Necessidade/contrato A1 | Decisão |
|---|---|---|
| **AppShell** | A1 tem uma página vanilla com quatro áreas e health já definido; a navegação B6 separa layout e decisão de domínio. | Incorporado somente comportamento útil de navegação/destino ativo, em implementação original A1 com âncoras semânticas. [B6, linhas 260–280](https://github.com/ods-26-2/b6/blob/61a9658b7c36e8abc016eff79ce9f5237d92aa64/b6-app-shell/b6_app_shell.ts#L260-L280) fornece o ponto de comparação. Shell inteiro, temas e painel Jetson dispensados: imporiam CSS/layout/estado paralelos e métricas sem contrato A1. |
| **AlertConsole** | [Payload e callbacks B6, linhas 9–27](https://github.com/ods-26-2/b6/blob/61a9658b7c36e8abc016eff79ce9f5237d92aa64/b6-alert-console/b6_alert_console.ts#L9-L27) usam ACTIVE/ACKNOWLEDGED/MUTED/CLOSED. A1 tem resultado I8, triagem, revisão e fila, com mudanças persistidas pelo servidor. | Não incorporado. Não há AlertPayload ou endpoints acknowledge/mute/close em A1; converter revisão em reconhecimento/silenciamento ou marcar lote localmente criaria significado incorreto e duplicaria o fluxo existente. O princípio de callbacks sem regras de negócio já está atendido pelos adaptadores/serviços A1. |
| **OverlayPlayer** | [Caixas e timeline B6, linhas 14–28](https://github.com/ods-26-2/b6/blob/61a9658b7c36e8abc016eff79ce9f5237d92aa64/b6-overlay-player/b6_overlay_player.ts#L14-L28) exigem vídeo, intervalos em segundos e caixas normalizadas. A1 consome snapshot S4 pontual e bbox I8 em pixels. | Não incorporado. Faltam timeline e dimensões de quadro garantidas para converter coordenadas corretamente. Player não resolve instante/URI/forma de mídia do S4 real; placeholders e expiração existentes continuam adequados. |
| **ZoneEditor** | [ZonePayload B6, linhas 13–18](https://github.com/ods-26-2/b6/blob/61a9658b7c36e8abc016eff79ce9f5237d92aa64/b6-zone-editor/b6_zone_editor.ts#L13-L18) define zona/polígono e o componente permite sua manutenção. Requisitos/arquitetura A1 tratam inspeção, triagem, revisão e relatórios, sem manutenção de zonas. | Não incorporado. Criaria domínio, persistência e contratos novos, fora da necessidade A1 desta atividade. Os limites de domínio são preservados. |

A [arquitetura A1](../../arquitetura.md) e o [contrato API](../../contratos/a1-api.md) permanecem a referência das capacidades reais. Não houve mudança de resultado/decisão, evidência, auditoria, política, contrato, persistência ou comandos externos.

## Licença e origem da implementação

A árvore B6 fixada contém README e quatro diretórios com fonte TypeScript, teste e HTML; não foi encontrada LICENSE/COPYING/NOTICE ou declaração de licença nos arquivos lidos. Portanto nenhuma licença permissiva foi presumida e nenhum fonte, CSS, HTML, teste ou dependência B6 foi copiado/transpilado/traduzido para A1.

Foi incorporado o comportamento geral útil identificado na avaliação: navegação por áreas com indicação de destino. A implementação A1 usa elementos nativos e código novo em [sectionNavigation.js](../../../frontend/js/ui/sectionNavigation.js), mantendo proveniência explícita sem alegar reutilização de pacote licenciado. Uso futuro do código B6 propriamente dito depende de esclarecer sua autorização/licença; não é necessário para esta implementação original.

Não foram adicionados TypeScript, Vite, Vitest, jsdom, pacote NPM, tema, CSS global B6 ou telemetria sintética. A stack vanilla e o runner nativo Node continuam suficientes.

## Comportamento incorporado e acessibilidade

- Barra `nav` rotulada “Seções do A1”, com links para inspeção exibida, histórico, relatórios e fila. Funciona por âncoras mesmo sem JavaScript e não muda inspeção selecionada/filtros/estado de negócio.
- Destinos são títulos únicos com `tabindex=-1`: clique/Enter move o foco ao título e mantém navegação nativa, rolagem, URL e histórico. A indicação `aria-current=location` acompanha o fragmento conhecido, inclusive voltar/avançar. Rolagem manual não altera o fragmento; o indicador representa o destino escolhido, não rastreamento automático da posição.
- Cliques com modificadores/botão secundário não roubam foco. Fragmento inválido ou destino ausente não gera rota ou execução de conteúdo; nenhuma string externa entra em innerHTML.
- Links têm alvo de pelo menos 44 px, contraste/contorno com tokens existentes e quebra de linha em telas estreitas. Não há animação/scroll forçado ou sidebar que bloqueie o conteúdo.
- O destino da inspeção é título sempre visível, fora do painel que pode ser ocultado por carregamento/vazio/erro, permitindo orientação mesmo quando a API falha.

## Evidências e reprodução

```powershell
node --test --test-isolation=none frontend/tests/sectionNavigation.test.js
node --test --test-isolation=none 'frontend/tests/*.test.js'
python scripts/validate_contracts.py
git diff --check
```

Resultado local: **4 testes novos de navegação aprovados; 27 frontend aprovados ao todo**, zero falhas/ignorados. Testes verificam fragmento inicial, voltar/avançar, foco por ativação, preservação da âncora, modificadores, destino ausente/fragmento inválido, limpeza dos listeners, landmark rotulado e IDs/títulos focáveis. Contratos 6c e diff foram validados separadamente. O isolamento Node foi desativado pela restrição local de spawn, como nas atividades anteriores; não muda os testes ou a aplicação.

Os testes B6 originais não foram executados: não há código B6 incorporado e instalar seu toolchain não acrescentaria prova do comportamento A1. A inspeção visual local foi executada no navegador integrado, em modo fake: layout sem sobreposição, navegação para Relatórios com foco e fragmento corretos, relatório de recorrência gerado para período preenchido e zero erros/warnings no console. Não houve prova mobile, API real ou operação com JavaScript desativado. Roteiro complementar: navegar com Tab/Enter entre links, conferir voltar/avançar, testar celular, API offline e operação sem JavaScript. Reabrir histórico/relatórios/revisão e confirmar que a navegação não modifica seleção, filtros ou decisões.

Esta atividade encerra a avaliação local dos quatro componentes com incorporação seletiva e justificativas explícitas. Não amplia tarefas anteriores nem implementa novas integrações de segurança, vídeo, zonas ou telemetria.
