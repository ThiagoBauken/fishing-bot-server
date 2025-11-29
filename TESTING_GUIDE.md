# 🧪 Guia de Testes - Multi-Usuário

## ⚡ Teste Rápido (5 minutos)

### 1. Iniciar Servidor
```bash
cd server
python server.py
```

**Verificar logs:**
```
✅ Database pool criado: 20 read connections, 1 write connection
✅ Banco de dados inicializado (HWID bindings)
✅ Servidor pronto para aceitar conexões!
```

---

### 2. Conectar Cliente Único
```bash
cd ..
python main.py
```

**Fluxo esperado:**
1. Ativar licença → HWID vinculado
2. F9 para iniciar pesca
3. Capturar 3 peixes → Servidor envia `request_inventory_scan`
4. Cliente detecta peixes → Servidor constrói sequência
5. Cliente executa limpeza

**Logs do servidor:**
```
🐟 user123: Peixe #1 capturado!
🐟 user123: Peixe #2 capturado!
🐟 user123: Peixe #3 capturado!
🧹 user123: Solicitando scan de inventário (trigger: clean_interval)
🐟 user123: 5 peixes detectados
✅ user123: Sequência de cleaning enviada (12 ações)
```

---

### 3. Teste de Timeout
Deixe o bot rodando sem capturar peixes (inventário vazio).

**Após 3 timeouts consecutivos:**
```
⏰ user123: Timeout #1 - Vara 1: 1 timeout(s) consecutivo(s)
⏰ user123: Timeout #2 - Vara 1: 2 timeout(s) consecutivo(s)
⏰ user123: Timeout #3 - Vara 1: 3 timeout(s) consecutivo(s)
🧹 user123: Trigger de limpeza por timeout (vara 1: 3/3 timeouts)
🧹 user123: Solicitando scan de inventário (trigger: timeout vara 1)
```

---

### 4. Teste de Troca de Par
Use as varas até esgotar par 1 (default: 20 usos cada).

**Logs esperados:**
```
🎣 user123: Comando SWITCH_ROD_PAIR enviado → Vara 3
🎣 user123: Solicitando análise de varas (trigger: switch_rod_pair)
🎣 user123: Status das varas recebido
✅ user123: Sequência de maintenance enviada (25 ações)
```

---

## 🔥 Teste de Concorrência (10+ usuários)

### Script de Teste
Crie `test_concurrent.py`:

```python
import asyncio
import websockets
import json
from datetime import datetime

async def simulate_user(user_id: int):
    """Simular um usuário pescando"""
    uri = "ws://localhost:8122/ws"

    # Token de teste (ajustar com license key real)
    token = f"test-key-{user_id}:hwid123"

    try:
        async with websockets.connect(uri) as ws:
            # Conectar
            await ws.send(json.dumps({"token": token}))

            print(f"[{user_id}] Conectado")

            # Simular 10 peixes
            for fish in range(10):
                await asyncio.sleep(2)  # Simular tempo entre peixes

                await ws.send(json.dumps({
                    "event": "fish_caught",
                    "data": {
                        "rod_uses": {1: fish + 1, 2: 0},
                        "current_rod": 1
                    }
                }))

                print(f"[{user_id}] Peixe #{fish + 1}")

                # Receber resposta do servidor
                response = await ws.recv()
                data = json.loads(response)

                if "cmd" in data:
                    print(f"[{user_id}] Comando recebido: {data['cmd']}")

    except Exception as e:
        print(f"[{user_id}] Erro: {e}")

async def main():
    # Criar 10 usuários simultâneos
    tasks = [simulate_user(i) for i in range(10)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
```

### Executar Teste
```bash
python test_concurrent.py
```

**Verificar:**
- ✅ Todos os 10 usuários conectam sem erro
- ✅ Nenhum race condition nos logs
- ✅ Cada usuário recebe comandos independentes
- ✅ Database pool não esgota conexões

---

## 🔍 Testes de Thread-Safety

### Teste 1: Race Condition em active_sessions

