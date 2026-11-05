# Hospedagem e endereços do A1

## Ambiente publicado

O A1 está no projeto Google Cloud `project-edbbdc9c-ccf7-4c1e-bcd`. O projeto `project-7b075f85-c4b9-4221-bfa` não contém a VM e não é o ambiente do A1.

A aplicação roda na VM `a1-vm`, tipo `n2-standard-2`, zona `southamerica-east1-b`, em São Paulo. O deploy usa Docker Compose, Caddy, nginx, backend Python e PostgreSQL 17.

O IP externo fixo chama-se `a1-ip` e vale `34.95.237.94`. O domínio gerado pelo script de inicialização é `34-95-237-94.sslip.io`. O valor também fica em `A1_DOMAIN`, no arquivo `/opt/a1/.env` da VM.

Na VM, consulte sem exibir a senha do banco:

```bash
sudo grep '^A1_DOMAIN=' /opt/a1/.env
```

Com o valor retornado, os endereços são:

| Recurso | Endereço |
|---|---|
| Entrada pública | `https://34-95-237-94.sslip.io/` |
| Frontend | `https://34-95-237-94.sslip.io/frontend/` |
| API v1 | `https://34-95-237-94.sslip.io/api/v1` |
| Saúde | `https://34-95-237-94.sslip.io/api/v1/health` |
| Histórico | `https://34-95-237-94.sslip.io/api/v1/inspections/<inspection_id>/history` |

As portas públicas são 80 e 443. O Caddy redireciona HTTP para HTTPS e obtém o certificado automaticamente. A porta 5500 fica vinculada a `127.0.0.1` na VM e não deve ser aberta na internet.

## PostgreSQL

O banco está hospedado na mesma VM, em um container PostgreSQL 17. Ele não possui endereço público nem porta publicada no host.

| Campo | Valor |
|---|---|
| Host interno Docker | `db` |
| Porta interna | `5432` |
| Banco | `a1` |
| Usuário | `a1` |
| URL usada pelo backend | `postgresql://a1:<POSTGRES_PASSWORD>@db:5432/a1` |
| Volume persistente | `a1-db-data` |
| Disco da VM | `a1-vm`, 20 GB, disco permanente padrão |

A senha fica somente em `/opt/a1/.env`, na variável `POSTGRES_PASSWORD`. Ela não deve ser versionada. O banco só pode ser acessado pelos serviços da rede Docker. Portanto, `IP-DA-VM:5432` não é um endereço válido e não deve ser liberado no firewall.

Para abrir o cliente dentro da VM:

```bash
cd /opt/a1
sudo docker compose exec db psql -U a1 -d a1
```

## Serviços internos

| Serviço | Endereço interno | Acesso no host da VM |
|---|---|---|
| Frontend nginx | `frontend:80` | `127.0.0.1:5500` |
| Backend | `backend:8000` | `127.0.0.1:8000` |
| PostgreSQL | `db:5432` | não publicado |
| Caddy | `caddy:80` e `caddy:443` | portas públicas 80 e 443 |

O frontend chama `/api/v1` no mesmo domínio público. O nginx encaminha `/api/` para `backend:8000`.

## Kafka

O A1 consome o tópico `ods.industria.defeito_classificado`, contrato 2.0, usando `KAFKA_BROKER_URL`. O endereço do broker deve ser definido em `/opt/a1/.env`. O valor padrão `localhost:9092` não alcança um broker externo a partir do container.

O broker B2 indicado para testes compartilhados é `34.66.235.91:9093`. Esse endereço é do Kafka, não do frontend, API, banco ou VM A1. A validação das etapas 07–09 usa Kafka local isolado em Docker e não altera o broker compartilhado.

No boot, `docker/gcp-startup.sh` configura esse broker B2 quando `KAFKA_BROKER_URL` está ausente, vazio ou contém `localhost:9092`/`127.0.0.1:9092`. Um endereço remoto personalizado é preservado. O B2 é temporário para testes; quando o broker final estiver disponível, configure seu endereço no `.env`.

