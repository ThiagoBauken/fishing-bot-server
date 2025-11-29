#!/usr/bin/env python3
"""
🧪 Teste Completo do Servidor Python FastAPI
Simula o comportamento do UnifiedAuthDialog e testa todos os endpoints
"""

import requests
import json
import asyncio
import websockets
import uuid

# Configuração do servidor
SERVER_URL = "http://localhost:8122"
WS_URL = "ws://localhost:8122/ws"

# Dados de teste
TEST_LOGIN = f"test_user_{uuid.uuid4().hex[:8]}"
TEST_PASSWORD = "test_password_123"
TEST_LICENSE_KEY = "TEST-KEY-" + uuid.uuid4().hex[:16].upper()
TEST_HWID = uuid.uuid4().hex
TEST_PC_NAME = "TEST-PC"

def print_separator(title=""):
    """Imprimir separador visual"""
    print("\n" + "="*70)
    if title:
        print(f"  {title}")
        print("="*70)

def test_health():
    """Teste 1: Health Check"""
    print_separator("TESTE 1: Health Check")

    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        print(f"✅ Status Code: {response.status_code}")
        print(f"✅ Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_auth_activate():
    """Teste 2: POST /auth/activate"""
    print_separator("TESTE 2: POST /auth/activate")

    payload = {
        "login": TEST_LOGIN,
        "password": TEST_PASSWORD,
        "license_key": TEST_LICENSE_KEY,
        "hwid": TEST_HWID,
        "pc_name": TEST_PC_NAME,
        "email": f"{TEST_LOGIN}@test.com"
    }

    print(f"📤 Enviando payload:")
    print(json.dumps(payload, indent=2))

    try:
        response = requests.post(
            f"{SERVER_URL}/auth/activate",
            json=payload,
            timeout=15  # Keymaster pode demorar
        )

        print(f"\n📥 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('success')}")
            print(f"✅ Message: {data.get('message')}")
            print(f"✅ Token: {data.get('token', 'N/A')[:30]}...")

            if data.get('rules'):
                print(f"✅ Rules received: {len(data['rules'])} configurações")

            return data.get('token'), data.get('success', False)
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            print(f"❌ Response: {response.text[:500]}")
            return None, False

    except Exception as e:
        print(f"❌ Erro: {e}")
        return None, False

async def test_websocket(token):
    """Teste 3: WebSocket /ws"""
    print_separator("TESTE 3: WebSocket /ws")

    if not token:
        print("❌ Token não disponível - pulando teste WebSocket")
        return False

    try:
        print(f"🔌 Conectando ao WebSocket: {WS_URL}")

        async with websockets.connect(WS_URL, ping_timeout=10) as websocket:
            # 1. Enviar autenticação
            auth_msg = {"token": token}
            print(f"📤 Enviando autenticação: {auth_msg}")
            await websocket.send(json.dumps(auth_msg))

            # 2. Receber resposta
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            print(f"📥 Resposta: {data}")

            if data.get('status') == 'authenticated':
                print(f"✅ Autenticado com sucesso!")
                print(f"✅ Login: {data.get('login', 'N/A')}")
                print(f"✅ PC: {data.get('pc_name', 'N/A')}")

                # 3. Enviar ping (heartbeat)
                ping_msg = {"event": "ping"}
                print(f"\n📤 Enviando ping: {ping_msg}")
                await websocket.send(json.dumps(ping_msg))

                # 4. Receber pong
                pong = await asyncio.wait_for(websocket.recv(), timeout=5)
                pong_data = json.loads(pong)
                print(f"📥 Pong recebido: {pong_data}")

                # 5. Simular fish_caught
                fish_msg = {"event": "fish_caught"}
                print(f"\n📤 Enviando fish_caught: {fish_msg}")
                await websocket.send(json.dumps(fish_msg))

                # 6. Receber resposta
                fish_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                fish_data = json.loads(fish_response)
                print(f"📥 Resposta fish_caught: {fish_data}")

                if fish_data.get('fish_count'):
                    print(f"✅ Fish count atualizado: {fish_data['fish_count']}")

                return True
            else:
                print(f"❌ Falha na autenticação: {data.get('error', 'Unknown')}")
                return False

    except asyncio.TimeoutError:
        print("❌ Timeout na conexão WebSocket")
        return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_stats_endpoint():
    """Teste 4: GET /api/stats/{license_key}"""
    print_separator("TESTE 4: GET /api/stats/{license_key}")

    try:
        url = f"{SERVER_URL}/api/stats/{TEST_LICENSE_KEY}"
        print(f"📤 GET {url}")

        response = requests.get(url, timeout=10)
        print(f"📥 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Username: {data.get('username', 'N/A')}")
            print(f"✅ Total Fish: {data.get('total_fish', 0)}")
            print(f"✅ Month Fish: {data.get('month_fish', 0)}")
            print(f"✅ Rank Monthly: #{data.get('rank_monthly', 0)}")
            print(f"✅ Rank All-Time: #{data.get('rank_alltime', 0)}")
            return True
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            print(f"❌ Response: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_ranking_monthly():
    """Teste 5: GET /api/ranking/monthly"""
    print_separator("TESTE 5: GET /api/ranking/monthly")

    try:
        url = f"{SERVER_URL}/api/ranking/monthly"
        print(f"📤 GET {url}")

        response = requests.get(url, timeout=10)
        print(f"📥 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Período: {data.get('month_start')} a {data.get('month_end')}")
            print(f"✅ Total usuários: {data.get('total', 0)}")

            ranking = data.get('ranking', [])
            print(f"✅ Top {len(ranking)} no ranking:")
            for entry in ranking[:5]:  # Top 5
                print(f"   #{entry['rank']} - {entry['username']} - {entry['month_fish']} peixes")

            return True
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            print(f"❌ Response: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def test_ranking_alltime():
    """Teste 6: GET /api/ranking/alltime"""
    print_separator("TESTE 6: GET /api/ranking/alltime")

    try:
        url = f"{SERVER_URL}/api/ranking/alltime"
        print(f"📤 GET {url}")

        response = requests.get(url, timeout=10)
        print(f"📥 Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Total usuários: {data.get('total', 0)}")

            ranking = data.get('ranking', [])
            print(f"✅ Top {len(ranking)} no ranking:")
            for entry in ranking[:5]:  # Top 5
                print(f"   #{entry['rank']} - {entry['username']} - {entry['total_fish']} peixes")

            return True
        else:
            print(f"❌ Erro HTTP {response.status_code}")
            print(f"❌ Response: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Erro: {e}")
        return False

def main():
    """Executar todos os testes"""
    print_separator("🧪 TESTE COMPLETO DO SERVIDOR PYTHON FASTAPI")
    print(f"Servidor: {SERVER_URL}")
    print(f"WebSocket: {WS_URL}")
    print(f"\n⚠️ IMPORTANTE: Servidor deve estar rodando em localhost:8122")
    print("   Execute: cd server_auth && python server.py")

    results = {}

    # Teste 1: Health
    results['health'] = test_health()

    # Teste 2: Ativação (simula UnifiedAuthDialog)
    token, success = test_auth_activate()
    results['activate'] = success

    # Teste 3: WebSocket
    if token:
        results['websocket'] = asyncio.run(test_websocket(token))
    else:
        results['websocket'] = False
        print("\n⚠️ Pulando teste WebSocket (token não obtido)")

    # Teste 4: Stats
    results['stats'] = test_stats_endpoint()

    # Teste 5: Ranking Mensal
    results['ranking_monthly'] = test_ranking_monthly()

    # Teste 6: Ranking All-Time
    results['ranking_alltime'] = test_ranking_alltime()

    # Resumo
    print_separator("📊 RESUMO DOS TESTES")
    total = len(results)
    passed = sum(1 for v in results.values() if v)

    for test_name, passed_test in results.items():
        status = "✅ PASSOU" if passed_test else "❌ FALHOU"
        print(f"  {test_name:20} - {status}")

    print(f"\n{'='*70}")
    print(f"  Total: {passed}/{total} testes passaram ({passed*100//total}%)")
    print(f"{'='*70}")

    if passed == total:
        print("\n🎉 TODOS OS TESTES PASSARAM!")
        print("✅ Servidor está funcionando corretamente")
        print("✅ Pode fazer rebuild no EasyPanel")
        print("✅ Pode recompilar o .exe com Nuitka")
    else:
        print("\n⚠️ ALGUNS TESTES FALHARAM")
        print("❌ Verifique os logs acima para detalhes")
        print("❌ Corrija os problemas antes de fazer rebuild")

if __name__ == "__main__":
    main()