```python
import asyncio
import random

async def stress_test_sessions():
    """Testar adição/remoção simultânea de sessões"""

    async def add_remove_session(user_id: int):
        for _ in range(100):
            # Simular add
            key = f"user-{user_id}"

            async with sessions_lock:
                active_sessions[key] = {"id": user_id}

            await asyncio.sleep(random.random() * 0.01)

            # Simular remove
            async with sessions_lock:
                if key in active_sessions:
                    del active_sessions[key]

            await asyncio.sleep(random.random() * 0.01)

    # 50 usuários fazendo add/remove 100x cada
    tasks = [add_remove_session(i) for i in range(50)]
    await asyncio.gather(*tasks)

    print(f"✅ Teste concluído. active_sessions final: {len(active_sessions)}")

asyncio.run(stress_test_sessions())
```

**Resultado esperado:**
```
✅ Teste concluído. active_sessions final: 0
# Sem KeyError ou race conditions
```

---

### Teste 2: FishingSession State Modifications

```python
import threading
import time

def stress_test_fishing_session():
    """Testar modificações simultâneas de estado"""

    session = FishingSession("test-user")

    def increment_fish_loop():
        for _ in range(1000):
            session.increment_fish()

    def increment_timeout_loop():
        for _ in range(1000):
            session.increment_timeout(1)

    # 10 threads incrementando simultaneamente
    threads = []
    for _ in range(5):
        threads.append(threading.Thread(target=increment_fish_loop))
        threads.append(threading.Thread(target=increment_timeout_loop))

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    print(f"✅ fish_count: {session.fish_count} (esperado: 5000)")
    print(f"✅ total_timeouts: {session.total_timeouts} (esperado: 5000)")

stress_test_fishing_session()
```

**Resultado esperado:**
```
✅ fish_count: 5000 (esperado: 5000)
✅ total_timeouts: 5000 (esperado: 5000)
# Contadores exatos, sem race conditions
```

---

## 💾 Teste de Database Pool

### Teste de Leitura Concorrente

```python
import threading
import time

def test_concurrent_reads():
    """Testar leituras simultâneas do pool"""

    def read_binding():
        with db_pool.get_read_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM hwid_bindings")
            result = cursor.fetchone()
            time.sleep(0.01)  # Simular processamento
            return result

    # 50 threads lendo simultaneamente
    threads = []
    start = time.time()

    for _ in range(50):
        t = threading.Thread(target=read_binding)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = time.time() - start

    print(f"✅ 50 leituras concorrentes em {duration:.2f}s")
    print(f"   Pool size: 20 conexões reutilizadas")

test_concurrent_reads()
```

---

### Teste de Escrita Serializada

```python
def test_serialized_writes():
    """Testar que writes são serializados"""

    def write_binding(user_id: int):
        with db_pool.get_write_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO hwid_bindings
                (license_key, hwid, login)
                VALUES (?, ?, ?)
            """, (f"key-{user_id}", f"hwid-{user_id}", f"user-{user_id}"))
            time.sleep(0.01)  # Simular processamento

    # 20 threads escrevendo (devem ser serializadas pelo lock)
    threads = []
    start = time.time()

    for i in range(20):
        t = threading.Thread(target=write_binding, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    duration = time.time() - start

    # Verificar que foram serializadas (não paralelas)
    print(f"✅ 20 escritas em {duration:.2f}s")
    print(f"   Esperado: ~0.2s (serializado)")
    print(f"   Se < 0.1s: WARNING - não está serializando!")

test_serialized_writes()
```

---

## 🧹 Teste de Cleanup

### Teste de Memory Leak

