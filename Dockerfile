# ══════════════════════════════════════════════════════════════
# 🎣 Fishing Bot v5.0 - Servidor Python FastAPI
# Dockerfile para deploy no EasyPanel ou qualquer plataforma Docker
# ══════════════════════════════════════════════════════════════

FROM python:3.11-slim

# Metadados
LABEL maintainer="Fishing Bot Team"
LABEL version="5.0.0"
LABEL description="Servidor de autenticação e gerenciamento com FastAPI, WebSocket e painel admin"

# Argumento de build para porta (padrão 8122)
ARG PORT=8122
ENV PORT=${PORT}

# Diretório de trabalho
WORKDIR /app

# Copiar requirements primeiro (cache de layers)
COPY requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do servidor
COPY server.py .
COPY action_sequences.py .
COPY action_builder.py .

# Copiar painel administrativo
COPY admin_panel.html .

# Criar diretório para banco de dados
RUN mkdir -p /app/data

# ✅ VOLUME PERSISTENTE: Garantir que banco não seja perdido em redeploy
VOLUME ["/app/data"]

# Expor porta
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen(f'http://localhost:{${PORT}}/health')"

# Comando para rodar o servidor
CMD ["python", "server.py"]
