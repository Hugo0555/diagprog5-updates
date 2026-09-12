from pathlib import Path
import os
import re
import sys
import time
import shutil
import subprocess
import py_compile
import traceback

TARGET_VERSION = "88"
OUTPUT_NAME = "bot_wallapop_profesional_v88_ADMIN_ESTABLE.py"
BANNER_NAME = "banner_dp5_limpio_v15.png"


def _leer_texto(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""


def _version_fuente(texto):
    m = re.search(
        r'def\s+version_actual_bot\s*\(\s*\)\s*:\s*\n\s*return\s*["\']([^"\']+)["\']',
        texto,
        re.MULTILINE,
    )
    return m.group(1).strip() if m else ""


def _es_fuente_completa(path):
    try:
        p = Path(path)
        if not p.is_file() or p.stat().st_size < 350_000:
            return False
        t = _leer_texto(p)
        requisitos = (
            "DIAGPROG5",
            "customtkinter",
            "def version_actual_bot",
            "sidebar = ctk.CTkFrame",
            "banner_dp5_limpio_v15.png",
            "def instalar_actualizacion_admin",
            "ventana.mainloop()",
        )
        return all(x in t for x in requisitos)
    except Exception:
        return False


def _candidatos_fuente():
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or home)
    data = local / "DIAGPROG5"
    bases = [
        data / "actualizaciones",
        data / "backups_actualizaciones",
        data,
        home / "Downloads",
        home / "Descargas",
        home / "Desktop",
        home / "Escritorio",
        home / "Documents",
        home / "Documentos",
    ]
    vistos = set()
    encontrados = []
    for base in bases:
        try:
            if not base.exists():
                continue
            for p in base.rglob("*.py"):
                try:
                    rp = str(p.resolve()).lower()
                    if rp in vistos:
                        continue
                    vistos.add(rp)
                    if _es_fuente_completa(p):
                        texto = _leer_texto(p)
                        version = _version_fuente(texto)
                        preferencia = 3 if version.startswith("87") else (2 if version.startswith("86") else 1)
                        encontrados.append((preferencia, p.stat().st_mtime, p.stat().st_size, p, texto, version))
                except Exception:
                    pass
        except Exception:
            pass
    encontrados.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return encontrados


def _buscar_banner(fuente):
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or home)
    data = local / "DIAGPROG5"
    candidatos = [
        fuente.parent / BANNER_NAME,
        fuente.parent.parent / BANNER_NAME,
        data / "assets" / BANNER_NAME,
        Path.cwd() / BANNER_NAME,
        home / "Downloads" / BANNER_NAME,
        home / "Descargas" / BANNER_NAME,
        home / "Desktop" / BANNER_NAME,
        home / "Escritorio" / BANNER_NAME,
        home / "Documents" / BANNER_NAME,
        home / "Documentos" / BANNER_NAME,
    ]
    for base in [
        data,
        home / "Downloads",
        home / "Descargas",
        home / "Desktop",
        home / "Escritorio",
        home / "Documents",
        home / "Documentos",
    ]:
        try:
            if base.exists():
                candidatos.extend(base.rglob(BANNER_NAME))
        except Exception:
            pass
    vistos = set()
    for p in candidatos:
        try:
            p = Path(p)
            k = str(p.resolve()).lower()
            if k in vistos:
                continue
            vistos.add(k)
            if p.is_file() and p.stat().st_size > 100_000:
                return p
        except Exception:
            pass
    return None


