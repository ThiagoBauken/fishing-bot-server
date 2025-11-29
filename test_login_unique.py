#!/usr/bin/env python3
"""
Teste de validação de login único
Verifica se o servidor bloqueia logins duplicados
"""

import requests
import sys

SERVER_URL = "http://localhost:8000"  # Alterar se necessário

def test_duplicate_login():
    """Testa se o servidor bloqueia login duplicado"""

    print("="*70)
    print("TESTE: VALIDAÇÃO DE LOGIN ÚNICO")
    print("="*70)
    print()

    # Cenário: Dois usuários tentando usar o MESMO login
    user1 = {
        "login": "thiago_teste",
        "email": "user1@test.com",
        "password": "senha123",
        "license_key": "TEST-LICENSE-001",
        "hwid": "HWID-PC1-12345",
        "pc_name": "PC-User1"
    }

    user2 = {
        "login": "thiago_teste",  # ❌ MESMO LOGIN!
        "email": "user2@test.com",
        "password": "senha456",
        "license_key": "TEST-LICENSE-002",  # License diferente
        "hwid": "HWID-PC2-67890",  # PC diferente
        "pc_name": "PC-User2"
    }

    print("[1/3] Ativando User1 (deve funcionar)...")
    try:
        response = requests.post(
            f"{SERVER_URL}/auth/activate",
            json=user1,
            timeout=10
        )

        if response.status_code == 200:
            print("   ✅ User1 ativado com sucesso!")
            print(f"   Login: {user1['login']}")
            print(f"   License: {user1['license_key']}")
        else:
            print(f"   ❌ ERRO ao ativar User1: {response.status_code}")
            print(f"   Resposta: {response.text}")
            return False

    except Exception as e:
        print(f"   ❌ ERRO de conexão: {e}")
        print(f"   Certifique-se que o servidor está rodando em {SERVER_URL}")
        return False

    print()
    print("[2/3] Tentando ativar User2 com MESMO login (deve BLOQUEAR)...")
    try:
        response = requests.post(
            f"{SERVER_URL}/auth/activate",
            json=user2,
            timeout=10
        )

        if response.status_code == 409:
            print("   ✅ BLOQUEIO CORRETO! (HTTP 409)")
            data = response.json()
            print(f"   Mensagem: {data.get('detail', 'N/A')}")
            print()
            print("   🎯 VALIDAÇÃO FUNCIONANDO!")

        elif response.status_code == 200:
            print("   ❌ ERRO: User2 foi ativado (NÃO DEVERIA!)")
            print("   ⚠️  VALIDAÇÃO NÃO ESTÁ FUNCIONANDO!")
            return False

        else:
            print(f"   ⚠️  Status inesperado: {response.status_code}")
            print(f"   Resposta: {response.text}")

    except Exception as e:
        print(f"   ❌ ERRO: {e}")
        return False

    print()
    print("[3/3] Limpando dados de teste...")
    # Aqui você pode adicionar DELETE se tiver endpoint de admin
    print("   ⚠️  Limpe manualmente o banco de dados:")
    print(f"   DELETE FROM hwid_bindings WHERE login='thiago_teste';")

    print()
    print("="*70)
    print("TESTE CONCLUÍDO!")
    print("="*70)

    return True

if __name__ == "__main__":
    success = test_duplicate_login()
    sys.exit(0 if success else 1)
