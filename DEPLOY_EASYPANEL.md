# 🚀 GUIA COMPLETO: Deploy no EasyPanel

## ✅ PRÉ-REQUISITOS

1. **Conta EasyPanel** (gratuito): https://easypanel.io/
2. **Servidor VPS** (ex: DigitalOcean, Hetzner, Linode)
3. **Repositório GitHub** com código do servidor

---

## 📦 PASSO 1: Preparar Repositório GitHub

### 1.1. Criar Repositório

```bash
# Na pasta server/
cd C:\Users\Thiago\Desktop\v5\server

# Inicializar git
git init

# Adicionar arquivos
git add .

# Commit inicial
git commit -m "Initial commit: Multi-user fishing bot server"

# Criar repo no GitHub (https://github.com/new)
# Nome: fishing-bot-server
# Visibilidade: Private (recomendado)

# Adicionar remote
git remote add origin https://github.com/SEU-USUARIO/fishing-bot-server.git

# Push
git branch -M main
git push -u origin main
```

### 1.2. Verificar Arquivos Necessários

Certifique-se que o repositório tem:
```
fishing-bot-server/
├── server.py              ✅ Servidor FastAPI
├── Dockerfile             ✅ Docker config
├── requirements.txt       ✅ Dependências Python
├── .gitignore             ✅ Git ignore
└── README.md              ✅ Documentação
```

---

## 🖥️ PASSO 2: Configurar VPS

### 2.1. Criar VPS (exemplo: DigitalOcean)

**Recomendação mínima:**
- **CPU:** 1 vCPU
- **RAM:** 512 MB (até 100 usuários) | 1GB (até 500 usuários)
- **Storage:** 10 GB
- **OS:** Ubuntu 22.04 LTS
- **Custo:** ~$4-6/mês

**Criar Droplet:**
1. Acessar https://www.digitalocean.com/
2. Create → Droplets
3. Escolher região mais próxima dos usuários
4. Ubuntu 22.04 LTS
5. Basic Plan ($4/mês)
6. Criar

### 2.2. Instalar EasyPanel no VPS

**SSH no servidor:**
```bash
ssh root@SEU-IP-VPS
```

**Instalar EasyPanel:**
```bash
curl -sSL https://get.easypanel.io | sh
```

**Aguardar instalação** (~2-3 minutos)

**Resultado:**
```
✅ EasyPanel instalado com sucesso!
🌐 Acesse: http://SEU-IP-VPS:3000
```

---

## 🔧 PASSO 3: Configurar EasyPanel

### 3.1. Acessar Painel

1. Abrir navegador: `http://SEU-IP-VPS:3000`
2. Criar senha de admin
3. Login

### 3.2. Criar Projeto

1. **New Project** → Nome: `fishing-bot`
2. Click no projeto criado

### 3.3. Adicionar App

1. **Create** → **App**
2. Tipo: **GitHub**
3. Conectar conta GitHub
4. Selecionar repositório: `fishing-bot-server`
5. Branch: `main`

---

## 📝 PASSO 4: Configurar Deploy

### 4.1. Build Settings

**General:**
- **Name:** fishing-bot-server
- **Source:** GitHub
- **Repository:** seu-usuario/fishing-bot-server
- **Branch:** main

**Build:**
- **Build Type:** Dockerfile
- **Dockerfile Path:** ./Dockerfile
- **Context:** ./

**Environment Variables** (opcional):
```
LOG_LEVEL=INFO
```

### 4.2. Deploy Settings

**Port:**
- **Port:** 8000 (igual no Dockerfile)

