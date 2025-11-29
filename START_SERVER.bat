@echo off
chcp 65001 >nul
echo.
echo ╔═══════════════════════════════════════════════════════╗
echo ║  🚀 Iniciando Servidor de Autenticação                ║
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

REM Verificar se banco de dados existe
if not exist "fishing_bot_auth.db" (
    echo ⚠️ Banco de dados não encontrado!
    echo.
    echo 💡 Execute INIT_DB.bat primeiro para criar o banco de dados
    echo.
    pause
    exit /b 1
)

REM Verificar se arquivo .env existe
if not exist ".env" (
    echo ⚠️ Arquivo .env não encontrado!
    echo.
    echo 💡 Copie .env.example para .env e configure as variáveis
    echo.
    pause
    exit /b 1
)

echo ✅ Pré-requisitos OK
echo.
echo 🌐 Iniciando servidor...
echo    Pressione Ctrl+C para parar
echo.

REM Iniciar servidor
node server.js

pause
