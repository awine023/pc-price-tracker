@echo off
REM ===================================================
REM Telegram Amazon Bot - Démarrage
REM ===================================================

cd /d "%~dp0"

echo.
echo ===================================================
echo   DEMARRAGE DU BOT TELEGRAM AMAZON
echo ===================================================
echo.

REM Vérifier que Python est installé
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERREUR: Python n'est pas installe ou n'est pas dans le PATH.
    echo Veuillez installer Python 3.10+ et reessayer.
    pause
    exit /b 1
)

REM Vérifier que les dépendances sont installées
echo Verification des dependances...
python -c "import telegram" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installation des dependances...
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo ERREUR: Impossible d'installer les dependances.
        pause
        exit /b 1
    )
)

REM Vérifier que Playwright est installé
python -c "import playwright" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installation de Playwright...
    pip install playwright
    python -m playwright install chromium
)

echo.
echo ===================================================
echo   LANCEMENT DU BOT...
echo ===================================================
echo.
echo Le bot va demarrer. Vous pouvez fermer cette fenetre
echo pour arreter le bot (Ctrl+C).
echo.

python bot.py

pause

