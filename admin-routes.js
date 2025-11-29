/**
 * 👨‍💼 Rotas do Painel Admin
 *
 * Endpoints:
 * - GET  /admin - Painel admin (HTML)
 * - GET  /admin/api/users - Listar todos os usuários
 * - POST /admin/api/reset-password - Resetar senha de um usuário
 * - POST /admin/api/toggle-active - Ativar/desativar usuário
 * - DELETE /admin/api/user/:id - Deletar usuário
 */

const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
const { getDatabase } = require('./database');
const path = require('path');

// Middleware de autenticação admin (simplificado)
function requireAdmin(req, res, next) {
  const { admin_password } = req.headers;

  const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin123';

  if (admin_password !== ADMIN_PASSWORD) {
    return res.status(401).json({
      success: false,
      message: 'Senha de admin inválida'
    });
  }

  next();
}

/**
 * GET /admin
 * Servir painel admin (HTML)
 */
router.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'admin-panel', 'index.html'));
});

/**
 * GET /admin/api/users
 * Listar todos os usuários
 */
router.get('/api/users', requireAdmin, (req, res) => {
  try {
    const db = getDatabase();

    const users = db.prepare(`
      SELECT
        u.id,
        u.username,
        u.email,
        u.license_key,
        u.hwid,
        u.pc_name,
        u.created_at,
        u.last_login,
        u.is_active,
        u.is_admin,
        COALESCE(SUM(s.total_fish), 0) as total_fish,
        COALESCE(MAX(s.month_fish), 0) as month_fish
      FROM users u
      LEFT JOIN fishing_stats s ON u.id = s.user_id
      WHERE u.is_admin = 0
      GROUP BY u.id
      ORDER BY u.created_at DESC
    `).all();

    return res.json({
      success: true,
      users: users.map(u => ({
        ...u,
        hwid: u.hwid ? `${u.hwid.substring(0, 16)}...` : null  // Ocultar HWID completo
      }))
    });

  } catch (error) {
    console.error('[ADMIN] ❌ Erro ao listar usuários:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao listar usuários: ' + error.message
    });
  }
});

/**
 * POST /admin/api/reset-password
 * Resetar senha de um usuário
 */
router.post('/api/reset-password', requireAdmin, (req, res) => {
  try {
    const { user_id, new_password } = req.body;

    if (!user_id || !new_password) {
      return res.status(400).json({
        success: false,
        message: 'user_id e new_password são obrigatórios'
      });
    }

    if (new_password.length < 6) {
      return res.status(400).json({
        success: false,
        message: 'Senha deve ter no mínimo 6 caracteres'
      });
    }

    const db = getDatabase();

    // Verificar se usuário existe
    const user = db.prepare('SELECT username FROM users WHERE id = ?').get(user_id);
    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'Usuário não encontrado'
      });
    }

    // Hash da nova senha
    const passwordHash = bcrypt.hashSync(new_password, 10);

    // Atualizar senha
    db.prepare(`
      UPDATE users
      SET password_hash = ?
      WHERE id = ?
    `).run(passwordHash, user_id);

    console.log(`[ADMIN] ✅ Senha resetada para usuário: ${user.username} (ID: ${user_id})`);

    return res.json({
      success: true,
      message: `Senha resetada para ${user.username}`
    });

  } catch (error) {
    console.error('[ADMIN] ❌ Erro ao resetar senha:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao resetar senha: ' + error.message
    });
  }
});

/**
 * POST /admin/api/toggle-active
 * Ativar/desativar usuário
 */
router.post('/api/toggle-active', requireAdmin, (req, res) => {
  try {
    const { user_id } = req.body;

    if (!user_id) {
      return res.status(400).json({
        success: false,
        message: 'user_id é obrigatório'
      });
    }

    const db = getDatabase();

    const user = db.prepare('SELECT username, is_active FROM users WHERE id = ?').get(user_id);
    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'Usuário não encontrado'
      });
    }

    const newStatus = user.is_active ? 0 : 1;

    db.prepare(`
      UPDATE users
      SET is_active = ?
      WHERE id = ?
    `).run(newStatus, user_id);

    console.log(`[ADMIN] ✅ Usuário ${user.username} ${newStatus ? 'ativado' : 'desativado'}`);

    return res.json({
      success: true,
      message: `Usuário ${newStatus ? 'ativado' : 'desativado'}`,
      is_active: newStatus
    });

  } catch (error) {
    console.error('[ADMIN] ❌ Erro ao alterar status:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao alterar status: ' + error.message
    });
  }
});

/**
 * DELETE /admin/api/user/:id
 * Deletar usuário
 */
router.delete('/api/user/:id', requireAdmin, (req, res) => {
  try {
    const { id } = req.params;

    const db = getDatabase();

    const user = db.prepare('SELECT username FROM users WHERE id = ?').get(id);
    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'Usuário não encontrado'
      });
    }

    db.prepare('DELETE FROM users WHERE id = ?').run(id);

    console.log(`[ADMIN] ✅ Usuário deletado: ${user.username} (ID: ${id})`);

    return res.json({
      success: true,
      message: `Usuário ${user.username} deletado`
    });

  } catch (error) {
    console.error('[ADMIN] ❌ Erro ao deletar usuário:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao deletar usuário: ' + error.message
    });
  }
});

