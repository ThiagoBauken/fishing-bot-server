@echo off
chcp 65001 >nul
echo.
echo ╔═══════════════════════════════════════════════════════╗
echo ║  🗄️  Inicializando Banco de Dados SQLite              ║
echo ╚═══════════════════════════════════════════════════════╝
echo.

REM Verificar se Node.js está instalado
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Node.js não encontrado!
    echo.
    echo 💡 Execute INSTALL_SERVER.bat primeiro
    echo.
    pause
    exit /b 1
)

REM Verificar se dependências estão instaladas
if not exist "node_modules\" (
    echo ❌ Dependências não instaladas!
    echo.
    echo 💡 Execute INSTALL_SERVER.bat primeiro
    echo.
    pause
    exit /b 1
)

REM Criar banco de dados
echo 🔧 Criando banco de dados...
echo.
node -e "const db = require('./database'); db.initialize(); setTimeout(() => process.exit(0), 1000);"

if %errorlevel% neq 0 (
    echo.
    echo ❌ Erro ao criar banco de dados!
    echo.
    pause
    exit /b 1
)

echo.
echo ╔═══════════════════════════════════════════════════════╗
echo ║  ✅ Banco de Dados Criado com Sucesso!               ║
echo ╚═══════════════════════════════════════════════════════╝
echo.
echo 📊 Tabelas criadas:
echo    - users (usuários)
echo    - password_resets (recuperação de senha)
echo    - fishing_stats (estatísticas de pesca)
echo    - sessions (sessões JWT)
echo    - config (configurações dinâmicas)
echo.
echo 👤 Usuário admin padrão criado:
echo    Username: admin
echo    Senha: admin123 (ou valor de ADMIN_PASSWORD no .env)
echo    ⚠️ ALTERE A SENHA EM PRODUÇÃO!
echo.
echo 📝 Próximo passo:
echo    Execute START_SERVER.bat para iniciar o servidor
echo.
pause
