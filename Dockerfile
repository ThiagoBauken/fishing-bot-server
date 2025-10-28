# Dockerfile para Fishing Bot Server
# Deploy no EasyPanel ou qualquer plataforma Docker

FROM python:3.11-slim

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

# Expor porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Comando para rodar
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
