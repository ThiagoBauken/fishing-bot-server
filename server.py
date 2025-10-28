#!/usr/bin/env python3
"""
🎣 Fishing Bot Server - Servidor Multi-Usuário Simples
Gerencia autenticação, licenças e lógica de decisão

VALIDAÇÃO AUTOMÁTICA COM KEYMASTER
Não precisa adicionar license keys manualmente!
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import sqlite3
import asyncio
from datetime import datetime
from typing import Dict
import logging
import requests

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# CONFIGURAÇÃO DO KEYMASTER
# ═══════════════════════════════════════════════════════

KEYMASTER_URL = "https://private-keygen.pbzgje.easypanel.host"
PROJECT_ID = "67a4a76a-d71b-4d07-9ba8-f7e794ce0578"

# FastAPI app
app = FastAPI(
    title="Fishing Bot Server",
    description="Servidor multi-usuário para Fishing Bot",
    version="1.0.0"
)

# CORS (permite conexões de qualquer origem)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════
# KEYMASTER INTEGRATION
# ═══════════════════════════════════════════════════════

def validate_with_keymaster(license_key: str, hwid: str) -> dict:
    """
    Validar license key com Keymaster (fonte de verdade)

    Retorna:
        {
            "valid": bool,
            "message": str,
            "plan": str (se disponível)
        }
    """
    try:
        logger.info(f"🔍 Validando com Keymaster: {license_key[:10]}...")

        response = requests.post(
            f"{KEYMASTER_URL}/validate",
            json={
                "activation_key": license_key,
                "hardware_id": hwid,
                "project_id": PROJECT_ID
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            is_valid = data.get("valid", False)

            if is_valid:
                logger.info(f"✅ Keymaster: License válida!")
                return {
                    "valid": True,
                    "message": "License válida",
                    "plan": data.get("plan", "basic")
                }
            else:
                logger.warning(f"❌ Keymaster: License inválida ou expirada")
                return {
                    "valid": False,
                    "message": data.get("message", "License inválida ou expirada")
                }
        else:
            logger.error(f"❌ Keymaster retornou status {response.status_code}")
            return {
                "valid": False,
                "message": f"Erro na validação (HTTP {response.status_code})"
            }

    except requests.exceptions.Timeout:
        logger.error("❌ Keymaster timeout (10s)")
        return {
            "valid": False,
            "message": "Servidor de licenças não respondeu (timeout)"
        }
    except Exception as e:
        logger.error(f"❌ Erro ao validar com Keymaster: {e}")
        return {
            "valid": False,
            "message": f"Erro na validação: {str(e)}"
        }

# ═══════════════════════════════════════════════════════
# BANCO DE DADOS (SQLite - MÍNIMO!)
# ═══════════════════════════════════════════════════════

def init_database():
    """
    Inicializar banco de dados SQLite

    APENAS HWID BINDINGS (anti-compartilhamento)
    NÃO precisa de tabela users - Keymaster já valida!
    """
    conn = sqlite3.connect("fishing_bot.db")
    cursor = conn.cursor()

    # Tabela de HWID (vincular license key a hardware ID)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hwid_bindings (
            license_key TEXT PRIMARY KEY,
            hwid TEXT NOT NULL,
            bound_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            pc_name TEXT,
            login TEXT
        )
    """)

    conn.commit()
    conn.close()
    logger.info("✅ Banco de dados inicializado (HWID bindings)")

# Inicializar ao startar
init_database()

# ═══════════════════════════════════════════════════════
# SESSÕES ATIVAS (em memória)
# ═══════════════════════════════════════════════════════

active_sessions: Dict[str, dict] = {}

# Regras de configuração (retornadas para o cliente)
DEFAULT_RULES = {
    "feed_interval_fish": 3,       # Alimentar a cada 3 peixes
    "clean_interval_fish": 1,      # Limpar a cada 1 peixe
    "break_interval_fish": 50,     # Pausar a cada 50 peixes
    "break_duration_minutes": 45   # Duração do break
}

class FishingSession:
    """
    Sessão de pesca de um usuário
    Mantém fish_count e decide quando executar ações (feed/clean/break)
    """
    def __init__(self, login: str):
        self.login = login
        self.fish_count = 0
        self.session_start = datetime.now()
        self.last_fish_time = None
        logger.info(f"🎣 Nova sessão criada para: {login}")

    def increment_fish(self):
        """Incrementar contador de peixes"""
        self.fish_count += 1
        self.last_fish_time = datetime.now()
        logger.info(f"🐟 {self.login}: Peixe #{self.fish_count} capturado!")

    def should_feed(self) -> bool:
        """Verificar se precisa alimentar (a cada N peixes)"""
        return self.fish_count % DEFAULT_RULES["feed_interval_fish"] == 0

    def should_clean(self) -> bool:
        """Verificar se precisa limpar (a cada N peixes)"""
        return self.fish_count % DEFAULT_RULES["clean_interval_fish"] == 0

    def should_break(self) -> bool:
        """Verificar se precisa dar break (a cada N peixes)"""
        return self.fish_count > 0 and self.fish_count % DEFAULT_RULES["break_interval_fish"] == 0

