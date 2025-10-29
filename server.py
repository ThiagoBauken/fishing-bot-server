#!/usr/bin/env python3
"""
🎣 Fishing Bot Server - Servidor Multi-Usuário Simples
Gerencia autenticação, licenças e lógica de decisão

VALIDAÇÃO AUTOMÁTICA COM KEYMASTER
Não precisa adicionar license keys manualmente!

🔒 NÍVEL 2 DE PROTEÇÃO:
Servidor envia COORDENADAS e SEQUÊNCIAS completas
Cliente apenas EXECUTA cegamente
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

# ✅ NOVO: Import do ActionSequenceBuilder para construir sequências
from action_sequences import ActionSequenceBuilder

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
    "feed_interval_fish": 2,       # ✅ CORRIGIDO: Alimentar a cada 2 peixes
    "clean_interval_fish": 1,      # ✅ CORRIGIDO: Limpar a cada 1 peixe
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

        # ✅ NOVO: Configurações do usuário (sincronizadas do cliente)
        # Inicializa com DEFAULT_RULES, será sobrescrito quando cliente enviar configs
        self.user_config = DEFAULT_RULES.copy()

        # ✅ Rod tracking multi-vara (sistema de 6 varas em 3 pares)
        self.rod_uses = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}  # Uso por vara
        self.current_rod = 1  # Vara atual em uso
        self.current_pair_index = 0  # Par atual (0=Par1, 1=Par2, 2=Par3)
        self.rod_pairs = [(1,2), (3,4), (5,6)]  # Pares de varas
        self.use_limit = 20  # Limite de usos por vara (será atualizado por user_config)

        # ✅ NOVO: Timeout tracking por vara (para limpeza automática)
        self.rod_timeout_history = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}  # Timeouts consecutivos por vara
        self.total_timeouts = 0  # Total de timeouts (estatística)

        # Trackers de última ação
        self.last_clean_at = 0
        self.last_feed_at = 0
        self.last_break_at = 0
        self.last_rod_switch_at = 0

        # Timing
        self.session_start = datetime.now()
        self.last_fish_time = None

        logger.info(f"🎣 Nova sessão criada para: {login}")

    def update_config(self, config: dict):
        """
        ✅ NOVO: Atualizar configurações do usuário

        Recebe configs do cliente e atualiza regras da sessão
        """
        self.user_config.update(config)

        # Atualizar use_limit baseado em rod_switch_limit da config
        if "rod_switch_limit" in config:
            self.use_limit = config["rod_switch_limit"]
            logger.info(f"⚙️ {self.login}: use_limit atualizado para {self.use_limit}")

        logger.info(f"⚙️ {self.login}: Configurações atualizadas: {config}")

    def increment_fish(self):
        """Incrementar contador de peixes"""
        self.fish_count += 1
        self.last_fish_time = datetime.now()
        logger.info(f"🐟 {self.login}: Peixe #{self.fish_count} capturado!")

    def increment_timeout(self, current_rod: int):
        """
        ✅ NOVO: Incrementar contador de timeout para vara específica

        Args:
            current_rod: Número da vara que teve timeout (1-6)
        """
        if current_rod not in self.rod_timeout_history:
            self.rod_timeout_history[current_rod] = 0

        self.rod_timeout_history[current_rod] += 1
        self.total_timeouts += 1

        logger.info(f"⏰ {self.login}: Timeout #{self.total_timeouts} - Vara {current_rod}: {self.rod_timeout_history[current_rod]} timeout(s) consecutivo(s)")

    def reset_timeout(self, current_rod: int):
        """
        ✅ NOVO: Resetar contador de timeout quando peixe é capturado

        Args:
            current_rod: Número da vara que capturou peixe (1-6)
        """
        if current_rod in self.rod_timeout_history:
            old_count = self.rod_timeout_history[current_rod]
            self.rod_timeout_history[current_rod] = 0
            if old_count > 0:
                logger.info(f"🎣 {self.login}: Vara {current_rod} - timeouts resetados ({old_count} → 0)")

    def should_clean_by_timeout(self, current_rod: int) -> bool:
        """
        ✅ NOVO: Verificar se deve limpar por timeout

        Regra: Limpar quando vara atinge maintenance_timeout timeouts consecutivos

        Args:
            current_rod: Número da vara que teve timeout (1-6)

        Returns:
            bool: True se deve limpar
        """
        maintenance_timeout_limit = self.user_config.get("maintenance_timeout", 3)
        timeouts = self.rod_timeout_history.get(current_rod, 0)

        should = timeouts >= maintenance_timeout_limit

        if should:
            logger.info(f"🧹 {self.login}: Trigger de limpeza por timeout (vara {current_rod}: {timeouts}/{maintenance_timeout_limit} timeouts)")
            # Resetar contador após trigger
            self.rod_timeout_history[current_rod] = 0

        return should

    # ─────────────────────────────────────────────────────────────
    # 🔒 LÓGICA PROTEGIDA - REGRAS DE DECISÃO (NINGUÉM VÊ ISSO!)
    # ─────────────────────────────────────────────────────────────

    def should_feed(self) -> bool:
        """Regra: Alimentar a cada N peixes (protegida)"""
        peixes_desde_ultimo = self.fish_count - self.last_feed_at
        # ✅ USA user_config ao invés de DEFAULT_RULES
        should = peixes_desde_ultimo >= self.user_config["feed_interval_fish"]

        if should:
            logger.info(f"🍖 {self.login}: Trigger de feeding ({peixes_desde_ultimo} peixes)")
            self.last_feed_at = self.fish_count

        return should

    def should_clean(self) -> bool:
        """Regra: Limpar a cada N peixes (protegida)"""
        peixes_desde_ultimo = self.fish_count - self.last_clean_at
        # ✅ USA user_config ao invés de DEFAULT_RULES
        should = peixes_desde_ultimo >= self.user_config["clean_interval_fish"]

        if should:
            logger.info(f"🧹 {self.login}: Trigger de cleaning ({peixes_desde_ultimo} peixes)")
            self.last_clean_at = self.fish_count

        return should

    def should_break(self) -> bool:
        """Regra: Pausar a cada N peixes OU tempo decorrido (protegida)"""
        peixes_desde_ultimo = self.fish_count - self.last_break_at
        tempo_decorrido = (datetime.now() - self.session_start).seconds / 3600

        # ✅ USA user_config ao invés de DEFAULT_RULES
        # Pausar a cada X peixes OU a cada Y horas
        should = peixes_desde_ultimo >= self.user_config["break_interval_fish"] or tempo_decorrido >= 2.0

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

    # ─────────────────────────────────────────────────────────────
    # 🎣 ROD TRACKING SYSTEM (Multi-vara)
    # ─────────────────────────────────────────────────────────────

    def increment_rod_use(self, rod: int):
        """
        Incrementar uso de vara específica

        Args:
            rod: Número da vara (1-6)
        """
        if rod in self.rod_uses:
            self.rod_uses[rod] += 1
            self.current_rod = rod
            logger.info(f"🎣 {self.login}: Vara {rod} usada ({self.rod_uses[rod]}/{self.use_limit} usos)")
        else:
            logger.warning(f"⚠️ {self.login}: Vara inválida: {rod}")

    def should_switch_rod_pair(self) -> bool:
        """
        Verificar se deve trocar de par de varas

        Regra: Trocar quando AMBAS as varas do par atual atingirem o limite de usos

        Returns:
            bool: True se deve trocar de par
        """
        current_pair = self.rod_pairs[self.current_pair_index]
        rod1, rod2 = current_pair

        # Checar se AMBAS as varas do par atingiram limite
        rod1_exhausted = self.rod_uses[rod1] >= self.use_limit
        rod2_exhausted = self.rod_uses[rod2] >= self.use_limit

        if rod1_exhausted and rod2_exhausted:
            logger.info(f"🔄 {self.login}: Par {current_pair} esgotado (Vara {rod1}: {self.rod_uses[rod1]}, Vara {rod2}: {self.rod_uses[rod2]})")
            return True

        return False

    def get_next_pair_rod(self) -> int:
        """
        Obter primeira vara do próximo par e resetar contadores

        Returns:
            int: Número da primeira vara do próximo par
        """
        # Avançar para próximo par (circular)
        next_pair_index = (self.current_pair_index + 1) % len(self.rod_pairs)
        next_pair = self.rod_pairs[next_pair_index]

        # Atualizar índice
        self.current_pair_index = next_pair_index

        # Reset contadores do novo par
        rod1, rod2 = next_pair
        self.rod_uses[rod1] = 0
        self.rod_uses[rod2] = 0

        # ✅ ATUALIZAR current_rod para primeira vara do novo par
        self.current_rod = next_pair[0]

        logger.info(f"🔄 {self.login}: Mudança Par{self.current_pair_index} → Par{next_pair_index+1} {next_pair}")
        logger.info(f"   Primeira vara do novo par: {next_pair[0]}")
        logger.info(f"   ✅ current_rod atualizado para: {self.current_rod}")

        return next_pair[0]  # Retornar primeira vara do par

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
                current_rod = data.get("current_rod", 1)  # ✅ NOVO: Vara atual

                # Incrementar contador de peixes
                session.increment_fish()

                # ✅ NOVO: Incrementar uso da vara atual
                session.increment_rod_use(current_rod)

                # ✅ NOVO: Resetar timeout da vara (peixe capturado = vara funcionando)
                session.reset_timeout(current_rod)

                # ═════════════════════════════════════════════════════════════
                # 🔒 LÓGICA DE DECISÃO - TODA PROTEGIDA NO SERVIDOR!
                # ═════════════════════════════════════════════════════════════
                commands = []

                # 🎣 PRIORIDADE 1: Trocar par de varas (se AMBAS esgotadas)
                if session.should_switch_rod_pair():
                    next_rod = session.get_next_pair_rod()
                    commands.append({
                        "cmd": "switch_rod_pair",
                        "params": {
                            "target_rod": next_rod,
                            "will_open_chest": True  # Vai precisar abrir baú
                        }
                    })
                    logger.info(f"🎣 {login}: Comando SWITCH_ROD_PAIR enviado → Vara {next_rod}")

                # 🍖 PRIORIDADE 2: Alimentar (a cada N peixes)
                if session.should_feed():
                    # Solicitar detecção de comida e botão eat
                    commands.append({
                        "cmd": "request_template_detection",
                        "templates": ["filefrito", "eat"]
                    })
                    logger.info(f"🍖 {login}: Solicitando detecção de comida (feeding)")

                # 🧹 PRIORIDADE 3: Limpar (a cada N peixes)
                if session.should_clean():
                    # Solicitar scan de inventário
                    commands.append({
                        "cmd": "request_inventory_scan"
                    })
                    logger.info(f"🧹 {login}: Solicitando scan de inventário (cleaning)")

                # ☕ PRIORIDADE 4: Pausar (a cada N peixes ou tempo)
                if session.should_break():
                    import random
                    duration = random.randint(30, 60)  # Duração aleatória (anti-ban)
                    commands.append({"cmd": "break", "params": {"duration_minutes": duration}})
                    logger.info(f"☕ {login}: Comando BREAK enviado ({duration} min)")

                # 🎲 PRIORIDADE 5: Randomizar timing (5% chance - anti-ban)
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
            # ✅ NOVO: EVENTO: Sincronizar configurações do cliente
            # ─────────────────────────────────────────────────
            elif event == "sync_config":
                # Receber configurações do cliente e atualizar sessão
                config = msg.get("data", {})
                session.update_config(config)

                # Confirmar recebimento
                await websocket.send_json({
                    "type": "config_synced",
                    "message": "Configurações atualizadas no servidor!",
                    "config": session.user_config
                })
                logger.info(f"⚙️ {login}: Configurações sincronizadas com sucesso")

            # ─────────────────────────────────────────────────
            # ✅ NOVO: EVENTO: Timeout (ciclo sem peixe)
            # ─────────────────────────────────────────────────
            elif event == "timeout":
                # Extrair dados do timeout
                data = msg.get("data", {})
                current_rod = data.get("current_rod", 1)

                # Incrementar contador de timeout
                session.increment_timeout(current_rod)

                # Verificar se precisa limpar por timeout
                if session.should_clean_by_timeout(current_rod):
                    # Enviar comando de limpeza
                    await websocket.send_json({
                        "cmd": "clean",
                        "params": {
                            # Coordenadas do chest (PROTEGIDAS no servidor!)
                            "chest_x": 1400,
                            "chest_y": 500,
                            # Área de scan do inventário
                            "inventory_area": {
                                "x1": 633,
                                "y1": 541,
                                "x2": 1233,
                                "y2": 953
                            },
                            # Coordenadas do divisor (esquerda=inventory, direita=chest)
                            "divider_x": 1243
                        }
                    })
                    logger.info(f"🧹 {login}: Comando CLEAN enviado (trigger: timeout vara {current_rod})")

            # ─────────────────────────────────────────────────
            # ✅ NOVO: EVENTO: Feeding locations detected
            # ─────────────────────────────────────────────────
            elif event == "feeding_locations_detected":
                data = msg.get("data", {})
                food_location = data.get("food_location")
                eat_location = data.get("eat_location")

                logger.info(f"🍖 {login}: Localizações de feeding recebidas")
                logger.info(f"   Food: {food_location}, Eat: {eat_location}")

                # Criar ActionSequenceBuilder com config do usuário
                builder = ActionSequenceBuilder(session.user_config)

                # Construir sequência completa de alimentação
                sequence = builder.build_feeding_sequence(food_location, eat_location)

                # Enviar sequência para cliente executar
                await websocket.send_json({
                    "cmd": "execute_sequence",
                    "actions": sequence,
                    "operation": "feeding"
                })

                logger.info(f"✅ {login}: Sequência de feeding enviada ({len(sequence)} ações)")

            # ─────────────────────────────────────────────────
            # ✅ NOVO: EVENTO: Fish locations detected
            # ─────────────────────────────────────────────────
            elif event == "fish_locations_detected":
                data = msg.get("data", {})
                fish_locations = data.get("fish_locations", [])

                logger.info(f"🐟 {login}: {len(fish_locations)} peixes detectados")

                # Criar ActionSequenceBuilder
                builder = ActionSequenceBuilder(session.user_config)

                # Construir sequência completa de limpeza
                sequence = builder.build_cleaning_sequence(fish_locations)

                # Enviar sequência para cliente executar
                await websocket.send_json({
                    "cmd": "execute_sequence",
                    "actions": sequence,
                    "operation": "cleaning"
                })

                logger.info(f"✅ {login}: Sequência de cleaning enviada ({len(sequence)} ações)")

            # ─────────────────────────────────────────────────
            # ✅ NOVO: EVENTO: Rod status detected
            # ─────────────────────────────────────────────────
            elif event == "rod_status_detected":
                data = msg.get("data", {})
                rod_status = data.get("rod_status", {})
                available_items = data.get("available_items", {})

                logger.info(f"🎣 {login}: Status das varas recebido")
                logger.info(f"   Status: {rod_status}")
                logger.info(f"   Varas disponíveis: {len(available_items.get('rods', []))}")
                logger.info(f"   Iscas disponíveis: {len(available_items.get('baits', []))}")

                # Criar ActionSequenceBuilder
                builder = ActionSequenceBuilder(session.user_config)

                # Construir sequência completa de manutenção
                sequence = builder.build_maintenance_sequence(rod_status, available_items)

                # Enviar sequência para cliente executar
                await websocket.send_json({
                    "cmd": "execute_sequence",
                    "actions": sequence,
                    "operation": "maintenance"
                })

                logger.info(f"✅ {login}: Sequência de maintenance enviada ({len(sequence)} ações)")

            # ─────────────────────────────────────────────────
            # ✅ NOVO: EVENTO: Sequence completed
            # ─────────────────────────────────────────────────
            elif event == "sequence_completed":
                data = msg.get("data", {})
                operation = data.get("operation", "unknown")

                logger.info(f"✅ {login}: Sequência {operation} concluída com sucesso")

                # Atualizar contadores de sessão
                if operation == "feeding":
                    session.last_feed_at = session.fish_count
                elif operation == "cleaning":
                    session.last_clean_at = session.fish_count

            # ─────────────────────────────────────────────────
            # ✅ NOVO: EVENTO: Sequence failed
            # ─────────────────────────────────────────────────
            elif event == "sequence_failed":
                data = msg.get("data", {})
                operation = data.get("operation", "unknown")
                step_index = data.get("step_index", 0)
                error = data.get("error", "")

                logger.error(f"❌ {login}: Sequência {operation} falhou no step {step_index}: {error}")

                # TODO: Decidir o que fazer em caso de falha
                # - Retry?
                # - Abortar?
                # - Notificar usuário?

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
