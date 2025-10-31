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
import sys
import queue  # ✅ CORREÇÃO #9: Para DatabasePool
import threading  # ✅ CORREÇÃO #6 e #9: Para locks e pool

# Adicionar diretório do script ao path (para imports locais)
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# ✅ NOVO: Import do ActionSequenceBuilder para construir sequências
try:
    from action_sequences import ActionSequenceBuilder
except ImportError:
    # Fallback: tentar import relativo
    try:
        from .action_sequences import ActionSequenceBuilder
    except ImportError:
        # Último recurso: adicionar pasta server ao path
        server_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server')
        if server_dir not in sys.path:
            sys.path.insert(0, server_dir)
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

# ✅ CORREÇÃO #9: Connection Pool para 100+ usuários simultâneos
class DatabasePool:
    """
    Pool de conexões SQLite para alta concorrência

    SQLite tem limitações com writes simultâneos, então:
    - Pool de conexões READ (compartilhadas)
    - Conexão WRITE única com lock (serialize writes)
    """
    def __init__(self, db_path: str, pool_size: int = 10):
        self.db_path = db_path
        self.pool_size = pool_size
        self.read_pool = queue.Queue(maxsize=pool_size)
        self.write_lock = threading.Lock()
        self._write_conn = None

        # Criar pool de conexões READ
        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # Retornar dicts
            self.read_pool.put(conn)

        # Criar conexão WRITE única
        self._write_conn = sqlite3.connect(db_path, check_same_thread=False)
        self._write_conn.isolation_level = None  # Autocommit

        logger.info(f"✅ Database pool criado: {pool_size} read connections, 1 write connection")

    def get_read_connection(self):
        """Pegar conexão READ do pool (context manager)"""
        return _ReadConnection(self)

    def get_write_connection(self):
        """Pegar conexão WRITE (context manager)"""
        return _WriteConnection(self)

    def close_all(self):
        """Fechar todas as conexões"""
        while not self.read_pool.empty():
            conn = self.read_pool.get()
            conn.close()

        if self._write_conn:
            self._write_conn.close()

class _ReadConnection:
    """Context manager para conexões READ"""
    def __init__(self, pool: DatabasePool):
        self.pool = pool
        self.conn = None

    def __enter__(self):
        self.conn = self.pool.read_pool.get()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.pool.read_pool.put(self.conn)

class _WriteConnection:
    """Context manager para conexão WRITE"""
    def __init__(self, pool: DatabasePool):
        self.pool = pool

    def __enter__(self):
        self.pool.write_lock.acquire()
        return self.pool._write_conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.pool._write_conn.commit()
        else:
            self.pool._write_conn.rollback()
        self.pool.write_lock.release()

# Criar pool global
db_pool = DatabasePool("fishing_bot.db", pool_size=20)

def init_database():
    """
    Inicializar banco de dados SQLite

    APENAS HWID BINDINGS (anti-compartilhamento)
    NÃO precisa de tabela users - Keymaster já valida!
    """
    # ✅ CORREÇÃO #9: Usar pool de conexões
    with db_pool.get_write_connection() as conn:
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

    logger.info("✅ Banco de dados inicializado (HWID bindings)")

# Inicializar ao startar
init_database()

# ═══════════════════════════════════════════════════════
# SESSÕES ATIVAS (em memória)
# ═══════════════════════════════════════════════════════

active_sessions: Dict[str, dict] = {}

