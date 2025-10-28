# 🎣 Fishing Bot Server

Servidor multi-usuário simples para gerenciar licenças e lógica de decisão do Fishing Bot.

## 📋 Características

- ✅ Autenticação de usuários (email + license key)
- ✅ WebSocket para comunicação em tempo real
- ✅ Lógica de decisão (quando alimentar, limpar, dar break)
- ✅ SQLite (simples, sem necessidade de PostgreSQL)
- ✅ Multi-usuário (sessões isoladas)
- ✅ Deploy fácil (Docker + EasyPanel)

## 🚀 Deploy no EasyPanel

### 1. Fazer Upload do Código

```bash
# Criar repositório Git (se ainda não tiver)
cd server/
git init
git add .
git commit -m "Initial server setup"

# Push para GitHub
git remote add origin https://github.com/SEU_USUARIO/fishing-bot-server.git
git push -u origin main
```

### 2. Configurar no EasyPanel

1. **Login no EasyPanel** → Criar Novo Projeto
2. **Nome do projeto:** `fishing-bot-server`
3. **Tipo:** Custom Docker
4. **Repository:** `https://github.com/SEU_USUARIO/fishing-bot-server`
5. **Branch:** `main`
6. **Dockerfile Path:** `./Dockerfile`
7. **Port:** `8000`

### 3. Configurar Domínio

1. **Domain:** `fishing-server.seudominio.com`
2. **SSL:** ✅ Automático (Let's Encrypt)
3. **Protocol:** `HTTPS + WSS`

### 4. Deploy!

Clique em **Deploy** → EasyPanel vai:
- ✅ Clonar repositório
- ✅ Buildar Dockerfile
- ✅ Criar container
- ✅ Configurar SSL
- ✅ Expor na porta 8000

**URL Final:**
- HTTP: `https://fishing-server.seudominio.com`
- WebSocket: `wss://fishing-server.seudominio.com/ws`

---

## 🧪 Testar Localmente

### 1. Instalar Dependências

```bash
cd server/
pip install -r requirements.txt
```

### 2. Rodar Servidor

```bash
python server.py
```

Servidor estará rodando em:
- **HTTP:** `http://localhost:8000`
- **WebSocket:** `ws://localhost:8000/ws`

### 3. Testar Endpoints

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"teste@teste.com","license_key":"TEST-KEY-12345"}'
```

**Resposta esperada:**
```json
{
  "success": true,
  "message": "Login bem-sucedido!",
  "token": "teste@teste.com"
}
```

---

## 📡 Protocolo WebSocket

### Cliente → Servidor (Eventos)

```json
// Autenticação inicial
{
  "token": "teste@teste.com"
}

// Peixe capturado
{
  "event": "fish_caught"
}

// Feeding concluído
{
  "event": "feeding_done"
}

// Limpeza concluída
{
  "event": "cleaning_done"
}

// Heartbeat
{
  "event": "ping"
}
```

### Servidor → Cliente (Comandos)

```json
// Conexão estabelecida
{
  "type": "connected",
  "message": "Conectado ao servidor!",
  "fish_count": 0
}

// Comando: Alimentar
{
  "cmd": "feed",
  "params": {
    "clicks": 5
  }
}

// Comando: Limpar inventário
{
  "cmd": "clean"
}

// Comando: Dar break
{
  "cmd": "break",
  "duration_minutes": 45
}

// Resposta ao ping
{
  "type": "pong"
}
```

---

## 🗄️ Banco de Dados

### SQLite Schema

**Tabela: users**
```sql
CREATE TABLE users (
    email TEXT PRIMARY KEY,
    license_key TEXT NOT NULL,
    plan TEXT DEFAULT 'trial',
    expires_at TEXT,
    max_pcs INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Tabela: user_stats**
```sql
CREATE TABLE user_stats (
    email TEXT PRIMARY KEY,
    fish_count INTEGER DEFAULT 0,
    last_fish_time TEXT,
    session_start TEXT,
    FOREIGN KEY(email) REFERENCES users(email)
);
```

### Adicionar Usuário Manualmente

```bash
# Conectar ao banco
sqlite3 fishing_bot.db

# Inserir usuário
INSERT INTO users (email, license_key, plan, expires_at)
VALUES ('usuario@email.com', 'KEY-12345-ABCDE', 'premium', '2026-12-31');

# Ver usuários
SELECT * FROM users;

# Sair
.exit
```

---

## 🔧 Configuração

### Variáveis de Ambiente (Opcional)

Criar arquivo `.env`:
```env
# Porta do servidor
PORT=8000

# Log level
LOG_LEVEL=INFO

# Database path
DATABASE_PATH=fishing_bot.db
```

---

## 📊 Monitoramento

### Logs em Tempo Real (EasyPanel)

1. EasyPanel → Projeto → **Logs**
2. Ver logs em tempo real
3. Filtrar por erro/warning

### Estatísticas

**Ver usuários ativos:**
```bash
curl https://fishing-server.seudominio.com/
```

Resposta:
```json
{
  "service": "Fishing Bot Server",
  "version": "1.0.0",
  "status": "online",
  "active_users": 3
}
```

---

## 🔒 Segurança

### HTTPS/WSS

EasyPanel configura SSL automaticamente (Let's Encrypt).

### Rate Limiting (Futuro)

Para adicionar rate limiting:
```python
from slowapi import Limiter

limiter = Limiter(key_func=lambda: request.client.host)

@app.post("/auth/login")
@limiter.limit("5/minute")
async def login(...):
    ...
```

---

## 🐛 Troubleshooting

### Servidor não inicia

```bash
# Verificar logs
docker logs fishing-bot-server

# Verificar porta
netstat -an | findstr 8000
```

### WebSocket não conecta

1. **Verificar SSL:** WSS precisa de HTTPS
2. **Verificar CORS:** Domínio do cliente permitido?
3. **Verificar firewall:** Porta 8000 aberta?

### Banco de dados corrompido

```bash
# Backup
cp fishing_bot.db fishing_bot.db.backup

# Recriar
rm fishing_bot.db
python server.py  # Recria automaticamente
```

---

## 📝 Changelog

### v1.0.0 (2025-01-XX)
- ✅ Servidor básico com WebSocket
- ✅ Autenticação simples (email + key)
- ✅ Lógica de decisão (feeding, cleaning, break)
- ✅ SQLite database
- ✅ Deploy via Docker

---

## 📞 Suporte

- **Email:** suporte@seudominio.com
- **Discord:** https://discord.gg/seu-servidor

---

## 📄 Licença

Proprietary - Uso apenas autorizado com licença válida.
