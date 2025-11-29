@echo off
chcp 65001 >nul
echo.
echo ╔═══════════════════════════════════════════════════════╗
echo ║  📦 Instalando Dependências do Servidor de Auth      ║
echo ╚═══════════════════════════════════════════════════════╝
echo.

REM Verificar se Node.js está instalado
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ Node.js não encontrado!
    echo.
    echo 💡 Instale Node.js v18+ em: https://nodejs.org
    echo.
    pause
    exit /b 1
)

echo ✅ Node.js encontrado:
node --version
echo.

REM Verificar se npm está instalado
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo ❌ npm não encontrado!
    echo.
    pause
    exit /b 1
)

echo ✅ npm encontrado:
npm --version
echo.

REM Instalar dependências
echo 📥 Instalando dependências...
echo.
npm install

if %errorlevel% neq 0 (
    echo.
    echo ❌ Erro ao instalar dependências!
    echo.
    pause
    exit /b 1
)

echo.
echo ╔═══════════════════════════════════════════════════════╗
echo ║  ✅ Instalação Completa!                              ║
echo ╚═══════════════════════════════════════════════════════╝
echo.
echo 📝 Próximos passos:
echo    1. Configure o arquivo .env (copiar de .env.example)
echo    2. Execute INIT_DB.bat para criar o banco de dados
echo    3. Execute START_SERVER.bat para iniciar o servidor
echo.
pause
