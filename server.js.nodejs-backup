#!/usr/bin/env node
/**
 * 🔐 Ultimate Fishing Bot v5.0 - Servidor de Autenticação
 *
 * Funcionalidades:
 * - Cadastro de usuários (primeira ativação)
 * - Login com username/email + senha + license_key
 * - Recuperação de senha via código por email
 * - Validação com Keymaster
 * - JWT tokens para sessão
 * - Rate limiting (proteção contra brute force)
 * - Painel admin web
 */

require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const path = require('path');

// Importar rotas e database
const database = require('./database');
const authRoutes = require('./auth-routes');
const statsRoutes = require('./stats-routes');
const adminRoutes = require('./admin-routes');
const wsHandler = require('./ws-handler');

// Criar app Express
const app = express();
const PORT = process.env.PORT || 3000;

// ═══════════════════════════════════════════════════════
// MIDDLEWARES
// ═══════════════════════════════════════════════════════

// Segurança
app.use(helmet({
  contentSecurityPolicy: false,  // Desabilitar para painel admin funcionar
}));

// CORS (permitir requisições do cliente Python)
app.use(cors({
  origin: '*',  // Em produção, restringir aos domínios permitidos
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Parse JSON
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Rate limiting (proteção contra brute force)
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,  // 15 minutos
  max: 10,  // Máximo 10 tentativas por IP
  message: {
    success: false,
    message: 'Muitas tentativas de autenticação. Tente novamente em 15 minutos.'
  }
});

const recoveryLimiter = rateLimit({
  windowMs: 60 * 60 * 1000,  // 1 hora
  max: 3,  // Máximo 3 solicitações de recuperação por hora
  message: {
    success: false,
    message: 'Muitas solicitações de recuperação. Tente novamente em 1 hora.'
  }
});

// ═══════════════════════════════════════════════════════
// ROTAS
// ═══════════════════════════════════════════════════════

// Health check
app.get('/', (req, res) => {
  res.json({
    service: 'Ultimate Fishing Bot v5.0 - Auth Server',
    status: 'online',
    version: '1.0.0',
    endpoints: {
      auth: {
        register: 'POST /auth/register',
        login: 'POST /auth/login',
        requestReset: 'POST /auth/request-reset',
        resetPassword: 'POST /auth/reset-password'
      },
      stats: {
        userStats: 'GET /api/stats/:license_key',
        monthlyRanking: 'GET /api/ranking/monthly',
        alltimeRanking: 'GET /api/ranking/alltime'
      },
      admin: {
        panel: 'GET /admin',
        users: 'GET /admin/api/users',
        resetUserPassword: 'POST /admin/api/reset-password'
      }
    }
  });
});

// Rotas de autenticação (com rate limiting)
app.use('/auth/register', authLimiter, authRoutes.register);
app.use('/auth/login', authLimiter, authRoutes.login);
app.use('/auth/request-reset', recoveryLimiter, authRoutes.requestReset);
app.use('/auth/reset-password', authLimiter, authRoutes.resetPassword);

// Rotas de estatísticas (sem autenticação - usa license_key na URL)
app.use('/api/stats', statsRoutes.getUserStats);
app.use('/api/ranking/monthly', statsRoutes.getMonthlyRanking);
app.use('/api/ranking/alltime', statsRoutes.getAlltimeRanking);

// ✅ NOVO: Rota de configurações públicas (Discord link, Telegram, etc.)
app.use('/api/config/public', statsRoutes.getPublicConfig);

// Rotas do painel admin (servir HTML estático)
app.use('/admin', adminRoutes);

// Servir arquivos estáticos do painel admin
app.use('/admin-static', express.static(path.join(__dirname, 'admin-panel')));

// ═══════════════════════════════════════════════════════
// ERROR HANDLING
// ═══════════════════════════════════════════════════════

// 404
app.use((req, res) => {
  res.status(404).json({
    success: false,
    message: 'Endpoint não encontrado'
  });
});

// Error handler
app.use((err, req, res, next) => {
  console.error('[ERROR]', err.stack);
  res.status(500).json({
    success: false,
    message: 'Erro interno do servidor',
    error: process.env.NODE_ENV === 'development' ? err.message : undefined
  });
});

// ═══════════════════════════════════════════════════════
// START SERVER
// ═══════════════════════════════════════════════════════

// Inicializar banco de dados
database.initialize();

// Iniciar servidor HTTP
const server = app.listen(PORT, () => {
  console.log(`
╔═══════════════════════════════════════════════════════╗
║  🎣 Ultimate Fishing Bot v5.0 - Auth Server          ║
║                                                       ║
║  🚀 Status: ONLINE                                    ║
║  🌐 URL: http://localhost:${PORT}                        ║
║  📊 Banco: SQLite (fishing_bot_auth.db)               ║
║                                                       ║
║  📍 Endpoints:                                        ║
║     POST /auth/register      - Cadastro              ║
║     POST /auth/login         - Login                 ║
║     POST /auth/request-reset - Recuperar senha       ║
║     POST /auth/reset-password- Resetar senha         ║
║     GET  /api/stats/:key     - Estatísticas          ║
║     GET  /admin              - Painel Admin          ║
║     WS   /ws                 - WebSocket             ║
╚═══════════════════════════════════════════════════════╝
  `);
});

// Inicializar WebSocket server
wsHandler.createWebSocketServer(server);

// Adicionar contador de usuários ativos ao endpoint raiz
const originalRoot = app._router.stack.find(r => r.route && r.route.path === '/');
app.get('/', (req, res) => {
  res.json({
    service: 'Fishing Bot Server',
    version: '5.0.0',
    status: 'online',
    active_users: wsHandler.getActiveConnectionsCount(),
    keymaster_integration: true
  });
});

module.exports = app;
