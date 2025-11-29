/**
 * 🔐 Rotas de Autenticação
 *
 * Endpoints:
 * - POST /auth/register - Cadastro (primeira ativação)
 * - POST /auth/login - Login
 * - POST /auth/request-reset - Solicitar código de recuperação
 * - POST /auth/reset-password - Resetar senha com código
 */

const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { getDatabase } = require('./database');
const axios = require('axios');
const { v4: uuidv4 } = require('uuid');

// Chave secreta JWT (usar variável de ambiente em produção)
const JWT_SECRET = process.env.JWT_SECRET || 'fishing-bot-secret-key-change-in-production';

// Configuração do Keymaster
const KEYMASTER_URL = process.env.KEYMASTER_URL || 'https://private-keygen.pbzgje.easypanel.host';
const PROJECT_ID = process.env.PROJECT_ID || '67a4a76a-d71b-4d07-9ba8-f7e794ce0578';

/**
 * Validar license_key com Keymaster
 */
async function validateWithKeymaster(licenseKey, hwid) {
  try {
    console.log(`[KEYMASTER] Validando license_key: ${licenseKey.substring(0, 10)}...`);
    console.log(`[KEYMASTER] HWID: ${hwid}`);

    const response = await axios.post(`${KEYMASTER_URL}/validate`, {
      activation_key: licenseKey,
      hardware_id: hwid,
      project_id: PROJECT_ID
    }, {
      timeout: 10000
    });

    console.log(`[KEYMASTER] Resposta: ${JSON.stringify(response.data)}`);

    if (response.data && response.data.valid) {
      console.log('[KEYMASTER] ✅ License key válida');
      return { valid: true, data: response.data };
    } else {
      console.log('[KEYMASTER] ❌ License key inválida');
      return { valid: false, message: response.data.message || 'License key inválida' };
    }
  } catch (error) {
    console.error('[KEYMASTER] ❌ Erro na validação:', error.message);
    return {
      valid: false,
      message: 'Erro ao validar license key com Keymaster: ' + error.message
    };
  }
}

/**
 * POST /auth/register
 * Cadastrar novo usuário (primeira ativação)
 */
async function register(req, res) {
  try {
    const { username, email, password, license_key, hwid, pc_name } = req.body;

    // Validações
    // ✅ Email é OPCIONAL - usuário pode deixar em branco
    if (!username || !password || !license_key || !hwid) {
      return res.status(400).json({
        success: false,
        message: 'Campos obrigatórios: username, password, license_key, hwid'
      });
    }

    // Validar formato de email (OPCIONAL - só validar se preenchido)
    if (email) {
      const emailRegex = /^[\w.-]+@[\w.-]+\.\w+$/;
      if (!emailRegex.test(email)) {
        return res.status(400).json({
          success: false,
          message: 'Email inválido'
        });
      }
    }

    // Validar senha (mínimo 6 caracteres)
    if (password.length < 6) {
      return res.status(400).json({
        success: false,
        message: 'Senha deve ter no mínimo 6 caracteres'
      });
    }

    const db = getDatabase();

    // Verificar se username já existe
    const existingUser = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
    if (existingUser) {
      return res.status(409).json({
        success: false,
        message: 'Username já cadastrado'
      });
    }

    // ✅ Verificar se email já existe (OPCIONAL - só se foi fornecido)
    if (email) {
      const existingEmail = db.prepare('SELECT id FROM users WHERE email = ?').get(email);
      if (existingEmail) {
        return res.status(409).json({
          success: false,
          message: 'Email já cadastrado'
        });
      }
    }

    // Verificar se license_key já foi usada
    const existingLicense = db.prepare('SELECT id FROM users WHERE license_key = ?').get(license_key);
    if (existingLicense) {
      return res.status(409).json({
        success: false,
        message: 'Esta license key já está vinculada a outra conta'
      });
    }

    // Validar license_key com Keymaster
    const keymasterValidation = await validateWithKeymaster(license_key, hwid);
    if (!keymasterValidation.valid) {
      return res.status(403).json({
        success: false,
        message: keymasterValidation.message || 'License key inválida ou expirada'
      });
    }

    // Hash da senha
    const passwordHash = bcrypt.hashSync(password, 10);

    // Inserir usuário
    const result = db.prepare(`
      INSERT INTO users (username, email, password_hash, license_key, hwid, pc_name)
      VALUES (?, ?, ?, ?, ?, ?)
    `).run(username, email, passwordHash, license_key, hwid, pc_name || 'Unknown');

    const userId = result.lastInsertRowid;

    // Criar estatísticas iniciais
    const currentMonth = new Date().toISOString().slice(0, 7);  // YYYY-MM
    db.prepare(`
      INSERT INTO fishing_stats (user_id, license_key, month_year)
      VALUES (?, ?, ?)
    `).run(userId, license_key, currentMonth);

    // Gerar JWT token
    const token = jwt.sign(
      { userId, username, license_key },
      JWT_SECRET,
      { expiresIn: '30d' }
    );

    console.log(`[REGISTER] ✅ Usuário cadastrado: ${username} (ID: ${userId})`);

    return res.json({
      success: true,
      message: 'Cadastro realizado com sucesso!',
      token,
      user: {
        id: userId,
        username,
        email,
        license_key
      }
    });

  } catch (error) {
    console.error('[REGISTER] ❌ Erro:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao cadastrar usuário: ' + error.message
    });
  }
}

