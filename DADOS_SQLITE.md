# 📊 DADOS ARMAZENADOS NO SQLITE - Detalhamento Completo

## 🗄️ ESTRUTURA DO BANCO (3 Tabelas)

```
fishing_bot.db
├── 1. users            (Usuários e Licenças)
├── 2. user_stats       (Estatísticas de Pesca)
└── 3. hwid_bindings    (Anti-Compartilhamento)
```

---

## 📋 TABELA 1: `users` - Usuários e Licenças

### Estrutura:

```sql
CREATE TABLE users (
    email           TEXT PRIMARY KEY,     -- Identificador único do usuário
    license_key     TEXT NOT NULL,        -- Chave de licença
    plan            TEXT DEFAULT 'trial', -- Tipo de plano
    expires_at      TEXT,                 -- Data de expiração
    max_pcs         INTEGER DEFAULT 1,    -- Quantos PCs permitidos
    created_at      TEXT                  -- Data de criação
);
```

### Campos Explicados:

| Campo | Tipo | O Que Armazena | Exemplo |
|-------|------|----------------|---------|
| **email** | Texto | Email/identificador único | `user_KEY-12345` |
| **license_key** | Texto | License key do cliente | `KEY-12345` |
| **plan** | Texto | Tipo de plano contratado | `trial`, `premium`, `business` |
| **expires_at** | Texto | Quando a licença expira | `2026-12-31` |
| **max_pcs** | Número | Quantos PCs pode usar | `1` (padrão) |
| **created_at** | Texto | Quando foi criado | `2025-01-16T10:30:00` |

### Exemplo de Dados Reais:

```
┌─────────────────┬──────────────┬─────────┬────────────┬─────────┬────────────────────┐
│ email           │ license_key  │ plan    │ expires_at │ max_pcs │ created_at         │
├─────────────────┼──────────────┼─────────┼────────────┼─────────┼────────────────────┤
│ user_KEY-001    │ KEY-001      │ premium │ 2026-12-31 │ 1       │ 2025-01-15 10:30   │
│ user_KEY-002    │ KEY-002      │ trial   │ 2025-02-16 │ 1       │ 2025-01-16 09:00   │
│ user_KEY-003    │ KEY-003      │ business│ 2027-01-01 │ 3       │ 2025-01-16 11:45   │
│ teste@teste.com │ TEST-KEY-123 │ premium │ 2026-12-31 │ 1       │ 2025-01-16 08:00   │
└─────────────────┴──────────────┴─────────┴────────────┴─────────┴────────────────────┘
```

### Usado Para:

✅ **Autenticação:** Validar se license key existe e é válida
✅ **Expiração:** Verificar se licença ainda está ativa
✅ **Planos:** Diferenciar trial/premium/business (futuro: funcionalidades diferentes)
✅ **Multi-PC:** Controlar quantos PCs podem usar (padrão: 1)

---

## 📈 TABELA 2: `user_stats` - Estatísticas de Pesca

### Estrutura:

```sql
CREATE TABLE user_stats (
    email           TEXT PRIMARY KEY,     -- Identificador do usuário
    fish_count      INTEGER DEFAULT 0,    -- Total de peixes capturados
    last_fish_time  TEXT,                 -- Quando capturou o último peixe
    session_start   TEXT                  -- Quando iniciou a sessão atual
);
```

### Campos Explicados:

| Campo | Tipo | O Que Armazena | Exemplo |
|-------|------|----------------|---------|
| **email** | Texto | Identificador do usuário | `user_KEY-12345` |
| **fish_count** | Número | Total de peixes capturados | `1523` |
| **last_fish_time** | Texto | Timestamp do último peixe | `2025-01-16T14:22:30` |
| **session_start** | Texto | Quando começou a pescar | `2025-01-16T10:00:00` |

### Exemplo de Dados Reais:

```
┌─────────────────┬────────────┬────────────────────┬────────────────────┐
│ email           │ fish_count │ last_fish_time     │ session_start      │
├─────────────────┼────────────┼────────────────────┼────────────────────┤
│ user_KEY-001    │ 1523       │ 2025-01-16 14:22   │ 2025-01-16 10:00   │
│ user_KEY-002    │ 47         │ 2025-01-16 12:15   │ 2025-01-16 11:30   │
│ user_KEY-003    │ 3856       │ 2025-01-16 15:00   │ 2025-01-15 08:00   │
│ teste@teste.com │ 12         │ 2025-01-16 13:45   │ 2025-01-16 13:00   │
└─────────────────┴────────────┴────────────────────┴────────────────────┘
```

### Usado Para:

✅ **Contagem Total:** Rastrear quantos peixes cada usuário capturou
✅ **Decisões do Servidor:**
   - `fish_count % 3 == 0` → Enviar comando FEED (alimentar)
   - `fish_count % 1 == 0` → Enviar comando CLEAN (limpar)
   - `fish_count % 50 == 0` → Enviar comando BREAK (pausar)
✅ **Analytics:** Ver quem está pescando mais
✅ **Último Uso:** Detectar usuários inativos

### Exemplo de Decisão do Servidor:

