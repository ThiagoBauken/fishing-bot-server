# 🔐 Fluxo de Reset de Senha pelo Admin

## Visão Geral

Este documento explica **passo a passo** como funciona o reset de senha quando o administrador reseta a senha de um usuário pelo painel admin.

---

## 🎯 Cenário

**Situação:** Um usuário esqueceu a senha e pediu ajuda ao administrador.

**Solução:** O admin reseta a senha pelo painel admin, e o usuário faz login com a nova senha.

---

## 📋 Passo a Passo Completo

### 1️⃣ Admin Acessa o Painel

1. Abrir navegador em: **http://localhost:3000/admin**
2. Digitar senha de admin (padrão: `admin123`)
3. Painel admin é exibido

---

### 2️⃣ Admin Localiza o Usuário

1. Na lista de usuários, encontrar o usuário que precisa resetar a senha
2. Verificar informações:
   - **ID:** Número único do usuário
   - **Username:** Nome de usuário
   - **Email:** Email do usuário
   - **License Key:** Chave de licença ativa

---

### 3️⃣ Admin Reseta a Senha

1. Clicar no botão **"Resetar Senha"** ao lado do usuário
2. **Dialog aparece solicitando:**
   - Nova senha (mínimo 6 caracteres)
   - Confirmação da nova senha
3. Admin digita a nova senha (exemplo: `NovaSenh@123`)
4. Clicar em **"Confirmar"**

**O que acontece no servidor:**

```javascript
// Endpoint: POST /admin/api/reset-password
// Payload: { user_id: 5, new_password: "NovaSenh@123" }

1. Servidor valida se usuário existe
2. Servidor cria hash bcrypt da nova senha
3. Servidor atualiza o campo password_hash no banco de dados
4. Retorna sucesso
```

**Resultado:** Senha foi alterada no banco de dados. O usuário **NÃO precisa recadastrar**.

---

### 4️⃣ Admin Informa o Usuário

O admin deve informar o usuário sobre a nova senha através de:
- WhatsApp
- Discord
- Telegram
- Email
- Qualquer outro canal de comunicação

**Mensagem sugerida:**
```
Olá [NOME]!

Sua senha foi resetada com sucesso.

🔑 Nova senha: NovaSenh@123

Por favor, faça login no bot com:
- Username: [USERNAME_DELE]
- Senha: NovaSenh@123
- License Key: [LICENSE_KEY_DELE]

Recomendamos que você altere a senha após fazer login.
```

---

### 5️⃣ Usuário Faz Login com a Nova Senha

**O usuário NÃO PRECISA RECADASTRAR! Apenas fazer login.**

1. Usuário abre o bot (FishingMageBOT.exe)
2. **Tela de autenticação aparece com 3 abas:**
   - 🔑 **Login** ← Usuário seleciona esta aba
   - 📝 Cadastro
   - 🔄 Recuperar Senha

3. Usuário preenche na aba **Login**:
   - **Email ou Username:** [USERNAME_DELE]
   - **Senha:** NovaSenh@123 (nova senha definida pelo admin)
   - **License Key:** [LICENSE_KEY_DELE]
   - ✅ **Manter conectado:** (marcar para não precisar digitar novamente)

4. Clicar em **"Entrar"**

**O que acontece:**

```
1. Cliente envia credenciais para servidor de auth:
   POST http://localhost:3000/auth/login
   {
     "username": "USERNAME_DELE",
     "password": "NovaSenh@123",
     "license_key": "LICENSE_KEY",
     "hwid": "HARDWARE_ID",
     "pc_name": "PC_DO_USUARIO"
   }

2. Servidor valida:
   - Username existe? ✅
   - Senha bate com hash no banco? ✅ (hash da nova senha)
   - License key válida no Keymaster? ✅
   - HWID corresponde? ✅

3. Servidor retorna:
   {
     "success": true,
     "token": "JWT_TOKEN",
     "user": { ... }
   }

4. Cliente salva credenciais localmente (se "Manter conectado" marcado)
5. Bot inicia normalmente
```

---

## ✅ Resumo do Fluxo

| Etapa | Quem | O que faz |
|-------|------|-----------|
| 1 | Admin | Acessa painel admin |
| 2 | Admin | Encontra usuário na lista |
| 3 | Admin | Reseta senha definindo nova senha |
| 4 | Servidor | Atualiza `password_hash` no banco de dados |
| 5 | Admin | Informa nova senha ao usuário (WhatsApp/Discord/etc.) |
| 6 | Usuário | Abre o bot e vai na aba **Login** |
| 7 | Usuário | Digita username + nova senha + license key |
| 8 | Servidor | Valida credenciais (nova senha) |
| 9 | Cliente | Salva credenciais localmente |
| 10 | Bot | Inicia normalmente |

---

## ⚠️ Importante

### O Usuário NÃO Precisa Recadastrar!

- ❌ **ERRADO:** "O usuário precisa ir na aba Cadastro e recadastrar"
- ✅ **CORRETO:** "O usuário vai na aba Login e faz login com a nova senha"

### Por Que Não Precisa Recadastrar?

Porque o **cadastro** só é feito **UMA VEZ** na primeira ativação da license key. Quando o admin reseta a senha, ele está **apenas alterando a senha**, não deletando a conta.

**Dados que permanecem os mesmos:**
- Username
- Email
- License Key
- ID do usuário
- HWID
- Estatísticas de pesca

**Único dado alterado:**
- `password_hash` (hash da senha)

---

## 🔄 Diferença entre Reset de Senha e Recuperação de Senha

