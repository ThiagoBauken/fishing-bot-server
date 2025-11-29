# 🎣 Ultimate Fishing Bot v5.0 - Servidor de Autenticação

Sistema completo de autenticação com login/senha obrigatórios, recuperação de senha e painel admin web.

## 📋 Funcionalidades

### ✨ Sistema de Autenticação
- **Cadastro** - Primeira ativação da license key cria conta com login/senha
- **Login** - Autenticação com username/email + senha + license_key
- **Recuperação de Senha** - Código de 6 dígitos enviado por email
- **Validação Keymaster** - Integração automática para validar license keys
- **Anti-compartilhamento** - HWID binding impede uso em múltiplos PCs

### 📊 Estatísticas
- Estatísticas pessoais (total de peixes, ranking)
- TOP 5 mensal
- TOP 5 geral (all-time)

### 👨‍💼 Painel Admin
- Interface web completa
- Gerenciar usuários
- Resetar senhas
- Ativar/desativar contas
- Visualizar estatísticas globais

---

## 🚀 Instalação

### 1. Instalar Node.js
Baixe e instale Node.js v18+ em: https://nodejs.org

### 2. Instalar Dependências
```bash
cd server_auth
npm install
```

### 3. Configurar Variáveis de Ambiente
```bash
# Copiar arquivo de exemplo
copy .env.example .env

# Editar .env e configurar:
# - ADMIN_PASSWORD (senha do painel admin)
# - JWT_SECRET (chave secreta para tokens)
# - KEYMASTER_URL e PROJECT_ID (já configurados)
```

### 4. Inicializar Banco de Dados
```bash
npm run init-db
```

Isso cria o arquivo `fishing_bot_auth.db` com todas as tabelas e um usuário admin padrão.

### 5. Iniciar Servidor
```bash
# Modo produção
npm start

# Modo desenvolvimento (auto-reload)
npm run dev
```

Servidor estará rodando em: **http://localhost:3000**

---

## 📡 Endpoints da API

### 🔐 Autenticação

#### **POST /auth/register** - Cadastro (primeira ativação)
**Request:**
```json
{
  "username": "meu_usuario",
  "email": "email@exemplo.com",
  "password": "senha123",
  "license_key": "ABC-123-XYZ",
  "hwid": "hardware_id_gerado",
  "pc_name": "MEU-PC"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Cadastro realizado com sucesso!",
  "token": "eyJhbGciOiJIUzI1...",
  "user": {
    "id": 1,
    "username": "meu_usuario",
    "email": "email@exemplo.com",
    "license_key": "ABC-123-XYZ"
  }
}
```

---

#### **POST /auth/login** - Login
**Request:**
```json
{
  "username": "meu_usuario",
  "password": "senha123",
  "license_key": "ABC-123-XYZ",
  "hwid": "hardware_id_gerado",
  "pc_name": "MEU-PC"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Login realizado com sucesso!",
  "token": "eyJhbGciOiJIUzI1...",
  "user": {
    "id": 1,
    "username": "meu_usuario",
    "email": "email@exemplo.com",
    "license_key": "ABC-123-XYZ"
  }
}
```

---

#### **POST /auth/request-reset** - Solicitar código de recuperação
**Request:**
```json
{
  "identifier": "email@exemplo.com"  // ou license_key
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Código de recuperação enviado!",
  "debug_code": "123456"  // apenas em desenvolvimento
}
```

---

#### **POST /auth/reset-password** - Resetar senha com código
**Request:**
```json
{
  "code": "123456",
  "new_password": "nova_senha123"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Senha resetada com sucesso!"
}
```

---

### 📊 Estatísticas

#### **GET /api/stats/:license_key** - Estatísticas do usuário
**Response (200):**
```json
{
  "success": true,
  "username": "meu_usuario",
  "email": "email@exemplo.com",
  "total_fish": 1234,
  "month_fish": 567,
  "rank_monthly": 3,
  "rank_alltime": 5,
  "member_since": "2025-01-15T10:30:00Z"
}
```

---

#### **GET /api/ranking/monthly** - TOP 5 do mês
**Response (200):**
```json
{
  "success": true,
  "month_year": "2025-01",
  "month_start": "2025-01-01",
  "month_end": "2025-01-31",
  "ranking": [
    {"rank": 1, "username": "usuario1", "month_fish": 1000},
    {"rank": 2, "username": "usuario2", "month_fish": 800},
    ...
  ]
}
```

---