/**
 * GET /admin/api/stats
 * Estatísticas gerais do servidor
 */
router.get('/api/stats', requireAdmin, (req, res) => {
  try {
    const db = getDatabase();

    const stats = {
      total_users: db.prepare('SELECT COUNT(*) as count FROM users WHERE is_admin = 0').get().count,
      active_users: db.prepare('SELECT COUNT(*) as count FROM users WHERE is_active = 1 AND is_admin = 0').get().count,
      total_fish: db.prepare('SELECT COALESCE(SUM(total_fish), 0) as total FROM fishing_stats').get().total,
      month_fish: db.prepare(`
        SELECT COALESCE(SUM(month_fish), 0) as total
        FROM fishing_stats
        WHERE month_year = ?
      `).get(new Date().toISOString().slice(0, 7)).total
    };

    return res.json({
      success: true,
      stats
    });

  } catch (error) {
    console.error('[ADMIN] ❌ Erro ao buscar stats:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao buscar estatísticas: ' + error.message
    });
  }
});

/**
 * GET /admin/api/config
 * Listar todas as configurações
 */
router.get('/api/config', requireAdmin, (req, res) => {
  try {
    const db = getDatabase();

    const configs = db.prepare(`
      SELECT key, value, description, updated_at
      FROM config
      ORDER BY key
    `).all();

    return res.json({
      success: true,
      configs
    });

  } catch (error) {
    console.error('[ADMIN] ❌ Erro ao buscar configs:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao buscar configurações: ' + error.message
    });
  }
});

/**
 * PUT /admin/api/update-license
 * Trocar license_key de um usuário (key expirada ou transferência)
 */
router.put('/api/update-license', requireAdmin, async (req, res) => {
  try {
    const { user_id, new_license_key } = req.body;

    if (!user_id || !new_license_key) {
      return res.status(400).json({
        success: false,
        message: 'user_id e new_license_key são obrigatórios'
      });
    }

    const db = getDatabase();

    // Verificar se usuário existe
    const user = db.prepare('SELECT username, license_key FROM users WHERE id = ?').get(user_id);
    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'Usuário não encontrado'
      });
    }

    // Verificar se a nova key já está em uso
    const existingKey = db.prepare('SELECT username FROM users WHERE license_key = ?').get(new_license_key);
    if (existingKey) {
      return res.status(409).json({
        success: false,
        message: `License key já está vinculada ao usuário: ${existingKey.username}`
      });
    }

    // Validar nova key com Keymaster
    const axios = require('axios');
    const KEYMASTER_URL = process.env.KEYMASTER_URL || 'https://private-keygen.pbzgje.easypanel.host';
    const PROJECT_ID = process.env.PROJECT_ID || '67a4a76a-d71b-4d07-9ba8-f7e794ce0578';

    try {
      const response = await axios.post(`${KEYMASTER_URL}/validate`, {
        activation_key: new_license_key,
        hardware_id: 'admin-update',  // HWID será atualizado no próximo login
        project_id: PROJECT_ID
      }, { timeout: 10000 });

      if (!response.data || !response.data.valid) {
        return res.status(403).json({
          success: false,
          message: 'Nova license key inválida ou expirada no Keymaster'
        });
      }
    } catch (error) {
      return res.status(500).json({
        success: false,
        message: 'Erro ao validar license key com Keymaster: ' + error.message
      });
    }

    // Atualizar license_key
    db.prepare(`
      UPDATE users
      SET license_key = ?
      WHERE id = ?
    `).run(new_license_key, user_id);

    // Atualizar também nas estatísticas
    db.prepare(`
      UPDATE fishing_stats
      SET license_key = ?
      WHERE user_id = ?
    `).run(new_license_key, user_id);

    console.log(`[ADMIN] ✅ License key atualizada para ${user.username}: ${user.license_key} → ${new_license_key}`);

    return res.json({
      success: true,
      message: `License key atualizada para ${user.username}`,
      old_key: user.license_key,
      new_key: new_license_key
    });

  } catch (error) {
    console.error('[ADMIN] ❌ Erro ao atualizar license:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao atualizar license key: ' + error.message
    });
  }
});

/**
 * PUT /admin/api/config
 * Atualizar uma configuração
 */
router.put('/api/config', requireAdmin, (req, res) => {
  try {
    const { key, value } = req.body;

    if (!key || value === undefined) {
      return res.status(400).json({
        success: false,
        message: 'key e value são obrigatórios'
      });
    }

    const db = getDatabase();

    // Verificar se configuração existe
    const config = db.prepare('SELECT id FROM config WHERE key = ?').get(key);
    if (!config) {
      return res.status(404).json({
        success: false,
        message: 'Configuração não encontrada'
      });
    }

    // Atualizar
    db.prepare(`
      UPDATE config
      SET value = ?, updated_at = CURRENT_TIMESTAMP
      WHERE key = ?
    `).run(value, key);

    console.log(`[ADMIN] ✅ Config atualizada: ${key} = ${value}`);

    return res.json({
      success: true,
      message: `Configuração '${key}' atualizada`
    });

  } catch (error) {
    console.error('[ADMIN] ❌ Erro ao atualizar config:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao atualizar configuração: ' + error.message
    });
  }
});

module.exports = router;
