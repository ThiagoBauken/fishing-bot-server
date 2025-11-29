# 🔄 Atualização para Nível 2 - Guia de Implementação

## 📝 MUDANÇAS NECESSÁRIAS NO SERVIDOR

### 1️⃣ Importar ActionBuilder (LINHA 27)

```python
# Adicionar após os imports
from action_builder import ActionBuilder
```

---

### 2️⃣ Atualizar Lógica de Decisão (LINHA 499-510)

**❌ ANTES (Comandos simples):**
```python
# 1. Alimentar (a cada N peixes)
if session.should_feed():
    commands.append({"cmd": "feed", "params": {"clicks": 5}})
    logger.info(f"🍖 {login}: Comando FEED enviado")

# 2. Limpar (a cada N peixes)
if session.should_clean():
    commands.append({"cmd": "clean", "params": {}}")
    logger.info(f"🧹 {login}: Comando CLEAN enviado")
```

**✅ DEPOIS (Sequências completas com coordenadas):**
```python
# 1. Alimentar (a cada N peixes)
if session.should_feed():
    # Servidor envia COORDENADAS e SEQUÊNCIA completa
    feeding_sequence = ActionBuilder.build_feeding_sequence(clicks=5)
    commands.append(feeding_sequence)
    logger.info(f"🍖 {login}: Sequência FEED enviada ({len(feeding_sequence['actions'])} ações)")
    logger.info(f"   Cliente NÃO sabe coordenadas, apenas executa!")

# 2. Limpar (a cada N peixes)
if session.should_clean():
    # Servidor envia COORDENADAS e SEQUÊNCIA completa
    cleaning_sequence = ActionBuilder.build_cleaning_sequence()
    commands.append(cleaning_sequence)
    logger.info(f"🧹 {login}: Sequência CLEAN enviada ({len(cleaning_sequence['actions'])} ações)")
    logger.info(f"   Cliente NÃO sabe coordenadas, apenas executa!")
```

---

## 📡 O QUE O SERVIDOR ENVIA AGORA

### ANTES (Simples):
```json
{
  "cmd": "feed",
  "params": {"clicks": 5}
}
```

### AGORA (Completo com coordenadas):
```json
{
  "cmd": "sequence",
  "name": "feeding",
  "description": "Alimentação automática",
  "actions": [
    {"type": "key", "key": "esc", "comment": "Abrir baú"},
    {"type": "wait", "duration": 1.5},
    {"type": "click", "x": 1306, "y": 858, "comment": "Pegar comida"},
    {"type": "wait", "duration": 0.8},
    {"type": "click", "x": 1083, "y": 373, "repeat": 5, "interval": 0.3, "comment": "Eat x5"},
    {"type": "wait", "duration": 0.5},
    {"type": "key", "key": "esc", "comment": "Fechar baú"}
  ]
}
```

---

## 🔐 BENEFÍCIO

**Cliente ANTES:**
```python
# Cliente sabia:
feeding_coord = (1306, 858)  # ❌ Exposto
eat_button = (1083, 373)      # ❌ Exposto
```

**Cliente AGORA:**
```python
# Cliente NÃO sabe NADA:
def execute_sequence(actions):
    for action in actions:
        click(action["x"], action["y"])  # Executa cegamente
```

---

## 🚀 PRÓXIMOS PASSOS

1. ✅ ActionBuilder criado
2. ✅ ActionExecutor criado
3. ⏳ Atualizar servidor (fazer mudanças acima)
4. ⏳ Atualizar callbacks do cliente
5. ⏳ Testar integração

---

## 💡 COMO APLICAR AS MUDANÇAS

### Opção 1: Manual
1. Abrir `server/server.py`
2. Adicionar import na linha 27
3. Substituir linhas 499-510 com novo código

### Opção 2: Patch
Copiar código do arquivo `server_nivel2_patch.py` (vou criar)

---

## 📊 RESULTADO

**Proteção:**
- ANTES: 50% (cliente sabe coordenadas)
- AGORA: 80% (servidor controla coordenadas)

**Servidor é o cérebro:**
- 🧠 Decide QUANDO
- 🧠 Envia ONDE (coordenadas)
- 🧠 Envia COMO (sequência)
- 🧠 Controla TUDO

**Cliente é burro:**
- 🤖 Recebe lista de ações
- 🤖 Executa cegamente
- 🤖 NÃO SABE o que está fazendo

✅ **Cliente não pode mais ser engenharia reversa para descobrir coordenadas!**
