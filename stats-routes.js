/**
 * 📊 Rotas de Estatísticas
 *
 * Endpoints:
 * - GET /api/stats/:license_key - Estatísticas do usuário
 * - GET /api/ranking/monthly - TOP 5 do mês
 * - GET /api/ranking/alltime - TOP 5 geral
 */

const { getDatabase } = require('./database');

/**
 * GET /api/stats/:license_key
 * Obter estatísticas de um usuário
 */
function getUserStats(req, res) {
  try {
    const { license_key } = req.params;

    if (!license_key) {
      return res.status(400).json({
        success: false,
        message: 'License key é obrigatória'
      });
    }

    const db = getDatabase();

    // Buscar usuário
    const user = db.prepare(`
      SELECT id, username, email, created_at
      FROM users
      WHERE license_key = ?
    `).get(license_key);

    if (!user) {
      return res.status(404).json({
        success: false,
        message: 'Usuário não encontrado'
      });
    }

    // Buscar estatísticas totais
    const totalStats = db.prepare(`
      SELECT SUM(total_fish) as total_fish
      FROM fishing_stats
      WHERE user_id = ?
    `).get(user.id);

    // Buscar estatísticas do mês atual
    const currentMonth = new Date().toISOString().slice(0, 7);  // YYYY-MM
    const monthStats = db.prepare(`
      SELECT month_fish
      FROM fishing_stats
      WHERE user_id = ? AND month_year = ?
    `).get(user.id, currentMonth);

    // Buscar rankings
    const monthlyRank = db.prepare(`
      SELECT COUNT(*) + 1 as rank
      FROM fishing_stats s1
      JOIN users u ON s1.user_id = u.id
      WHERE s1.month_year = ? AND s1.month_fish > (
        SELECT month_fish FROM fishing_stats
        WHERE user_id = ? AND month_year = ?
      )
    `).get(currentMonth, user.id, currentMonth);

    const alltimeRank = db.prepare(`
      SELECT COUNT(*) + 1 as rank
      FROM (
        SELECT user_id, SUM(total_fish) as total
        FROM fishing_stats
        GROUP BY user_id
      ) ranked
      WHERE total > (
        SELECT SUM(total_fish) FROM fishing_stats WHERE user_id = ?
      )
    `).get(user.id);

    return res.json({
      success: true,
      username: user.username,
      email: user.email,
      total_fish: totalStats?.total_fish || 0,
      month_fish: monthStats?.month_fish || 0,
      rank_monthly: monthlyRank?.rank || 0,
      rank_alltime: alltimeRank?.rank || 0,
      member_since: user.created_at
    });

  } catch (error) {
    console.error('[STATS] ❌ Erro:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao buscar estatísticas: ' + error.message
    });
  }
}

/**
 * GET /api/ranking/monthly
 * Obter TOP 5 do mês atual
 */
function getMonthlyRanking(req, res) {
  try {
    const db = getDatabase();
    const currentMonth = new Date().toISOString().slice(0, 7);  // YYYY-MM

    // Calcular primeiro e último dia do mês
    const year = parseInt(currentMonth.split('-')[0]);
    const month = parseInt(currentMonth.split('-')[1]);
    const monthStart = new Date(year, month - 1, 1).toISOString().split('T')[0];
    const monthEnd = new Date(year, month, 0).toISOString().split('T')[0];

    // Buscar TOP 5
    const ranking = db.prepare(`
      SELECT
        u.username,
        s.month_fish,
        ROW_NUMBER() OVER (ORDER BY s.month_fish DESC) as rank
      FROM fishing_stats s
      JOIN users u ON s.user_id = u.id
      WHERE s.month_year = ? AND s.month_fish > 0
      ORDER BY s.month_fish DESC
      LIMIT 5
    `).all(currentMonth);

    return res.json({
      success: true,
      month_year: currentMonth,
      month_start: monthStart,
      month_end: monthEnd,
      ranking: ranking.map(r => ({
        rank: r.rank,
        username: r.username,
        month_fish: r.month_fish
      }))
    });

  } catch (error) {
    console.error('[RANKING] ❌ Erro:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao buscar ranking mensal: ' + error.message
    });
  }
}

/**
 * GET /api/ranking/alltime
 * Obter TOP 5 de todos os tempos
 */
function getAlltimeRanking(req, res) {
  try {
    const db = getDatabase();

    // Buscar TOP 5
    const ranking = db.prepare(`
      SELECT
        u.username,
        SUM(s.total_fish) as total_fish,
        ROW_NUMBER() OVER (ORDER BY SUM(s.total_fish) DESC) as rank
      FROM fishing_stats s
      JOIN users u ON s.user_id = u.id
      GROUP BY u.id, u.username
      HAVING total_fish > 0
      ORDER BY total_fish DESC
      LIMIT 5
    `).all();

    return res.json({
      success: true,
      ranking: ranking.map(r => ({
        rank: r.rank,
        username: r.username,
        total_fish: r.total_fish
      }))
    });

  } catch (error) {
    console.error('[RANKING] ❌ Erro:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao buscar ranking geral: ' + error.message
    });
  }
}

/**
 * GET /api/config/public
 * Obter configurações públicas (sem autenticação)
 */
function getPublicConfig(req, res) {
  try {
    const db = getDatabase();

    // Buscar apenas configs públicas (excluir configs sensíveis)
    const publicKeys = ['discord_link', 'telegram_link', 'support_email', 'announcement'];

    const configs = db.prepare(`
      SELECT key, value
      FROM config
      WHERE key IN (${publicKeys.map(() => '?').join(',')})
    `).all(...publicKeys);

    // Converter array para objeto { key: value }
    const configObj = {};
    configs.forEach(c => {
      configObj[c.key] = c.value;
    });

    return res.json({
      success: true,
      config: configObj
    });

  } catch (error) {
    console.error('[CONFIG] ❌ Erro:', error);
    return res.status(500).json({
      success: false,
      message: 'Erro ao buscar configurações: ' + error.message
    });
  }
}

module.exports = {
  getUserStats,
  getMonthlyRanking,
  getAlltimeRanking,
  getPublicConfig
};
