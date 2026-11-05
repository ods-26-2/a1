#!/bin/bash
# Script de boot da VM no GCP (metadata startup-script). Roda como root a cada
# boot: instala o que falta, atualiza o código e sobe o A1 com HTTPS.
set -euo pipefail

if ! command -v git >/dev/null; then
  apt-get update && apt-get install -y git
fi
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
if [ ! -d /opt/a1/.git ]; then
  git clone https://github.com/ods-26-2/a1.git /opt/a1
else
  git -C /opt/a1 pull --ff-only
fi

cd /opt/a1
umask 077
touch .env

set_env() {
  if grep -q "^$1=" .env; then
    sed -i "s|^$1=.*|$1=$2|" .env
  else
    echo "$1=$2" >> .env
  fi
}

# Senha e domínio só são gerados na primeira vez; edite o .env para trocar.
if ! grep -q '^POSTGRES_PASSWORD=' .env; then
  set_env POSTGRES_PASSWORD "$(openssl rand -hex 24)"
fi
if ! grep -q '^A1_DOMAIN=' .env; then
  ip=$(curl -fs -H Metadata-Flavor:Google \
    http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip)
  set_env A1_DOMAIN "${ip//./-}.sslip.io"
fi
set_env A1_PORT 127.0.0.1:5500
set_env COMPOSE_PROFILES https

# Na VM, o fallback local do Compose aponta para o próprio container.
# Preencha o broker B2 de testes sem sobrescrever um broker remoto configurado.
broker=$(sed -n 's/^KAFKA_BROKER_URL=//p' .env | tail -n 1)
case "$broker" in
  ""|localhost:9092|127.0.0.1:9092)
    set_env KAFKA_BROKER_URL 34.66.235.91:9093
    ;;
esac

docker compose up -d --build --remove-orphans
