# Imagem do A1 com três alvos:
#   tests    -> valida os contratos 6c e roda os testes Python e do frontend
#   backend  -> API v1 do A1 (FastAPI + PostgreSQL)
#   frontend -> serve frontend/ e shared/ por HTTP e repassa /api/ ao backend
#               (alvo padrão)

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
COPY requirements-contracts.txt requirements-backend.txt requirements-tests.txt ./
RUN pip install --no-cache-dir -r requirements-tests.txt

COPY . .

CMD ["sh", "-c", "python scripts/validate_contracts.py && python -m pytest -q && npm test"]

# ---------- backend ----------
FROM python:3.11-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt

# Schemas, taxonomia e política em shared/ são lidos em tempo de execução
COPY backend/ backend/
COPY shared/ shared/

RUN useradd --system --uid 10001 a1
USER a1

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import json,sys,urllib.request; response=urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2); sys.exit(json.load(response).get('status') != 'ONLINE')"

CMD ["uvicorn", "backend.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

# ---------- frontend ----------
FROM nginx:1.27-alpine AS frontend

# O entrypoint do nginx substitui ${A1_API_BASE} do template ao iniciar
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template

# O frontend carrega os JSON de shared/ por caminho relativo à raiz do
# repositório, então os dois diretórios mantêm a mesma estrutura de pastas
COPY frontend/ /usr/share/nginx/html/frontend/
COPY shared/ /usr/share/nginx/html/shared/

ENV A1_API_BASE=/api/v1

EXPOSE 80
