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

# ✅ CORREÇÃO CRÍTICA: Carregar variáveis de ambiente do arquivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Variáveis de ambiente carregadas do arquivo .env")
except ImportError:
    print("⚠️ python-dotenv não instalado - usando variáveis de ambiente do sistema")

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
# 🔒 SEGURANÇA: Documentação DESABILITADA em produção
app = FastAPI(
    title="Fishing Bot Server",
    description="Servidor multi-usuário para Fishing Bot",
    version="1.0.0",
    docs_url=None,  # ✅ DESABILITADO: /docs
    redoc_url=None,  # ✅ DESABILITADO: /redoc
    openapi_url=None  # ✅ DESABILITADO: /openapi.json
)

logger.info("✅ Documentação Swagger PERMANENTEMENTE DESABILITADA (segurança)")


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
        logger.info(f"📋 Configurações:")
        logger.info(f"   KEYMASTER_URL: {KEYMASTER_URL}")
        logger.info(f"   PROJECT_ID: {PROJECT_ID}")
        logger.info(f"   HWID: {hwid[:16]}...")

        payload = {
            "activation_key": license_key,
            "hardware_id": hwid,
            "project_id": PROJECT_ID
        }

        logger.info(f"📤 Payload sendo enviado: {json.dumps(payload, indent=2)}")

        response = requests.post(
            f"{KEYMASTER_URL}/validate",
            json=payload,
            timeout=10
        )

        logger.info(f"📥 Response Status: {response.status_code}")
        logger.info(f"📥 Response Body: {response.text[:500]}...")

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
# ✅ CORREÇÃO: Salvar banco em /app/data para persistência em Docker
import os
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "fishing_bot.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
db_pool = DatabasePool(DB_PATH, pool_size=20)

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
                login TEXT,
                email TEXT,
                password TEXT,
                total_fish INTEGER DEFAULT 0,
                month_fish INTEGER DEFAULT 0,
                last_fish_date TEXT
            )
        """)

        # ✅ NOVA: Tabela de tentativas de reset (anti-brute-force + notificação)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reset_attempts (
                license_key TEXT PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                last_attempt TEXT,
                last_hwid_tried TEXT,
                blocked_until TEXT
            )
        """)

        # ✅ NOVA: Tabela de logs de segurança (para painel admin)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                event_type TEXT NOT NULL,
                license_key TEXT,
                hwid TEXT,
                details TEXT,
                severity TEXT
            )
        """)

    logger.info("✅ Banco de dados inicializado (HWID bindings + security)")

# Inicializar ao startar
init_database()

# ═══════════════════════════════════════════════════════
# FUNÇÕES DE SEGURANÇA
# ═══════════════════════════════════════════════════════

def log_security_event(event_type: str, license_key: str, hwid: str, details: str, severity: str = "WARNING"):
    """
    📝 Registrar evento de segurança para painel admin

    Args:
        event_type: Tipo do evento (ex: "HWID_MISMATCH", "RESET_BLOCKED", etc)
        license_key: License key envolvida
        hwid: HWID tentado
        details: Detalhes do evento
        severity: INFO, WARNING, CRITICAL
    """
    try:
        with db_pool.get_write_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO security_logs (event_type, license_key, hwid, details, severity)
                VALUES (?, ?, ?, ?, ?)
            """, (event_type, license_key[:10] + "...", hwid[:16] + "...", details, severity))

        logger.warning(f"🔐 {severity}: {event_type} - {details}")
    except Exception as e:
        logger.error(f"Erro ao logar evento de segurança: {e}")

def check_reset_attempts(license_key: str) -> tuple[bool, str]:
    """
    🚫 Verificar se license key está bloqueada por tentativas excessivas

    Returns:
        (bloqueado, mensagem)
    """
    try:
        with db_pool.get_read_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT attempts, last_attempt, blocked_until
                FROM reset_attempts
                WHERE license_key = ?
            """, (license_key,))

            result = cursor.fetchone()

            if not result:
                return (False, "")  # Primeira tentativa

            attempts, last_attempt, blocked_until = result

            # Verificar se está bloqueado
            if blocked_until:
                from datetime import datetime
                blocked_until_dt = datetime.fromisoformat(blocked_until)
                now = datetime.now()

                if now < blocked_until_dt:
                    remaining = int((blocked_until_dt - now).total_seconds() / 60)
                    return (True, f"Bloqueado por tentativas excessivas. Aguarde {remaining} minutos.")

            # Verificar se passou 1 hora desde última tentativa (resetar contador)
            if last_attempt:
                from datetime import datetime, timedelta
                last_dt = datetime.fromisoformat(last_attempt)
                if datetime.now() - last_dt > timedelta(hours=1):
                    # Resetar contador
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE reset_attempts
                        SET attempts = 0, blocked_until = NULL
                        WHERE license_key = ?
                    """, (license_key,))
                    return (False, "")

            # Verificar se atingiu limite (3 tentativas)
            if attempts >= 3:
                return (True, "Limite de tentativas atingido. Aguarde 1 hora ou contate o admin.")

            return (False, "")

    except Exception as e:
        logger.error(f"Erro ao verificar tentativas: {e}")
        return (False, "")

