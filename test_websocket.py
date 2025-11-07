#!/usr/bin/env python3
"""
Script de teste para verificar se WebSocket está funcionando
"""
import asyncio
import websockets
import json

async def test_websocket():
    """Testar conexão WebSocket"""

    # Token de teste (use o token real dos logs)
    token = "OF5Y-ZPOI-ZFXC-YBAH:be10ce58a64d16ce"

    print("🔵 Conectando ao WebSocket...")

    try:
        # Conectar ao WebSocket
        async with websockets.connect("ws://localhost:8122/ws") as ws:
            print("✅ Conexão estabelecida!")

            # 1. Enviar autenticação
            print("🔑 Enviando token de autenticação...")
            await ws.send(json.dumps({"token": token}))

            # Receber confirmação
            response = await ws.recv()
            print(f"📥 Resposta do servidor: {response}")

            # 2. Enviar sync_config
            print("⚙️ Enviando configurações...")
            await ws.send(json.dumps({
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

            # Receber confirmação
            response = await ws.recv()
            print(f"📥 Resposta sync_config: {response}")

            # 3. Enviar ping
            print("💓 Enviando ping...")
            await ws.send(json.dumps({"event": "ping"}))

            response = await ws.recv()
            print(f"📥 Resposta ping: {response}")

            print("✅ Teste concluído com sucesso!")

    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_websocket())
