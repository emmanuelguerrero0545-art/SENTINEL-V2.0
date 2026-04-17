@echo off
:: ============================================================
::  SENTINEL — Setup inicial para GitHub
::  Ejecutar UNA VEZ desde la carpeta del proyecto (V2\)
::  Requisito: git instalado en Windows
:: ============================================================

echo [1/5] Inicializando repositorio git...
git init -b main

echo.
echo [2/5] Configurando identidad...
git config user.name "Emmanuel Guerrero"
git config user.email "emmanuel.guerrero0545@alumnos.udg.mx"

echo.
echo [3/5] Conectando con GitHub...
:: CAMBIA la URL por la de tu repositorio SENTINEL en GitHub
git remote add origin https://github.com/TU-USUARIO/SENTINEL.git

echo.
echo [4/5] Staging de todos los archivos utiles...
git add .
git status

echo.
echo [5/5] Primer commit...
git commit -m "feat: SENTINEL v2.0 - initial release

- Clasificador LogisticRegression (AUC 0.81, no tautologico)
- 7 parametros de perfusion ICG
- Validacion estadistica N=500 (5/5 robustness, 3/3 falsification)
- Suite de 58 tests pytest (todos PASS)
- GUI Tkinter multilenguaje (8 idiomas)
- Generador de reportes PDF clinicos
- Modo tiempo real y lector de video NIR
- Logging centralizado, type hints, pyproject.toml"

echo.
echo =============================================
echo  Primer commit listo. Ahora ejecuta:
echo  git push -u origin main
echo =============================================
pause