# ═══════════════════════════════════════════════════════
# MODELOS DE DADOS
# ═══════════════════════════════════════════════════════

class ActivationRequest(BaseModel):
    """Requisição de ativação com login/senha/license_key"""
    login: str                  # Login do usuário (qualquer valor)
    password: str               # Senha (qualquer valor)
    license_key: str            # License key do Keymaster
    hwid: str                   # Hardware ID do PC
    pc_name: str = None         # Nome do PC (opcional)

class ActivationResponse(BaseModel):
    """Resposta de ativação"""
    success: bool
    message: str
    token: str = None
    rules: dict = None

# ═══════════════════════════════════════════════════════
# ROTAS HTTP
# ═══════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Health check"""
    return {
        "service": "Fishing Bot Server",
        "version": "2.0.0",
        "status": "online",
        "active_users": len(active_sessions),
        "keymaster_integration": True
    }

@app.get("/health")
async def health():
    """Health check para EasyPanel"""
    return {"status": "healthy"}

@app.post("/auth/activate", response_model=ActivationResponse)
async def activate_license(request: ActivationRequest):
    """
    Ativar bot com login/senha/license_key

    FLUXO:
    1. Validar license_key com Keymaster (fonte de verdade)
    2. Verificar HWID binding (anti-compartilhamento)
    3. Salvar login/senha associado à license_key
    4. Retornar token + regras de configuração
    """
    try:
        # ══════════════════════════════════════════════════════
        # 1. VALIDAR COM KEYMASTER (OBRIGATÓRIO)
        # ══════════════════════════════════════════════════════

        keymaster_result = validate_with_keymaster(request.license_key, request.hwid)

        if not keymaster_result["valid"]:
            logger.warning(f"❌ Keymaster rejeitou: {request.license_key[:10]}...")
            return ActivationResponse(
                success=False,
                message=keymaster_result["message"]
            )

        logger.info(f"✅ Keymaster validou: {request.license_key[:10]}... (Plan: {keymaster_result.get('plan', 'N/A')})")

        # ══════════════════════════════════════════════════════
        # 2. VERIFICAR HWID BINDING (Anti-compartilhamento)
        # ══════════════════════════════════════════════════════

        conn = sqlite3.connect("fishing_bot.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT hwid, pc_name, bound_at, login
            FROM hwid_bindings
            WHERE license_key=?
        """, (request.license_key,))

        binding = cursor.fetchone()

        if binding:
            # JÁ TEM HWID VINCULADO
            bound_hwid, bound_pc_name, bound_at, bound_login = binding

            if request.hwid == bound_hwid:
                # ✅ MESMO PC - permitir
                logger.info(f"✅ HWID válido: {request.login} (PC: {request.pc_name or 'N/A'})")

                # Atualizar last_seen e login
                cursor.execute("""
                    UPDATE hwid_bindings
                    SET last_seen=?, pc_name=?, login=?
                    WHERE license_key=?
                """, (datetime.now().isoformat(), request.pc_name, request.login, request.license_key))
                conn.commit()

            else:
                # ❌ PC DIFERENTE - bloquear
                conn.close()
                logger.warning(f"🚫 HWID BLOQUEADO para license {request.license_key[:10]}...")
                logger.warning(f"   Login tentativa: {request.login}")
                logger.warning(f"   Login vinculado: {bound_login}")
                logger.warning(f"   PC esperado: {bound_pc_name}")
                logger.warning(f"   PC recebido: {request.pc_name}")

                return ActivationResponse(
                    success=False,
                    message=f"Esta licença já está vinculada a outro PC ({bound_pc_name or 'N/A'}). Login: {bound_login}"
                )

        else:
            # NÃO TEM HWID VINCULADO → VINCULAR AGORA (primeiro uso)
            cursor.execute("""
                INSERT INTO hwid_bindings (license_key, hwid, pc_name, login)
                VALUES (?, ?, ?, ?)
            """, (request.license_key, request.hwid, request.pc_name, request.login))
            conn.commit()

            logger.info(f"🔗 HWID vinculado pela primeira vez:")
            logger.info(f"   License: {request.license_key[:10]}...")
            logger.info(f"   Login: {request.login}")
            logger.info(f"   PC: {request.pc_name or 'N/A'}")
            logger.info(f"   HWID: {request.hwid[:16]}...")

        conn.close()

        # ══════════════════════════════════════════════════════
        # 3. GERAR TOKEN E RETORNAR REGRAS
        # ══════════════════════════════════════════════════════

        token = f"{request.license_key}:{request.hwid[:16]}"  # Token simples

        logger.info(f"✅ Ativação bem-sucedida: {request.login}")

        return ActivationResponse(
            success=True,
            message="Ativação bem-sucedida!",
            token=token,
            rules=DEFAULT_RULES
        )

    except Exception as e:
        logger.error(f"❌ Erro na ativação: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════
# WEBSOCKET (HEARTBEAT - Mantém conexão ativa)
# ═══════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Endpoint WebSocket para heartbeat

    Cliente mantém conexão ativa para validar que ainda está licenciado.
    NÃO envia fish_caught - cliente executa tudo localmente!
    """
    await websocket.accept()
    token = None
    license_key = None

    try:
        # 1. AUTENTICAÇÃO
        auth_msg = await websocket.receive_json()
        token = auth_msg.get("token")

        if not token:
            await websocket.send_json({"error": "Token inválido"})
            await websocket.close()
            return

        # Extrair license_key do token (formato: license_key:hwid_prefix)
        license_key = token.split(":")[0] if ":" in token else token

        # 2. VALIDAR TOKEN (verificar HWID binding)
        conn = sqlite3.connect("fishing_bot.db")
        cursor = conn.cursor()
        cursor.execute("SELECT login, pc_name FROM hwid_bindings WHERE license_key=?", (license_key,))
        binding = cursor.fetchone()
        conn.close()

        if not binding:
            await websocket.send_json({"error": "Token inválido ou licença não vinculada"})
            await websocket.close()
            return

        login, pc_name = binding

        # 3. CRIAR FISHING SESSION (mantém fish_count e decide ações)
        session = FishingSession(login)

        # 4. REGISTRAR SESSÃO ATIVA
        active_sessions[license_key] = {
            "login": login,
            "pc_name": pc_name,
            "websocket": websocket,
            "connected_at": datetime.now(),
            "session": session  # ✅ Adicionar session
        }

        logger.info(f"🟢 Cliente conectado: {login} (PC: {pc_name})")

        # Enviar confirmação + fish_count atual
        await websocket.send_json({
            "type": "connected",
            "message": "Conectado ao servidor!",
            "fish_count": session.fish_count  # ✅ Enviar fish_count
        })

        # 5. LOOP DE MENSAGENS
        while True:
            msg = await websocket.receive_json()

            event = msg.get("event")

            # ─────────────────────────────────────────────────
            # EVENTO: Peixe capturado (IMPORTANTE!)
            # ─────────────────────────────────────────────────
            if event == "fish_caught":
                session.increment_fish()

                # Decidir próxima ação
                commands = []

                # Alimentar a cada N peixes
                if session.should_feed():
                    commands.append({"cmd": "feed", "params": {"clicks": 5}})
                    logger.info(f"🍖 {login}: Enviando comando de feeding")

                # Limpar a cada N peixes
                if session.should_clean():
                    commands.append({"cmd": "clean"})
                    logger.info(f"🧹 {login}: Enviando comando de limpeza")

                # Break a cada N peixes
                if session.should_break():
                    commands.append({"cmd": "break", "duration_minutes": DEFAULT_RULES["break_duration_minutes"]})
                    logger.info(f"☕ {login}: Enviando comando de break")

                # Enviar comandos
                for cmd in commands:
                    await websocket.send_json(cmd)

            # ─────────────────────────────────────────────────
            # EVENTO: Feeding concluído
            # ─────────────────────────────────────────────────
            elif event == "feeding_done":
                logger.info(f"✅ {login}: Feeding concluído")

            # ─────────────────────────────────────────────────
            # EVENTO: Limpeza concluída
            # ─────────────────────────────────────────────────
            elif event == "cleaning_done":
                logger.info(f"✅ {login}: Limpeza concluída")

            # ─────────────────────────────────────────────────
            # PING (heartbeat)
            # ─────────────────────────────────────────────────
            elif event == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"🔴 Cliente desconectado: {license_key or 'desconhecido'}")

    except Exception as e:
        logger.error(f"❌ Erro no WebSocket ({license_key or 'desconhecido'}): {e}")

    finally:
        # Remover sessão
        if license_key and license_key in active_sessions:
            del active_sessions[license_key]
            logger.info(f"🗑️ Sessão removida: {license_key}")

# ═══════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    logger.info("="*60)
    logger.info("🚀 Fishing Bot Server iniciando...")
    logger.info("="*60)
    logger.info("✅ Servidor pronto para aceitar conexões!")
    logger.info("📊 Usuários ativos: 0")
    logger.info("="*60)

@app.on_event("shutdown")
async def shutdown():
    logger.info("🛑 Encerrando servidor...")

    # Fechar todas as conexões
    for email, data in active_sessions.items():
        try:
            await data["websocket"].close()
        except:
            pass

    logger.info("✅ Servidor encerrado")

# ═══════════════════════════════════════════════════════
# EXECUTAR SERVIDOR
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload em desenvolvimento
        log_level="info"
    )
