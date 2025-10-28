# 🔐 INTEGRAÇÃO COM KEYMASTER - License Validation

## 🎯 SITUAÇÃO ATUAL

### Sistema de Licenças ANTERIOR (Bot v4):

**Keymaster/Keygen Server:**
- **URL:** `https://private-keygen.pbzgje.easypanel.host`
- **Project ID:** `67a4a76a-d71b-4d07-9ba8-f7e794ce0578`
- **Endpoints:**
  - `/validate` - Validar license key existente
  - `/activate` - Ativar nova license key

**Fluxo:**
```
Cliente inicia bot
    ↓
LicenseManager.check_license()
    ↓
Envia para Keymaster: {activation_key, hardware_id, project_id}
    ↓
Keymaster valida
    ↓
Se válido: Bot inicia ✅
Se inválido: Bot bloqueia ❌
```

---

### Sistema Novo (Servidor Multi-Usuário):

**Nosso Servidor:**
- **URL:** `http://localhost:8000` (ou `https://seu-dominio.com`)
- **Endpoints:**
  - `/auth/activate` - Ativar com license_key + HWID

**Fluxo ATUAL:**
```
Cliente inicia bot
    ↓
Conecta ao nosso servidor: {license_key, hwid}
    ↓
Servidor valida no SQLite local
    ↓
Se válido: Conecta WebSocket ✅
Se inválido: Bloqueia ❌
```

---

## ⚠️ PROBLEMA

**Atualmente:** Servidor multi-usuário **NÃO** valida com o Keymaster!

**Consequência:**
- ❌ License keys adicionadas manualmente no SQLite (você adiciona via SQL)
- ❌ Não há validação externa (pode adicionar qualquer key)
- ❌ Não usa o sistema Keymaster existente

---

## ✅ SOLUÇÃO: INTEGRAR COM KEYMASTER

### Arquitetura Híbrida (Recomendado):

```
Cliente inicia bot
    ↓
1. LicenseManager valida no Keymaster (como sempre)
    ↓
    Se INVÁLIDO → Bot nem inicia ❌
    ↓
    Se VÁLIDO → Prossegue ✅
    ↓
2. Cliente conecta ao servidor multi-usuário
    ↓
3. Servidor TAMBÉM valida no Keymaster
    ↓
    Se INVÁLIDO → Bloqueia conexão ❌
    ↓
    Se VÁLIDO → Aceita WebSocket ✅
    ↓
4. Servidor vincula HWID (anti-compartilhamento)
```

**Vantagem:** Validação em 2 camadas!
- Camada 1: Cliente valida com Keymaster (evita bots crackeados)
- Camada 2: Servidor valida com Keymaster (garante que só keys válidas conectam)

---

## 🔧 IMPLEMENTAÇÃO

### OPÇÃO 1: Servidor Valida com Keymaster (RECOMENDADO)

Modificar `server/server.py` para validar no Keymaster:

```python
# server/server.py

import requests

# Configuração do Keymaster
KEYMASTER_URL = "https://private-keygen.pbzgje.easypanel.host"
PROJECT_ID = "67a4a76a-d71b-4d07-9ba8-f7e794ce0578"

def validate_with_keymaster(license_key: str, hwid: str) -> dict:
    """
    Validar license key no Keymaster

    Returns:
        {"valid": bool, "message": str, "data": dict}
    """
    try:
        payload = {
            "activation_key": license_key,
            "hardware_id": hwid,
            "project_id": PROJECT_ID
        }

        response = requests.post(
            f"{KEYMASTER_URL}/validate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            if data.get("valid"):
                return {
                    "valid": True,
                    "message": "License válida no Keymaster",
                    "data": data
                }
            else:
                return {
                    "valid": False,
                    "message": data.get("message", "License inválida"),
                    "data": data
                }

        else:
            return {
                "valid": False,
                "message": f"Keymaster retornou {response.status_code}",
                "data": {}
            }

    except requests.exceptions.Timeout:
        # Se Keymaster cair, permitir offline?
        return {
            "valid": True,  # ← DECISÃO: Permitir se Keymaster offline?
            "message": "Keymaster offline, validação local",
            "data": {}
        }

    except Exception as e:
        logger.error(f"Erro ao validar com Keymaster: {e}")
        return {
            "valid": False,
            "message": f"Erro: {e}",
            "data": {}
        }


@app.post("/auth/activate", response_model=LicenseKeyResponse)
async def activate_license(request: LicenseKeyRequest):
    """
    Autenticar com license_key + HWID

    NOVO: Valida no Keymaster ANTES de aceitar
    """
    try:
        # 1. VALIDAR NO KEYMASTER (prioridade!)
        if request.hwid:
            logger.info(f"🔍 Validando com Keymaster: {request.license_key[:10]}...")

            keymaster_result = validate_with_keymaster(
                request.license_key,
                request.hwid
            )

            if not keymaster_result["valid"]:
                logger.warning(f"❌ Keymaster rejeitou: {keymaster_result['message']}")
                return LicenseKeyResponse(
                    success=False,
                    message=f"License inválida: {keymaster_result['message']}"
                )

            logger.info(f"✅ Keymaster validou: {request.license_key[:10]}...")

        # 2. BUSCAR/CRIAR USUÁRIO no SQLite local
        conn = sqlite3.connect("fishing_bot.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT email FROM users WHERE license_key=?
        """, (request.license_key,))

        user = cursor.fetchone()

        if not user:
            # Criar usuário automaticamente se validou no Keymaster
            email = f"user_{request.license_key}"
            cursor.execute("""
                INSERT INTO users (email, license_key, plan, expires_at)
                VALUES (?, ?, 'premium', '2026-12-31')
            """, (email, request.license_key))
            conn.commit()
            logger.info(f"🆕 Novo usuário criado: {email}")
        else:
            email = user[0]

        # 3. VALIDAÇÃO DE HWID (como antes)
        # ... (código existente)

        conn.close()

        return LicenseKeyResponse(
            success=True,
            message="Licença ativada com sucesso!",
            token=email,
            email=email
        )

    except Exception as e:
        logger.error(f"❌ Erro na ativação: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

**Resultado:**
- ✅ License key validada no Keymaster ANTES de aceitar
- ✅ Usuário criado automaticamente no SQLite se passar no Keymaster
- ✅ Não precisa adicionar keys manualmente!

---

### OPÇÃO 2: Apenas Cliente Valida (Atual - Mais Simples)

Mantém como está:
- Cliente valida com Keymaster (LicenseManager)
- Servidor apenas registra no SQLite

**Vantagem:**
- ✅ Mais simples
- ✅ Servidor não depende do Keymaster

**Desvantagem:**
- ❌ Se crackearem o cliente, podem burlar a validação
- ❌ Precisa adicionar keys manualmente no servidor

---

### OPÇÃO 3: Dual Validation (Máxima Segurança)

Cliente E Servidor validam:

```
1. Cliente valida com Keymaster → Se INVÁLIDO: Bot nem inicia
2. Cliente conecta ao servidor
3. Servidor valida com Keymaster → Se INVÁLIDO: Bloqueia conexão
4. Servidor vincula HWID → Anti-compartilhamento
```

**Vantagem:**
- ✅✅ Segurança máxima
- ✅ Mesmo se crackearem cliente, servidor bloqueia

**Desvantagem:**
- ⚠️ 2x requisições ao Keymaster (mais lento)
- ⚠️ Se Keymaster cair, ninguém conecta

---

## 🎯 RECOMENDAÇÃO

### Para Começar: OPÇÃO 2 (Atual)

**Por quê:**
- ✅ Mais simples
- ✅ Keymaster já valida no cliente
- ✅ Servidor não depende de serviço externo

**Adicionar keys manualmente:**
```sql
INSERT INTO users (email, license_key, plan, expires_at)
VALUES ('user_KEY-123', 'KEY-123', 'premium', '2026-12-31');
```

---

### Depois de Escalar: OPÇÃO 1 (Servidor Valida)

**Quando:**
- Ter 100+ vendas
- Keymaster estável
- Quer automatizar (não adicionar keys manualmente)

**Benefício:**
- ✅ Keys são validadas automaticamente
- ✅ Não precisa adicionar no SQLite manualmente
- ✅ Integração com sistema de vendas (Keymaster gera keys)

---

## 📊 COMPARAÇÃO

| Aspecto | Opção 1 (Servidor Valida) | Opção 2 (Cliente Valida) | Opção 3 (Dual) |
|---------|---------------------------|--------------------------|----------------|
| **Segurança** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Simplicidade** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Depende Keymaster** | ✅ Sim | ❌ Não | ✅ Sim |
| **Auto-criação users** | ✅ Sim | ❌ Não (manual) | ✅ Sim |
| **Recomendado para** | Escalado | Início | Máxima segurança |

---

## 🔄 MIGRAÇÃO: Como Integrar Keymaster

### Passo 1: Adicionar Validação no Servidor

```python
# server/server.py (adicionar no topo)
import requests

