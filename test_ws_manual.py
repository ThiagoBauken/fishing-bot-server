#!/usr/bin/env python3
"""
Teste manual: Simular o que o cliente DEVERIA fazer
"""
import asyncio
import json

async def test_full_flow():
    """Testar fluxo completo: HTTP + WebSocket"""

    # Usar aiohttp para HTTP e websockets para WS
    import aiohttp

    server_url = "http://localhost:8122"

    print("="*60)
    print("1. TESTANDO ATIVAÇÃO HTTP")
    print("="*60)

    async with aiohttp.ClientSession() as session:
        # 1. Ativação HTTP
        async with session.post(
            f"{server_url}/auth/activate",
            json={
                "login": "TESTE_MANUAL",
                "license_key": "OF5Y-ZPOI-ZFXC-YBAH",
                "hwid": "be10ce58a64d16ce0123456789abcdef",
                "pc_name": "PC_TESTE"
            }
        ) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Response: {json.dumps(data, indent=2)}")

            if resp.status != 200:
                print("❌ Ativação falhou!")
                return

            token = data.get("token")
            rules = data.get("rules", {})

            print(f"\n✅ Token recebido: {token[:30]}...")
            print(f"✅ Rules recebidas: {rules}")

    print("\n" + "="*60)
    print("2. TESTANDO WEBSOCKET")
    print("="*60)

    try:
        # Importar websockets (pode não estar instalado)
        import websockets

        # 2. Conectar WebSocket
        ws_url = "ws://localhost:8122/ws"
        print(f"🔵 Conectando ao WebSocket: {ws_url}")

        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket conectado!")

            # 3. Autenticar
            print(f"🔑 Enviando token...")
            await websocket.send(json.dumps({"token": token}))

            # 4. Receber confirmação
            confirmation = await websocket.recv()
            print(f"📥 Confirmação recebida: {confirmation}")

            # 5. Enviar sync_config
            print("\n⚙️ Enviando configurações...")
            await websocket.send(json.dumps({
                "event": "sync_config",
                "data": {
                    "fish_per_feed": 2,
                    "clean_interval": 1,
                    "rod_switch_limit": 20,
                    "break_interval": 50,
                    "break_duration": 45,
                    "maintenance_timeout": 3
                }
            }))

            # 6. Receber confirmação de sync
            sync_response = await websocket.recv()
            print(f"📥 Resposta sync_config: {sync_response}")

            print("\n✅ TESTE COMPLETO - SUCESSO!")
            print("="*60)

    except ImportError:
        print("❌ Módulo 'websockets' não instalado")
        print("   Instale com: pip install websockets")
    except Exception as e:
        print(f"❌ Erro no WebSocket: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_flow())
