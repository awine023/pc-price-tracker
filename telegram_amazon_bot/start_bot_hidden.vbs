' ===================================================
' Telegram Amazon Bot - Demarrage silencieux
' ===================================================
' Ce script lance le bot SANS fenetre visible
' ===================================================

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' ===================================================
' CONFIGURATION
' ===================================================
ProjectPath = "C:\Users\bouch\pc-price-tracker\telegram_amazon_bot"
BatchPath = ProjectPath & "\start_bot.bat"
PythonPath = ProjectPath & "\venv\Scripts\python.exe"
MainScript = ProjectPath & "\bot.py"

' ===================================================
' VERIFICATIONS
' ===================================================
If Not fso.FolderExists(ProjectPath) Then
    MsgBox "ERREUR: Le dossier du projet n'existe pas: " & ProjectPath, vbCritical, "Telegram Bot - Erreur"
    WScript.Quit
End If

If Not fso.FileExists(MainScript) Then
    MsgBox "ERREUR: Le fichier bot.py n'existe pas: " & MainScript, vbCritical, "Telegram Bot - Erreur"
    WScript.Quit
End If

' ===================================================
' LANCER LE BOT
' ===================================================
WshShell.CurrentDirectory = ProjectPath

' Lancer le bot en mode cache (fenetre invisible)
WshShell.Run "cmd /c python bot.py", 0, False

' 0 = Fenetre invisible
' False = Ne pas attendre que le script se termine

Set WshShell = Nothing
Set fso = Nothing