def increment_reset_attempts(license_key: str, hwid: str):
    """
    ➕ Incrementar contador de tentativas de reset

    Bloqueia por 1 hora após 3 tentativas
    """
    try:
        from datetime import datetime, timedelta

        with db_pool.get_write_connection() as conn:
            cursor = conn.cursor()

            # Verificar se já existe
            cursor.execute("SELECT attempts FROM reset_attempts WHERE license_key = ?", (license_key,))
            result = cursor.fetchone()

            if result:
                new_attempts = result[0] + 1

                # Bloquear se atingiu 3 tentativas
                blocked_until = None
                if new_attempts >= 3:
                    blocked_until = (datetime.now() + timedelta(hours=1)).isoformat()
                    log_security_event(
                        "RESET_BLOCKED",
                        license_key,
                        hwid,
                        f"Bloqueado por {new_attempts} tentativas de reset com HWID incorreto",
                        "CRITICAL"
                    )

                cursor.execute("""
                    UPDATE reset_attempts
                    SET attempts = ?, last_attempt = ?, last_hwid_tried = ?, blocked_until = ?
                    WHERE license_key = ?
                """, (new_attempts, datetime.now().isoformat(), hwid, blocked_until, license_key))
            else:
                # Primeira tentativa
                cursor.execute("""
                    INSERT INTO reset_attempts (license_key, attempts, last_attempt, last_hwid_tried)
                    VALUES (?, 1, ?, ?)
                """, (license_key, datetime.now().isoformat(), hwid))

        logger.info(f"🔢 Reset attempts incrementado para {license_key[:10]}...")
    except Exception as e:
        logger.error(f"Erro ao incrementar tentativas: {e}")

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
    def __init__(self, login: str, license_key: str = None):
        # ✅ CORREÇÃO #6: Thread-safety para modificações de estado (100+ usuários)
        self.lock = threading.RLock()

        self.login = login
        self.license_key = license_key  # ✅ NOVO: Para salvar stats no banco

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
        self.two_rod_mode = False  # ✅ NOVO: Modo 2 varas (apenas slots 1-2)

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

            # ✅ NOVO: Atualizar two_rod_mode
            if "two_rod_mode" in config:
                self.two_rod_mode = bool(config["two_rod_mode"])
                modo_str = "ATIVO (apenas slots 1-2)" if self.two_rod_mode else "DESATIVADO (6 varas)"
                logger.info(f"🎣 {self.login}: Modo 2 varas: {modo_str}")

            logger.info(f"⚙️ {self.login}: Configurações atualizadas: {validated_config}")
        except Exception as e:
            logger.error(f"❌ {self.login}: Erro ao validar configs: {e}")
            raise

    def increment_fish(self):
        """Incrementar contador de peixes e salvar no banco"""
        with self.lock:
            self.fish_count += 1
            self.last_fish_time = datetime.now()
            logger.info(f"🐟 {self.login}: Peixe #{self.fish_count} capturado!")

            # ✅ NOVO: Salvar no banco de dados
            if self.license_key:
                self._save_fish_count_to_db()

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
        ✅ NOVO: Se two_rod_mode ativo, NUNCA trocar de par (manter no par 1)

        Returns:
            bool: True se deve trocar de par
        """
        # ✅ MODO 2 VARAS: Não trocar de par, acionar manutenção ao invés
        if self.two_rod_mode:
            current_pair = self.rod_pairs[0]  # Sempre par 1
            rod1, rod2 = current_pair
            rod1_exhausted = self.rod_uses[rod1] >= self.use_limit
            rod2_exhausted = self.rod_uses[rod2] >= self.use_limit

            if rod1_exhausted and rod2_exhausted:
                logger.info(f"🎣 {self.login}: MODO 2 VARAS - Par 1 esgotado, mas NÃO trocando de par")
                logger.info(f"   Vara {rod1}: {self.rod_uses[rod1]}/{self.use_limit}, Vara {rod2}: {self.rod_uses[rod2]}/{self.use_limit}")
                logger.info(f"   → Servidor aguarda MANUTENÇÃO ao invés de troca de par")
                # Reset contadores (manutenção vai recarregar)
                self.rod_uses[rod1] = 0
                self.rod_uses[rod2] = 0

            return False  # NUNCA trocar quando modo ativo

        # MODO NORMAL: Trocar quando ambas varas esgotadas
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

    def _save_fish_count_to_db(self):
        """
        ✅ NOVO: Salvar fish_count no banco de dados

        Atualiza total_fish e month_fish (reseta month_fish no dia 1 do mês)
        """
        try:
            from datetime import date
            today = date.today()
            current_month = today.strftime("%Y-%m")

            with db_pool.get_write_connection() as conn:
                cursor = conn.cursor()

                # Buscar última data de pesca
                cursor.execute("SELECT last_fish_date, total_fish, month_fish FROM hwid_bindings WHERE license_key = ?",
                             (self.license_key,))
                row = cursor.fetchone()

                if row:
                    last_fish_date, total_fish, month_fish = row

                    # Verificar se é um novo mês
                    if last_fish_date:
                        last_month = last_fish_date[:7]  # "YYYY-MM"
                        if last_month != current_month:
                            # Novo mês! Resetar month_fish
                            month_fish = 1
                            logger.info(f"📅 {self.login}: Novo mês detectado! Resetando month_fish.")
                        else:
                            month_fish = (month_fish or 0) + 1
                    else:
                        month_fish = 1

                    total_fish = (total_fish or 0) + 1

                    # Atualizar banco
                    cursor.execute("""
                        UPDATE hwid_bindings
                        SET total_fish = ?, month_fish = ?, last_fish_date = ?, last_seen = ?
                        WHERE license_key = ?
                    """, (total_fish, month_fish, today.isoformat(), datetime.now().isoformat(), self.license_key))

                    logger.debug(f"💾 {self.login}: Stats salvas - Total: {total_fish}, Mês: {month_fish}")

        except Exception as e:
            logger.error(f"❌ {self.login}: Erro ao salvar fish_count no banco: {e}")

    def stop_fishing(self):
        """
        🛑 Parar fishing - RESETA VARA PARA SLOT 1

        Chamado quando cliente para o bot (F2 ou stop button).
        SEMPRE reseta para vara 1 para evitar dessincronização.
        """
        with self.lock:
            logger.info(f"🛑 {self.login}: Bot parado - resetando sistema de varas")

            # ✅ RESET: Sempre voltar para PAR 1, VARA 1 (slot absoluto 1)
            # Evita dessincronização quando usuário para e troca vara manualmente
            self.current_pair_index = 0  # Volta pro par 1
            self.current_rod = 1         # Volta pra vara 1 (slot absoluto)

            logger.info(f"   ✅ Sistema resetado - próximo início será SEMPRE na vara 1 (slot absoluto)")

    def pause_fishing(self):
        """
        ⏸️ Pausar fishing - RESETA VARA PARA SLOT 1

        Chamado quando cliente pausa o bot (F1).
        SEMPRE reseta para vara 1 para evitar dessincronização.
        """
        with self.lock:
            logger.info(f"⏸️ {self.login}: Bot pausado - resetando sistema de varas")

            # ✅ RESET: Sempre voltar para PAR 1, VARA 1 (slot absoluto 1)
            # Evita dessincronização quando usuário pausa e troca vara manualmente
            self.current_pair_index = 0  # Volta pro par 1
            self.current_rod = 1         # Volta pra vara 1 (slot absoluto)

            logger.info(f"   ✅ Sistema resetado - ao despausar começará SEMPRE na vara 1 (slot absoluto)")

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

            # ✅ RESET: Resetar vara para slot 1 no cleanup também
            self.current_pair_index = 0
            self.current_rod = 1
            logger.info(f"   ✅ Vara resetada para slot 1 no cleanup")

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
    email: str = None           # Email do usuário (opcional)

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

            # ✅ CORREÇÃO CRÍTICA: Buscar binding pelo HWID primeiro
            # Se o mesmo PC mudou de license key, devemos ATUALIZAR, não bloquear!
            cursor.execute("""
                SELECT license_key, hwid, pc_name, bound_at, login
                FROM hwid_bindings
                WHERE hwid=?
            """, (request.hwid,))

            hwid_binding = cursor.fetchone()

            if hwid_binding:
                # ENCONTROU BINDING PELO HWID
                old_license_key, bound_hwid, bound_pc_name, bound_at, bound_login = hwid_binding

                if old_license_key != request.license_key:
                    # 🔄 MESMO PC, MAS LICENSE KEY DIFERENTE → ATUALIZAR!
                    logger.warning(f"🔄 Detectada mudança de license key para o mesmo PC!")
                    logger.warning(f"   License antiga: {old_license_key[:10]}...")
                    logger.warning(f"   License nova: {request.license_key[:10]}...")
                    logger.warning(f"   HWID: {request.hwid[:16]}...")
                    logger.warning(f"   PC: {request.pc_name or 'N/A'}")

                    # Remover binding antigo
                    cursor.execute("""
                        DELETE FROM hwid_bindings
                        WHERE hwid=? AND license_key=?
                    """, (request.hwid, old_license_key))

                    # Criar novo binding com a nova license key
                    cursor.execute("""
                        INSERT INTO hwid_bindings (license_key, hwid, pc_name, login, email, password)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (request.license_key, request.hwid, request.pc_name, request.login, request.email, request.password))

                    logger.info(f"✅ Binding atualizado com sucesso!")
                    logger.info(f"   Nova license: {request.license_key[:10]}...")

                else:
                    # ✅ MESMO PC, MESMA LICENSE KEY - apenas atualizar timestamp
                    logger.info(f"✅ HWID válido: {request.login} (PC: {request.pc_name or 'N/A'})")

                    cursor.execute("""
                        UPDATE hwid_bindings
                        SET last_seen=?, pc_name=?, login=?, email=?, password=?
                        WHERE hwid=? AND license_key=?
                    """, (datetime.now().isoformat(), request.pc_name, request.login, request.email, request.password, request.hwid, request.license_key))

            else:
                # NÃO TEM HWID VINCULADO → VINCULAR AGORA (primeiro uso)
                cursor.execute("""
                    INSERT INTO hwid_bindings (license_key, hwid, pc_name, login, email, password)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (request.license_key, request.hwid, request.pc_name, request.login, request.email, request.password))

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

@app.post("/auth/reset-password")
async def user_reset_password(request: dict):
    """
    🔑 AUTO-RESET DE SENHA (SEM ADMIN)

    Permite que o próprio usuário resete sua senha usando:
    - License Key (autenticação)
    - HWID (prova que é o mesmo PC)
    - Nova senha

    Body:
    {
        "license_key": "G871-5U0N-PPH2-3YON",
        "hwid": "ABC123...",
        "new_password": "nova_senha_aqui",
        "new_login": "novo_login" (opcional)
    }
    """
    try:
        license_key = request.get("license_key")
        hwid = request.get("hwid")
        new_password = request.get("new_password")
        new_login = request.get("new_login")  # Opcional

        # Validação básica
        if not license_key or not hwid or not new_password:
            raise HTTPException(
                status_code=400,
                detail="license_key, hwid e new_password são obrigatórios"
            )

        if len(new_password) < 6:
            raise HTTPException(
                status_code=400,
                detail="Senha deve ter no mínimo 6 caracteres"
            )

        # ══════════════════════════════════════════════════════
        # 🛡️ PROTEÇÃO: Verificar tentativas excessivas
        # ══════════════════════════════════════════════════════
        bloqueado, msg_bloqueio = check_reset_attempts(license_key)
        if bloqueado:
            raise HTTPException(status_code=429, detail=msg_bloqueio)

        # ══════════════════════════════════════════════════════
        # 1. VALIDAR LICENSE KEY COM KEYMASTER
        # ══════════════════════════════════════════════════════
        keymaster_result = validate_with_keymaster(license_key, hwid)

        if not keymaster_result["valid"]:
            logger.warning(f"❌ Reset senha - Keymaster rejeitou: {license_key[:10]}...")
            raise HTTPException(
                status_code=401,
                detail=keymaster_result["message"]
            )

        # ══════════════════════════════════════════════════════
        # 2. VERIFICAR HWID BINDING (mesmo PC)
        # ══════════════════════════════════════════════════════
        with db_pool.get_read_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT login, hwid, pc_name
                FROM hwid_bindings
                WHERE license_key = ?
            """, (license_key,))

            binding = cursor.fetchone()

        if not binding:
            raise HTTPException(
                status_code=404,
                detail="License key não encontrada no banco de dados"
            )

        old_login, bound_hwid, pc_name = binding

        # Verificar se HWID bate
        if bound_hwid != hwid:
            # 🚨 NOTIFICAÇÃO AO ADMIN: Tentativa de reset em PC diferente
            logger.warning(f"🚨 TENTATIVA DE RESET EM PC DIFERENTE!")
            logger.warning(f"   License: {license_key[:10]}...")
            logger.warning(f"   Login: {old_login}")
            logger.warning(f"   PC original: {pc_name or 'N/A'}")
            logger.warning(f"   HWID esperado: {bound_hwid[:16]}...")
            logger.warning(f"   HWID recebido: {hwid[:16]}...")

            # 📝 Logar evento de segurança para painel admin
            log_security_event(
                "HWID_MISMATCH_RESET",
                license_key,
                hwid,
                f"Tentativa de reset de senha com HWID incorreto. Login: {old_login}, PC: {pc_name or 'N/A'}",
                "WARNING"
            )

            # 🔢 Incrementar contador de tentativas
            increment_reset_attempts(license_key, hwid)

            raise HTTPException(
                status_code=403,
                detail="HWID não corresponde! Este não é o PC vinculado à license key. Contate o admin."
            )

        # ══════════════════════════════════════════════════════
        # 3. ATUALIZAR SENHA (e login se fornecido)
        # ══════════════════════════════════════════════════════
        with db_pool.get_write_connection() as conn:
            cursor = conn.cursor()

            if new_login:
                # Atualizar senha E login
                cursor.execute("""
                    UPDATE hwid_bindings
                    SET password = ?, login = ?, last_seen = ?
                    WHERE license_key = ?
                """, (new_password, new_login, datetime.now().isoformat(), license_key))

                logger.info(f"🔑 Usuário resetou senha e login:")
                logger.info(f"   License: {license_key[:10]}...")
                logger.info(f"   Login antigo: {old_login}")
                logger.info(f"   Login novo: {new_login}")
                logger.info(f"   PC: {pc_name or 'N/A'}")

                message = f"Senha e login atualizados com sucesso! Novo login: {new_login}"
            else:
                # Atualizar apenas senha
                cursor.execute("""
                    UPDATE hwid_bindings
                    SET password = ?, last_seen = ?
                    WHERE license_key = ?
                """, (new_password, datetime.now().isoformat(), license_key))

                logger.info(f"🔑 Usuário resetou senha:")
                logger.info(f"   License: {license_key[:10]}...")
                logger.info(f"   Login: {old_login}")
                logger.info(f"   PC: {pc_name or 'N/A'}")

                message = f"Senha atualizada com sucesso para '{old_login}'!"

        return {
            "success": True,
            "message": message,
            "login": new_login or old_login
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro no reset de senha: {e}")
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
        session = FishingSession(login, license_key=license_key)

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

                # ✅ VALIDAÇÃO: Verificar consistência do modo 2 varas
                if session.two_rod_mode and current_rod > 2:
                    logger.warning(f"⚠️ {login}: INCONSISTÊNCIA DETECTADA!")
                    logger.warning(f"   Modo 2 varas ATIVO mas cliente usando vara {current_rod}")
                    logger.warning(f"   Possível bug ou comportamento anormal")
                    # TODO: Decidir ação (fechar conexão? forçar vara 1?)

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
                # ✅ MODO 2 VARAS: should_switch_rod_pair() retorna False quando modo ativo
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
                #    4. ✅ NOVO: Modo 2 varas E ambas varas esgotadas (recarregar ao invés de trocar par)
                has_feeding = any(op["type"] == "feeding" for op in operations)
                will_clean = session.should_clean()
                has_timeout = any(session.rod_timeout_history.get(r, 0) >= 1 for r in session.rod_timeout_history)

                # ✅ MODO 2 VARAS: Verificar se precisa manutenção (ambas varas esgotadas)
                two_rod_pair_exhausted = False
                if session.two_rod_mode:
                    rod1, rod2 = session.rod_pairs[0]  # Par 1
                    rod1_exhausted = session.rod_uses[rod1] >= session.use_limit
                    rod2_exhausted = session.rod_uses[rod2] >= session.use_limit
                    two_rod_pair_exhausted = rod1_exhausted and rod2_exhausted

                    if two_rod_pair_exhausted:
                        logger.info(f"🔧 {login}: MODO 2 VARAS - Par 1 esgotado, acionando MANUTENÇÃO")

                # Executar manutenção se qualquer condição for verdadeira
                if has_feeding or will_clean or has_timeout or two_rod_pair_exhausted:
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
                    if two_rod_pair_exhausted:
                        reason.append("modo 2 varas esgotado")
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
            # ✅ NOVO: EVENTO: Bot parado (F2 ou stop button)
            # ─────────────────────────────────────────────────
            elif event == "fishing_stopped":
                logger.info(f"🛑 {login}: Cliente parou o bot")
                session.stop_fishing()  # Reseta vara para slot 1

            # ─────────────────────────────────────────────────
            # ✅ NOVO: EVENTO: Bot pausado (F1)
            # ─────────────────────────────────────────────────
            elif event == "fishing_paused":
                logger.info(f"⏸️ {login}: Cliente pausou o bot")
                session.pause_fishing()  # Reseta vara para slot 1

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
# API PÚBLICA: STATS E RANKING
# ═══════════════════════════════════════════════════════

@app.get("/api/stats/{license_key}")
async def get_user_stats(license_key: str):
    """
    📊 Retornar estatísticas do usuário

    Retorna:
    - username (login)
    - total_fish (total de peixes de todos os tempos)
    - month_fish (peixes do mês atual)
    - rank_monthly (posição no ranking mensal)
    - rank_alltime (posição no ranking geral)
    """
    try:
        from datetime import date
        current_month = date.today().strftime("%Y-%m")

        with db_pool.get_read_connection() as conn:
            cursor = conn.cursor()

            # Buscar dados do usuário
            cursor.execute("""
                SELECT login, total_fish, month_fish, last_fish_date
                FROM hwid_bindings
                WHERE license_key = ?
            """, (license_key,))

            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")

            login, total_fish, month_fish, last_fish_date = row

            # Resetar month_fish se for mês diferente
            if last_fish_date and last_fish_date[:7] != current_month:
                month_fish = 0

            # Calcular ranking mensal
            cursor.execute("""
                SELECT COUNT(*) + 1
                FROM hwid_bindings
                WHERE month_fish > ? AND (last_fish_date IS NULL OR last_fish_date >= ?)
            """, (month_fish or 0, f"{current_month}-01"))
            rank_monthly = cursor.fetchone()[0]

            # Calcular ranking geral
            cursor.execute("""
                SELECT COUNT(*) + 1
                FROM hwid_bindings
                WHERE total_fish > ?
            """, (total_fish or 0,))
            rank_alltime = cursor.fetchone()[0]

            return {
                "username": login or "Anônimo",
                "total_fish": total_fish or 0,
                "month_fish": month_fish or 0,
                "rank_monthly": rank_monthly,
                "rank_alltime": rank_alltime
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao buscar stats do usuário: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ranking/monthly")
async def get_monthly_ranking():
    """
    🏆 Retornar TOP 5 ranking mensal

    Retorna lista de usuários com mais peixes capturados este mês
    """
    try:
        from datetime import date
        current_month = date.today().strftime("%Y-%m")
        month_start = f"{current_month}-01"

        with db_pool.get_read_connection() as conn:
            cursor = conn.cursor()

            # Buscar TOP 5 do mês
            cursor.execute("""
                SELECT login, month_fish
                FROM hwid_bindings
                WHERE last_fish_date >= ? AND month_fish > 0
                ORDER BY month_fish DESC
                LIMIT 5
            """, (month_start,))

            rows = cursor.fetchall()

            ranking = []
            for idx, (login, month_fish) in enumerate(rows, start=1):
                ranking.append({
                    "rank": idx,
                    "username": login or "Anônimo",
                    "month_fish": month_fish or 0
                })

            # Calcular período do mês
            today = date.today()
            last_day = (date(today.year, today.month + 1, 1) if today.month < 12 else date(today.year + 1, 1, 1)) - date.resolution
            month_end = last_day.isoformat()

            return {
                "month_start": month_start,
                "month_end": month_end,
                "ranking": ranking
            }

    except Exception as e:
        logger.error(f"❌ Erro ao buscar ranking mensal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ranking/alltime")
async def get_alltime_ranking():
    """
    🏆 Retornar TOP 5 ranking de todos os tempos

    Retorna lista de usuários com mais peixes capturados no total
    """
    try:
        with db_pool.get_read_connection() as conn:
            cursor = conn.cursor()

            # Buscar TOP 5 de todos os tempos
            cursor.execute("""
                SELECT login, total_fish
                FROM hwid_bindings
                WHERE total_fish > 0
                ORDER BY total_fish DESC
                LIMIT 5
            """)

            rows = cursor.fetchall()

            ranking = []
            for idx, (login, total_fish) in enumerate(rows, start=1):
                ranking.append({
                    "rank": idx,
                    "username": login or "Anônimo",
                    "total_fish": total_fish or 0
                })

            return {
                "ranking": ranking
            }

    except Exception as e:
        logger.error(f"❌ Erro ao buscar ranking geral: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
# PAINEL ADMINISTRATIVO
# ═══════════════════════════════════════════════════════

from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi import Header
from pydantic import BaseModel

# Senha do painel admin
# ✅ TOTALMENTE HARDCODED (ignora .env e variáveis de ambiente!)
# NÃO USAR os.getenv() - usar valor direto para debug
ADMIN_PASSWORD = "AdminPesca2025Seguro"  # ← HARDCODED DIRETO!

# ✅ DEBUG: Logar senha configurada COMPLETA (apenas para debug!)
logger.info(f"="*60)
logger.info(f"🔑 ADMIN_PASSWORD HARDCODED DEBUG:")
logger.info(f"   Valor completo: {ADMIN_PASSWORD}")
logger.info(f"   Primeiros 4 chars: {ADMIN_PASSWORD[:4]}...")
logger.info(f"   Total caracteres: {len(ADMIN_PASSWORD)}")
logger.info(f"   Tipo: {type(ADMIN_PASSWORD)}")
logger.info(f"="*60)

class AdminAction(BaseModel):
    license_key: str
    action: str  # 'delete', 'reset_password', 'toggle_active'

# ✅ ROTA DE DEBUG REMOVIDA POR SEGURANÇA
# Não expor informações sensíveis em produção

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel():
    """Serve o painel administrativo HTML"""
    try:
        with open("admin_panel.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Painel admin não encontrado")

@app.get("/admin/api/users")
async def get_all_users(
    admin_password: str = Header(None, alias="admin_password"),
    password: str = None  # Query param alternativo
):
    """Lista todos os usuários (requer senha admin)"""
    # ✅ FIX: Aceitar senha de header OU query param (igual /admin/api/stats)
    senha_recebida = admin_password or password

    logger.info(f"🔐 /admin/api/users - Header: '{admin_password}', Query: '{password}', Usado: '{senha_recebida}'")

    if senha_recebida != ADMIN_PASSWORD:
        logger.error(f"❌ /admin/api/users - SENHA INCORRETA! '{senha_recebida}' != '{ADMIN_PASSWORD}'")
        raise HTTPException(status_code=401, detail="Senha de admin inválida")

    with db_pool.get_read_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT login, pc_name, license_key, bound_at, last_seen, hwid, email, password
            FROM hwid_bindings
            ORDER BY last_seen DESC
        """)
        users = cursor.fetchall()

    users_list = [
        {
            "id": idx + 1,
            "login": user[0],
            "pc_name": user[1],
            "license_key": user[2],
            "created_at": user[3],
            "last_seen": user[4],
            "hwid": user[5],
            "email": user[6] or "N/A",
            "password": user[7] or "N/A",
            "is_active": user[2] in active_sessions
        }
        for idx, user in enumerate(users)
    ]

    return {"success": True, "users": users_list}

@app.delete("/admin/api/user/{license_key}")
async def delete_user(
    license_key: str,
    admin_password: str = Header(None, alias="admin_password"),
    password: str = None  # Query param alternativo
):
    """Deletar usuário (requer senha admin)"""
    # ✅ FIX: Aceitar senha de header OU query param
    senha_recebida = admin_password or password

    if senha_recebida != ADMIN_PASSWORD:
        logger.error(f"❌ DELETE user - Senha incorreta: '{senha_recebida}'")
        raise HTTPException(status_code=401, detail="Senha de admin inválida")

    try:
        with db_pool.get_write_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM hwid_bindings WHERE license_key = ?", (license_key,))

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")

        # Desconectar se estiver ativo
        async with sessions_lock:
            if license_key in active_sessions:
                try:
                    await active_sessions[license_key]["websocket"].close()
                except:
                    pass
                del active_sessions[license_key]

        logger.info(f"🗑️ Admin deletou usuário: {license_key}")
        return {"success": True, "message": "Usuário deletado com sucesso"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao deletar usuário: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/api/user/{license_key}")
async def get_user_details(
    license_key: str,
    admin_password: str = Header(None, alias="admin_password"),
    password: str = None  # Query param alternativo
):
    """Obter detalhes de um usuário específico (requer senha admin)"""
    # ✅ Aceitar senha de header OU query param
    senha_recebida = admin_password or password

    if senha_recebida != ADMIN_PASSWORD:
        logger.error(f"❌ GET user details - Senha incorreta")
        raise HTTPException(status_code=401, detail="Senha de admin inválida")

    try:
        with db_pool.get_read_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT login, pc_name, license_key, bound_at, last_seen,
                       hwid, email, password, total_fish, month_fish, last_fish_date
                FROM hwid_bindings
                WHERE license_key = ?
            """, (license_key,))
            user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        user_data = {
            "login": user[0],
            "pc_name": user[1],
            "license_key": user[2],
            "created_at": user[3],
            "last_seen": user[4],
            "hwid": user[5],
            "email": user[6] or "N/A",
            "password": user[7] or "N/A",
            "total_fish": user[8] or 0,
            "month_fish": user[9] or 0,
            "last_fish_date": user[10] or "N/A",
            "is_active": license_key in active_sessions
        }

        logger.info(f"📊 Admin consultou detalhes do usuário: {user[0]}")
        return {"success": True, "user": user_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar usuário: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/api/reset-password")
async def reset_password(
    request: dict,
    admin_password: str = Header(None, alias="admin_password"),
    password: str = None  # Query param alternativo
):
    """Resetar senha de um usuário (requer senha admin)"""
    # ✅ FIX: Aceitar senha de header OU query param
    senha_recebida = admin_password or password

    if senha_recebida != ADMIN_PASSWORD:
        logger.error(f"❌ RESET PASSWORD - Senha incorreta: '{senha_recebida}'")
        raise HTTPException(status_code=401, detail="Senha de admin inválida")

    license_key = request.get("license_key")
    new_password = request.get("new_password")

    if not license_key or not new_password:
        raise HTTPException(status_code=400, detail="license_key e new_password são obrigatórios")

    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Senha deve ter no mínimo 6 caracteres")

    try:
        with db_pool.get_write_connection() as conn:
            cursor = conn.cursor()

            # Verificar se usuário existe
            cursor.execute("SELECT login FROM hwid_bindings WHERE license_key = ?", (license_key,))
            user = cursor.fetchone()

            if not user:
                raise HTTPException(status_code=404, detail="Usuário não encontrado")

            # Atualizar senha
            cursor.execute("""
                UPDATE hwid_bindings
                SET password = ?
                WHERE license_key = ?
            """, (new_password, license_key))

        logger.info(f"🔑 Admin resetou senha do usuário: {user[0]} (License: {license_key[:10]}...)")
        return {"success": True, "message": f"Senha de '{user[0]}' resetada com sucesso"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao resetar senha: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/api/stats")
async def get_admin_stats(
    admin_password: str = Header(None, alias="admin_password"),
    password: str = None  # Query param alternativo
):
    """Estatísticas gerais do servidor"""
    # ✅ FIX: Aceitar senha de header OU query param
    senha_recebida = admin_password or password

    # ✅ DEBUG COMPLETO: Logar tentativa de autenticação
    logger.info(f"="*60)
    logger.info(f"🔐 AUTENTICAÇÃO ADMIN - DEBUG COMPLETO:")
    logger.info(f"   Header 'admin_password': '{admin_password}'")
    logger.info(f"   Query param 'password': '{password}'")
    logger.info(f"   Senha final usada: '{senha_recebida}'")
    logger.info(f"   Senha esperada: '{ADMIN_PASSWORD}'")
    logger.info(f"   Recebida length: {len(senha_recebida) if senha_recebida else 0}")
    logger.info(f"   Esperada length: {len(ADMIN_PASSWORD)}")
    logger.info(f"   Comparação: {senha_recebida == ADMIN_PASSWORD}")
    logger.info(f"="*60)

    if senha_recebida != ADMIN_PASSWORD:
        logger.error(f"❌ SENHA INCORRETA! Recebida='{senha_recebida}' != Esperada='{ADMIN_PASSWORD}'")
        raise HTTPException(status_code=401, detail="Senha de admin inválida")

    with db_pool.get_read_connection() as conn:
        cursor = conn.cursor()

        # Total de usuários
        cursor.execute("SELECT COUNT(*) FROM hwid_bindings")
        total_users = cursor.fetchone()[0]

    # Calcular total de peixes de todas as sessões ativas
    total_fish = 0
    month_fish = 0  # TODO: Implementar contador mensal quando tiver tabela fish_stats

    for session_data in active_sessions.values():
        if "session" in session_data:
            total_fish += session_data["session"].fish_count

    return {
        "success": True,
        "stats": {
            "total_users": total_users,
            "active_users": len(active_sessions),  # ✅ CORRIGIDO: active_users ao invés de active_connections
            "total_fish": total_fish,
            "month_fish": month_fish,
            "server_version": "2.0.0",
            "keymaster_url": KEYMASTER_URL
        }
    }

@app.get("/admin/api/security-logs")
async def get_security_logs(
    admin_password: str = Header(None, alias="admin_password"),
    password: str = None,  # Query param alternativo
    limit: int = 100,  # Limite de logs (padrão: 100 mais recentes)
    severity: str = None  # Filtro opcional por severity (INFO, WARNING, CRITICAL)
):
    """
    🛡️ Visualizar logs de segurança (requer senha admin)

    Mostra tentativas de reset com HWID incorreto, bloqueios, etc.
    """
    # ✅ Aceitar senha de header OU query param
    senha_recebida = admin_password or password

    if senha_recebida != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Senha de admin inválida")

    try:
        with db_pool.get_read_connection() as conn:
            cursor = conn.cursor()

            # Query base
            query = """
                SELECT id, timestamp, event_type, license_key, hwid, details, severity
                FROM security_logs
            """

            params = []

            # Filtro por severity (opcional)
            if severity:
                query += " WHERE severity = ?"
                params.append(severity)

            # Ordenar por mais recentes
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            logs = cursor.fetchall()

        logs_list = [
            {
                "id": log[0],
                "timestamp": log[1],
                "event_type": log[2],
                "license_key": log[3],
                "hwid": log[4],
                "details": log[5],
                "severity": log[6]
            }
            for log in logs
        ]

        return {
            "success": True,
            "total": len(logs_list),
            "logs": logs_list
        }

    except Exception as e:
        logger.error(f"Erro ao buscar logs de segurança: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

