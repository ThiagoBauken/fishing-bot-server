# ══════════════════════════════════════════════════════════════
# 🎣 Fishing Bot v5.0 - Servidor de Autenticação Node.js
# Dockerfile para deploy no EasyPanel ou qualquer plataforma Docker
# ══════════════════════════════════════════════════════════════

FROM node:18-alpine

# Metadados
LABEL maintainer="Fishing Bot Team"
LABEL version="5.0.0"
LABEL description="Servidor de autenticação com JWT, admin panel e stats"

# Argumento de build para porta (padrão 3000)
ARG PORT=3000
ENV PORT=${PORT}

# Variável de ambiente para produção
ENV NODE_ENV=production

# Diretório de trabalho
WORKDIR /app

# Copiar package.json e package-lock.json primeiro (cache de layers)
COPY package*.json ./

# Instalar dependências de produção
RUN npm ci --only=production

# Copiar todo o código do servidor
COPY server.js .
COPY database.js .
COPY auth-routes.js .
COPY admin-routes.js .
COPY stats-routes.js .
COPY ws-handler.js .

# Copiar painel administrativo
COPY admin-panel/ ./admin-panel/

# Criar diretório para banco de dados
RUN mkdir -p /app/data

# Expor porta
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:${process.env.PORT || 3000}/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

# Comando para rodar o servidor
CMD ["node", "server.js"]
