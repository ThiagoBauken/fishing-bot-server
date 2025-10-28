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
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# CONFIGURAÇÃO DO KEYMASTER (lê do .env)
# ═══════════════════════════════════════════════════════

KEYMASTER_URL = os.getenv("KEYMASTER_URL", "https://private-keygen.pbzgje.easypanel.host")
PROJECT_ID = os.getenv("PROJECT_ID", "67a4a76a-d71b-4d07-9ba8-f7e794ce0578")
PORT = int(os.getenv("PORT", "8122"))

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
    🔒 SESSÃO DE PESCA - TODA LÓGICA PROTEGIDA AQUI!

    Mantém fish_count e decide quando executar ações (feed/clean/break/rod_switch)
    CLIENTE NÃO TEM ACESSO A ESSAS REGRAS - TUDO CONTROLADO PELO SERVIDOR
    """
    def __init__(self, login: str):
        self.login = login

        # Contadores
        self.fish_count = 0
        self.rod_uses = 0

        # Trackers de última ação
        self.last_clean_at = 0
        self.last_feed_at = 0
        self.last_break_at = 0
        self.last_rod_switch_at = 0

        # Timing
        self.session_start = datetime.now()
        self.last_fish_time = None

        logger.info(f"🎣 Nova sessão criada para: {login}")

    def increment_fish(self, rod_uses: int = None):
        """Incrementar contador de peixes e usos de vara"""
        self.fish_count += 1
        self.last_fish_time = datetime.now()

        if rod_uses is not None:
            self.rod_uses = rod_uses

        logger.info(f"🐟 {self.login}: Peixe #{self.fish_count} capturado! (Vara: {self.rod_uses} usos)")

    # ─────────────────────────────────────────────────────────────
    # 🔒 LÓGICA PROTEGIDA - REGRAS DE DECISÃO (NINGUÉM VÊ ISSO!)
    # ─────────────────────────────────────────────────────────────

    def should_feed(self) -> bool:
        """Regra: Alimentar a cada N peixes (protegida)"""
        peixes_desde_ultimo = self.fish_count - self.last_feed_at
        should = peixes_desde_ultimo >= DEFAULT_RULES["feed_interval_fish"]

        if should:
            logger.info(f"🍖 {self.login}: Trigger de feeding ({peixes_desde_ultimo} peixes)")
            self.last_feed_at = self.fish_count

        return should

    def should_clean(self) -> bool:
        """Regra: Limpar a cada N peixes (protegida)"""
        peixes_desde_ultimo = self.fish_count - self.last_clean_at
        should = peixes_desde_ultimo >= DEFAULT_RULES["clean_interval_fish"]

        if should:
            logger.info(f"🧹 {self.login}: Trigger de cleaning ({peixes_desde_ultimo} peixes)")
            self.last_clean_at = self.fish_count

        return should

    def should_break(self) -> bool:
        """Regra: Pausar a cada N peixes OU tempo decorrido (protegida)"""
        peixes_desde_ultimo = self.fish_count - self.last_break_at
        tempo_decorrido = (datetime.now() - self.session_start).seconds / 3600

        # Pausar a cada X peixes OU a cada Y horas
        should = peixes_desde_ultimo >= DEFAULT_RULES["break_interval_fish"] or tempo_decorrido >= 2.0

        if should:
            logger.info(f"☕ {self.login}: Trigger de break ({peixes_desde_ultimo} peixes ou {tempo_decorrido:.1f}h)")
            self.last_break_at = self.fish_count

        return should

    def should_switch_rod(self) -> bool:
        """Regra: Trocar vara a cada N usos (protegida)"""
        should = self.rod_uses >= 20  # Trocar a cada 20 usos

        if should:
            logger.info(f"🎣 {self.login}: Trigger de rod switch ({self.rod_uses} usos)")
            self.rod_uses = 0  # Reset contador

        return should

    def should_randomize_timing(self) -> bool:
        """Regra: Randomizar timing para anti-ban (protegida)"""
        import random
        should = random.random() < 0.05  # 5% de chance

        if should:
            logger.info(f"🎲 {self.login}: Trigger de randomização de timing")

        return should

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
                # Extrair dados do evento
                data = msg.get("data", {})
                rod_uses = data.get("rod_uses", 0)

                # Incrementar contador
                session.increment_fish(rod_uses=rod_uses)

                # ═════════════════════════════════════════════════════════════
                # 🔒 LÓGICA DE DECISÃO - TODA PROTEGIDA NO SERVIDOR!
                # ═════════════════════════════════════════════════════════════
                commands = []

                # 1. Alimentar (a cada N peixes)
                if session.should_feed():
                    commands.append({"cmd": "feed", "params": {"clicks": 5}})
                    logger.info(f"🍖 {login}: Comando FEED enviado")

                # 2. Limpar (a cada N peixes)
                if session.should_clean():
                    commands.append({"cmd": "clean", "params": {}})
                    logger.info(f"🧹 {login}: Comando CLEAN enviado")

                # 3. Pausar (a cada N peixes ou tempo)
                if session.should_break():
                    import random
                    duration = random.randint(30, 60)  # Duração aleatória (anti-ban)
                    commands.append({"cmd": "break", "params": {"duration_minutes": duration}})
                    logger.info(f"☕ {login}: Comando BREAK enviado ({duration} min)")

                # 4. Trocar vara (a cada 20 usos)
                if session.should_switch_rod():
                    commands.append({"cmd": "switch_rod", "params": {}})
                    logger.info(f"🎣 {login}: Comando SWITCH_ROD enviado")

                # 5. Randomizar timing (5% chance - anti-ban)
                if session.should_randomize_timing():
                    import random
                    commands.append({
                        "cmd": "adjust_timing",
                        "params": {
                            "click_delay": random.uniform(0.08, 0.15),
                            "movement_pause_min": random.uniform(0.2, 0.4),
                            "movement_pause_max": random.uniform(0.5, 0.8)
                        }
                    })
                    logger.info(f"🎲 {login}: Comando ADJUST_TIMING enviado")

                # Enviar todos os comandos
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

    # Ler configurações do .env
    reload = os.getenv("RELOAD", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    logger.info(f"🚀 Iniciando servidor na porta {PORT}...")

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=PORT,
        reload=reload,
        log_level=log_level
    )
