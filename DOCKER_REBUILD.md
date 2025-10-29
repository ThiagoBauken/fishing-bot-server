# 🐋 Como Fazer Rebuild do Docker

## ⚠️ IMPORTANTE: Mudança no Código

O arquivo `action_sequences.py` foi adicionado recentemente. Para que funcione no Docker, você precisa **reconstruir a imagem**.

---

## 🔄 Rebuild Local

Se você está testando localmente com Docker:

```bash
cd server

# Parar container atual
docker stop fishing-bot-server
docker rm fishing-bot-server

# Rebuild da imagem
docker build -t fishing-bot-server:latest .

# Rodar novamente
docker run -d \
  --name fishing-bot-server \
  -p 8122:8122 \
  -e PORT=8122 \
  -e KEYMASTER_URL=https://private-keygen.pbzgje.easypanel.host \
  -e PROJECT_ID=67a4a76a-d71b-4d07-9ba8-f7e794ce0578 \
  fishing-bot-server:latest
```

---

## 🚀 Rebuild no EasyPanel

Se você está usando EasyPanel:

### Opção 1: Via Interface Web
1. Acesse seu projeto no EasyPanel
2. Vá em **Services** → Seu serviço
3. Clique em **Rebuild**
4. Aguarde o rebuild completar

### Opção 2: Via Git Push
```bash
# Commit as mudanças
git add server/action_sequences.py server/Dockerfile
git commit -m "feat: Add action_sequences.py to Docker build"

# Push para seu repositório
git push origin main

# EasyPanel detectará e fará rebuild automático
```

---

## ✅ Verificar se Funcionou

Após o rebuild, verifique os logs:

```bash
# Local Docker
docker logs fishing-bot-server

# EasyPanel
# Veja logs na interface web
```

**Não deve mais aparecer:**
```
ModuleNotFoundError: No module named 'action_sequences'
```

**Deve aparecer:**
```
INFO:     Application startup complete.
```

---

## 📋 Checklist Pós-Rebuild

- [ ] Container iniciou sem erros
- [ ] Logs mostram "Application startup complete"
- [ ] Health check está passando: `curl http://localhost:8122/health`
- [ ] Cliente consegue conectar

---

## 🐛 Se Ainda Não Funcionar

### 1. Verificar se arquivo foi copiado
```bash
docker exec fishing-bot-server ls -la /app/*.py
```

**Deve listar:**
- server.py
- action_sequences.py
- action_builder.py

### 2. Verificar imports dentro do container
```bash
docker exec fishing-bot-server python -c "from action_sequences import ActionSequenceBuilder; print('OK')"
```

### 3. Ver logs detalhados
```bash
docker logs fishing-bot-server --tail 100
```

---

## 📚 Arquivos Modificados

- ✅ `Dockerfile` - Agora copia todos os .py files
- ✅ `server.py` - Import com fallback robusto
- ✅ `.dockerignore` - Evita copiar arquivos desnecessários

---

**Última Atualização:** 2025-10-29
