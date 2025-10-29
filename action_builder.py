#!/usr/bin/env python3
"""
🏗️ Action Builder - Construtor de Sequências de Ações
Servidor constrói sequências COMPLETAS com coordenadas, timing, etc.
Cliente NÃO tem acesso a essas informações!
"""

class ActionBuilder:
    """
    Construtor de sequências de ações para o cliente executar

    SERVIDOR CONTROLA:
    - Coordenadas exatas (onde clicar)
    - Sequência de ações (ordem)
    - Timing entre ações (delays)
    - Validações (templates)

    CLIENTE NÃO SABE:
    - Onde está clicando (recebe coordenadas)
    - O que está fazendo (recebe lista)
    - Por que está fazendo (apenas executa)
    """

    # ═══════════════════════════════════════════════════════
    # COORDENADAS (PROTEGIDAS NO SERVIDOR!)
    # ═══════════════════════════════════════════════════════

    COORDINATES = {
        # Chest/Feeding
        "chest_food_slot1": (1306, 858),
        "chest_food_slot2": (1403, 877),
        "eat_button": (1083, 373),

        # Inventory
        "inventory_area_start": (900, 700),
        "inventory_area_end": (1200, 900),

        # Chest drag (cleaning)
        "chest_area_start": (1400, 500),
        "chest_area_end": (1600, 700),

        # Rod slots
        "rod_slot_1": (709, 1005),
        "rod_slot_2": (805, 1005),
        "rod_slot_3": (899, 1005),
        "rod_slot_4": (992, 1005),
        "rod_slot_5": (1092, 1005),
        "rod_slot_6": (1188, 1005),
    }

    # ═══════════════════════════════════════════════════════
    # TIMING (PROTEGIDO NO SERVIDOR!)
    # ═══════════════════════════════════════════════════════

    TIMING = {
        "chest_open_wait": 1.5,      # Espera após abrir baú
        "after_click_wait": 0.8,     # Espera após clicar
        "eat_click_interval": 0.3,   # Intervalo entre cliques em "eat"
        "before_close_wait": 0.5,    # Espera antes de fechar baú
        "drag_duration": 0.5,        # Duração do arraste
    }

    # ═══════════════════════════════════════════════════════
    # BUILDERS DE SEQUÊNCIAS
    # ═══════════════════════════════════════════════════════

    @classmethod
    def build_feeding_sequence(cls, clicks: int = 5) -> dict:
        """
        Construir sequência de alimentação

        Cliente NÃO sabe:
        - Onde está o baú
        - Onde está a comida
        - Onde está o botão "eat"
        - Quantos cliques fazer

        Args:
            clicks: Número de cliques em "eat" (padrão: 5)

        Returns:
            Comando completo para o cliente executar cegamente
        """
        return {
            "cmd": "sequence",
            "name": "feeding",
            "description": "Alimentação automática",
            "actions": [
                # 1. Abrir baú
                {
                    "type": "key",
                    "key": "esc",
                    "comment": "Abrir baú"
                },

                # 2. Aguardar baú abrir
                {
                    "type": "wait",
                    "duration": cls.TIMING["chest_open_wait"]
                },

                # 3. Validar baú aberto (opcional)
                # {
                #     "type": "template",
                #     "name": "chest_open",
                #     "timeout": 3
                # },

                # 4. Clicar na comida (slot 1)
                {
                    "type": "click",
                    "x": cls.COORDINATES["chest_food_slot1"][0],
                    "y": cls.COORDINATES["chest_food_slot1"][1],
                    "comment": "Pegar comida do baú"
                },

                # 5. Aguardar
                {
                    "type": "wait",
                    "duration": cls.TIMING["after_click_wait"]
                },

                # 6. Clicar em "eat" N vezes
                {
                    "type": "click",
                    "x": cls.COORDINATES["eat_button"][0],
                    "y": cls.COORDINATES["eat_button"][1],
                    "repeat": clicks,
                    "interval": cls.TIMING["eat_click_interval"],
                    "comment": f"Clicar em 'eat' {clicks} vezes"
                },

                # 7. Aguardar antes de fechar
                {
                    "type": "wait",
                    "duration": cls.TIMING["before_close_wait"]
                },

                # 8. Fechar baú
                {
                    "type": "key",
                    "key": "esc",
                    "comment": "Fechar baú"
                }
            ]
        }

    @classmethod
    def build_cleaning_sequence(cls) -> dict:
        """
        Construir sequência de limpeza de inventário

        Cliente NÃO sabe:
        - Área do inventário
        - Área do baú
        - Como fazer drag

        Returns:
            Comando completo para o cliente executar cegamente
        """
        return {
            "cmd": "sequence",
            "name": "cleaning",
            "description": "Limpeza de inventário",
            "actions": [
                # 1. Abrir baú
                {
                    "type": "key",
                    "key": "esc",
                    "comment": "Abrir baú"
                },

                # 2. Aguardar baú abrir
                {
                    "type": "wait",
                    "duration": cls.TIMING["chest_open_wait"]
                },

                # 3. Arrastar itens do inventário para baú
                {
                    "type": "drag",
                    "from_x": cls.COORDINATES["inventory_area_start"][0],
                    "from_y": cls.COORDINATES["inventory_area_start"][1],
                    "to_x": cls.COORDINATES["chest_area_start"][0],
                    "to_y": cls.COORDINATES["chest_area_start"][1],
                    "duration": cls.TIMING["drag_duration"],
                    "comment": "Arrastar itens para baú"
                },

                # 4. Aguardar
                {
                    "type": "wait",
                    "duration": cls.TIMING["before_close_wait"]
                },

                # 5. Fechar baú
                {
                    "type": "key",
                    "key": "esc",
                    "comment": "Fechar baú"
                }
            ]
        }

    @classmethod
    def build_rod_switch_sequence(cls, rod_slot: int) -> dict:
        """
        Construir sequência de troca de vara

        Cliente NÃO sabe:
        - Posição dos slots de vara (1-6)

        Args:
            rod_slot: Número do slot (1-6)

        Returns:
            Comando completo para o cliente executar cegamente
        """
        if rod_slot not in range(1, 7):
            raise ValueError(f"rod_slot deve ser 1-6, recebido: {rod_slot}")

        slot_key = f"rod_slot_{rod_slot}"
        x, y = cls.COORDINATES[slot_key]

        return {
            "cmd": "sequence",
            "name": "rod_switch",
            "description": f"Trocar para vara #{rod_slot}",
            "actions": [
                # 1. Clicar no slot da vara
                {
                    "type": "click",
                    "x": x,
                    "y": y,
                    "comment": f"Clicar no slot da vara {rod_slot}"
                },

                # 2. Aguardar equipar
                {
                    "type": "wait",
                    "duration": 0.5
                }
            ]
        }

    @classmethod
    def build_custom_sequence(cls, actions: list) -> dict:
        """
        Construir sequência customizada

        Permite servidor criar sequências dinâmicas

        Args:
            actions: Lista de ações

        Returns:
            Comando completo
        """
        return {
            "cmd": "sequence",
            "name": "custom",
            "description": "Sequência customizada",
            "actions": actions
        }

    # ═══════════════════════════════════════════════════════
    # HELPERS - AÇÕES ATÔMICAS
    # ═══════════════════════════════════════════════════════

    @staticmethod
    def action_click(x: int, y: int, repeat: int = 1, interval: float = 0.1) -> dict:
        """Criar ação de clique"""
        return {
            "type": "click",
            "x": x,
            "y": y,
            "repeat": repeat,
            "interval": interval
        }

    @staticmethod
    def action_wait(duration: float) -> dict:
        """Criar ação de espera"""
        return {
            "type": "wait",
            "duration": duration
        }

    @staticmethod
    def action_key(key: str) -> dict:
        """Criar ação de tecla"""
        return {
            "type": "key",
            "key": key
        }

    @staticmethod
    def action_drag(from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.5) -> dict:
        """Criar ação de arraste"""
        return {
            "type": "drag",
            "from_x": from_x,
            "from_y": from_y,
            "to_x": to_x,
            "to_y": to_y,
            "duration": duration
        }

    @staticmethod
    def action_template(name: str, timeout: float = 5, confidence: float = 0.8) -> dict:
        """Criar ação de detecção de template"""
        return {
            "type": "template",
            "name": name,
            "timeout": timeout,
            "confidence": confidence
        }