# ✅ CORREÇÃO #5: Thread-safety para active_sessions (100+ usuários simultâneos)
sessions_lock = asyncio.Lock()

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
        # ✅ CORREÇÃO #6: Thread-safety para modificações de estado (100+ usuários)
        self.lock = threading.RLock()

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

    def _validate_config(self, config: dict) -> dict:
        """
        ✅ CORREÇÃO #4: Validar configurações para prevenir exploits

        Regras de validação:
        - Valores numéricos devem estar em ranges razoáveis
        - Previne valores negativos
        - Previne valores extremamente grandes (DoS)
        - Garante tipos corretos

        Args:
            config: Configurações recebidas do cliente

        Returns:
            dict: Configurações validadas e sanitizadas

        Raises:
            ValueError: Se configurações inválidas
        """
        validated = {}

        # Limites de validação (min, max, tipo)
        limits = {
            "fish_per_feed": (1, 100, int),
            "clean_interval": (1, 50, int),
            "rod_switch_limit": (1, 100, int),
            "break_interval": (1, 200, int),
            "break_duration": (1, 3600, int),
            "maintenance_timeout": (1, 20, int),
        }

        for key, value in config.items():
            if key in limits:
                min_val, max_val, expected_type = limits[key]

                # Validar tipo
                if not isinstance(value, expected_type):
                    try:
                        value = expected_type(value)
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️ {self.login}: Config '{key}' tipo inválido, usando padrão")
                        continue

                # Validar range
                if value < min_val or value > max_val:
                    logger.warning(f"⚠️ {self.login}: Config '{key}'={value} fora do range [{min_val}, {max_val}], ajustando")
                    value = max(min_val, min(value, max_val))

                validated[key] = value
            else:
                # Permitir outras configs, mas logar
                validated[key] = value
                logger.debug(f"⚙️ {self.login}: Config '{key}' aceita sem validação")

        return validated

    def update_config(self, config: dict):
        """
        ✅ NOVO: Atualizar configurações do usuário

        Recebe configs do cliente e atualiza regras da sessão
        """
        # ✅ CORREÇÃO #4: Validar antes de aplicar
        try:
            validated_config = self._validate_config(config)
            self.user_config.update(validated_config)

            # Atualizar use_limit baseado em rod_switch_limit da config
            if "rod_switch_limit" in validated_config:
                self.use_limit = validated_config["rod_switch_limit"]
                logger.info(f"⚙️ {self.login}: use_limit atualizado para {self.use_limit}")

            logger.info(f"⚙️ {self.login}: Configurações atualizadas: {validated_config}")
        except Exception as e:
            logger.error(f"❌ {self.login}: Erro ao validar configs: {e}")
            raise

    def increment_fish(self):
        """Incrementar contador de peixes"""
        with self.lock:
            self.fish_count += 1
            self.last_fish_time = datetime.now()
            logger.info(f"🐟 {self.login}: Peixe #{self.fish_count} capturado!")

    def increment_timeout(self, current_rod: int):
        """
        ✅ NOVO: Incrementar contador de timeout para vara específica

        Args:
            current_rod: Número da vara que teve timeout (1-6)
        """
        with self.lock:
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
        with self.lock:
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
        with self.lock:
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

    def cleanup(self):
        """
        ✅ CORREÇÃO #3: Cleanup de recursos ao desconectar

        Libera recursos e salva estatísticas finais
        """
        with self.lock:
            session_duration = (datetime.now() - self.session_start).total_seconds()
            logger.info(f"🧹 {self.login}: Limpeza de sessão iniciada")
            logger.info(f"   Duração: {session_duration:.1f}s")
            logger.info(f"   Peixes capturados: {self.fish_count}")
            logger.info(f"   Timeouts totais: {self.total_timeouts}")
            logger.info(f"   Vara atual: {self.current_rod}")

            # Limpar referências (opcional, mas boa prática)
            self.user_config.clear()
            self.rod_uses.clear()
            self.rod_timeout_history.clear()

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

        # ✅ CORREÇÃO #9: Usar pool de conexões (write para SELECT+UPDATE/INSERT)
        with db_pool.get_write_connection() as conn:
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
                    # Commit automático via context manager

                else:
                    # ❌ PC DIFERENTE - bloquear
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
                # Commit automático via context manager

                logger.info(f"🔗 HWID vinculado pela primeira vez:")
                logger.info(f"   License: {request.license_key[:10]}...")
                logger.info(f"   Login: {request.login}")
                logger.info(f"   PC: {request.pc_name or 'N/A'}")
                logger.info(f"   HWID: {request.hwid[:16]}...")

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
        # ✅ CORREÇÃO #9: Usar pool de conexões (read para SELECT apenas)
        with db_pool.get_read_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT login, pc_name FROM hwid_bindings WHERE license_key=?", (license_key,))
            binding = cursor.fetchone()

        if not binding:
            await websocket.send_json({"error": "Token inválido ou licença não vinculada"})
            await websocket.close()
            return

        login, pc_name = binding

        # 3. CRIAR FISHING SESSION (mantém fish_count e decide ações)
        session = FishingSession(login)

        # 4. REGISTRAR SESSÃO ATIVA (thread-safe)
        async with sessions_lock:
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
                # ✅ NOVA ARQUITETURA: Coletar operações e enviar em BATCH
                # ═════════════════════════════════════════════════════════════
                logger.info(f"🔍 {login}: DEBUG - Iniciando construção do batch de operações")
                operations = []

                # 🍖 PRIORIDADE 1: Alimentar (a cada N peixes)
                logger.info(f"🔍 {login}: DEBUG - Verificando should_feed()...")
                if session.should_feed():
                    operations.append({
                        "type": "feeding",
                        "params": {
                            "feeds_per_session": 2,  # Quantas vezes comer
                            "food_template": "filefrito",
                            "eat_template": "eat"
                        }
                    })
                    logger.info(f"🍖 {login}: Operação FEEDING adicionada ao batch")

                # 🎣 PRIORIDADE 2: Trocar par de varas (se AMBAS esgotadas)
                if session.should_switch_rod_pair():
                    target_rod = session.get_next_pair_rod()
                    operations.append({
                        "type": "switch_rod_pair",
                        "params": {
                            "target_rod": target_rod
                        }
                    })
                    logger.info(f"🎣 {login}: Operação SWITCH_ROD_PAIR adicionada ao batch (→ Vara {target_rod})")

                # 🔧 PRIORIDADE 2.5: Manutenção de varas
                # ✅ REGRA: Executar manutenção SE:
                #    1. Houve FEEDING (acabou de comer - verificar vara)
                #    2. Houve TIMEOUT (vara pode estar quebrada/sem isca)
                #    3. Vai fazer CLEANING (verificar antes de limpar)
                has_feeding = any(op["type"] == "feeding" for op in operations)
                will_clean = session.should_clean()
                has_timeout = any(session.rod_timeout_history.get(r, 0) >= 1 for r in session.rod_timeout_history)

                # Executar manutenção se qualquer condição for verdadeira
                if has_feeding or will_clean or has_timeout:
                    operations.append({
                        "type": "maintenance",
                        "params": {}
                    })
                    reason = []
                    if has_feeding:
                        reason.append("após feeding")
                    if has_timeout:
                        reason.append("timeout detectado")
                    if will_clean:
                        reason.append("antes cleaning")
                    logger.info(f"🔧 {login}: Operação MAINTENANCE adicionada ao batch ({', '.join(reason)})")

                # 🧹 PRIORIDADE 3: Limpar (a cada N peixes) - DEPOIS DA MANUTENÇÃO
                # ✅ USAR will_clean (já calculado acima) ao invés de chamar should_clean() novamente!
                # Chamar should_clean() duas vezes causa BUG pois ela modifica last_clean_at na primeira chamada!
                logger.info(f"🔍 {login}: DEBUG - Verificando will_clean (já calculado)...")
                if will_clean:
                    operations.append({
                        "type": "cleaning",
                        "params": {
                            "fish_templates": ["SALMONN", "shark", "herring", "anchovies", "trout"]
                        }
                    })
                    logger.info(f"🧹 {login}: Operação CLEANING adicionada ao batch")

                # 🔄 PRIORIDADE 4: Trocar vara dentro do par (SEMPRE após pescar)
                # ✅ CORREÇÃO: Cliente NÃO decide mais - servidor envia comando!
                # Regra: Trocar vara a cada peixe (vara 1 → vara 2 → vara 1 → ...)
                logger.info(f"🔍 {login}: DEBUG - Adicionando switch_rod (sempre executado)...")
                operations.append({
                    "type": "switch_rod",
                    "params": {
                        "will_open_chest": False  # Troca sem abrir baú
                    }
                })
                logger.info(f"🔄 {login}: Operação SWITCH_ROD adicionada ao batch (troca no par)")

                # ☕ PRIORIDADE 4: Pausar (a cada N peixes ou tempo)
                if session.should_break():
                    import random
                    duration = random.randint(30, 60)  # Duração aleatória (anti-ban)
                    operations.append({
                        "type": "break",
                        "params": {
                            "duration_minutes": duration
                        }
                    })
                    logger.info(f"☕ {login}: Operação BREAK adicionada ao batch ({duration} min)")

                # 🎲 PRIORIDADE 5: Randomizar timing (5% chance - anti-ban)
                if session.should_randomize_timing():
                    import random
                    operations.append({
                        "type": "adjust_timing",
                        "params": {
                            "click_delay": random.uniform(0.08, 0.15),
                            "movement_pause_min": random.uniform(0.2, 0.4),
                            "movement_pause_max": random.uniform(0.5, 0.8)
                        }
                    })
                    logger.info(f"🎲 {login}: Operação ADJUST_TIMING adicionada ao batch")

                # ✅ ENVIAR BATCH ÚNICO (ao invés de comandos separados)
                logger.info(f"🔍 {login}: DEBUG - Verificando operations list: {len(operations)} operações")
                if operations:
                    try:
                        logger.info(f"📤 {login}: DEBUG - Preparando envio do batch...")
                        batch_message = {
                            "cmd": "execute_batch",
                            "operations": operations
                        }
                        logger.info(f"📤 {login}: DEBUG - Mensagem preparada: {batch_message}")

                        await websocket.send_json(batch_message)

                        logger.info(f"📦 {login}: ✅ BATCH enviado com {len(operations)} operação(ões): {[op['type'] for op in operations]}")
                    except Exception as e:
                        logger.error(f"❌ {login}: ERRO ao enviar batch: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    logger.warning(f"⚠️ {login}: Nenhuma operação no batch (não deveria acontecer!)")

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
                    # ✅ ORDEM CORRETA: FEEDING → MAINTENANCE → CLEANING
                    # Timeout = verificar feeding + verificar vara + limpar inventário
                    operations = []

                    # 🍖 PRIORIDADE 1: Verificar se precisa alimentar
                    if session.should_feed():
                        operations.append({
                            "type": "feeding",
                            "params": {
                                "feeds_per_session": 2,
                                "food_template": "filefrito",
                                "eat_template": "eat"
                            }
                        })
                        logger.info(f"🍖 {login}: Operação FEEDING adicionada ao batch (timeout)")

                    # 🔧 PRIORIDADE 2: SEMPRE verificar manutenção de vara (pode estar quebrada/sem isca)
                    operations.append({
                        "type": "maintenance",
                        "params": {
                            "current_rod": current_rod
                        }
                    })
                    logger.info(f"🔧 {login}: Operação MAINTENANCE adicionada ao batch (verificar vara {current_rod})")

                    # 🧹 PRIORIDADE 3: Limpar inventário (DEPOIS da manutenção)
                    operations.append({
                        "type": "cleaning",
                        "params": {
                            "fish_templates": ["SALMONN", "shark", "herring", "anchovies", "trout"]
                        }
                    })
                    logger.info(f"🧹 {login}: Operação CLEANING adicionada ao batch (timeout vara {current_rod})")

                    # ✅ ENVIAR BATCH
                    await websocket.send_json({
                        "cmd": "execute_batch",
                        "operations": operations
                    })
                    logger.info(f"📦 {login}: BATCH de timeout enviado ({len(operations)} operações: cleaning + maintenance)")

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
            # ✅ NOVO: EVENTO: Batch completed (NOVA ARQUITETURA)
            # ─────────────────────────────────────────────────
            elif event == "batch_completed":
                data = msg.get("data", {})
                operations = data.get("operations", [])

                logger.info(f"✅ {login}: BATCH concluído com {len(operations)} operação(ões): {operations}")

                # Atualizar contadores de sessão baseado em quais operações foram executadas
                if "feeding" in operations:
                    session.last_feed_at = session.fish_count
                if "cleaning" in operations:
                    session.last_clean_at = session.fish_count
                if "switch_rod_pair" in operations:
                    session.last_rod_switch_at = session.fish_count

            # ─────────────────────────────────────────────────
            # ✅ NOVO: EVENTO: Batch failed (NOVA ARQUITETURA)
            # ─────────────────────────────────────────────────
            elif event == "batch_failed":
                data = msg.get("data", {})
                operation = data.get("operation", "unknown")
                error = data.get("error", "")

                logger.error(f"❌ {login}: BATCH falhou na operação {operation}: {error}")

                # TODO: Decidir o que fazer em caso de falha
                # - Retry?
                # - Abortar?
                # - Notificar usuário?

            # ─────────────────────────────────────────────────
            # ⚠️ DEPRECATED: Eventos antigos (manter por compatibilidade temporária)
            # ─────────────────────────────────────────────────
            elif event == "sequence_completed":
                data = msg.get("data", {})
                operation = data.get("operation", "unknown")
                logger.info(f"✅ {login}: Sequência {operation} concluída com sucesso (DEPRECATED - use batch_completed)")

                # Atualizar contadores de sessão
                if operation == "feeding":
                    session.last_feed_at = session.fish_count
                elif operation == "cleaning":
                    session.last_clean_at = session.fish_count

            elif event == "sequence_failed":
                data = msg.get("data", {})
                operation = data.get("operation", "unknown")
                step_index = data.get("step_index", 0)
                error = data.get("error", "")
                logger.error(f"❌ {login}: Sequência {operation} falhou no step {step_index}: {error} (DEPRECATED - use batch_failed)")

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
        # Remover sessão (thread-safe)
        async with sessions_lock:
            if license_key and license_key in active_sessions:
                # ✅ CORREÇÃO #3: Cleanup antes de remover
                session_data = active_sessions[license_key]
                if "session" in session_data:
                    session_data["session"].cleanup()

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

    # Fechar todas as conexões (thread-safe)
    async with sessions_lock:
        sessions_to_close = list(active_sessions.items())

    for email, data in sessions_to_close:
        try:
            # ✅ CORREÇÃO #3: Cleanup de cada sessão
            if "session" in data:
                data["session"].cleanup()
            await data["websocket"].close()
        except:
            pass

    # ✅ CORREÇÃO #9: Fechar pool de conexões do banco
    db_pool.close_all()
    logger.info("✅ Database pool fechado")

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
