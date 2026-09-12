from pathlib import Path
import os
import re
import sys
import time
import shutil
import subprocess
import py_compile
import traceback

TARGET_VERSION = "89"
OUTPUT_NAME = "bot_wallapop_profesional_v89_ADMIN_ROTACION_FIX.py"
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
# V89 · CAPA DE FLUIDEZ DE INTERFAZ
# =========================================================
# Agrupa refrescos repetidos que ocurren casi al mismo tiempo.
try:
    _v89_dashboard_original = refrescar_dashboard
    _v89_dashboard_after_id = None
    _v89_dashboard_ultimo = 0.0

    def refrescar_dashboard():
        global _v89_dashboard_after_id, _v89_dashboard_ultimo
        ahora = time.monotonic()
        transcurrido = ahora - _v89_dashboard_ultimo

        if transcurrido >= 0.12:
            _v89_dashboard_ultimo = ahora
            _v89_dashboard_after_id = None
            return _v89_dashboard_original()

        if _v89_dashboard_after_id is None:
            espera = max(1, int((0.12 - transcurrido) * 1000))

            def _ejecutar_dashboard_v88():
                global _v89_dashboard_after_id, _v89_dashboard_ultimo
                _v89_dashboard_after_id = None
                _v89_dashboard_ultimo = time.monotonic()
                try:
                    _v89_dashboard_original()
                except Exception:
                    pass

            try:
                _v89_dashboard_after_id = ventana.after(
                    espera,
                    _ejecutar_dashboard_v88
                )
            except Exception:
                return _v89_dashboard_original()

except Exception as _e_v89_ui:
    print("[V89] Capa de fluidez dashboard no aplicada:", _e_v89_ui)

"""


def _inyectar_fluidez(texto):
    if "V89 · CAPA DE FLUIDEZ DE INTERFAZ" in texto:
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
    nuevo = """# Comprobación silenciosa del servidor de actualizaciones (V89, no bloqueante).
def _v89_comprobar_updates_en_segundo_plano():
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
    ventana.after(2400, _v89_comprobar_updates_en_segundo_plano)
except Exception:
    pass