#### **GET /api/ranking/alltime** - TOP 5 geral
**Response (200):**
```json
{
  "success": true,
  "ranking": [
    {"rank": 1, "username": "usuario1", "total_fish": 5000},
    {"rank": 2, "username": "usuario2", "total_fish": 4200},
    ...
  ]
}
```

---

## 👨‍💼 Painel Admin

### Acessar Painel
1. Abrir navegador em: **http://localhost:3000/admin**
2. Digitar senha de admin (padrão: `admin123`)
3. **⚠️ ALTERE A SENHA PADRÃO IMEDIATAMENTE EM PRODUÇÃO!**

### Funcionalidades do Painel
- ✅ Ver lista de todos os usuários
- ✅ Resetar senha de qualquer usuário
- ✅ Ativar/desativar contas
- ✅ Ver estatísticas globais (total de usuários, peixes, etc.)

---

## 🗄️ Banco de Dados (SQLite)

### Tabelas Criadas

#### **users**
- `id` - ID único
- `username` - Username (único)
- `email` - Email (único)
- `password_hash` - Hash bcrypt da senha
- `license_key` - License key (único)
- `hwid` - Hardware ID (anti-compartilhamento)
- `pc_name` - Nome do PC
- `created_at` - Data de cadastro
- `last_login` - Último login
- `is_active` - Conta ativa (1) ou desativada (0)
- `is_admin` - Administrador (1) ou usuário comum (0)

#### **password_resets**
- `id` - ID único
- `user_id` - ID do usuário
- `reset_code` - Código de recuperação (6 dígitos)
- `expires_at` - Expiração (1 hora)
- `used` - Código foi usado (0/1)
- `created_at` - Data de criação

#### **fishing_stats**
- `id` - ID único
- `user_id` - ID do usuário
- `license_key` - License key
- `total_fish` - Total de peixes pescados
- `month_fish` - Peixes no mês atual
- `month_year` - Mês/ano (YYYY-MM)
- `last_updated` - Última atualização

#### **sessions** (opcional)
- `id` - ID único
- `user_id` - ID do usuário
- `token` - JWT token
- `created_at` - Data de criação
- `expires_at` - Expiração
- `is_valid` - Token válido (1) ou invalidado (0)

---

## 🔒 Segurança

### Proteções Implementadas
- ✅ **Bcrypt** - Hashing seguro de senhas (salt rounds: 10)
- ✅ **JWT Tokens** - Autenticação stateless (expiração: 30 dias)
- ✅ **Rate Limiting** - Proteção contra brute force
  - Autenticação: 10 tentativas / 15 minutos
  - Recuperação: 3 solicitações / 1 hora
- ✅ **HWID Binding** - Anti-compartilhamento de contas
- ✅ **Helmet.js** - Headers de segurança HTTP
- ✅ **CORS** - Controle de origem das requisições
- ✅ **Validação de Inputs** - Validação de email, senha, etc.

### ⚠️ **IMPORTANTE - PRODUÇÃO**
1. **Altere `ADMIN_PASSWORD`** no arquivo `.env`
2. **Altere `JWT_SECRET`** para uma chave longa e aleatória
3. **Configure CORS** para permitir apenas domínios confiáveis
4. **Configure HTTPS** (use Nginx/Apache como reverse proxy)
5. **Faça backup** do arquivo `fishing_bot_auth.db` regularmente

---

## 📧 Recuperação de Senha (Email)

### Configuração SMTP (Opcional)
Para enviar códigos de recuperação por email, configure no `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASS=sua-senha-de-app
EMAIL_FROM=noreply@fishingbot.com
```

**Nota:** Se não configurado, os códigos aparecerão apenas no console do servidor (útil para desenvolvimento).

---

## 🐛 Troubleshooting

### Erro: "Cannot find module 'better-sqlite3'"
```bash
npm install
```

### Erro: "Port 3000 is already in use"
Altere a porta no arquivo `.env`:
```env
PORT=8080
```

### Erro: "EACCES: permission denied"
Execute com permissões de administrador ou mude o diretório de trabalho.

### Resetar banco de dados
```bash
# Deletar banco e recriar
del fishing_bot_auth.db
npm run init-db
```

---

## 📞 Suporte

Para problemas ou dúvidas:
1. Verifique os logs do servidor no console
2. Confira o arquivo `.env`
3. Teste os endpoints com Postman ou Insomnia

---

## 📜 Licença
MIT License - Livre para uso pessoal e comercial

---

**🎣 Desenvolvido para Ultimate Fishing Bot v5.0**
