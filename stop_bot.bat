@echo off
REM ===================================================
REM Telegram Amazon Bot - Arret
REM ===================================================

echo.
echo ===================================================
echo   ARRET DU BOT TELEGRAM AMAZON
echo ===================================================
echo.

REM Arrêter tous les processus Python qui exécutent bot.py
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *bot.py*" >nul 2>&1

REM Méthode alternative: arrêter tous les processus Python
REM (Attention: cela arrêtera TOUS les scripts Python en cours)
echo Arret des processus Python...
taskkill /F /IM python.exe /T >nul 2>&1

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ===================================================
    echo SUCCES!
    echo ===================================================
    echo Le bot a ete arrete.
    echo.
) else (
    echo.
    echo Aucun processus Python trouve.
    echo Le bot n'est peut-etre pas en cours d'execution.
    echo.
)

pause

