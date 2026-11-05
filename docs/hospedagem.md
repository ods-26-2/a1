# Hospedagem e endereços do A1

## Ambiente publicado

O A1 está no projeto Google Cloud `project-edbbdc9c-ccf7-4c1e-bcd`. O projeto `project-7b075f85-c4b9-4221-bfa` não contém a VM e não é o ambiente do A1.

A aplicação roda na VM `a1-vm`, tipo `e2-small`, zona `southamerica-east1-b`, em São Paulo. O deploy usa Docker Compose, Caddy, nginx, backend Python e PostgreSQL 17.

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

## Desenvolvimento local

| Recurso | Endereço |
|---|---|
| Frontend Docker | `http://localhost:5500/frontend/` |
| API | `http://localhost:8000/api/v1` |
| Saúde | `http://localhost:8000/api/v1/health` |
| PostgreSQL | somente `db:5432` dentro do Compose |

## Deploy e atualização

O script [`docker/gcp-startup.sh`](../docker/gcp-startup.sh) clona ou atualiza `/opt/a1`, preserva o `.env` e executa `docker compose up -d --build --remove-orphans`. Reiniciar a VM executa esse script novamente.

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

O retorno esperado da saúde é `ONLINE`. O componente `i8-subscriber` só fica `UP` quando `KAFKA_BROKER_URL`, tópico e rede do broker estão corretos.

```bash
sudo docker compose logs --tail=200 backend frontend db caddy
sudo docker compose exec db pg_isready -U a1 -d a1
sudo docker compose exec db psql -U a1 -d a1 -c 'SELECT count(*) FROM inspections;'
```

Em 5 de novembro de 2026, a URL pública respondeu HTTP 200, e API e PostgreSQL estavam `UP`. A VM ainda executava a versão anterior, na qual `i8-subscriber` aparecia como `SIMULATED`. Atualize a `main`, configure `KAFKA_BROKER_URL` e repita a verificação para concluir o deploy Kafka.
