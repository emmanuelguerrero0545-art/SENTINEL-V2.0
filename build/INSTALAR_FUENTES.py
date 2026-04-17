#!/usr/bin/env python3
# ============================================================
#  BIOCONNECT — Instalador de fuentes OpenDyslexic
#  Ejecutar UNA VEZ antes de usar la tipografía accesible.
#
#  Uso:
#    python INSTALAR_FUENTES.py
#
#  Descarga OpenDyslexic desde GitHub y la copia al directorio
#  de fuentes del usuario del sistema operativo.
# ============================================================

import os
import sys
import shutil
import platform
import urllib.request
from pathlib import Path

FUENTES = {
    "OpenDyslexic-Regular.otf":
        "https://github.com/antijingoist/opendyslexic/raw/master/compiled/OpenDyslexic-Regular.otf",
    "OpenDyslexic-Bold.otf":
        "https://github.com/antijingoist/opendyslexic/raw/master/compiled/OpenDyslexic-Bold.otf",
    "OpenDyslexic-Italic.otf":
        "https://github.com/antijingoist/opendyslexic/raw/master/compiled/OpenDyslexic-Italic.otf",
}

FONTS_DIR = Path(__file__).parent   # Carpeta fonts/ de la app


def directorio_usuario():
    sistema = platform.system()
    if sistema == "Linux":
        return Path.home() / ".local" / "share" / "fonts"
    elif sistema == "Darwin":
        return Path.home() / "Library" / "Fonts"
    elif sistema == "Windows":
        return Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
    return None


def main():
    print("BioConnect — Instalador de fuentes OpenDyslexic")
    print("=" * 50)

    destino = directorio_usuario()
    if destino is None:
        print("ERROR: Sistema operativo no reconocido.")
        sys.exit(1)

    destino.mkdir(parents=True, exist_ok=True)
    print(f"Directorio de instalación: {destino}\n")

    instalados = 0
    for nombre, url in FUENTES.items():
        local = FONTS_DIR / nombre
        dst   = destino / nombre

        if dst.exists():
            print(f"  ✓ Ya existe: {nombre}")
            instalados += 1
            continue

        # Intentar descargar si no está en fonts/
        if not local.exists():
            print(f"  ↓ Descargando {nombre}...")
            try:
                urllib.request.urlretrieve(url, local)
                print(f"    Descargado OK")
            except Exception as e:
                print(f"    ERROR descargando: {e}")
                print(f"    Descarga manual: {url}")
                continue

        # Copiar al directorio del sistema
        try:
            shutil.copy2(local, dst)
            print(f"  ✓ Instalado: {nombre}")
            instalados += 1
        except Exception as e:
            print(f"  ✗ Error al copiar {nombre}: {e}")

    # Actualizar cache de fuentes en Linux
    if platform.system() == "Linux" and instalados > 0:
        print("\nActualizando cache de fuentes (fc-cache)...")
        os.system("fc-cache -f -q")

    print(f"\n{'=' * 50}")
    if instalados == len(FUENTES):
        print("✓ Instalación completa. Reinicia BioConnect.")
        print("  En Configuración → Accesibilidad → Tipografia OpenDyslexic")
    else:
        print(f"⚠ {instalados}/{len(FUENTES)} fuentes instaladas.")
        print("  Puedes descargarlas manualmente desde:")
        print("  https://github.com/antijingoist/opendyslexic/tree/master/compiled")
        print(f"  y colocarlas en: {FONTS_DIR}")


if __name__ == "__main__":
    main()