/**
 * POST /auth/login
 * Autenticar usuário existente
 */
async function login(req, res) {
  try {
    const { username, password, license_key, hwid, pc_name } = req.body;

    // Validações
    if (!username || !password || !license_key || !hwid) {
      return res.status(400).json({
        success: false,
        message: 'Campos obrigatórios: username, password, license_key, hwid'
      });
    }

    const db = getDatabase();

    // Buscar usuário (por username ou email)
    const user = db.prepare(`
      SELECT * FROM users
      WHERE (username = ? OR email = ?) AND license_key = ?
    `).get(username, username, license_key);

    if (!user) {
      return res.status(401).json({
        success: false,
        message: 'Credenciais inválidas'
      });
    }

    // Verificar se usuário está ativo
    if (!user.is_active) {
      return res.status(403).json({
        success: false,
        message: 'Conta desativada. Entre em contato com o suporte.'
      });
    }

    // Verificar senha
    const passwordValid = bcrypt.compareSync(password, user.password_hash);
    if (!passwordValid) {
      return res.status(401).json({
        success: false,
        message: 'Credenciais inválidas'
      });
    }

    // Verificar HWID (anti-compartilhamento)
    if (user.hwid && user.hwid !== hwid) {
      return res.status(403).json({
        success: false,
        message: 'Esta conta está vinculada a outro computador. Entre em contato para transferência.'
      });
    }

    // Validar license_key com Keymaster
    const keymasterValidation = await validateWithKeymaster(license_key, hwid);
    if (!keymasterValidation.valid) {
      return res.status(403).json({
        success: false,
        message: 'License key inválida ou expirada'
      });
    }

    // Atualizar HWID e último login
    db.prepare(`
      UPDATE users
      SET hwid = ?, pc_name = ?, last_login = CURRENT_TIMESTAMP
      WHERE id = ?
    `).run(hwid, pc_name || user.pc_name, user.id);

    // Gerar JWT token
    const token = jwt.sign(
      { userId: user.id, username: user.username, license_key },
      JWT_SECRET,
      { expiresIn: '30d' }
    );

    console.log(`[LOGIN] ✅ Login bem-sucedido: ${user.username} (ID: ${user.id})`);

    return res.json({
      success: true,
      message: 'Login realizado com sucesso!',
      token,
      user: {
        id: user.id,
        username: user.username,
        email: user.email,
        license_key: user.license_key
      }
    });

  } catch (error) {
    console.error('[LOGIN] ❌ Erro:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao fazer login: ' + error.message
    });
  }
}

/**
 * POST /auth/request-reset
 * Solicitar código de recuperação de senha
 */