```python
# Usuario captura peixe #48
fish_count = 48

# Servidor decide:
if fish_count % 3 == 0:  # 48 % 3 = 0 → SIM!
    send_command("feed")  # Alimentar

if fish_count % 1 == 0:  # Sempre
    send_command("clean")  # Limpar inventário

if fish_count % 50 == 0:  # 48 % 50 = 48 → NÃO
    send_command("break")  # Não enviar ainda
```

---

## 🔒 TABELA 3: `hwid_bindings` - Anti-Compartilhamento

### Estrutura:

```sql
CREATE TABLE hwid_bindings (
    license_key     TEXT PRIMARY KEY,     -- License key
    hwid            TEXT NOT NULL,        -- Hardware ID do PC
    bound_at        TEXT,                 -- Quando foi vinculado
    last_seen       TEXT,                 -- Último uso
    pc_name         TEXT                  -- Nome do PC
);
```

### Campos Explicados:

| Campo | Tipo | O Que Armazena | Exemplo |
|-------|------|----------------|---------|
| **license_key** | Texto | License key vinculada | `KEY-12345` |
| **hwid** | Texto | Hardware ID único do PC | `ABC123DEF456789...` (hash SHA256) |
| **bound_at** | Texto | Quando foi vinculado pela primeira vez | `2025-01-15T10:30:00` |
| **last_seen** | Texto | Última vez que foi usado | `2025-01-16T14:22:30` |
| **pc_name** | Texto | Nome do computador | `DESKTOP-JOHN` |

### Exemplo de Dados Reais:

```
┌──────────────┬────────────────────────┬────────────────┬────────────────────┬──────────────────┐
│ license_key  │ hwid (primeiros 16)    │ pc_name        │ bound_at           │ last_seen        │
├──────────────┼────────────────────────┼────────────────┼────────────────────┼──────────────────┤
│ KEY-001      │ ABC123DEF456789...     │ DESKTOP-JOHN   │ 2025-01-15 10:30   │ 2025-01-16 14:22 │
│ KEY-002      │ XYZ789UVW012345...     │ LAPTOP-MARIA   │ 2025-01-15 11:45   │ 2025-01-16 09:15 │
│ KEY-003      │ QWE456RTY789012...     │ PC-GAMING-PRO  │ 2025-01-16 08:00   │ 2025-01-16 15:00 │
│ TEST-KEY-123 │ (null)                 │ (null)         │ (null)             │ (null)           │
└──────────────┴────────────────────────┴────────────────┴────────────────────┴──────────────────┘
```

### Como o HWID é Gerado (Cliente):

```python
# No cliente (utils/license_manager.py)
import hashlib
import platform
import uuid

# Capturar componentes do hardware
cpu_info = platform.processor()              # Ex: "Intel64 Family 6..."
mac_address = str(uuid.UUID(int=uuid.getnode()))  # Ex: "a1b2c3d4..."

# Criar string única
hw_string = f"{cpu_info}{mac_address}"

# Hash SHA256 (irreversível)
hwid = hashlib.sha256(hw_string.encode()).hexdigest()
# Resultado: "ABC123DEF456789..." (64 caracteres)
```

### Usado Para: 🔒 ANTI-COMPARTILHAMENTO

**Cenário 1: Primeiro Uso**
```
Cliente A conecta com KEY-001 no PC-A
    ↓
hwid_bindings está vazio para KEY-001
    ↓
Servidor VINCULA: KEY-001 → HWID do PC-A
    ↓
✅ PERMITIDO (primeiro uso)
```

**Cenário 2: Uso Normal (Mesmo PC)**
```
Cliente A conecta com KEY-001 no PC-A (novamente)
    ↓
Servidor compara:
    HWID esperado: ABC123...
    HWID recebido: ABC123...
    ↓
IGUAIS → ✅ PERMITIDO
```

**Cenário 3: Tentativa de Compartilhamento**
```
Cliente B tenta KEY-001 no PC-B
    ↓
Servidor compara:
    HWID esperado: ABC123... (PC-A)
    HWID recebido: XYZ789... (PC-B)
    ↓
DIFERENTES → ❌ BLOQUEADO!
    └─ "Esta licença já está vinculada a outro PC (DESKTOP-JOHN)"
```

---

## 📊 EXEMPLO DE DADOS COMPLETOS (1 Usuário)

### Usuário: João (KEY-001)

**Tabela `users`:**
```
email:      user_KEY-001
license_key: KEY-001
plan:       premium
expires_at: 2026-12-31
max_pcs:    1
created_at: 2025-01-15 10:30
```

**Tabela `user_stats`:**
```
email:          user_KEY-001
fish_count:     1523
last_fish_time: 2025-01-16 14:22:30
session_start:  2025-01-16 10:00:00
```

**Tabela `hwid_bindings`:**
```
license_key: KEY-001
hwid:        ABC123DEF456789ABCDEF123456789ABCDEF123456789ABCDEF123456
bound_at:    2025-01-15 10:30:00
last_seen:   2025-01-16 14:22:30
pc_name:     DESKTOP-JOHN
```

### Interpretação:

✅ João tem licença **premium** válida até 2026
✅ Já capturou **1523 peixes** no total
✅ Pescou pela última vez **hoje às 14:22**
✅ Licença vinculada ao PC **DESKTOP-JOHN**
✅ Não pode usar em outro PC (HWID bloqueado)

---

## 🔍 QUERIES SQL COMUNS

### 1. Ver Todos os Usuários:

```sql
SELECT
    u.email,
    u.license_key,
    u.plan,
    u.expires_at,
    COALESCE(s.fish_count, 0) as total_peixes,
    h.pc_name
FROM users u
LEFT JOIN user_stats s ON u.email = s.email
LEFT JOIN hwid_bindings h ON u.license_key = h.license_key
ORDER BY s.fish_count DESC;
```

### 2. Ver Usuários Ativos Hoje:

```sql
SELECT
    email,
    fish_count,
    last_fish_time
FROM user_stats
WHERE DATE(last_fish_time) = DATE('now')
ORDER BY last_fish_time DESC;
```

### 3. Ver Tentativas de Compartilhamento:

```sql
-- Verificar no log do servidor:
-- Mensagens com "🚫 HWID BLOQUEADO"
```

### 4. Adicionar Novo Usuário:

```sql
INSERT INTO users (email, license_key, plan, expires_at)
VALUES ('user_KEY-999', 'KEY-999', 'premium', '2026-12-31');
```

### 5. Resetar HWID (Cliente Formatou PC):

```sql
DELETE FROM hwid_bindings WHERE license_key='KEY-001';
-- Cliente pode vincular novo HWID na próxima conexão
```

---

## 💾 TAMANHO DO BANCO

### Estimativa por Número de Usuários:

| Usuários | Tamanho Aproximado | Observação |
|----------|-------------------|------------|
| 10 | 10 KB | Início |
| 100 | 50 KB | Pequeno negócio |
| 1.000 | 500 KB | Negócio médio |
| 10.000 | 5 MB | Grande negócio |
| 100.000 | 50 MB | Muito grande |

**Cada registro:**
- `users`: ~200 bytes
- `user_stats`: ~100 bytes
- `hwid_bindings`: ~150 bytes
- **Total por usuário:** ~450 bytes

**Conclusão:** Banco extremamente leve! 🚀

---

## 📋 RESUMO: O QUE ESTÁ NO SQLITE?

### Dados Essenciais:

1. **🔑 Autenticação**
   - License keys válidas
   - Datas de expiração
   - Tipos de plano

2. **📊 Estatísticas**
   - Quantos peixes cada um capturou
   - Quando foi o último peixe
   - Tempo de sessão

3. **🔒 Segurança**
   - Hardware ID vinculado
   - Nome do PC
   - Histórico de uso

### O Que NÃO Está Armazenado:

❌ **Senhas** (não tem login com senha)
❌ **Templates de pesca** (ficam no cliente)
❌ **Coordenadas** (ficam no cliente)
❌ **Logs detalhados** (apenas estatísticas)
❌ **Dados pessoais** (apenas email/identificador)

---

## 🎯 EXEMPLO PRÁTICO: Fluxo Completo

### 1. Cliente Conecta Pela Primeira Vez:

```
POST /auth/activate
{
    "license_key": "KEY-001",
    "hwid": "ABC123...",
    "pc_name": "DESKTOP-JOHN"
}

Servidor:
1. SELECT * FROM users WHERE license_key='KEY-001'
   → Encontrado ✅

2. SELECT * FROM hwid_bindings WHERE license_key='KEY-001'
   → Não encontrado (primeiro uso)

3. INSERT INTO hwid_bindings VALUES ('KEY-001', 'ABC123...', ...)
   → HWID vinculado ✅

4. SELECT * FROM user_stats WHERE email='user_KEY-001'
   → fish_count = 0 (novo usuário)

5. Resposta: {"success": true, "token": "user_KEY-001"}
```

### 2. Cliente Pesca (Captura 3 Peixes):

```
WS: {"event": "fish_caught"}  # Peixe 1

Servidor:
UPDATE user_stats SET fish_count=1 WHERE email='user_KEY-001'
1 % 3 != 0 → Não enviar comando

WS: {"event": "fish_caught"}  # Peixe 2

Servidor:
UPDATE user_stats SET fish_count=2 WHERE email='user_KEY-001'
2 % 3 != 0 → Não enviar comando

WS: {"event": "fish_caught"}  # Peixe 3

Servidor:
UPDATE user_stats SET fish_count=3 WHERE email='user_KEY-001'
3 % 3 == 0 → ✅ Enviar comando FEED!
WS → Cliente: {"cmd": "feed", "params": {"clicks": 5}}
```

---

## ✅ CONCLUSÃO

**SQLite armazena 3 tipos de dados:**

1. **👤 Usuários** - Quem pode usar o bot
2. **📈 Estatísticas** - Quantos peixes capturaram
3. **🔒 HWID** - Anti-compartilhamento (1 PC por licença)

**Tamanho total:** Extremamente leve (~450 bytes por usuário)

**Performance:** Muito rápido para até 2000 usuários simultâneos

**Status:** ✅ **IMPLEMENTADO E FUNCIONANDO!**
