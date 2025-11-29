# 🚀 ATUALIZAR SERVIDOR NO EASYPANEL

## ⚠️ PROBLEMA ATUAL

**Painel admin NÃO mostra estatísticas de pesca!**

### Por quê?
- ✅ Código do servidor JÁ tem as colunas (total_fish, month_fish, last_fish_date)
- ✅ HTML do admin panel JÁ mostra as colunas
- ❌ Servidor rodando no EasyPanel está com VERSÃO ANTIGA!

---

## 🔧 SOLUÇÃO: REBUILD DO DOCKER

### Opção 1: Rebuild via SSH (MAIS RÁPIDO)

```bash
# 1. Conectar no servidor via SSH
ssh usuario@private-serverpesca.pbzgje.easypanel.host

# 2. Ir para pasta do projeto
cd /app/server_auth

# 3. Puxar código atualizado
git pull origin main

# 4. Rebuild Docker
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 5. Verificar logs
docker-compose logs -f
```

### Opção 2: Rebuild via EasyPanel UI

1. Acessar: https://easypanel.io
2. Ir em **Projects** → **fishing-bot-server**
3. Clicar em **Settings** → **Rebuild**
4. Aguardar rebuild completar (2-3 minutos)
5. Verificar logs: **Logs** tab

### Opção 3: Force Rebuild Local

```bash
# Na pasta server_auth do seu PC
cd c:\Users\Thiago\Desktop\v5\server_auth

# Criar arquivo .force-rebuild
echo. > .force-rebuild

# Commit e push
git add .force-rebuild
git commit -m "force: Trigger rebuild for fish stats update"
git push

# Aguardar EasyPanel detectar e fazer rebuild automático
```

---

## ✅ VERIFICAR SE FUNCIONOU

### 1. Testar endpoint direto

```bash
# Substituir SENHA_ADMIN pela sua senha
curl "https://private-serverpesca.pbzgje.easypanel.host/admin/api/users?password=SENHA_ADMIN"
```

**Resposta esperada:**
```json
{
  "success": true,
  "users": [
    {
      "login": "usuario1",
      "total_fish": 150,        ← DEVE TER ESTE CAMPO!
      "month_fish": 45,         ← DEVE TER ESTE CAMPO!
      "last_fish_date": "2025-11-29 14:30:00"  ← DEVE TER ESTE CAMPO!
    }
  ]
}
```

### 2. Acessar painel admin

```
https://private-serverpesca.pbzgje.easypanel.host/admin
```

**Deve mostrar 3 novas colunas:**
- 🐟 Total
- 🐟 Mês
- Última Pescaria

---

## 🔍 VERIFICAR BANCO DE DADOS

Se após rebuild ainda não funcionar, verificar se banco tem as colunas:

```bash
# Conectar no container
docker exec -it fishing-bot-server sh

# Abrir SQLite
sqlite3 /app/data/users.db

# Verificar schema
.schema hwid_bindings

# Deve mostrar:
# CREATE TABLE hwid_bindings (
#   ...
#   total_fish INTEGER DEFAULT 0,
#   month_fish INTEGER DEFAULT 0,
#   last_fish_date TEXT
# );
```

### Se colunas não existirem (banco antigo):

```sql
-- Adicionar colunas manualmente
ALTER TABLE hwid_bindings ADD COLUMN total_fish INTEGER DEFAULT 0;
ALTER TABLE hwid_bindings ADD COLUMN month_fish INTEGER DEFAULT 0;
ALTER TABLE hwid_bindings ADD COLUMN last_fish_date TEXT;
.quit
```

---

## 📊 CÓDIGO JÁ CORRETO

### ✅ server.py (linhas 1960-1980)

```python
cursor.execute("""
    SELECT login, pc_name, license_key, bound_at, last_seen, hwid, email, password,
           total_fish, month_fish, last_fish_date  ← RETORNA OS DADOS!
    FROM hwid_bindings
    ORDER BY last_seen DESC
""")

users_list = [
    {
        "total_fish": user[8] or 0,   ← INCLUI NO JSON!
        "month_fish": user[9] or 0,   ← INCLUI NO JSON!
        "last_fish_date": user[10],   ← INCLUI NO JSON!
    }
]
```

### ✅ admin_panel.html (linhas 324-326, 473-475)

```html
<th>🐟 Total</th>
<th>🐟 Mês</th>
<th>Última Pescaria</th>

<!-- E depois... -->
<td><strong style="color: #28a745;">${user.total_fish || 0}</strong></td>
<td><strong style="color: #0078d7;">${user.month_fish || 0}</strong></td>
<td>${lastFishDate}</td>
```

---

## 🎯 RESUMO

**O QUE FAZER AGORA:**

1. **Fazer git pull no servidor** (SSH ou EasyPanel)
2. **Rebuild do Docker** (--no-cache para garantir)
3. **Verificar painel admin** (deve mostrar 3 colunas)

**Commits necessários já foram enviados:**
- `0d5d0fa` - feat: Add fish statistics to admin panel

**Você SÓ precisa fazer rebuild do servidor!** 🚀
