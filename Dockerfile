# Imagem do A1 com dois alvos:
#   tests    -> valida os contratos 6c e roda os testes Python e do frontend
#   frontend -> serve frontend/ e shared/ por HTTP (alvo padrão)

# ---------- tests ----------
# Node 22 (runner nativo aceita glob em --test) + Python 3.11 do Debian Bookworm
FROM node:22-bookworm-slim AS tests

# Evita a criacao de ficheiros .pyc dentro do contentor
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Garante que a raiz /app esta no caminho de importação do Python
ENV PYTHONPATH=/app
# O venv isola as dependencias do Python do sistema (PEP 668)
ENV PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv

WORKDIR /app

# Copia e instala as dependencias antes do codigo para aproveitar o cache
COPY requirements-contracts.txt .
RUN pip install --no-cache-dir -r requirements-contracts.txt

COPY . .

CMD ["sh", "-c", "python scripts/validate_contracts.py && python -m pytest -q && npm test"]

# ---------- frontend ----------
FROM nginx:1.27-alpine AS frontend

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# O frontend carrega os JSON de shared/ por caminho relativo à raiz do
# repositório, então os dois diretórios mantêm a mesma estrutura de pastas
COPY frontend/ /usr/share/nginx/html/frontend/
COPY shared/ /usr/share/nginx/html/shared/

EXPOSE 80
