# Sprint 3 — atividade 28: composição local VER-1

Esta composição reúne a interface e a API do A1, PostgreSQL, Kafka local e o
publisher real do I8. Ela permite testar a ligação entre os componentes sem
aguardar acesso aos serviços das outras equipes.

O I8 envia quatro eventos **sintéticos**: CONFORMING, NON_CONFORMING, ANOMALY e
UNCERTAIN. Não há inferência de imagens nem avaliação da qualidade dos modelos.
A política atualmente ativa do A1 encaminha os quatro para revisão humana.

## Testar na sua máquina Linux

Pré-requisitos: Docker com Compose v2 e acesso ao daemon, Git e Python 3.
Não precisa instalar Python de inferência, Kafka ou PostgreSQL na máquina.
O primeiro uso precisa de internet para obter o I8 fixado e construir as imagens.

Na raiz do repositório A1, na branch que contém esta composição:

```bash
bash composicao-ver1/executar.sh testar
```

O comando constrói as imagens, sobe os serviços, publica quatro eventos pelo
I8, confere a API através do nginx da interface, o banco e os offsets do Kafka.
Depois reenvia os mesmos eventos e reinicia o backend. O resultado esperado é
**oito entregas no Kafka, quatro inspeções e quatro comandos no banco**, sem
duplicar a auditoria de ingestão. Ao terminar, executa `compose down -v`.

Consulte `composicao-ver1/evidencias/resultado.json`. O sucesso final aparece como
`composicao-local-aprovada`. Logs, recibos e identificação das versões ficam na
mesma pasta. Esses arquivos são locais e não entram automaticamente no Git.

## Ver a interface com os dados do teste

```bash
bash composicao-ver1/executar.sh demonstrar
```

O comando executa a mesma verificação e mantém os serviços após o sucesso.
Abra <http://localhost:5501/frontend/>. A interface usa a API real desta
composição. A verificação automatizada confirma HTML, JavaScript e proxy da API;
ela não substitui um teste visual de todos os controles da interface.

**Depois de usar, inclusive antes de mudar para um ambiente de nuvem:**

```bash
bash composicao-ver1/executar.sh parar
```

Esse comando remove os containers e o volume de banco **deste laboratório**.
Por isso ele apaga os dados locais da demonstração. Uma nova execução começa
vazia. O script recusa iniciar outro teste sobre um laboratório já existente.

## Configuração por ambiente

O arquivo `.env.example` fornece os padrões. Para alterar a porta ou o grupo:

```bash
cp composicao-ver1/.env.example composicao-ver1/.env
# Edite composicao-ver1/.env; exemplo: VER1_PORT=5502
VER1_ENV_FILE=.env bash composicao-ver1/executar.sh demonstrar
VER1_ENV_FILE=.env bash composicao-ver1/executar.sh parar
```

Use o mesmo arquivo ao iniciar e parar. `VER1_DB_PASSWORD` é senha exclusiva
do laboratório, sem uso em produção; para interpolação na URL, use caracteres
alfanuméricos. `VER1_GROUP_ID` identifica o consumidor local. O frontend publica
somente em `127.0.0.1`; Kafka e PostgreSQL não publicam portas no host.

O broker `kafka:9092` e o tópico industrial
`ods.industria.defeito_classificado` são passados aos componentes por variáveis
de ambiente dentro do Compose. O tópico permanece fixo porque o publisher 2.0
recusa outro nome. A configuração local não consulta o broker compartilhado,
o Google Cloud ou a rede Dcomp.

`versoes.json` fixa o commit do I8 e registra a base A1. A cópia do I8 é obtida em
`.dependencias/i8/`, ignorada pelo Git; uma cópia alterada ou em outro commit é
recusada. O A1 é construído a partir do checkout atual: seu commit e a presença
de alterações são registrados. Não usa o PR I8 #10 enquanto está em revisão.

## Relação com a arquitetura e limites

- I8 publica resultados; não decide a consequência operacional.
- Kafka transporta os eventos; PostgreSQL mantém o histórico persistido pelo A1.
- A1 aplica sua política e fornece os dados à interface pelo proxy nginx.
- A1 cria pedidos de evidência para S4, mas `S4_ENABLED=0` evita tentar falar com
  um serviço externo. Comandos pendentes no teste são esperados.
- Os adaptadores preparados S5 e P7 continuam disponíveis no A1, mas esta
  composição não inventa workers, serviços físicos ou respostas para eles.

Esta entrega prepara a **base local da atividade 28**. O fechamento coletivo
continua dependendo da atividade 21 e da integração aceita dos componentes.
Atividades 18, 20, 25, 29 e 30 não são homologadas por este teste. As imagens
reais, execução no ambiente final e registro do aceite TRA-1 continuam pendentes.

A prova reutiliza as verificações observacionais de
`validacao-local/provar_fluxo.py` e usa `scripts.publish_events` do I8 como
produtor. Não usa o produtor fake do A1. O workflow **Sprint 3 - composição local
VER-1** repete essa prova em Docker no GitHub Actions e publica seus artefatos.