async function requestReset(req, res) {
  try {
    const { identifier } = req.body;  // email ou license_key

    if (!identifier) {
      return res.status(400).json({
        success: false,
        message: 'Digite seu email ou license key'
      });
    }

    const db = getDatabase();

    // Buscar usuário (por email ou license_key)
    const user = db.prepare(`
      SELECT * FROM users
      WHERE email = ? OR license_key = ?
    `).get(identifier, identifier);

    if (!user) {
      // Por segurança, não revelar se o usuário existe ou não
      return res.json({
        success: true,
        message: 'Se o email/license key existir, você receberá um código de recuperação.'
      });
    }

    // Gerar código de recuperação (6 dígitos)
    const resetCode = Math.floor(100000 + Math.random() * 900000).toString();

    // Expiração: 1 hora
    const expiresAt = new Date(Date.now() + 60 * 60 * 1000).toISOString();

    // Salvar código no banco
    db.prepare(`
      INSERT INTO password_resets (user_id, reset_code, expires_at)
      VALUES (?, ?, ?)
    `).run(user.id, resetCode, expiresAt);

    console.log(`[RESET] ✅ Código gerado para ${user.username}: ${resetCode}`);

    // TODO: Enviar email com o código (implementar nodemailer)
    // Por enquanto, apenas logar no console (para desenvolvimento)
    console.log(`
    ╔═══════════════════════════════════════════════════╗
    ║  🔑 CÓDIGO DE RECUPERAÇÃO DE SENHA                ║
    ║                                                   ║
    ║  Usuário: ${user.username.padEnd(40)} ║
    ║  Email: ${user.email.padEnd(42)} ║
    ║  Código: ${resetCode.padEnd(42)} ║
    ║  Expira em: 1 hora                                ║
    ╚═══════════════════════════════════════════════════╝
    `);

    // Em produção, enviar email aqui
    // await sendRecoveryEmail(user.email, resetCode);

    return res.json({
      success: true,
      message: 'Código de recuperação enviado! (Verifique o console do servidor em desenvolvimento)',
      // Em desenvolvimento, retornar código (REMOVER EM PRODUÇÃO!)
      ...(process.env.NODE_ENV === 'development' && { debug_code: resetCode })
    });

  } catch (error) {
    console.error('[RESET] ❌ Erro:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao solicitar recuperação: ' + error.message
    });
  }
}

/**
 * POST /auth/reset-password
 * Resetar senha com código de recuperação
 */
async function resetPassword(req, res) {
  try {
    const { code, new_password } = req.body;

    // Validações
    if (!code || !new_password) {
      return res.status(400).json({
        success: false,
        message: 'Código e nova senha são obrigatórios'
      });
    }

    if (new_password.length < 6) {
      return res.status(400).json({
        success: false,
        message: 'Nova senha deve ter no mínimo 6 caracteres'
      });
    }

    const db = getDatabase();

    // Buscar código de recuperação
    const reset = db.prepare(`
      SELECT * FROM password_resets
      WHERE reset_code = ? AND used = 0 AND expires_at > datetime('now')
    `).get(code);

    if (!reset) {
      return res.status(400).json({
        success: false,
        message: 'Código inválido ou expirado'
      });
    }

    // Hash da nova senha
    const passwordHash = bcrypt.hashSync(new_password, 10);

    // Atualizar senha
    db.prepare(`
      UPDATE users
      SET password_hash = ?
      WHERE id = ?
    `).run(passwordHash, reset.user_id);

    // Marcar código como usado
    db.prepare(`
      UPDATE password_resets
      SET used = 1
      WHERE id = ?
    `).run(reset.id);

    console.log(`[RESET] ✅ Senha resetada para user_id: ${reset.user_id}`);

    return res.json({
      success: true,
      message: 'Senha resetada com sucesso! Faça login novamente.'
    });

  } catch (error) {
    console.error('[RESET] ❌ Erro:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao resetar senha: ' + error.message
    });
  }
}

module.exports = {
  register,
  login,
  requestReset,
  resetPassword
};
