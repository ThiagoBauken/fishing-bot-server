@echo off
cls
echo ========================================
echo   FORCAR REBUILD DO SERVIDOR
echo   (EasyPanel detecta e rebuilda)
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Criando marcador .force-rebuild...
echo. > .force-rebuild
echo OK - Marcador criado!
echo.

echo [2/3] Commitando marcador...
git add .force-rebuild admin_panel.html server.py
git commit -m "force: Trigger rebuild for fish statistics update"
echo.

echo [3/3] Enviando para GitHub...
git push
echo.

if %errorlevel% equ 0 (
    echo ========================================
    echo SUCESSO! REBUILD SERA ACIONADO!
    echo ========================================
    echo.
    echo EasyPanel detectara a mudanca e fara rebuild automatico.
    echo Aguarde 2-3 minutos e acesse:
    echo.
    echo https://private-serverpesca.pbzgje.easypanel.host/admin
    echo.
    echo Verifique se as colunas aparecem:
    echo - Total Fish
    echo - Mes Fish
    echo - Ultima Pescaria
    echo.
) else (
    echo.
    echo ERRO ao fazer push!
    echo Verifique sua conexao e tente novamente.
    echo.
)

pause