# ═══════════════════════════════════════════════════════
# EXEMPLO DE USO
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n🏗️ Demonstração do ActionBuilder\n")
    print("="*60)

    # Exemplo 1: Feeding
    print("\n1️⃣ Sequência de Feeding:")
    feeding = ActionBuilder.build_feeding_sequence(clicks=5)
    print(f"   Ações: {len(feeding['actions'])}")
    print(f"   Nome: {feeding['name']}")
    print(f"   Descrição: {feeding['description']}")

    # Exemplo 2: Cleaning
    print("\n2️⃣ Sequência de Cleaning:")
    cleaning = ActionBuilder.build_cleaning_sequence()
    print(f"   Ações: {len(cleaning['actions'])}")
    print(f"   Nome: {cleaning['name']}")

    # Exemplo 3: Rod Switch
    print("\n3️⃣ Sequência de Troca de Vara:")
    rod_switch = ActionBuilder.build_rod_switch_sequence(rod_slot=3)
    print(f"   Ações: {len(rod_switch['actions'])}")
    print(f"   Nome: {rod_switch['name']}")

    # Exemplo 4: Custom
    print("\n4️⃣ Sequência Customizada:")
    custom = ActionBuilder.build_custom_sequence([
        ActionBuilder.action_key("esc"),
        ActionBuilder.action_wait(1.0),
        ActionBuilder.action_click(100, 200),
    ])
    print(f"   Ações: {len(custom['actions'])}")

    print("\n" + "="*60)
    print("✅ ActionBuilder pronto para uso no servidor!")
    print("\n🔒 Cliente NÃO tem acesso a coordenadas ou sequências!")
