/**
 * 🔌 WebSocket Handler
 * Gerencia conexões WebSocket para comunicação em tempo real com clientes
 */

const WebSocket = require('ws');
const jwt = require('jsonwebtoken');
const { getDatabase } = require('./database');

// Armazena conexões ativas: { userId: { username, ws, connectedAt, config } }
const activeConnections = new Map();

/**
 * Inicializa servidor WebSocket
 */
function createWebSocketServer(server) {
  const wss = new WebSocket.Server({ 
    server,
    path: '/ws'
  });

  console.log('🔌 WebSocket server iniciado em /ws');

  wss.on('connection', (ws, req) => {
    console.log('🔗 Nova conexão WebSocket recebida');

    let userId = null;
    let username = null;
    let authenticated = false;

    // Timeout de autenticação (30 segundos)
    const authTimeout = setTimeout(() => {
      if (!authenticated) {
        console.log('⏱️ Timeout de autenticação WebSocket');
        ws.send(JSON.stringify({ error: 'Timeout de autenticação' }));
        ws.close();
      }
    }, 30000);

    ws.on('message', async (message) => {
      try {
        const data = JSON.parse(message.toString());

        // Primeira mensagem deve ser autenticação
        if (!authenticated) {
          if (data.event === 'auth') {
            const token = data.token;

            if (!token) {
              ws.send(JSON.stringify({ error: 'Token não fornecido' }));
              ws.close();
              return;
            }

            try {
              // Verificar token JWT
              const decoded = jwt.verify(token, process.env.JWT_SECRET || 'fishing-bot-secret-key-change-in-production');
              userId = decoded.userId;
              username = decoded.username;

              authenticated = true;
              clearTimeout(authTimeout);

              // Armazenar conexão
              activeConnections.set(userId, {
                username,
                ws,
                connectedAt: new Date(),
                config: data.config || {}
              });

              console.log(`✅ Cliente autenticado: ${username} (ID: ${userId})`);

              // Confirmar autenticação
              ws.send(JSON.stringify({
                event: 'authenticated',
                success: true,
                username,
                connectedUsers: activeConnections.size
              }));

            } catch (err) {
              console.error('❌ Erro ao verificar token:', err.message);
              ws.send(JSON.stringify({ error: 'Token inválido' }));
              ws.close();
            }
          } else {
            ws.send(JSON.stringify({ error: 'Autenticação necessária' }));
            ws.close();
          }
          return;
        }

        // Processar eventos autenticados
        await handleAuthenticatedMessage(ws, userId, username, data);

      } catch (err) {
        console.error('❌ Erro ao processar mensagem WebSocket:', err);
        ws.send(JSON.stringify({ error: 'Erro ao processar mensagem' }));
      }
    });

    ws.on('close', () => {
      if (userId) {
        activeConnections.delete(userId);
        console.log(`🔌 Cliente desconectado: ${username} (ID: ${userId})`);
      } else {
        console.log('🔌 Conexão não autenticada fechada');
      }
      clearTimeout(authTimeout);
    });

    ws.on('error', (error) => {
      console.error('❌ Erro WebSocket:', error);
    });
  });

  return wss;
}

/**
 * Processa mensagens de clientes autenticados
 */
async function handleAuthenticatedMessage(ws, userId, username, data) {
  const db = getDatabase();

  switch (data.event) {
    case 'fish_caught':
      await handleFishCaught(db, userId, username, data, ws);
      break;

    case 'config_update':
      await handleConfigUpdate(userId, data, ws);
      break;

    case 'heartbeat':
      ws.send(JSON.stringify({ event: 'heartbeat_ack', timestamp: Date.now() }));
      break;

    default:
      ws.send(JSON.stringify({ error: 'Evento desconhecido', event: data.event }));
  }
}

/**
 * Registra peixe capturado no banco de dados
 */
async function handleFishCaught(db, userId, username, data, ws) {
  try {
    const { fish_type, fish_rarity, exp_gained, timestamp } = data;

    // Inserir no banco de dados
    const stmt = db.prepare(`
      INSERT INTO fish_stats (user_id, fish_type, fish_rarity, exp_gained, caught_at)
      VALUES (?, ?, ?, ?, ?)
    `);

    const result = stmt.run(
      userId,
      fish_type || 'unknown',
      fish_rarity || 'common',
      exp_gained || 0,
      timestamp || Math.floor(Date.now() / 1000)
    );

    console.log(`🐟 Peixe registrado: ${fish_type} (${fish_rarity}) por ${username}`);

    // Confirmar recebimento
    ws.send(JSON.stringify({
      event: 'fish_recorded',
      success: true,
      fish_id: result.lastInsertRowid,
      fish_type,
      fish_rarity
    }));

  } catch (err) {
    console.error('❌ Erro ao registrar peixe:', err);
    ws.send(JSON.stringify({
      event: 'fish_recorded',
      success: false,
      error: err.message
    }));
  }
}

/**
 * Atualiza configurações do cliente
 */
async function handleConfigUpdate(userId, data, ws) {
  const connection = activeConnections.get(userId);
  if (connection) {
    connection.config = data.config || {};
    console.log(`⚙️ Configuração atualizada para usuário ${connection.username}`);

    ws.send(JSON.stringify({
      event: 'config_updated',
      success: true
    }));
  }
}

/**
 * Retorna número de conexões ativas
 */
function getActiveConnectionsCount() {
  return activeConnections.size;
}

/**
 * Envia mensagem para usuário específico
 */
function sendToUser(userId, message) {
  const connection = activeConnections.get(userId);
  if (connection && connection.ws.readyState === WebSocket.OPEN) {
    connection.ws.send(JSON.stringify(message));
    return true;
  }
  return false;
}

/**
 * Broadcast para todos os usuários conectados
 */
function broadcastToAll(message) {
  let sent = 0;
  activeConnections.forEach((connection) => {
    if (connection.ws.readyState === WebSocket.OPEN) {
      connection.ws.send(JSON.stringify(message));
      sent++;
    }
  });
  return sent;
}

module.exports = {
  createWebSocketServer,
  getActiveConnectionsCount,
  sendToUser,
  broadcastToAll
};
