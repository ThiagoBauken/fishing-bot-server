# 🎛️ Painel Administrativo - Fishing Bot v5.0

## 🌐 Acesso ao Painel

**URL:** `https://seu-servidor.com/admin`

**Exemplo (EasyPanel):** `https://private-serverpesca.pbzgje.easypanel.host/admin`

## 🔐 Login

1. Acesse a URL do painel
2. Digite a senha de admin
3. Clique em "Entrar"

**Senha padrão:** `admin123`

⚠️ **IMPORTANTE:** Altere a senha padrão em produção!

## ⚙️ Configurar Senha

### Via arquivo `.env`

```bash
# Copie o .env.example
cp .env.example .env

# Edite e configure sua senha
ADMIN_PASSWORD=sua_senha_segura_aqui
```

### Via variável de ambiente (Docker/EasyPanel)

Configure a variável de ambiente no seu provedor:

```
ADMIN_PASSWORD=sua_senha_segura_aqui
```

## 📊 Funcionalidades

### Dashboard

- **Total de usuários:** Quantidade de usuários cadastrados
- **Usuários ativos:** Quantos estão conectados agora (WebSocket)
- **Total de peixes:** Soma de peixes de todas as sessões ativas
- **Peixes do mês:** (TODO - será implementado)

### Gerenciamento de Usuários

**Tabela de usuários mostra:**
- ID
- Login
- Nome do PC
- License Key (primeiros 20 caracteres)
- Data de cadastro
- Status (🟢 Online / ⚪ Offline)

**Ações disponíveis:**
- 🗑️ **Deletar usuário** - Remove do banco e desconecta WebSocket

## 🔒 Segurança

- ✅ Todas as rotas admin requerem senha
- ✅ Senha enviada via header HTTP
- ✅ Não é armazenada no navegador
- ✅ Deletar usuário desconecta automaticamente

## 🛠️ API Admin (para desenvolvedores)

### GET /admin/api/stats

Retorna estatísticas do servidor.

```bash
curl -H "admin_password: admin123" \
  https://seu-servidor.com/admin/api/stats
```

**Resposta:**
```json
{
  "success": true,
  "stats": {
    "total_users": 10,
    "active_users": 3,
    "total_fish": 150,
    "month_fish": 0,
    "server_version": "2.0.0",
    "keymaster_url": "https://private-keygen.pbzgje.easypanel.host"
  }
}
```

### GET /admin/api/users

Lista todos os usuários cadastrados.

```bash
curl -H "admin_password: admin123" \
  https://seu-servidor.com/admin/api/users
```

**Resposta:**
```json
{
  "success": true,
  "users": [
    {
      "id": 1,
      "login": "usuario1",
      "pc_name": "DESKTOP-ABC123",
      "license_key": "XXXX-XXXX-XXXX-XXXX",
      "created_at": "2025-11-29 10:30:00",
      "last_seen": "2025-11-29 12:45:00",
      "hwid": "abc123def456...",
      "is_active": true
    }
  ]
}
```

### DELETE /admin/api/user/{license_key}

Deletar usuário específico.

```bash
curl -X DELETE \
  -H "admin_password: admin123" \
  https://seu-servidor.com/admin/api/user/XXXX-XXXX-XXXX-XXXX
```

**Resposta:**
```json
{
  "success": true,
  "message": "Usuário deletado com sucesso"
}
```

## 🐛 Troubleshooting

### "Senha incorreta"

- Verifique se configurou `ADMIN_PASSWORD` no `.env`
- Reinicie o servidor após alterar o `.env`
- Senha padrão é `admin123`

### Painel não carrega (404)

- Verifique se `admin_panel.html` existe no servidor
- Confira logs do servidor: `docker logs nome-do-container`
- Verifique se o servidor Python está rodando

### Usuários não aparecem

- Verifique se há usuários cadastrados no banco
- Confira permissões de leitura do banco SQLite
- Veja logs do servidor

## 📝 Notas

- O painel é **totalmente funcional** com o servidor Python FastAPI
- Não interfere no funcionamento do WebSocket ou lógica de fishing
- **Thread-safe** - pode ser acessado por múltiplos admins simultaneamente
- Usa pool de conexões do banco SQLite (read/write separados)

## 🚀 Próximas Funcionalidades

- [ ] Estatísticas de peixes por mês
- [ ] Gráficos de uso
- [ ] Exportar relatórios
- [ ] Logs em tempo real
- [ ] Alterar configurações do servidor via painel
