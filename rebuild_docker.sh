#!/bin/bash
# Script para rebuild do Docker Server

echo "=========================================="
echo "  Rebuilding Fishing Bot Server Docker"
echo "=========================================="
echo ""

# Parar e remover container antigo
echo "1. Stopping old container..."
docker stop fishing-bot-server 2>/dev/null
docker rm fishing-bot-server 2>/dev/null

# Rebuild imagem
echo ""
echo "2. Building new image..."
docker build -t fishing-bot-server:latest .

# Verificar se build foi bem-sucedido
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    echo "3. Starting new container..."

    # Rodar novo container
    docker run -d \
      --name fishing-bot-server \
      -p 8122:8122 \
      -e PORT=8122 \
      -e KEYMASTER_URL=https://private-keygen.pbzgje.easypanel.host \
      -e PROJECT_ID=67a4a76a-d71b-4d07-9ba8-f7e794ce0578 \
      fishing-bot-server:latest

    echo ""
    echo "✅ Container started!"
    echo ""
    echo "4. Checking logs..."
    sleep 3
    docker logs fishing-bot-server --tail 20

    echo ""
    echo "=========================================="
    echo "✅ Rebuild complete!"
    echo "=========================================="
    echo ""
    echo "Test health: curl http://localhost:8122/health"
else
    echo ""
    echo "❌ Build failed! Check errors above."
    exit 1
fi