def _reemplazar_version(texto):
    texto, n = re.subn(
        r'(def\s+version_actual_bot\s*\(\s*\)\s*:\s*\n\s*return\s*)["\'][^"\']+["\']',
        lambda m: m.group(1) + '"' + TARGET_VERSION + '"',
        texto,
        count=1,
        flags=re.MULTILINE,
    )
    if n != 1:
        raise RuntimeError("No pude actualizar version_actual_bot de la versión base.")

    texto = re.sub(
        r'(ventana\.title\(["\']DIAGPROG5 - WALLAPOP BOT \(ADMIN\) · V)[^"\']+(["\']\))',
        r'\g<1>' + TARGET_VERSION + r'\g<2>',
        texto,
        count=1,
    )
    texto = re.sub(
        r'(text=["\']DIAGPROG5 · WALLAPOP BOT · V)[^"\']+(["\'])',
        r'\g<1>' + TARGET_VERSION + r'\g<2>',
        texto,
        count=1,
    )
    return texto


def _mejorar_asset_path(texto):
    needle = "    # 5) Descargas/Downloads\n    try:\n        home = Path.home()\n"
    if needle in texto and 'DIAGPROG5" / "assets" / nombre' not in texto:
        extra = """    # 5) Cache persistente de recursos de DIAGPROG5
    try:
        _raiz_assets = (
            Path(
                os.environ.get("LOCALAPPDATA")
                or os.environ.get("APPDATA")
                or Path.home()
            )
            / "DIAGPROG5"
            / "assets"
        )
        candidatos.append(
            _raiz_assets / nombre
        )
    except Exception:
        pass

    # 6) Descargas/Downloads
    try:
        home = Path.home()
"""
        texto = texto.replace(needle, extra, 1)
    return texto


def _mejorar_instalador(texto):
    old = """        estado.configure(
            text=(
                f"✅ Nueva versión V{version} abierta. "
                "Puedes cerrar esta versión cuando compruebes que funciona."
            )
        )
"""
    new = """        estado.configure(
            text=(
                f"✅ Nueva versión V{version} abierta. "
                "Cerrando la versión anterior..."
            )
        )

        # Cerrar automáticamente la versión anterior después de arrancar la nueva.
        try:
            def _cerrar_version_anterior():
                try:
                    fn_cerrar = globals().get("cerrar_aplicacion")
                    if callable(fn_cerrar):
                        fn_cerrar()
                    else:
                        ventana.destroy()
                except Exception:
                    try:
                        ventana.destroy()
                    except Exception:
                        pass

            ventana.after(900, _cerrar_version_anterior)
        except Exception:
            pass
"""
    if old in texto:
        texto = texto.replace(old, new, 1)
    return texto


def _capa_fluidez():
    return """

# =========================================================
# V88 · CAPA DE FLUIDEZ DE INTERFAZ
# =========================================================
# Agrupa refrescos repetidos que ocurren casi al mismo tiempo.
try:
    _v88_dashboard_original = refrescar_dashboard
    _v88_dashboard_after_id = None
    _v88_dashboard_ultimo = 0.0

    def refrescar_dashboard():
        global _v88_dashboard_after_id, _v88_dashboard_ultimo
        ahora = time.monotonic()
        transcurrido = ahora - _v88_dashboard_ultimo

        if transcurrido >= 0.12:
            _v88_dashboard_ultimo = ahora
            _v88_dashboard_after_id = None
            return _v88_dashboard_original()

        if _v88_dashboard_after_id is None:
            espera = max(1, int((0.12 - transcurrido) * 1000))

            def _ejecutar_dashboard_v88():
                global _v88_dashboard_after_id, _v88_dashboard_ultimo
                _v88_dashboard_after_id = None
                _v88_dashboard_ultimo = time.monotonic()
                try:
                    _v88_dashboard_original()
                except Exception:
                    pass

            try:
                _v88_dashboard_after_id = ventana.after(
                    espera,
                    _ejecutar_dashboard_v88
                )
            except Exception:
                return _v88_dashboard_original()

except Exception as _e_v88_ui:
    print("[V88] Capa de fluidez dashboard no aplicada:", _e_v88_ui)

"""


def _inyectar_fluidez(texto):
    if "V88 · CAPA DE FLUIDEZ DE INTERFAZ" in texto:
        return texto
    marker = "actualizar_menu_lotes()\n\ntry:\n    ventana.after(\n        5000,\n        _programar_autoguardado_borrador\n    )"
    if marker in texto:
        return texto.replace(marker, _capa_fluidez() + "\n" + marker, 1)
    return texto


