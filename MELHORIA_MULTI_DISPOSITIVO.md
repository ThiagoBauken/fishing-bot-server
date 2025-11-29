# 🔧 MELHORIA: Suportar Mesmo Usuário em Múltiplos Dispositivos

## ⚠️ PROBLEMA ATUAL

Se o **mesmo usuário** conectar de 2 PCs com a mesma license key, a segunda conexão SOBRESCREVE a primeira.

**Código atual (`server.py` linha 320-324):**
```python
session = FishingSession(email)
active_sessions[email] = {  # ← Usa email como chave única
    "session": session,
    "websocket": websocket
}
```

**Comportamento:**
- Usuário A conecta PC 1 → OK
- Usuário A conecta PC 2 → PC 1 desconecta!

---

## ✅ SOLUÇÃO: Usar UUID por Conexão

**Mudar de:**
```python
active_sessions[email] = {...}  # Sobrescreve
```

**Para:**
```python
connection_id = str(uuid.uuid4())  # Único por conexão
active_sessions[connection_id] = {
    "email": email,
    "session": session,  # Compartilhado entre todas as conexões do mesmo email
    "websocket": websocket
}
```

---

## 📝 IMPLEMENTAÇÃO

### Passo 1: Adicionar imports
```python
# server.py linha 10
import uuid
```

### Passo 2: Separar sessões de pesca de conexões
```python
# Linha 92
active_sessions: Dict[str, dict] = {}  # connection_id → connection info
user_sessions: Dict[str, FishingSession] = {}  # email → FishingSession (compartilhada)
```

### Passo 3: Modificar WebSocket handler
```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    email = None
    connection_id = str(uuid.uuid4())  # ← Gerar ID único

    try:
        # 1. AUTENTICAÇÃO
        auth_msg = await websocket.receive_json()
        email = auth_msg.get("token")

        if not email:
            await websocket.send_json({"error": "Token inválido"})
            await websocket.close()
            return

        # Validar usuário (mesmo código...)

        # 2. CRIAR/RECUPERAR SESSÃO
        if email not in user_sessions:
            # Primeira conexão deste usuário
            user_sessions[email] = FishingSession(email)
            logger.info(f"🆕 Nova sessão criada para {email}")
        else:
            logger.info(f"♻️ Reutilizando sessão existente para {email}")

        session = user_sessions[email]

        # 3. REGISTRAR CONEXÃO
        active_sessions[connection_id] = {
            "email": email,
            "session": session,  # Compartilhada!
            "websocket": websocket
        }

        logger.info(f"🟢 Cliente conectado: {email} (conexão {connection_id[:8]})")
        logger.info(f"   Total de conexões ativas: {len(active_sessions)}")

        # Enviar confirmação
        await websocket.send_json({
            "type": "connected",
            "message": f"Conectado ao servidor! (dispositivo {connection_id[:8]})",
            "fish_count": session.fish_count,
            "connection_id": connection_id
        })

        # 4. LOOP DE MENSAGENS (mesmo código...)
        while True:
            msg = await websocket.receive_json()
            event = msg.get("event")

            if event == "fish_caught":
                session.increment_fish()  # ← MESMA sessão compartilhada!

                # Notificar TODAS as conexões deste usuário
                for conn_id, conn_info in active_sessions.items():
                    if conn_info["email"] == email:
                        try:
                            await conn_info["websocket"].send_json({
                                "type": "fish_count_update",
                                "fish_count": session.fish_count
                            })
                        except:
                            pass  # Conexão pode ter caído

                # Decidir e enviar comandos (mesmo código...)

    except WebSocketDisconnect:
        logger.warning(f"🔴 Cliente desconectado: {email} (conexão {connection_id[:8]})")

    finally:
        # Remover apenas ESTA conexão
        if connection_id in active_sessions:
            del active_sessions[connection_id]

        # Remover sessão apenas se NÃO houver outras conexões do mesmo usuário
        if email:
            has_other_connections = any(
                conn["email"] == email
                for conn in active_sessions.values()
            )

            if not has_other_connections:
                if email in user_sessions:
                    del user_sessions[email]
                    logger.info(f"🗑️ Sessão removida: {email} (sem conexões ativas)")
```

---

## 🎯 RESULTADO

**Comportamento APÓS correção:**

```
Usuário A conecta PC 1:
├─ connection_id: abc123
├─ user_sessions["user_KEY-111"] = FishingSession A (criada)
└─ active_sessions["abc123"] = {email, session A, ws1}

Usuário A conecta PC 2:
├─ connection_id: def456  ← DIFERENTE!
├─ user_sessions["user_KEY-111"] = FishingSession A (reutilizada!)
└─ active_sessions["def456"] = {email, session A, ws2}

Peixe capturado em PC 1:
├─ session.fish_count += 1
├─ Notifica ws1 (PC 1) ✅
└─ Notifica ws2 (PC 2) ✅  ← Ambos veem a mesma contagem!
```

**Vantagens:**
- ✅ Mesmo usuário pode conectar de múltiplos dispositivos
- ✅ Todos compartilham a mesma sessão (fish_count sincronizado)
- ✅ Se um dispositivo desconectar, os outros continuam
- ✅ Sessão só é removida quando TODOS os dispositivos desconectarem

---

## 📋 QUANDO USAR

**Use esta melhoria SE:**
- ✅ Você quer permitir 1 license = múltiplos dispositivos
- ✅ Usuário pode ter bot rodando em 2 PCs ao mesmo tempo
- ✅ Você quer sincronizar progresso entre dispositivos

**NÃO use SE:**
- ❌ Você quer 1 license = 1 uso simultâneo (proteção anti-compartilhamento)
- ❌ Cada dispositivo deve ter progresso independente

---

## ⚡ IMPLEMENTAÇÃO RÁPIDA

Se quiser aplicar esta melhoria:

1. Backup do servidor atual:
```bash
cp server/server.py server/server.py.backup
```

2. Editar `server/server.py` conforme código acima

3. Testar:
```bash
# Terminal 1: Servidor
python server/server.py

# Terminal 2: Cliente 1
python main.py

# Terminal 3: Cliente 2 (mesma license key)
python main.py
```

**Resultado esperado:** Ambos conectados, fish_count sincronizado!
