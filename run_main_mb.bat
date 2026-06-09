@echo off
setlocal

rem Always run from this script's directory
cd /d "%~dp0"

if exist "C:\Users\Asus\miniconda3\condabin\conda.bat" (
    call "C:\Users\Asus\miniconda3\condabin\conda.bat" activate mb
) else (
    call conda activate mb
)

if errorlevel 1 (
    echo [ERROR] Failed to activate conda environment "mb".
    exit /b 1
)

python "E:\Godot_interface\MOBBO_3D_GAMES_ADS\MOBBO_3D_GAMES\main_new.py"
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%