def _hacer_comprobacion_update_inicio_no_bloqueante(texto):
    inicio = texto.find("# Comprobación silenciosa del servidor de actualizaciones.")
    fin = texto.find("# Autochequeo del creador al arrancar.", inicio)
    if inicio == -1 or fin == -1:
        return texto
    nuevo = """# Comprobación silenciosa del servidor de actualizaciones (V88, no bloqueante).
def _v88_comprobar_updates_en_segundo_plano():
    def _trabajo():
        try:
            _update_inicio = comprobar_actualizacion_admin(
                mostrar=False
            )
            if (
                _update_inicio.get("ok")
                and _update_inicio.get("disponible")
            ):
                print(
                    "[UPDATER] Nueva versión disponible:",
                    _update_inicio.get("version_remota", "?")
                )
        except Exception as e:
            print("[UPDATER] No pude comprobar actualizaciones:", e)

    try:
        threading.Thread(
            target=_trabajo,
            daemon=True
        ).start()
    except Exception:
        pass

try:
    ventana.after(2400, _v88_comprobar_updates_en_segundo_plano)
except Exception:
    pass

"""
    return texto[:inicio] + nuevo + texto[fin:]


def construir_v88(fuente_path, texto):
    nuevo = _reemplazar_version(texto)
    nuevo = _mejorar_asset_path(nuevo)
    nuevo = _mejorar_instalador(nuevo)
    nuevo = _inyectar_fluidez(nuevo)
    nuevo = _hacer_comprobacion_update_inicio_no_bloqueante(nuevo)

    requisitos = [
        'return "88"',
        "banner_dp5_limpio_v15.png",
        "sidebar = ctk.CTkFrame",
        "Centro de actualizaciones",
        "def instalar_actualizacion_admin",
        "ventana.mainloop()",
    ]
    faltan = [x for x in requisitos if x not in nuevo]
    if faltan:
        raise RuntimeError(
            "La base encontrada no es válida para V88. Falta: " + ", ".join(faltan)
        )
    return nuevo


def _cerrar_padre_tras_arranque(parent_pid):
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(parent_pid), "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=8,
            )
        else:
            import signal
            os.kill(parent_pid, signal.SIGTERM)
    except Exception:
        pass


def main():
    parent_pid = os.getppid()
    encontrados = _candidatos_fuente()
    if not encontrados:
        raise RuntimeError(
            "No encontré una instalación completa de DIAGPROG5 para actualizar. "
            "Conserva abierta tu V87 y vuelve a pulsar Actualizar."
        )

    _, _, _, fuente, texto, version_fuente = encontrados[0]
    banner = _buscar_banner(fuente)
    if banner is None:
        raise RuntimeError(
            "No encontré banner_dp5_limpio_v15.png. "
            "He cancelado la actualización para no crear otra versión sin banner."
        )

    nuevo = construir_v88(fuente, texto)

    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or home)
    data = local / "DIAGPROG5"
    carpeta_updates = data / "actualizaciones"
    carpeta_updates.mkdir(parents=True, exist_ok=True)

    destino = carpeta_updates / OUTPUT_NAME
    destino.write_text(nuevo, encoding="utf-8")

    assets = data / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copy2(banner, carpeta_updates / BANNER_NAME)
    shutil.copy2(banner, assets / BANNER_NAME)

    py_compile.compile(str(destino), doraise=True)

    subprocess.Popen(
        [sys.executable, str(destino)],
        cwd=str(carpeta_updates),
    )

    time.sleep(1.8)
    _cerrar_padre_tras_arranque(parent_pid)
    return destino


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "DIAGPROG5 · Actualización V88",
                "No pude completar la actualización:\n\n" + str(e),
            )
            root.destroy()
        except Exception:
            traceback.print_exc()
        raise