**Domain:**
- **Subdomain:** fishing-server (ou nome desejado)
- **Domain:** easypanel.host (automático)
- **SSL:** ✅ Enable (Let's Encrypt automático)

**Resultado:** `https://fishing-server.easypanel.host`

### 4.3. Resources

- **CPU:** 0.5 (metade de 1 core)
- **Memory:** 512 MB
- **Storage:** 1 GB (para banco SQLite)

---

## 🚀 PASSO 5: Deploy!

1. Click em **Deploy**
2. Aguardar build (~2-3 minutos)

**Log esperado:**
```
Building...
[+] Building 45.3s
Successfully built abc123def456
Deploying...
✅ Deploy successful!
```

3. Verificar status: **Running** ✅

---

## ✅ PASSO 6: Testar Servidor

### 6.1. Teste Health Check

```bash
curl https://fishing-server.easypanel.host
```

**Resposta esperada:**
```json
{
  "service": "Fishing Bot Server",
  "version": "1.0.0",
  "status": "online",
  "active_users": 0
}
```

✅ **Funcionou?** Servidor online!

### 6.2. Teste Autenticação

```bash
curl -X POST https://fishing-server.easypanel.host/auth/activate \
  -H "Content-Type: application/json" \
  -d '{"license_key":"TEST-KEY-12345","hwid":"test-hwid-123","pc_name":"TestPC"}'
```

**Resposta esperada:**
```json
{
  "success": true,
  "message": "Licença ativada com sucesso!",
  "token": "user_TEST-KEY-12345",
  "email": "user_TEST-KEY-12345"
}
```

✅ **Funcionou?** Servidor autenticando!

---

## 🔐 PASSO 7: Adicionar Usuários (License Keys)

### 7.1. Acessar Terminal do Container

**No EasyPanel:**
1. Abrir app `fishing-bot-server`
2. **Terminal** (ícone de terminal)
3. Abre shell dentro do container

### 7.2. Adicionar Usuário no Banco

```bash
# Entrar no Python
python3

# Executar
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("/app/fishing_bot.db")
cursor = conn.cursor()

# Adicionar nova license key
cursor.execute("""
    INSERT INTO users (email, license_key, plan, expires_at)
    VALUES (?, ?, ?, ?)
""", (
    "cliente@email.com",
    "SUA-LICENSE-KEY-AQUI",
    "premium",
    (datetime.now() + timedelta(days=365)).isoformat()  # Expira em 1 ano
))

conn.commit()
conn.close()

print("✅ Usuário adicionado!")
exit()
```

### 7.3. Verificar Usuário Adicionado

```bash
# No terminal do container
sqlite3 /app/fishing_bot.db

# Query
SELECT email, license_key, plan, expires_at FROM users;

# Sair
.quit
```

---

## 🔄 PASSO 8: Atualizar Cliente para Produção

### 8.1. Editar main.py

```python
# main.py linha 208
server_url = "wss://fishing-server.easypanel.host/ws"  # ← Trocar!
```

### 8.2. Build .exe Atualizado

```bash
pyinstaller --onefile --windowed main.py
```

**Resultado:** `dist/main.exe` conecta ao servidor de produção!

---

## 📊 PASSO 9: Monitoramento

### 9.1. Ver Logs

**EasyPanel:**
1. App → **Logs**
2. Ver em tempo real

**Logs importantes:**
```
🟢 Cliente conectado: cliente@email.com
🐟 cliente@email.com: Peixe #1 capturado!
🍖 cliente@email.com: Enviando comando de feeding
✅ HWID válido: cliente@email.com
```

### 9.2. Métricas

**EasyPanel:**
- **Metrics** → Ver CPU/RAM/Network

**Alertas:**
- CPU > 80% → Aumentar resources
- RAM > 80% → Aumentar memória

---

## 🔒 SEGURANÇA

### 1. Firewall

EasyPanel já configura automaticamente:
- ✅ Porta 80 (HTTP)
- ✅ Porta 443 (HTTPS)
- ✅ Porta 8000 (WebSocket)

### 2. SSL/TLS

- ✅ Automático (Let's Encrypt)
- ✅ Renovação automática

### 3. Backup

**Backup do banco SQLite:**

1. **No EasyPanel → Terminal:**
```bash
# Copiar banco
cp /app/fishing_bot.db /tmp/backup_$(date +%Y%m%d).db

# Download via SFTP ou:
cat /tmp/backup_*.db | base64
```

2. **Agendar backup automático** (opcional):
```bash
# Criar cron job
crontab -e

# Adicionar (backup diário às 3am)
0 3 * * * cp /app/fishing_bot.db /backups/fishing_bot_$(date +\%Y\%m\%d).db
```

---

## ❓ TROUBLESHOOTING

### Problema 1: Deploy falhou

**Erro:** `Build failed`

**Solução:**
1. Verificar logs de build
2. Conferir Dockerfile
3. Testar build local:
```bash
docker build -t fishing-bot-server .
docker run -p 8000:8000 fishing-bot-server
```

### Problema 2: WebSocket não conecta

**Erro:** `Connection refused`

**Solução:**
1. Verificar porta 8000 está exposta
2. Conferir URL: deve ser `wss://` (não `ws://`)
3. Testar health check primeiro

### Problema 3: Banco de dados vazio

**Solução:**
1. Container recriado? Banco foi perdido!
2. Adicionar volume permanente:
   - EasyPanel → App → **Volumes**
   - Mount path: `/app`
   - Isso persiste o banco entre deploys

### Problema 4: Alta latência

**Solução:**
1. Escolher VPS em região mais próxima dos usuários
2. Aumentar CPU/RAM do servidor
3. Verificar logs para erros

---

## 💰 CUSTOS ESTIMADOS

| Usuários | VPS | Custo/mês |
|----------|-----|-----------|
| 1-100 | 512MB RAM, 1 vCPU | $4-6 |
| 100-500 | 1GB RAM, 1 vCPU | $6-12 |
| 500-1000 | 2GB RAM, 2 vCPU | $12-24 |
| 1000+ | 4GB RAM, 4 vCPU | $24-48 |

**+ Domínio próprio (opcional):** ~$10/ano

---

## ✅ CHECKLIST FINAL

Antes de começar a vender:

- [ ] Servidor deployado no EasyPanel
- [ ] HTTPS funcionando (SSL válido)
- [ ] Health check retornando 200
- [ ] Autenticação funcionando
- [ ] HWID bloqueando compartilhamento
- [ ] License key de teste funcionando
- [ ] Cliente .exe conectando ao servidor
- [ ] Logs monitorados
- [ ] Backup configurado

---

## 🎉 PRONTO!

Agora você tem:
- ✅ Servidor rodando 24/7 na nuvem
- ✅ SSL automático
- ✅ HWID anti-compartilhamento
- ✅ Multi-usuário isolado
- ✅ Escalável

**Próximo passo:** Vender! 💰

**URL final do servidor:**
```
wss://fishing-server.easypanel.host/ws
```

**Para adicionar usuários:**
1. Entrar no terminal do EasyPanel
2. Executar SQL (Passo 7.2)
3. Distribuir license key ao cliente