KEYMASTER_URL = "https://private-keygen.pbzgje.easypanel.host"
PROJECT_ID = "67a4a76a-d71b-4d07-9ba8-f7e794ce0578"

def validate_with_keymaster(license_key, hwid):
    # Código acima
    pass
```

### Passo 2: Modificar /auth/activate

Adicionar validação antes de aceitar (código acima).

### Passo 3: Testar

```bash
# Servidor
python server/server.py

# Cliente
python main.py

# Deve validar no Keymaster antes de conectar!
```

### Passo 4: Monitorar Logs

```
🔍 Validando com Keymaster: KEY-123...
✅ Keymaster validou: KEY-123
🆕 Novo usuário criado: user_KEY-123
🔗 HWID vinculado: user_KEY-123
```

---

## ⚠️ CONSIDERAÇÕES

### E Se o Keymaster Cair?

**Decisão de design:**

**Opção A: Bloquear tudo**
```python
if not keymaster_result["valid"]:
    return {"success": False}  # Ninguém conecta
```

**Opção B: Fallback para SQLite**
```python
except requests.exceptions.Timeout:
    # Keymaster offline → validar localmente
    return {"valid": True}
```

**Recomendação:** Opção B (permite funcionamento offline do Keymaster)

---

### Múltiplas Fontes de Verdade

**Atualmente temos 2 bancos:**
1. **Keymaster:** Keys válidas (fonte principal)
2. **Nosso SQLite:** Keys + HWID + stats

**Solução:**
- Keymaster = validação (fonte de verdade)
- SQLite = cache + HWID + estatísticas

**Fluxo ideal:**
```
1. Keymaster diz: "KEY-123 é válida"
2. Servidor cria/atualiza no SQLite
3. Servidor vincula HWID no SQLite (Keymaster não tem isso)
4. Servidor rastreia stats no SQLite (fish_count, etc.)
```

---

## ✅ RESUMO

### Situação Atual:
- ✅ Cliente valida com Keymaster (funciona)
- ❌ Servidor NÃO valida com Keymaster
- ❌ Keys adicionadas manualmente no SQLite

### Opções:
1. **Servidor valida com Keymaster** (auto-criação de users)
2. **Manter como está** (mais simples, manual)
3. **Dual validation** (máxima segurança)

### Recomendação:
- **Início:** Opção 2 (manter como está - simples)
- **Escala:** Opção 1 (servidor valida - automático)
- **Máxima segurança:** Opção 3 (dual validation)

### Próximo Passo:
Decidir qual opção usar e implementar se necessário!

---

**Status Atual:** ✅ Cliente valida com Keymaster (funciona)
**Servidor:** ⚠️ Validação local (SQLite) - Pode integrar com Keymaster se quiser
