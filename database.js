/**
 * 🗄️ Database Manager - SQLite
 *
 * Gerencia esquema e operações do banco de dados
 */

const Database = require('better-sqlite3');
const path = require('path');

// Criar conexão com SQLite
const dbPath = path.join(__dirname, 'fishing_bot_auth.db');
const db = new Database(dbPath);

// Ativar WAL mode (melhor performance)
db.pragma('journal_mode = WAL');

console.log(`📊 Banco de dados: ${dbPath}`);

/**
 * Inicializar esquema do banco de dados
 */
function initialize() {
  console.log('📦 Inicializando esquema do banco de dados...');

  // Tabela de usuários
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      license_key TEXT UNIQUE NOT NULL,
      hwid TEXT,
      pc_name TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      last_login TEXT,
      is_active INTEGER DEFAULT 1,
      is_admin INTEGER DEFAULT 0
    )
  `);

  // Índices para buscas rápidas
  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_users_license_key ON users(license_key);
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
  `);

  // Tabela de tokens de recuperação de senha
  db.exec(`
    CREATE TABLE IF NOT EXISTS password_resets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      reset_code TEXT UNIQUE NOT NULL,
      expires_at TEXT NOT NULL,
      used INTEGER DEFAULT 0,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
  `);

  // Tabela de estatísticas de pesca
  db.exec(`
    CREATE TABLE IF NOT EXISTS fishing_stats (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      license_key TEXT NOT NULL,
      total_fish INTEGER DEFAULT 0,
      month_fish INTEGER DEFAULT 0,
      month_year TEXT,  -- Formato: YYYY-MM
      last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      UNIQUE(user_id, month_year)
    )
  `);

  // Índices para estatísticas
  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_stats_license_key ON fishing_stats(license_key);
    CREATE INDEX IF NOT EXISTS idx_stats_month_year ON fishing_stats(month_year);
  `);

  // Tabela de sessões/tokens JWT (opcional - para invalidação)
  db.exec(`
    CREATE TABLE IF NOT EXISTS sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      token TEXT NOT NULL,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      expires_at TEXT NOT NULL,
      is_valid INTEGER DEFAULT 1,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
  `);

  // ✅ NOVO: Tabela de configurações dinâmicas
  db.exec(`
    CREATE TABLE IF NOT EXISTS config (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      key TEXT UNIQUE NOT NULL,
      value TEXT,
      description TEXT,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
  `);

  console.log('✅ Esquema do banco de dados criado com sucesso!');
  console.log('📊 Tabelas: users, password_resets, fishing_stats, sessions, config');

  // Criar usuário admin padrão se não existir
  createDefaultAdmin();

  // Criar configurações padrão
  createDefaultConfig();
}

/**
 * Criar usuário admin padrão
 */
function createDefaultAdmin() {
  const bcrypt = require('bcryptjs');

  const adminExists = db.prepare('SELECT id FROM users WHERE is_admin = 1').get();

  if (!adminExists) {
    console.log('👤 Criando usuário admin padrão...');

    const adminPassword = process.env.ADMIN_PASSWORD || 'admin123';
    const passwordHash = bcrypt.hashSync(adminPassword, 10);

    db.prepare(`
      INSERT INTO users (username, email, password_hash, license_key, is_admin)
      VALUES (?, ?, ?, ?, 1)
    `).run('admin', 'admin@fishingbot.local', passwordHash, 'ADMIN-KEY-00000');

    console.log('✅ Admin criado:');
    console.log('   Username: admin');
    console.log(`   Senha: ${adminPassword}`);
    console.log('   ⚠️ ALTERE A SENHA PADRÃO EM PRODUÇÃO!');
  }
}

/**
 * Criar configurações padrão
 */
function createDefaultConfig() {
  const defaultConfigs = [
    {
      key: 'discord_link',
      value: 'https://discord.gg/seu-servidor',
      description: 'Link do servidor Discord'
    },
    {
      key: 'telegram_link',
      value: 'https://t.me/seu_canal',
      description: 'Link do canal Telegram'
    },
    {
      key: 'support_email',
      value: 'suporte@fishingbot.com',
      description: 'Email de suporte'
    },
    {
      key: 'maintenance_mode',
      value: 'false',
      description: 'Modo manutenção (true/false)'
    },
    {
      key: 'announcement',
      value: '',
      description: 'Anúncio importante para usuários'
    }
  ];

  defaultConfigs.forEach(config => {
    const existing = db.prepare('SELECT id FROM config WHERE key = ?').get(config.key);

    if (!existing) {
      db.prepare(`
        INSERT INTO config (key, value, description)
        VALUES (?, ?, ?)
      `).run(config.key, config.value, config.description);

      console.log(`✅ Config criada: ${config.key} = ${config.value}`);
    }
  });
}

/**
 * Obter instância do banco de dados
 */
function getDatabase() {
  return db;
}

/**
 * Fechar conexão
 */
function close() {
  db.close();
  console.log('📊 Conexão com banco de dados fechada');
}

module.exports = {
  initialize,
  getDatabase,
  close
};