```python
import psutil
import os

def test_session_cleanup():
    """Testar que sessões são limpas sem memory leak"""

    process = psutil.Process(os.getpid())

    # Memória inicial
    mem_start = process.memory_info().rss / 1024 / 1024  # MB

    # Criar e destruir 1000 sessões
    for i in range(1000):
        session = FishingSession(f"user-{i}")

        # Simular uso
        for _ in range(100):
            session.increment_fish()
            session.increment_timeout(1)

        # Cleanup
        session.cleanup()

        # Forçar garbage collection
        if i % 100 == 0:
            import gc
            gc.collect()
            mem_current = process.memory_info().rss / 1024 / 1024
            print(f"Sessão {i}: {mem_current:.1f} MB")

    # Memória final
    mem_end = process.memory_info().rss / 1024 / 1024

    print(f"\n✅ Teste concluído:")
    print(f"   Memória inicial: {mem_start:.1f} MB")
    print(f"   Memória final: {mem_end:.1f} MB")
    print(f"   Diferença: {mem_end - mem_start:.1f} MB")
    print(f"   Esperado: < 10 MB")

test_session_cleanup()
```

---

## ⚙️ Teste de Config Validation

### Teste de Valores Inválidos

```python
def test_config_validation():
    """Testar que configs inválidas são bloqueadas"""

    session = FishingSession("test-user")

    # Teste 1: Valores negativos
    try:
        session.update_config({"fish_per_feed": -10})
        # Deve ajustar para 1 (mínimo)
        assert session.user_config.get("fish_per_feed") == 1
        print("✅ Valores negativos bloqueados")
    except Exception as e:
        print(f"❌ Falha: {e}")

    # Teste 2: Valores extremamente grandes
    try:
        session.update_config({"clean_interval": 99999})
        # Deve ajustar para 50 (máximo)
        assert session.user_config.get("clean_interval") == 50
        print("✅ Valores grandes limitados")
    except Exception as e:
        print(f"❌ Falha: {e}")

    # Teste 3: Tipos incorretos
    try:
        session.update_config({"rod_switch_limit": "invalid"})
        # Deve rejeitar ou converter
        print("✅ Tipos inválidos tratados")
    except Exception as e:
        print(f"❌ Falha: {e}")

test_config_validation()
```

---

## 📊 Checklist de Testes

Antes de dar OK para produção:

### Testes Funcionais
- [ ] Cliente conecta e desconecta sem erros
- [ ] Captura de peixe incrementa contador
- [ ] Limpeza automática funciona (3 peixes)
- [ ] Timeout trigger funciona (3 timeouts)
- [ ] Troca de vara funciona (20 usos)
- [ ] Troca de par funciona (40 usos)

### Testes de Concorrência
- [ ] 10 usuários simultâneos sem race conditions
- [ ] 50 usuários simultâneos sem travamentos
- [ ] 100 usuários simultâneos sem crash

### Testes de Segurança
- [ ] Configs inválidas são rejeitadas
- [ ] HWID binding funciona (mesmo PC OK, outro PC bloqueado)
- [ ] License key inválida é rejeitada

### Testes de Performance
- [ ] Database pool não esgota conexões
- [ ] Memória estável após 1000 conexões/desconexões
- [ ] CPU < 30% com 50 usuários

### Testes de Robustez
- [ ] Servidor aguenta restart sem perder sessões ativas
- [ ] Cliente reconecta após queda de rede
- [ ] Cleanup de sessões funciona no shutdown

---

## 🐛 Debug de Problemas

### Problema: Race Conditions

**Sintomas:**
```
KeyError: 'user-123' in active_sessions
RuntimeError: dictionary changed size during iteration
```

**Verificar:**
```bash
# Procurar acessos a active_sessions sem lock
grep -n "active_sessions\[" server/server.py | grep -v "async with sessions_lock"
```

---

### Problema: Database Locked

**Sintomas:**
```
sqlite3.OperationalError: database is locked
```

**Verificar:**
```python
# Pool está sendo usado?
grep -n "sqlite3.connect" server/server.py
# Deve retornar apenas linhas dentro de DatabasePool class
```

---

### Problema: Memory Leak

**Sintomas:**
Memória do servidor cresce continuamente

**Verificar:**
```python
# Cleanup está sendo chamado?
grep -n "session.cleanup()" server/server.py
# Deve aparecer em disconnect e shutdown
```

---

**Última Atualização:** 2025-10-29
