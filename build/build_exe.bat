@echo off
:: ============================================================
::  SENTINEL v2.0 — Script de compilacion a .exe
::  Ejecutar desde: la carpeta V2\ del proyecto
::  Requisito: Python 3.9+ instalado en Windows
:: ============================================================

echo [1/4] Instalando dependencias...
pip install numpy scipy scikit-learn opencv-python matplotlib reportlab Pillow joblib pyinstaller

echo.
echo [2/4] Limpiando builds anteriores...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

echo.
echo [3/4] Compilando SENTINEL.exe...
pyinstaller sentinel.spec --noconfirm

echo.
echo [4/4] Verificando resultado...
if exist "dist\SENTINEL.exe" (
    echo =============================================
    echo  EXITO: dist\SENTINEL.exe generado
    for %%F in ("dist\SENTINEL.exe") do echo  Tamanio: %%~zF bytes
    echo =============================================
) else (
    echo ERROR: No se genero el .exe. Revisa los mensajes anteriores.
)

pause