| Reset pelo Admin | Recuperação pelo Usuário |
|------------------|-------------------------|
| Admin define a nova senha | Usuário define a nova senha |
| Admin informa a senha ao usuário | Usuário recebe código por email |
| Usado quando usuário não tem acesso ao email | Usado quando usuário tem acesso ao email |
| Aba: **Login** (após receber nova senha) | Aba: **Recuperar Senha** (solicitar código) |

---

## 📞 Casos de Uso

### Caso 1: Usuário esqueceu a senha e não tem acesso ao email
**Solução:** Admin reseta a senha pelo painel e informa a nova senha ao usuário

### Caso 2: Usuário esqueceu a senha mas tem acesso ao email
**Solução:** Usuário usa a aba **Recuperar Senha** no bot para receber código por email

### Caso 3: Usuário deseja trocar a senha
**Solução:** Usuário usa a aba **Recuperar Senha** ou pede ao admin para resetar

---

## 🛡️ Segurança

### O que o Admin pode ver?
- ✅ Username
- ✅ Email
- ✅ License Key
- ✅ HWID (parcialmente ofuscado)
- ✅ Estatísticas de pesca
- ❌ **Senha do usuário (NUNCA é exibida!)**

### O que o Admin pode fazer?
- ✅ Resetar senha (definir nova senha)
- ✅ Ativar/desativar conta
- ✅ Deletar usuário
- ✅ Atualizar license key (quando expirar)
- ❌ **Ver a senha atual do usuário**

### Como a senha é armazenada?
```javascript
// Senha NUNCA é salva em texto puro!
// Sempre é salvo o hash bcrypt:

password_hash = bcrypt.hashSync('NovaSenh@123', 10)
// Resultado: $2a$10$N9qo8uLOickgx2ZMRZoMyeIjZAgcfl7p92ldGxad68LJZdL17lhWy

// Este hash é irreversível. Não há como "descriptografar" para obter a senha original.
```

---

## 📊 Fluxograma Visual

```
┌─────────────────┐
│ Usuário esqueceu│
│     senha       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Admin acessa   │
│  painel admin   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Admin encontra  │
│    usuário      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Admin reseta   │
│     senha       │
│ (Nova: XYZ123)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Servidor       │
│  atualiza hash  │
│  no banco       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Admin informa  │
│  nova senha ao  │
│    usuário      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Usuário abre   │
│      bot        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Usuário vai    │
│  aba LOGIN      │
│  (NÃO CADASTRO!)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Usuário digita:│
│  - Username     │
│  - Nova senha   │
│  - License Key  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Servidor       │
│  valida e       │
│  retorna token  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Bot inicia     │
│  normalmente    │
└─────────────────┘
```

---

## 🎓 Exemplo Prático

**Situário Real:**

```
📞 Usuário: "Ei admin, esqueci minha senha, me ajuda?"

👨‍💼 Admin:
1. Acessa http://localhost:3000/admin
2. Procura pelo username do usuário: "joaopescador"
3. Clica em "Resetar Senha"
4. Define nova senha: "PeixeGrande2025"
5. Confirma

💬 Admin envia mensagem ao usuário:
   "Sua senha foi resetada! Nova senha: PeixeGrande2025
    Faça LOGIN (não cadastro) com seu username e essa senha."

🎣 Usuário:
1. Abre FishingMageBOT.exe
2. Vai na aba LOGIN
3. Digita:
   - Email/Username: joaopescador
   - Senha: PeixeGrande2025
   - License Key: ABC-123-XYZ
   - ✅ Manter conectado
4. Clica "Entrar"
5. ✅ Bot inicia normalmente!
```

---

## 📚 Endpoints Envolvidos

### Admin reseta senha:
```http
POST /admin/api/reset-password
Headers:
  admin_password: admin123

Body:
{
  "user_id": 5,
  "new_password": "NovaSenh@123"
}

Response:
{
  "success": true,
  "message": "Senha resetada para joaopescador"
}
```

### Usuário faz login com nova senha:
```http
POST /auth/login

Body:
{
  "username": "joaopescador",
  "password": "NovaSenh@123",
  "license_key": "ABC-123-XYZ",
  "hwid": "HARDWARE_ID",
  "pc_name": "PC_DO_JOAO"
}

Response:
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 5,
    "username": "joaopescador",
    "email": "joao@email.com",
    "license_key": "ABC-123-XYZ"
  }
}
```

---

## ✅ Checklist para Admin

Quando um usuário pede reset de senha:

- [ ] Acesso painel admin
- [ ] Encontrei o usuário na lista
- [ ] Resetei a senha definindo nova senha forte
- [ ] Informei a nova senha ao usuário (WhatsApp/Discord/Telegram)
- [ ] **IMPORTANTE:** Avisei ao usuário para ir na aba **LOGIN** (não Cadastro)
- [ ] Confirmei que o usuário conseguiu fazer login com sucesso

---

## 🆘 Troubleshooting

### Usuário não consegue fazer login após reset

**Possíveis causas:**

1. **Usuário está tentando CADASTRAR ao invés de FAZER LOGIN**
   - Solução: Orientar usuário a ir na aba **Login**

2. **Usuário está digitando a senha antiga ao invés da nova**
   - Solução: Confirmar que usuário está usando a senha que o admin definiu

3. **License Key incorreta**
   - Solução: Verificar se license key não expirou

4. **HWID diferente (tentando usar em outro PC)**
   - Solução: Admin pode atualizar HWID ou transferir licença

---

**📅 Última atualização:** 2025-01-29
