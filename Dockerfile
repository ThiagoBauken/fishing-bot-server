# Dockerfile para Fishing Bot Server
# Deploy no EasyPanel ou qualquer plataforma Docker

FROM python:3.11-slim

# Argumento de build para porta (padrão 8122)
ARG PORT=8122
ENV PORT=${PORT}

# Diretório de trabalho
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY server.py .

# Criar diretório para banco de dados
RUN mkdir -p /app/data

# Expor porta (usa variável de ambiente)
EXPOSE ${PORT}

# Health check (usa variável de ambiente)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8122\")}/health')"

# Comando para rodar (usa python server.py que lê do .env)
CMD ["python", "server.py"]