## Desenvolvimento local

| Recurso | Endereço |
|---|---|
| Frontend Docker | `http://localhost:5500/frontend/` |
| API | `http://localhost:8000/api/v1` |
| Saúde | `http://localhost:8000/api/v1/health` |
| PostgreSQL | somente `db:5432` dentro do Compose |

## Deploy e atualização

O script [`docker/gcp-startup.sh`](../docker/gcp-startup.sh) clona ou atualiza `/opt/a1`, preserva o `.env` e executa `docker compose up -d --build --remove-orphans`. Reiniciar a VM executa esse script novamente.

O arquivo no Git e o `startup-script` instalado na metadata da VM são cópias distintas. Atualizar a `main` não substitui automaticamente a metadata: para aplicar o novo comportamento no boot, atualize também o startup script configurado na VM. O procedimento de atualização por `docker compose` abaixo não executa o startup script nem preenche a variável Kafka; nesse caso, configure `KAFKA_BROKER_URL=34.66.235.91:9093` no `/opt/a1/.env` antes de subir os serviços, preservando as demais variáveis.

### Atualização dentro da VM

Execute depois que o PR estiver aprovado e integrado à `main`:

```bash
cd /opt/a1
sudo git status --short --branch
sudo git switch main
sudo git pull --ff-only origin main
sudo docker compose up -d --build --remove-orphans
sudo docker compose ps
curl -fsS https://34-95-237-94.sslip.io/api/v1/health
```

O `git status` deve estar limpo antes do `pull`. Não use `git reset --hard` na VM. O volume `a1-db-data` não é removido pelo deploy e preserva o PostgreSQL.

### Atualização com Google Cloud CLI

O mesmo procedimento pode ser disparado da máquina do responsável:

```bash
gcloud compute ssh a1-vm \
  --project=project-edbbdc9c-ccf7-4c1e-bcd \
  --zone=southamerica-east1-b \
  --command='cd /opt/a1 && sudo git status --short --branch && sudo git switch main && sudo git pull --ff-only origin main && sudo docker compose up -d --build --remove-orphans && sudo docker compose ps'
```

Reiniciar `a1-vm` também executa o startup script. Prefira o comando explícito acima: ele mostra a falha no ponto exato e evita reinício desnecessário do sistema operacional.

### Verificação e diagnóstico

Antes de considerar o deploy concluído, confirme na VM:

```bash
cd /opt/a1
sudo docker compose ps
curl -fsS "https://$(sudo sed -n 's/^A1_DOMAIN=//p' .env)/api/v1/health"
```

Verifique os componentes: `api-a1` e `database` devem estar `UP`; após configurar Kafka, `i8-subscriber` também deve ficar `UP`, com broker, tópico e rede acessíveis. `s4` permanece `DOWN` até a implementação do adaptador em S3-09. No backend atual, o estado global considera somente banco e assinante Kafka: pode retornar `ONLINE` mesmo com S4 indisponível. Portanto, o estado global sozinho não comprova que todas as integrações estão concluídas; enquanto Kafka estiver `DOWN`, ele será `DEGRADED`.

```bash
sudo docker compose logs --tail=200 backend frontend db caddy
sudo docker compose exec db pg_isready -U a1 -d a1
sudo docker compose exec db psql -U a1 -d a1 -c 'SELECT count(*) FROM inspections;'
```

Na verificação pública mais recente, em 5 de novembro de 2026, API e PostgreSQL estavam `UP`, mas o estado global estava `DEGRADED`: `i8-subscriber` estava `DOWN`, tentando acessar `localhost:9092` dentro do container. S4 também estava `DOWN`, pois seu adaptador ainda não está implementado. A VM foi confirmada como `n2-standard-2`. Configure o broker B2, recrie o backend e repita a verificação; esta documentação não afirma que a conexão ao broker compartilhado já foi validada. O S4 pendente não é corrigido pela configuração Kafka.
