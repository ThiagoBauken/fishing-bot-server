"""
Action Sequence Builder - Construtor de Sequências de Ações

Este módulo contém TODA a lógica de negócio de operações de baú.
O servidor usa este módulo para construir sequências completas de ações atômicas
que são enviadas ao cliente para execução cega.

ARQUITETURA:
- Servidor TEM toda a lógica (quando, como, onde)
- Cliente APENAS executa sequências JSON (burro)

Operações suportadas:
- Feeding (alimentação)
- Cleaning (limpeza de inventário)
- Maintenance (manutenção de varas)
- Rod Switch (troca de vara)
"""

import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ActionSequenceBuilder:
    """
    Construtor de sequências de ações para operações de baú

    TODA a lógica de negócio está aqui!
    Cliente não sabe o que está fazendo, apenas executa ações atômicas.
    """

    def __init__(self, user_config: dict):
        """
        Inicializar builder com configurações do usuário

        Args:
            user_config: Configurações sincronizadas do cliente
                - chest_side: "left" ou "right"
                - chest_distance: pixels de movimento de câmera
                - chest_vertical_offset: offset vertical
                - slot_positions: {1: (x, y), 2: (x, y), ...}
                - inventory_area: [x1, y1, x2, y2]
                - chest_area: [x1, y1, x2, y2]
                - feeds_per_session: quantas comidas por alimentação
                - bait_priority: ordem de prioridade de iscas
        """
        self.config = user_config
        logger.info(f"🏗️ ActionSequenceBuilder inicializado")

    # ========== MÉTODOS PÚBLICOS (OPERAÇÕES COMPLETAS) ==========

    def build_feeding_sequence(
        self,
        food_location: Dict[str, int],
        eat_location: Dict[str, int]
    ) -> List[Dict]:
        """
        Construir sequência completa de alimentação

        Sequência:
        1. Parar fishing cycle
        2. Abrir baú
        3. Clicar na comida
        4. Clicar no botão "eat" N vezes
        5. Fechar baú

        Args:
            food_location: {"x": 1306, "y": 858} (detectado no cliente)
            eat_location: {"x": 1083, "y": 373} (detectado no cliente)

        Returns:
            Lista de ações atômicas
        """
        logger.info(f"🍖 Construindo sequência de feeding")
        logger.info(f"   Food: ({food_location['x']}, {food_location['y']})")
        logger.info(f"   Eat: ({eat_location['x']}, {eat_location['y']})")

        actions = []

        # Passo 1: Parar fishing cycle
        actions.extend(self._build_stop_fishing())

        # Passo 2: Abrir baú
        actions.extend(self._build_chest_open())

        # Passo 3: Aguardar baú abrir completamente
        actions.append({
            "type": "wait",
            "duration": 1.5,
            "comment": "Aguardar baú abrir"
        })

        # Passo 4: Clicar na comida
        actions.append({
            "type": "click",
            "x": food_location["x"],
            "y": food_location["y"],
            "comment": "Pegar comida do baú"
        })
        actions.append({"type": "wait", "duration": 1.0})

        # Passo 5: Clicar no botão "eat" N vezes
        feeds_per_session = self.config.get("feeds_per_session", 2)
        logger.info(f"   Feeds per session: {feeds_per_session}")

        for i in range(feeds_per_session):
            actions.append({
                "type": "click",
                "x": eat_location["x"],
                "y": eat_location["y"],
                "comment": f"Comer {i+1}/{feeds_per_session}"
            })
            actions.append({"type": "wait", "duration": 1.5})

        # Passo 6: Fechar baú
        actions.extend(self._build_chest_close())

        logger.info(f"✅ Sequência de feeding construída: {len(actions)} ações")
        return actions

    def build_cleaning_sequence(
        self,
        fish_locations: List[Dict[str, int]]
    ) -> List[Dict]:
        """
        Construir sequência completa de limpeza de inventário

        Sequência:
        1. Parar fishing cycle
        2. Abrir baú
        3. Para cada peixe:
           - Clicar direito (transfere para baú)
        4. Fechar baú

        Args:
            fish_locations: [{"x": 709, "y": 700}, ...] (detectados no cliente)

        Returns:
            Lista de ações atômicas
        """
        logger.info(f"🧹 Construindo sequência de cleaning")
        logger.info(f"   Peixes detectados: {len(fish_locations)}")

        actions = []

        # Passo 1: Parar fishing cycle
        actions.extend(self._build_stop_fishing())

        # Passo 2: Abrir baú
        actions.extend(self._build_chest_open())

        # Passo 3: Aguardar baú abrir completamente (mais tempo para itens carregarem)
        actions.append({
            "type": "wait",
            "duration": 2.5,
            "comment": "Aguardar baú abrir e itens carregarem"
        })

        # Passo 4: Transferir cada peixe (máximo 30 itens)
        max_items = min(len(fish_locations), 30)
        logger.info(f"   Transferindo {max_items} itens")

        for i, loc in enumerate(fish_locations[:max_items]):
            actions.append({
                "type": "click_right",
                "x": loc["x"],
                "y": loc["y"],
                "comment": f"Transferir item {i+1}/{max_items}"
            })
            actions.append({"type": "wait", "duration": 0.15})

        # Passo 5: Aguardar transferências completarem
        actions.append({
            "type": "wait",
            "duration": 1.0,
            "comment": "Aguardar transferências completarem"
        })

        # Passo 6: Fechar baú
        actions.extend(self._build_chest_close())

        logger.info(f"✅ Sequência de cleaning construída: {len(actions)} ações")
        return actions

    def build_maintenance_sequence(
        self,
        rod_status: Dict[int, str],
        available_items: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """
        Construir sequência completa de manutenção de varas

        Sequência:
        1. Parar fishing cycle
        2. Remover vara da mão
        3. Abrir baú
        4. Para cada slot que precisa manutenção:
           - Se quebrada/vazia: arrastar vara nova
           - Se sem isca: arrastar isca (seguindo prioridade)
        5. Fechar baú
        6. Equipar vara

        Args:
            rod_status: {1: "COM_ISCA", 2: "SEM_ISCA", 3: "QUEBRADA", ...}
            available_items: {
                "rods": [{"x": 1300, "y": 200}, ...],
                "baits": [{"x": 1400, "y": 300, "type": "carneurso"}, ...]
            }

        Returns:
            Lista de ações atômicas
        """
        logger.info(f"🔧 Construindo sequência de maintenance")
        logger.info(f"   Status: {rod_status}")
        logger.info(f"   Varas disponíveis: {len(available_items.get('rods', []))}")
        logger.info(f"   Iscas disponíveis: {len(available_items.get('baits', []))}")

        actions = []

        # Passo 1: Parar fishing cycle
        actions.extend(self._build_stop_fishing())

        # Passo 2: Remover vara da mão
        current_rod = self.config.get("current_rod", 1)
        actions.append({
            "type": "key_press",
            "key": str(current_rod),
            "comment": f"Remover vara {current_rod} da mão"
        })
        actions.append({"type": "wait", "duration": 0.3})

        # Passo 3: Abrir baú
        actions.extend(self._build_chest_open())

        # Passo 4: Aguardar baú abrir
        actions.append({
            "type": "wait",
            "duration": 1.5,
            "comment": "Aguardar baú abrir"
        })

        # Passo 5: Loop de manutenção para cada slot
        slot_positions = self.config.get("slot_positions", {})
        available_rods = available_items.get("rods", []).copy()
        available_baits = available_items.get("baits", []).copy()

        for slot, status in rod_status.items():
            slot_pos = slot_positions.get(str(slot))
            if not slot_pos:
                logger.warning(f"⚠️ Slot {slot} sem posição configurada")
                continue

            # Se vara quebrada ou slot vazio: substituir vara
            if status in ["QUEBRADA", "VAZIO"]:
                if available_rods:
                    rod_loc = available_rods.pop(0)  # Pegar primeira vara disponível
                    actions.append({
                        "type": "drag",
                        "from_x": rod_loc["x"],
                        "from_y": rod_loc["y"],
                        "to_x": slot_pos[0],
                        "to_y": slot_pos[1],
                        "comment": f"Substituir vara no slot {slot}"
                    })
                    actions.append({"type": "wait", "duration": 0.5})
                else:
                    logger.warning(f"⚠️ Sem varas disponíveis para slot {slot}")

            # Se sem isca (ou acabou de substituir): colocar isca
            if status in ["SEM_ISCA", "VAZIO", "QUEBRADA"]:
                best_bait = self._get_best_bait(available_baits)
                if best_bait:
                    available_baits.remove(best_bait)  # Remover da lista
                    actions.append({
                        "type": "drag",
                        "from_x": best_bait["x"],
                        "from_y": best_bait["y"],
                        "to_x": slot_pos[0],
                        "to_y": slot_pos[1],
                        "comment": f"Colocar isca ({best_bait.get('type', 'unknown')}) no slot {slot}"
                    })
                    actions.append({"type": "wait", "duration": 0.5})
                else:
                    logger.warning(f"⚠️ Sem iscas disponíveis para slot {slot}")

        # Passo 6: Fechar baú
        actions.extend(self._build_chest_close())

        # Passo 7: Equipar vara
        target_rod = self.config.get("target_rod", current_rod)
        actions.extend(self._build_equip_rod(target_rod))

        logger.info(f"✅ Sequência de maintenance construída: {len(actions)} ações")
        return actions

    def build_rod_switch_sequence(self, target_rod: int) -> List[Dict]:
        """
        Construir sequência de troca de vara (modo direto, sem baú)

        Sequência:
        1. Segurar botão direito
        2. Pressionar número da próxima vara

        Args:
            target_rod: Número da vara (1-6)

        Returns:
            Lista de ações atômicas
        """
        logger.info(f"🎣 Construindo sequência de rod switch para vara {target_rod}")

        actions = [
            {
                "type": "mouse_down_relative",
                "button": "right",
                "comment": "Segurar botão direito"
            },
            {
                "type": "wait",
                "duration": 0.5
            },
            {
                "type": "key_press",
                "key": str(target_rod),
                "comment": f"Equipar vara {target_rod}"
            },
            {
                "type": "wait",
                "duration": 0.3
            }
        ]

        logger.info(f"✅ Sequência de rod switch construída: {len(actions)} ações")
        return actions

    # ========== MÉTODOS AUXILIARES PRIVADOS ==========

    def _build_chest_open(self) -> List[Dict]:
        """
        Sequência de abrir baú (baseada no v3 que FUNCIONA)

        Sequência EXATA do chest_manager.py - execute_standard_macro():
        1. Safety: Soltar ALT preventivamente
        2. Safety: Soltar botões do mouse
        3. Parar ações contínuas (cliques, movimentos A/D)
        4. ALT DOWN (segurar)
        5. Movimento de câmera (dx, dy)
        6. Pressionar E
        7. ALT permanece pressionado!

        Returns:
            Lista de ações atômicas
        """
        chest_side = self.config.get("chest_side", "left")
        chest_distance = self.config.get("chest_distance", 1200)
        chest_vertical = self.config.get("chest_vertical_offset", 200)

        # Calcular dx, dy baseado no lado do baú
        dx = chest_distance if chest_side == "left" else -chest_distance
        dy = abs(chest_vertical)

        logger.debug(f"   Chest open: side={chest_side}, dx={dx}, dy={dy}")

        return [
            # Safety releases
            {
                "type": "key_up",
                "key": "alt",
                "comment": "Safety: garantir ALT solto"
            },
            {
                "type": "mouse_up",
                "button": "right",
                "comment": "Safety: soltar botão direito"
            },
            {
                "type": "mouse_up",
                "button": "left",
                "comment": "Safety: soltar botão esquerdo"
            },
            {
                "type": "stop_continuous_clicking",
                "comment": "Parar cliques contínuos"
            },
            {
                "type": "stop_camera_movement",
                "comment": "Parar movimentos A/D"
            },
            {
                "type": "wait",
                "duration": 0.1
            },

            # Sequência principal de abertura
            {
                "type": "key_down",
                "key": "alt",
                "comment": "ALT DOWN (inicia sequência)"
            },
            {
                "type": "wait",
                "duration": 0.8
            },
            {
                "type": "move_camera",
                "dx": dx,
                "dy": dy,
                "comment": f"Mover câmera para baú ({chest_side})"
            },
            {
                "type": "wait",
                "duration": 0.3
            },
            {
                "type": "key_press",
                "key": "e",
                "comment": "Pressionar E (abrir baú)"
            },
            {
                "type": "wait",
                "duration": 0.5,
                "comment": "ALT ainda pressionado!"
            }
        ]

    def _build_chest_close(self) -> List[Dict]:
        """
        Sequência de fechar baú (baseada no v3 que FUNCIONA)

        Sequência:
        1. Soltar ALT
        2. Aguardar 1 segundo
        3. Pressionar TAB
        4. Force release TAB (via Arduino, se disponível)
        5. Aguardar 0.8s

        Returns:
            Lista de ações atômicas
        """
        logger.debug(f"   Chest close")

        return [
            {
                "type": "key_up",
                "key": "alt",
                "comment": "Soltar ALT"
            },
            {
                "type": "wait",
                "duration": 1.0,
                "comment": "Aguardar antes de fechar"
            },
            {
                "type": "key_press",
                "key": "tab",
                "comment": "Pressionar TAB (fechar)"
            },
            {
                "type": "force_release_key",
                "key": "tab",
                "comment": "Force release TAB (Arduino)"
            },
            {
                "type": "wait",
                "duration": 0.8,
                "comment": "Aguardar baú fechar"
            }
        ]

    def _build_stop_fishing(self) -> List[Dict]:
        """
        Parar fishing cycle antes de abrir baú

        Para:
        - Cliques contínuos (fast phase)
        - Movimentos de câmera (A/D)
        - Botão direito (casting)

        Returns:
            Lista de ações atômicas
        """
        logger.debug(f"   Stop fishing")

        return [
            {
                "type": "stop_continuous_clicking",
                "comment": "Parar cliques contínuos"
            },
            {
                "type": "stop_camera_movement",
                "comment": "Parar movimentos A/D"
            },
            {
                "type": "mouse_up",
                "button": "right",
                "comment": "Soltar botão direito"
            },
            {
                "type": "mouse_up",
                "button": "left",
                "comment": "Soltar botão esquerdo"
            },
            {
                "type": "wait",
                "duration": 0.6,
                "comment": "Aguardar ações pararem"
            }
        ]

    def _build_equip_rod(self, target_rod: int) -> List[Dict]:
        """
        Equipar vara após fechar baú (para maintenance)

        Sequência:
        1. Segurar botão direito
        2. Aguardar 0.8s
        3. Pressionar número da vara
        4. Aguardar 0.6s

        Args:
            target_rod: Número da vara (1-6)

        Returns:
            Lista de ações atômicas
        """
        logger.debug(f"   Equip rod: {target_rod}")

        return [
            {
                "type": "mouse_down_relative",
                "button": "right",
                "comment": "Segurar botão direito"
            },
            {
                "type": "wait",
                "duration": 0.8
            },
            {
                "type": "key_press",
                "key": str(target_rod),
                "comment": f"Equipar vara {target_rod}"
            },
            {
                "type": "wait",
                "duration": 0.6
            }
        ]

    def _get_best_bait(self, available_baits: List[Dict]) -> Optional[Dict]:
        """
        Selecionar melhor isca disponível seguindo prioridade

        Prioridade (do melhor para pior):
        1. carneurso (carne de urso)
        2. carnedelobo (carne de lobo)
        3. TROUTT (truta)
        4. grub (larva)
        5. minhoca (worm)

        Args:
            available_baits: Lista de iscas disponíveis
                [{"x": 1400, "y": 300, "type": "carneurso"}, ...]

        Returns:
            Melhor isca disponível ou None
        """
        if not available_baits:
            return None

        # Obter prioridade do config (ou usar default)
        bait_priority = self.config.get("bait_priority", {
            "crocodilo": 1,
            "carneurso": 2,
            "carnedelobo": 3,
            "bigcat": 4,
            "TROUTT": 5,
            "grub": 6,
            "minhoca": 7
        })

        # Ordenar iscas por prioridade (menor número = melhor)
        def get_priority(bait: Dict) -> int:
            bait_type = bait.get("type", "unknown")
            return bait_priority.get(bait_type, 99)  # 99 = prioridade baixa se não encontrado

        sorted_baits = sorted(available_baits, key=get_priority)
        best_bait = sorted_baits[0]

        logger.debug(f"   Melhor isca: {best_bait.get('type', 'unknown')}")
        return best_bait