"""
    return texto[:inicio] + nuevo + texto[fin:]



def _aplicar_fix_rotacion_v89(texto):
    """
    Corrige tres problemas de rotación:
    1) publicados.json deja de depender del directorio desde el que se ejecuta.
    2) migra automáticamente registros antiguos de publicados.json.
    3) los interruptores de rotación guardan su valor al cambiar.
    """

    # ---- Registro de publicados persistente ----
    viejo = 'ARCHIVO_PUBLICADOS = "publicados.json"'
    nuevo = '''ARCHIVO_PUBLICADOS = os.path.join(
    CARPETA_DATOS_USUARIO,
    "publicados.json"
)

_PUBLICADOS_LEGACY_MIGRADO = False


def _migrar_publicados_legacy():
    global _PUBLICADOS_LEGACY_MIGRADO

    if _PUBLICADOS_LEGACY_MIGRADO:
        return

    _PUBLICADOS_LEGACY_MIGRADO = True

    destino = Path(
        ARCHIVO_PUBLICADOS
    )

    destino.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    combinados = {}

    # Conservar primero lo que ya exista en la ubicación persistente.
    try:
        if destino.exists():
            datos = json.loads(
                destino.read_text(
                    encoding="utf-8"
                )
            )
            if isinstance(datos, dict):
                combinados.update(
                    datos
                )
    except Exception:
        pass

    home = Path.home()

    candidatos = [
        Path.cwd() / "publicados.json",
        Path(__file__).resolve().parent / "publicados.json",
        home / "Downloads" / "publicados.json",
        home / "Descargas" / "publicados.json",
        home / "Desktop" / "publicados.json",
        home / "Escritorio" / "publicados.json",
        home / "Documents" / "publicados.json",
        home / "Documentos" / "publicados.json",
    ]

    # Buscar copias antiguas dentro de las carpetas de DIAGPROG5 y ubicaciones
    # habituales. Solo importamos diccionarios con estructura de publicados.
    bases = [
        Path(
            CARPETA_DATOS_USUARIO
        ),
        home / "Downloads",
        home / "Descargas",
        home / "Desktop",
        home / "Escritorio",
        home / "Documents",
        home / "Documentos",
    ]

    for base in bases:
        try:
            if base.exists():
                candidatos.extend(
                    base.rglob(
                        "publicados.json"
                    )
                )
        except Exception:
            pass

    vistos = set()

    for ruta in candidatos:
        try:
            ruta = Path(
                ruta
            )

            clave = str(
                ruta.resolve()
            ).lower()

            if clave in vistos:
                continue

            vistos.add(
                clave
            )

            if not ruta.is_file():
                continue

            datos = json.loads(
                ruta.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(
                datos,
                dict
            ):
                continue

            for identificador, item in datos.items():
                if not isinstance(
                    item,
                    dict
                ):
                    continue

                # Solo migramos entradas que parecen registros DIAGPROG5.
                if not str(
                    item.get(
                        "titulo",
                        ""
                    )
                ).strip():
                    continue

                if not str(
                    item.get(
                        "fecha",
                        ""
                    )
                ).strip():
                    continue

                existente = combinados.get(
                    identificador
                )

                if not isinstance(
                    existente,
                    dict
                ):
                    combinados[
                        identificador
                    ] = dict(
                        item
                    )
                else:
                    # Mantener protecciones/estado ya guardados y completar
                    # campos que falten con la copia antigua.
                    for k, v in item.items():
                        existente.setdefault(
                            k,
                            v
                        )

        except Exception:
            pass

    try:
        destino.write_text(
            json.dumps(
                combinados,
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )
    except Exception:
        pass
'''
    if viejo in texto:
        texto = texto.replace(
            viejo,
            nuevo,
            1
        )

    # Hacer que cargar_publicados migre antes de leer.
    viejo_cargar = '''def cargar_publicados():
    if not os.path.isfile(ARCHIVO_PUBLICADOS):
        return {}
'''
    nuevo_cargar = '''def cargar_publicados():
    try:
        _migrar_publicados_legacy()
    except Exception:
        pass

    if not os.path.isfile(ARCHIVO_PUBLICADOS):
        return {}
'''
    if viejo_cargar in texto:
        texto = texto.replace(
            viejo_cargar,
            nuevo_cargar,
            1
        )

    # Guardado atómico y siempre en carpeta persistente.
    viejo_guardar = '''    with open(ARCHIVO_PUBLICADOS, "w", encoding="utf-8") as archivo:
        json.dump(publicados, archivo, ensure_ascii=False, indent=4)
'''
    nuevo_guardar = '''    ruta_publicados = Path(
        ARCHIVO_PUBLICADOS
    )

    ruta_publicados.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporal = ruta_publicados.with_suffix(
        ".json.tmp"
    )

    temporal.write_text(
        json.dumps(
            publicados,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )

    temporal.replace(
        ruta_publicados
    )
'''
    texto = texto.replace(
        viejo_guardar,
        nuevo_guardar
    )

    # Autoguardado al mover cualquier switch de rotación.
    bloque_funcion = '''def guardar_ajustes_rotacion_ui():
'''
    if (
        bloque_funcion in texto
        and "def _rotacion_autoguardar_switch(" not in texto
    ):
        idx = texto.find(
            bloque_funcion
        )

        # Insertamos helper justo antes de la función de guardado.
        helper = '''def _rotacion_autoguardar_switch():
    try:
        # Dejar que CustomTkinter actualice primero la BooleanVar.
        ventana.after(
            40,
            guardar_ajustes_rotacion_ui
        )
    except Exception:
        try:
            guardar_ajustes_rotacion_ui()
        except Exception:
            pass


'''
        texto = (
            texto[:idx]
            + helper
            + texto[idx:]
        )

    # Añadir command a los 3 switches si aún no existe.
    texto = texto.replace(
        '''    variable=var_rotacion_activa,
    progress_color=COLOR_ACENTO
''',
        '''    variable=var_rotacion_activa,
    command=_rotacion_autoguardar_switch,
    progress_color=COLOR_ACENTO
''',
        1
    )

    texto = texto.replace(
        '''    variable=var_rotacion_backup,
    progress_color=COLOR_ACENTO
''',
        '''    variable=var_rotacion_backup,
    command=_rotacion_autoguardar_switch,
    progress_color=COLOR_ACENTO
''',
        1
    )

    texto = texto.replace(
        '''    variable=var_rotacion_reintentar,
    progress_color=COLOR_ACENTO
''',
        '''    variable=var_rotacion_reintentar,
    command=_rotacion_autoguardar_switch,
    progress_color=COLOR_ACENTO
''',
        1
    )

    # El diagnóstico debe mostrar también el valor visual actual, para detectar
    # enseguida una discrepancia entre UI y disco.
    needle_diag = '''    lineas = [
        "DIAGNÓSTICO DE ROTACIÓN",
'''
    if needle_diag in texto and "Estado interruptor UI:" not in texto:
        texto = texto.replace(
            needle_diag,
            '''    try:
        _ui_activa = bool(
            var_rotacion_activa.get()
        )
    except Exception:
        _ui_activa = bool(
            cfg.get(
                "activo",
                True
            )
        )

    lineas = [
        "DIAGNÓSTICO DE ROTACIÓN",
''',
            1
        )

        texto = texto.replace(
            '''        (
            "Activo: "
            + (
                "Sí"
                if cfg.get("activo", True)
                else "No"
            )
        ),
''',
            '''        (
            "Activo guardado: "
            + (
                "Sí"
                if cfg.get("activo", True)
                else "No"
            )
        ),
        (
            "Estado interruptor UI: "
            + (
                "Sí"
                if _ui_activa
                else "No"
            )
        ),
''',
            1
        )

    # Mejorar mensaje cuando no hay candidatos para explicar la migración.
    texto = texto.replace(
        '''            (
                "No hay anuncios de DIAGPROG5 suficientemente antiguos "
                "y sin protección para liberar espacio."
            )
''',
        '''            (
                "No hay candidatos seguros registrados por DIAGPROG5. "
                "V89 ya migró automáticamente los publicados.json antiguos. "
                "Si sigue en 0, esos anuncios fueron publicados antes de que "
                "DIAGPROG5 los registrara y no se borrarán automáticamente."
            )
''',
        1
    )

    return texto


def construir_v89(fuente_path, texto):
    nuevo = _reemplazar_version(texto)
    nuevo = _aplicar_fix_rotacion_v89(nuevo)
    nuevo = _mejorar_asset_path(nuevo)
    nuevo = _mejorar_instalador(nuevo)
    nuevo = _inyectar_fluidez(nuevo)
    nuevo = _hacer_comprobacion_update_inicio_no_bloqueante(nuevo)

    requisitos = [
        'return "89"',
        "banner_dp5_limpio_v15.png",
        "sidebar = ctk.CTkFrame",
        "Centro de actualizaciones",
        "def instalar_actualizacion_admin",
        "ventana.mainloop()",
    ]
    faltan = [x for x in requisitos if x not in nuevo]
    if faltan:
        raise RuntimeError(
            "La base encontrada no es válida para V89. Falta: " + ", ".join(faltan)
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

    nuevo = construir_v89(fuente, texto)

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
                "DIAGPROG5 · Actualización V89",
                "No pude completar la actualización:\n\n" + str(e),
            )
            root.destroy()
        except Exception:
            traceback.print_exc()
        raise
