# 🚀 GUIA: Configurar Variáveis de Ambiente no EasyPanel

## 🔴 PROBLEMA IDENTIFICADO

Você está tendo erro de autenticação no painel admin porque:

1. **Arquivo `.env` NÃO é copiado para o container Docker** (por segurança, está no `.dockerignore`)
2. **Senha com `#` no `.env` local é truncada** (caractere `#` inicia comentários)

**Resultado:** Servidor não tem a senha correta configurada

---

## ✅ SOLUÇÃO: Configurar no EasyPanel

### Passo 1: Acessar Configurações do App

1. Abrir EasyPanel: `http://seu-ip-vps:3000`
2. Navegar para o projeto: `fishing-bot`
3. Click no app: `fishing-bot-server`
4. Click na aba: **Environment** (ou **Variables**)

### Passo 2: Adicionar Variáveis de Ambiente

**Adicionar as seguintes variáveis:**

```
ADMIN_PASSWORD=AdminPesca2025Seguro
```

**OU se quiser manter caracteres especiais, use aspas:**

```
ADMIN_PASSWORD="Admin#Pesca#2025!Seguro"
```

**⚠️ IMPORTANTE:** No EasyPanel, você NÃO precisa de aspas. Basta digitar:
- **Name:** `ADMIN_PASSWORD`
- **Value:** `AdminPesca2025Seguro` (SEM aspas, SEM `#`)

**Outras variáveis importantes (já devem estar configuradas):**

```
PORT=8122
KEYMASTER_URL=https://private-keygen.pbzgje.easypanel.host
PROJECT_ID=67a4a76a-d71b-4d07-9ba8-f7e794ce0578
LOG_LEVEL=INFO
```

### Passo 3: Salvar e Redesployar

1. Click em **Save**
2. Click em **Deploy** (ou aguardar auto-deploy)
3. Aguardar build (~2-3 minutos)

### Passo 4: Verificar Logs

1. No EasyPanel, abrir **Logs** do app
2. Procurar pela linha:

```
🔑 ADMIN_PASSWORD configurada: Admi... (total: 21 caracteres)
```

**✅ Se mostrar 21 caracteres** = senha completa carregada!
**❌ Se mostrar 5 caracteres** = ainda está lendo apenas "Admin"

---

## 🧪 TESTE DE AUTENTICAÇÃO

### Opção 1: Pelo Navegador

1. Abrir: `https://private-serverpesca.pbzgje.easypanel.host/admin`
2. Digitar senha: `AdminPesca2025Seguro` (ou a que você configurou)
3. Click em **Login**

**✅ Sucesso:** Você verá o painel com lista de usuários

### Opção 2: Por cURL (Terminal)

```bash
# Testar autenticação
curl -X GET "https://private-serverpesca.pbzgje.easypanel.host/admin/api/stats" \
  -H "admin_password: AdminPesca2025Seguro"
```

**Resposta esperada (sucesso):**
```json
{
  "success": true,
  "stats": {
    "total_users": 0,
    "active_users": 0,
    "total_fish": 0,
    "month_fish": 0,
    "server_version": "2.0.0",
    "keymaster_url": "https://private-keygen.pbzgje.easypanel.host"
  }
}
```

**Resposta erro 401 (senha incorreta):**
```json
{
  "detail": "Senha de admin inválida"
}
```

---

## 🔐 RECOMENDAÇÕES DE SENHA

### ✅ Senhas SEGURAS (funcionam sem problemas):

- `AdminPesca2025Seguro` (sem caracteres especiais)
- `MyStrongPassword123` (letras + números)
- `FishingBotAdmin2025` (alfanumérico)

### ⚠️ Senhas PROBLEMÁTICAS (evitar em .env):

- `Admin#Pesca#2025!Seguro` (contém `#` = comentário)
- `password=123` (contém `=` = problema de parsing)
- `senha "com aspas"` (aspas podem causar problemas)

### 🛡️ Senha FORTE recomendada:

```
AdminPescaBotSecure2025XYZ
```

- 26 caracteres
- Maiúsculas e minúsculas
- Números
- SEM caracteres especiais problemáticos

---

## 📋 CHECKLIST DE VERIFICAÇÃO

- [ ] Variável `ADMIN_PASSWORD` configurada no EasyPanel
- [ ] Senha SEM caractere `#` (ou com aspas)
- [ ] App redesployado após configurar variável
- [ ] Logs mostram senha com tamanho correto (não 5 caracteres)
- [ ] Login no `/admin` funcionando
- [ ] API `/admin/api/stats` respondendo sem erro 401

---

## 🆘 TROUBLESHOOTING

### Problema: Ainda dá erro 401 após configurar

**Solução:**
1. Verificar se salvou a variável no EasyPanel
2. Verificar se redesployou o app (não basta salvar, precisa rebuild)
3. Checar logs para ver qual senha está sendo carregada
4. Testar com senha simples primeiro: `admin123`

### Problema: Não encontro onde adicionar variáveis no EasyPanel

**Solução:**
1. No painel do app, procurar por:
   - "Environment Variables"
   - "Env Vars"
   - "Variables"
   - Ícone de engrenagem ⚙️ → Environment
2. Se não encontrar, consultar docs: https://easypanel.io/docs

### Problema: Senha funciona local mas não no EasyPanel

**Motivo:** Arquivo `.env` NÃO é copiado para Docker!
**Solução:** Configurar variável direto no EasyPanel (não usar `.env`)

---

## 📝 DIFERENÇAS: Local vs EasyPanel

| Aspecto | Local (desenvolvimento) | EasyPanel (produção) |
|---------|------------------------|----------------------|
| **Config** | Arquivo `.env` | Variáveis de ambiente no painel |
| **Segurança** | `.env` no `.gitignore` | Variáveis criptografadas |
| **Atualização** | Editar `.env` + restart | Editar variável + redeploy |
| **Backup** | Arquivo local | Gerenciado pelo EasyPanel |

---

## ✅ PRÓXIMOS PASSOS

Depois de configurar a senha no EasyPanel:

1. **Testar login** em `https://private-serverpesca.pbzgje.easypanel.host/admin`
2. **Documentar senha** em local seguro (gerenciador de senhas)
3. **Alterar senha default** para algo único e forte
4. **Configurar backup** do banco de dados (ver `DEPLOY_EASYPANEL.md`)

---

## 🎯 RESUMO

**Problema:**
```
ADMIN_PASSWORD=Admin#Pesca#2025!Seguro  ❌ (# = comentário)
└─> Senha lida: "Admin" (5 chars)
```

**Solução:**
```
No EasyPanel → Environment Variables:
ADMIN_PASSWORD = AdminPesca2025Seguro  ✅ (sem #)
```

**Teste:**
```bash
curl https://private-serverpesca.pbzgje.easypanel.host/admin/api/stats \
  -H "admin_password: AdminPesca2025Seguro"
```

**Sucesso:**
```json
{"success": true, "stats": {...}}
```
