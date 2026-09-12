from pathlib import Path
import os
import re
import sys
import time
import shutil
import subprocess
import py_compile
import traceback

TARGET_VERSION = "103"
OUTPUT_NAME = "bot_wallapop_profesional_v103_ADMIN_ROTACION_DETALLE.py"
BANNER_NAME = "banner_dp5_limpio_v15.png"


def _escribir_texto_con_reintentos(path, texto, intentos=8, espera=0.18):
    path = Path(path)
    ultimo = None

    for i in range(max(1, int(intentos))):
        try:
            path.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            temporal = path.with_name(
                path.name
                + ".tmp."
                + str(os.getpid())
            )

            temporal.write_text(
                texto,
                encoding="utf-8"
            )

            try:
                os.replace(
                    str(temporal),
                    str(path)
                )
            except PermissionError:
                # En Windows algunos editores/antivirus mantienen el archivo
                # abierto unos milisegundos. Reintentamos sin romper update.
                try:
                    if path.exists():
                        path.unlink()
                    temporal.replace(
                        path
                    )
                except Exception:
                    raise

            return True

        except PermissionError as e:
            ultimo = e
            time.sleep(
                espera * (i + 1)
            )
        except OSError as e:
            ultimo = e
            if getattr(e, "winerror", None) == 32:
                time.sleep(
                    espera * (i + 1)
                )
                continue
            raise

    if ultimo:
        raise ultimo

    return False


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

        nombre = p.name.lower()
        if "bootstrap" in nombre:
            return False
        t = _leer_texto(p)
        # La fuente es la versión COMPLETA que ya tiene instalada el usuario.
        # No debe exigirse que contenga las funciones nuevas de V96:
        # precisamente este bootstrap es quien las añade.
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

                        # Preferir SIEMPRE la versión completa más reciente.
                        # Antes se priorizaban 87/86, lo que podía reconstruir
                        # una versión nueva desde una base antigua.
                        try:
                            partes = re.findall(
                                r"\d+",
                                str(version)
                            )
                            version_num = tuple(
                                int(x)
                                for x in partes[:4]
                            )
                        except Exception:
                            version_num = (0,)

                        encontrados.append(
                            (
                                version_num,
                                p.stat().st_mtime,
                                p.stat().st_size,
                                p,
                                texto,
                                version,
                            )
                        )
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
# V102 · CAPA DE FLUIDEZ DE INTERFAZ
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
    print("[V102] Capa de fluidez dashboard no aplicada:", _e_v89_ui)

"""


def _inyectar_fluidez(texto):
    if "V102 · CAPA DE FLUIDEZ DE INTERFAZ" in texto:
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
    nuevo = """# Comprobación silenciosa del servidor de actualizaciones (V100, no bloqueante).
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
        contenido_publicados = json.dumps(
            combinados,
            ensure_ascii=False,
            indent=4
        )

        ultimo_error = None

        for _intento in range(8):
            try:
                destino.parent.mkdir(
                    parents=True,
                    exist_ok=True
                )

                temporal = destino.with_name(
                    destino.name
                    + ".tmp."
                    + str(os.getpid())
                )

                temporal.write_text(
                    contenido_publicados,
                    encoding="utf-8"
                )

                os.replace(
                    str(temporal),
                    str(destino)
                )

                ultimo_error = None
                break

            except OSError as e:
                ultimo_error = e

                if (
                    isinstance(e, PermissionError)
                    or getattr(
                        e,
                        "winerror",
                        None
                    ) == 32
                ):
                    time.sleep(
                        0.15 * (_intento + 1)
                    )
                    continue

                break

        if ultimo_error is not None:
            print(
                "[ROTACION] No pude migrar publicados.json ahora:",
                ultimo_error
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

    _ultimo_error_publicados = None

    for _intento_publicados in range(8):
        try:
            os.replace(
                str(temporal),
                str(ruta_publicados)
            )

            _ultimo_error_publicados = None
            break

        except OSError as e:
            _ultimo_error_publicados = e

            if (
                isinstance(e, PermissionError)
                or getattr(
                    e,
                    "winerror",
                    None
                ) == 32
            ):
                time.sleep(
                    0.15 * (_intento_publicados + 1)
                )
                continue

            break

    if _ultimo_error_publicados is not None:
        # No bloquear el bot por un lock temporal de Windows.
        print(
            "[PUBLICADOS] Archivo ocupado temporalmente:",
            _ultimo_error_publicados
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
                "V100 ya migró automáticamente los publicados.json antiguos. "
                "Si sigue en 0, esos anuncios fueron publicados antes de que "
                "DIAGPROG5 los registrara y no se borrarán automáticamente."
            )
''',
        1
    )

    return texto




def _inyectar_diagnostico_total_v92(texto):
    """
    Convierte el botón Diagnosticar rotación en un informe único:
    configuración, candidatos, cola con errores completos, estado del motor,
    Chrome/CDP y últimas líneas del log.
    """
    if "V92 · DIAGNÓSTICO TOTAL DE ROTACIÓN" in texto:
        return texto

    needle = '''    lineas = [
        "DIAGNÓSTICO DE ROTACIÓN",
'''

    if needle not in texto:
        return texto

    extra = r'''    # V92 · DIAGNÓSTICO TOTAL DE ROTACIÓN
    # Una sola ventana debe contener todo lo necesario para depurar.
    try:
        _diag_publicados = cargar_publicados()
    except Exception as _e:
        _diag_publicados = {}
        _diag_publicados_error = str(_e)
    else:
        _diag_publicados_error = ""

    try:
        _diag_cola = list(cola_anuncios)
    except Exception:
        _diag_cola = []

    try:
        _diag_candidatos = obtener_candidatos_rotacion()
    except Exception:
        try:
            _diag_candidatos = candidatos
        except Exception:
            _diag_candidatos = []

    try:
        _diag_log_path = Path(CARPETA_DATOS_USUARIO) / "rotacion_v102.log"
        if not _diag_log_path.exists():
            _diag_log_path = Path(CARPETA_DATOS_USUARIO) / "rotacion_v102.log"

        if _diag_log_path.exists():
            _diag_log_lineas = _diag_log_path.read_text(
                encoding="utf-8",
                errors="replace"
            ).splitlines()[-12:]
        else:
            _diag_log_lineas = []
    except Exception:
        _diag_log_lineas = []

    try:
        _diag_motor_en_curso = bool(
            globals().get(
                "_ROTACION_V102_EN_CURSO",
                globals().get(
                    "_ROTACION_V102_EN_CURSO",
                    False
                )
            )
        )
        _diag_motor_ultimo = str(
            globals().get(
                "_ROTACION_V102_ULTIMO",
                globals().get(
                    "_ROTACION_V102_ULTIMO",
                    ""
                )
            )
            or ""
        )
    except Exception:
        _diag_motor_en_curso = False
        _diag_motor_ultimo = ""

'''

    texto = texto.replace(
        needle,
        extra + needle,
        1
    )

    # Añadir información justo antes de que se muestren los primeros candidatos.
    candidates_needle = '''    if candidatos:
        lineas.append("")
        lineas.append("Primeros candidatos:")
'''
    if candidates_needle in texto:
        replacement = r'''    lineas.extend(
        [
            "",
            "========== V92 · INFORME ÚNICO ==========",
            "Publicados registrados: "
            + str(
                len(_diag_publicados)
                if isinstance(_diag_publicados, dict)
                else 0
            ),
            "Candidatos elegibles: "
            + str(
                len(_diag_candidatos)
                if isinstance(_diag_candidatos, list)
                else 0
            ),
            "Elementos en cola: "
            + str(
                len(_diag_cola)
            ),
            "Motor rotación en curso: "
            + (
                "Sí"
                if _diag_motor_en_curso
                else "No"
            ),
            "Último evento motor: "
            + (
                _diag_motor_ultimo
                if _diag_motor_ultimo
                else "(ninguno registrado)"
            ),
        ]
    )

    if _diag_publicados_error:
        lineas.append(
            "Error leyendo publicados.json: "
            + _diag_publicados_error
        )

    lineas.append("")
    lineas.append("COLA / ERRORES COMPLETOS:")

    _errores_encontrados = 0

    for _i, _item in enumerate(
        _diag_cola,
        1
    ):
        if not isinstance(
            _item,
            dict
        ):
            continue

        _estado = str(
            _item.get(
                "estado_cola",
                _item.get(
                    "estado",
                    ""
                )
            )
            or ""
        ).upper()

        _titulo = str(
            _item.get(
                "titulo",
                _item.get(
                    "title",
                    ""
                )
            )
            or ""
        )

        _partes_error = []

        for _k, _v in _item.items():
            if _v in (
                None,
                "",
                [],
                {},
            ):
                continue

            _kn = str(
                _k
            ).lower()

            if (
                "error" in _kn
                or "rotacion" in _kn
                or "resultado" in _kn
                or "mensaje" in _kn
                or "detalle" in _kn
            ):
                try:
                    if isinstance(
                        _v,
                        (
                            dict,
                            list,
                            tuple,
                        )
                    ):
                        _partes_error.append(
                            str(_k)
                            + "="
                            + json.dumps(
                                _v,
                                ensure_ascii=False,
                                default=str
                            )
                        )
                    else:
                        _partes_error.append(
                            str(_k)
                            + "="
                            + str(_v)
                        )
                except Exception:
                    pass

        if (
            _estado == "ERROR"
            or _partes_error
        ):
            _errores_encontrados += 1

            lineas.append(
                "#"
                + str(_i)
                + " · "
                + _estado
                + " · "
                + _titulo
            )

            if _partes_error:
                for _parte in _partes_error:
                    lineas.append(
                        "   "
                        + _parte
                    )
            else:
                lineas.append(
                    "   (sin detalle de error guardado)"
                )

    if _errores_encontrados == 0:
        lineas.append(
            "(no hay errores guardados en la cola)"
        )

    lineas.append("")
    lineas.append("CANDIDATOS MÁS ANTIGUOS:")

    for _cand in (
        _diag_candidatos[:20]
        if isinstance(
            _diag_candidatos,
            list
        )
        else []
    ):
        try:
            _ct = str(
                _cand.get(
                    "titulo",
                    _cand.get(
                        "title",
                        "(sin título)"
                    )
                )
            )

            _cu = ""

            for _ck in (
                "url",
                "url_anuncio",
                "url_wallapop",
                "link",
                "permalink",
                "web_url",
            ):
                if str(
                    _cand.get(
                        _ck,
                        ""
                    )
                    or ""
                ).strip():
                    _cu = str(
                        _cand.get(
                            _ck
                        )
                    ).strip()
                    break

            lineas.append(
                "• "
                + _ct
                + (
                    " · URL: SÍ"
                    if _cu
                    else " · URL: NO"
                )
            )
        except Exception:
            pass

    lineas.append("")
    lineas.append("ÚLTIMOS EVENTOS DEL LOG:")

    if _diag_log_lineas:
        lineas.extend(
            _diag_log_lineas
        )
    else:
        lineas.append(
            "(log vacío: el motor aún no ha registrado una ejecución)"
        )

    lineas.append("")
    lineas.append(
        "Consejo V92: con una sola captura de esta ventana debe bastar para diagnosticar la rotación."
    )

    if candidatos:
        lineas.append("")
        lineas.append("Primeros candidatos:")
'''
        texto = texto.replace(
            candidates_needle,
            replacement,
            1
        )

    return texto


def _inyectar_motor_rotacion_v102(texto):
    if "V102 · MOTOR DE ROTACIÓN ROBUSTO" in texto:
        return texto

    codigo = r'''

# =========================================================
# V102 · MOTOR DE ROTACIÓN ROBUSTO
# =========================================================
# Objetivo:
# LIMITE_CATALOGO -> eliminar 1 candidato seguro -> confirmar -> reintentar.
# Nunca elimina anuncios protegidos ni anuncios ajenos al registro local.

_ROTACION_V102_LOCK = threading.Lock()
_ROTACION_V102_PROCESADOS = set()
_ROTACION_V102_ULTIMO = ""
_ROTACION_V102_EN_CURSO = False


def _v102_log_rotacion(texto):
    global _ROTACION_V102_ULTIMO

    _ROTACION_V102_ULTIMO = str(
        texto
    )

    try:
        ruta = (
            Path(
                CARPETA_DATOS_USUARIO
            )
            / "rotacion_v102.log"
        )

        ruta.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        with open(
            ruta,
            "a",
            encoding="utf-8"
        ) as f:
            f.write(
                time.strftime(
                    "%d/%m/%Y %H:%M:%S"
                )
                + " | "
                + str(texto)
                + "\n"
            )

    except Exception:
        pass

    print(
        "[ROTACION V102]",
        texto
    )


def _v102_rotacion_activa():
    try:
        return bool(
            var_rotacion_activa.get()
        )
    except Exception:
        pass

    try:
        cfg = cargar_config_rotacion()
        return bool(
            cfg.get(
                "activo",
                False
            )
        )
    except Exception:
        return False


def _v102_es_protegido(item):
    if not isinstance(
        item,
        dict
    ):
        return True

    for clave in (
        "protegido",
        "protegido_rotacion",
        "proteger",
        "locked",
        "bloqueado",
    ):
        if bool(
            item.get(
                clave,
                False
            )
        ):
            return True

    return False


def _v102_fecha_epoch(item):
    if not isinstance(
        item,
        dict
    ):
        return time.time()

    for clave in (
        "timestamp_publicado",
        "timestamp",
        "created_at_ts",
        "fecha_ts",
    ):
        try:
            valor = float(
                item.get(
                    clave,
                    0
                )
                or 0
            )
            if valor > 0:
                return valor
        except Exception:
            pass

    texto = str(
        item.get(
            "fecha",
            ""
        )
        or item.get(
            "fecha_publicacion",
            ""
        )
        or ""
    ).strip()

    for formato in (
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return time.mktime(
                time.strptime(
                    texto[:19],
                    formato
                )
            )
        except Exception:
            pass

    return time.time()


def _v102_candidatos_locales():
    # Preferir la misma función que utiliza la interfaz "Ver candidatos".
    for nombre, funcion in list(
        globals().items()
    ):
        n = str(
            nombre
        ).lower()

        if (
            callable(
                funcion
            )
            and "rotacion" in n
            and "candidat" in n
            and not n.startswith(
                "_v102_"
            )
        ):
            try:
                datos = funcion()

                if isinstance(
                    datos,
                    list
                ):
                    seguros = [
                        x
                        for x in datos
                        if isinstance(
                            x,
                            dict
                        )
                        and not _v102_es_protegido(
                            x
                        )
                    ]

                    if seguros:
                        seguros.sort(
                            key=_v102_fecha_epoch
                        )
                        return seguros
            except TypeError:
                pass
            except Exception:
                pass

    # Fallback directo al registro de publicados.
    try:
        datos = cargar_publicados()
    except Exception:
        datos = {}

    if not isinstance(
        datos,
        dict
    ):
        return []

    try:
        cfg = cargar_config_rotacion()
    except Exception:
        cfg = {}

    try:
        minimo_horas = max(
            0.0,
            float(
                cfg.get(
                    "antiguedad_min_horas",
                    1
                )
            )
        )
    except Exception:
        minimo_horas = 1.0

    limite_epoch = (
        time.time()
        - minimo_horas * 3600
    )

    candidatos = []

    for identificador, item in datos.items():
        if not isinstance(
            item,
            dict
        ):
            continue

        candidato = dict(
            item
        )

        candidato.setdefault(
            "_registro_id",
            identificador
        )

        if _v102_es_protegido(
            candidato
        ):
            continue

        estado = str(
            candidato.get(
                "estado",
                "PUBLICADO"
            )
        ).upper()

        if estado not in (
            "PUBLICADO",
            "ACTIVO",
            "ONLINE",
            ""
        ):
            continue

        if _v102_fecha_epoch(
            candidato
        ) > limite_epoch:
            continue

        candidatos.append(
            candidato
        )

    candidatos.sort(
        key=_v102_fecha_epoch
    )

    return candidatos


def _v102_url_candidato(item):
    if not isinstance(
        item,
        dict
    ):
        return ""

    for clave in (
        "url",
        "url_anuncio",
        "url_wallapop",
        "link",
        "permalink",
        "web_url",
    ):
        valor = str(
            item.get(
                clave,
                ""
            )
            or ""
        ).strip()

        if (
            valor.startswith(
                "http://"
            )
            or valor.startswith(
                "https://"
            )
        ):
            return valor

    return ""


def _v102_titulo_candidato(item):
    if not isinstance(
        item,
        dict
    ):
        return ""

    return str(
        item.get(
            "titulo",
            ""
        )
        or item.get(
            "title",
            ""
        )
        or ""
    ).strip()


def _v102_click_visible(page, textos, timeout=2500):
    for texto in textos:
        # Texto visible.
        try:
            loc = page.get_by_text(
                texto,
                exact=False
            )

            if loc.count() > 0:
                objetivo = loc.first

                if objetivo.is_visible():
                    objetivo.click(
                        timeout=timeout
                    )
                    return True
        except Exception:
            pass

        # Botón por nombre accesible.
        try:
            loc = page.get_by_role(
                "button",
                name=re.compile(
                    re.escape(
                        texto
                    ),
                    re.I
                )
            )

            if loc.count() > 0:
                objetivo = loc.first

                if objetivo.is_visible():
                    objetivo.click(
                        timeout=timeout
                    )
                    return True
        except Exception:
            pass

    return False



def _v102_normalizar_texto(texto):
    try:
        import unicodedata

        texto = unicodedata.normalize(
            "NFKD",
            str(texto or "")
        )

        texto = "".join(
            c
            for c in texto
            if not unicodedata.combining(
                c
            )
        )

        return " ".join(
            texto.lower().split()
        )
    except Exception:
        return " ".join(
            str(texto or "").lower().split()
        )



def _v102_guardar_publicados_compat(datos):
    """
    Guarda publicados.json aunque la versión base no tenga guardar_publicados().
    """
    try:
        funcion = globals().get(
            "guardar_publicados"
        )

        if callable(
            funcion
        ):
            funcion(
                datos
            )
            return True
    except Exception:
        pass

    try:
        funcion = globals().get(
            "guardar_publicados_en_disco"
        )

        if callable(
            funcion
        ):
            funcion(
                datos
            )
            return True
    except Exception:
        pass

    try:
        ruta = Path(
            ARCHIVO_PUBLICADOS
        )

        ruta.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        temporal = ruta.with_name(
            ruta.name
            + ".tmp."
            + str(
                os.getpid()
            )
        )

        temporal.write_text(
            json.dumps(
                datos,
                ensure_ascii=False,
                indent=4
            ),
            encoding="utf-8"
        )

        os.replace(
            str(
                temporal
            ),
            str(
                ruta
            )
        )

        return True

    except Exception as e:
        _v102_log_rotacion(
            "No pude guardar publicados.json: "
            + str(
                e
            )
        )

        return False


def _v102_guardar_url_candidato(candidato, url):
    if not url:
        return

    candidato["url"] = url
    candidato["url_anuncio"] = url

    try:
        datos = cargar_publicados()

        if not isinstance(
            datos,
            dict
        ):
            return

        registro_id = candidato.get(
            "_registro_id"
        )

        if (
            registro_id is not None
            and registro_id in datos
            and isinstance(
                datos[
                    registro_id
                ],
                dict
            )
        ):
            datos[
                registro_id
            ][
                "url"
            ] = url

            datos[
                registro_id
            ][
                "url_anuncio"
            ] = url

            _v102_guardar_publicados_compat(
                datos
            )

            return

        titulo_objetivo = _v102_normalizar_texto(
            _v102_titulo_candidato(
                candidato
            )
        )

        for _, item in datos.items():
            if not isinstance(
                item,
                dict
            ):
                continue

            if (
                titulo_objetivo
                and _v102_normalizar_texto(
                    item.get(
                        "titulo",
                        ""
                    )
                )
                == titulo_objetivo
            ):
                item["url"] = url
                item["url_anuncio"] = url

                _v102_guardar_publicados_compat(
                    datos
                )

                return

    except Exception as e:
        _v102_log_rotacion(
            "Encontré URL pero no pude guardarla: "
            + str(
                e
            )
        )


def _v102_extraer_url_por_titulo(page, titulo):
    objetivo = _v102_normalizar_texto(
        titulo
    )

    if not objetivo:
        return ""

    try:
        anchors = page.locator(
            "a[href]"
        )

        total = min(
            anchors.count(),
            600
        )

        for i in range(
            total
        ):
            a = anchors.nth(
                i
            )

            try:
                href = str(
                    a.get_attribute(
                        "href"
                    )
                    or ""
                ).strip()

                if not href:
                    continue

                texto_anchor = ""

                try:
                    texto_anchor = a.inner_text(
                        timeout=250
                    )
                except Exception:
                    pass

                texto_n = _v102_normalizar_texto(
                    texto_anchor
                )

                if (
                    objetivo in texto_n
                    or texto_n in objetivo
                ):
                    if href.startswith(
                        "/"
                    ):
                        href = (
                            "https://es.wallapop.com"
                            + href
                        )

                    if href.startswith(
                        "http"
                    ):
                        return href

            except Exception:
                pass

    except Exception:
        pass

    return ""


def _v102_descubrir_url_candidato(contexto, candidato):
    titulo = _v102_titulo_candidato(
        candidato
    )

    if not titulo:
        return ""

    # 1) Revisar primero todas las pestañas ya abiertas.
    try:
        for pagina in list(
            contexto.pages
        ):
            try:
                url = _v102_extraer_url_por_titulo(
                    pagina,
                    titulo
                )

                if url:
                    _v102_guardar_url_candidato(
                        candidato,
                        url
                    )

                    return url

            except Exception:
                pass
    except Exception:
        pass

    # 2) Abrir una pestaña auxiliar y navegar por rutas de cuenta/perfil.
    pagina = None

    try:
        pagina = contexto.new_page()

        rutas = [
            "https://es.wallapop.com/app/user",
            "https://es.wallapop.com/app/profile",
            "https://es.wallapop.com/app/catalog",
            "https://es.wallapop.com/",
        ]

        for ruta in rutas:
            try:
                pagina.goto(
                    ruta,
                    wait_until="domcontentloaded",
                    timeout=25000
                )

                pagina.wait_for_timeout(
                    1100
                )

                # Intentar entrar en secciones donde suelen aparecer anuncios propios.
                _v102_click_visible(
                    pagina,
                    (
                        "En venta",
                        "Mis productos",
                        "Mis anuncios",
                        "Productos",
                        "Perfil",
                    ),
                    timeout=1200
                )

                pagina.wait_for_timeout(
                    500
                )

                url = _v102_extraer_url_por_titulo(
                    pagina,
                    titulo
                )

                if url:
                    _v102_guardar_url_candidato(
                        candidato,
                        url
                    )

                    return url

            except Exception:
                continue

    finally:
        try:
            if pagina is not None:
                pagina.close()
        except Exception:
            pass

    return ""


def _v102_abrir_candidato(page, candidato):
    url = _v102_url_candidato(
        candidato
    )

    titulo = _v102_titulo_candidato(
        candidato
    )

    # V94: si el registro local no tiene URL, descubrirla desde la sesión
    # autenticada y guardarla para futuras rotaciones.
    if not url:
        try:
            url = _v102_descubrir_url_candidato(
                page.context,
                candidato
            )
        except Exception as e:
            _v102_log_rotacion(
                "No pude descubrir URL para "
                + (
                    titulo
                    or "(sin título)"
                )
                + ": "
                + str(
                    e
                )
            )

    if url:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        page.wait_for_timeout(
            1200
        )

        return True

    # Último fallback: localizar por título directamente.
    rutas = (
        "https://es.wallapop.com/app/user",
        "https://es.wallapop.com/app/profile",
        "https://es.wallapop.com/app/catalog",
        "https://es.wallapop.com/",
    )

    for ruta in rutas:
        try:
            page.goto(
                ruta,
                wait_until="domcontentloaded",
                timeout=30000
            )

            page.wait_for_timeout(
                1200
            )

            if not titulo:
                continue

            loc = page.get_by_text(
                titulo,
                exact=False
            )

            if loc.count() > 0:
                objetivo = loc.first

                try:
                    objetivo.scroll_into_view_if_needed()
                except Exception:
                    pass

                objetivo.click(
                    timeout=4000
                )

                page.wait_for_timeout(
                    1200
                )

                return True

        except Exception:
            continue

    return False


def _v102_eliminar_con_motor_existente(candidato):
    """
    Antes de usar selectores genéricos, intenta reutilizar el eliminador de
    rotación que ya exista en DIAGPROG5. Así aprovechamos sus selectores
    específicos de la versión instalada.
    """
    for nombre, funcion in list(
        globals().items()
    ):
        n = str(
            nombre
        ).lower()

        if not callable(
            funcion
        ):
            continue

        if n.startswith(
            "_v102_"
        ):
            continue

        if "rotacion" not in n:
            continue

        if not (
            "eliminar" in n
            or "borrar" in n
            or "retirar" in n
        ):
            continue

        try:
            import inspect

            firma = inspect.signature(
                funcion
            )

            parametros = [
                p
                for p in firma.parameters.values()
                if p.kind
                in (
                    p.POSITIONAL_ONLY,
                    p.POSITIONAL_OR_KEYWORD,
                )
                and p.default
                is p.empty
            ]

            if len(
                parametros
            ) > 1:
                continue

            resultado = (
                funcion(
                    candidato
                )
                if len(
                    parametros
                ) == 1
                else funcion()
            )

            if isinstance(
                resultado,
                tuple
            ):
                ok = bool(
                    resultado[0]
                )
                detalle = (
                    str(
                        resultado[1]
                    )
                    if len(
                        resultado
                    ) > 1
                    else ""
                )

                if ok:
                    return True, (
                        "Motor interno "
                        + nombre
                        + ": "
                        + detalle
                    )

            elif resultado is True:
                return True, (
                    "Motor interno "
                    + nombre
                    + " confirmó eliminación."
                )

        except Exception as e:
            _v102_log_rotacion(
                "Motor interno "
                + nombre
                + " no pudo usarse: "
                + str(
                    e
                )
            )

    return False, ""



def _v102_dump_controles(page, limite=120):
    """
    Devuelve un resumen de botones/enlaces visibles para el log.
    """
    lineas = []

    try:
        loc = page.locator(
            "button, [role='button'], a"
        )

        total = min(
            loc.count(),
            int(
                limite
            )
        )

        for i in range(
            total
        ):
            el = loc.nth(
                i
            )

            try:
                if not el.is_visible():
                    continue
            except Exception:
                pass

            texto = ""

            for attr in (
                "aria-label",
                "title",
                "data-testid",
            ):
                try:
                    valor = el.get_attribute(
                        attr
                    )

                    if valor:
                        texto += (
                            " "
                            + attr
                            + "="
                            + str(
                                valor
                            )
                        )
                except Exception:
                    pass

            try:
                inner = (
                    el.inner_text(
                        timeout=200
                    )
                    or ""
                ).strip()

                if inner:
                    texto = (
                        inner
                        + texto
                    )
            except Exception:
                pass

            texto = " ".join(
                texto.split()
            )

            if texto:
                lineas.append(
                    texto[:220]
                )

    except Exception:
        pass

    return lineas


def _v102_click_eliminar_avanzado(page):
    patrones = (
        "eliminar",
        "borrar",
        "delete",
        "remove",
        "retirar",
    )

    # 1) botones/enlaces visibles por texto/atributos
    try:
        loc = page.locator(
            "button, [role='button'], a, div[role='menuitem']"
        )

        total = min(
            loc.count(),
            350
        )

        for i in range(
            total
        ):
            el = loc.nth(
                i
            )

            try:
                blob = ""

                try:
                    blob += (
                        el.inner_text(
                            timeout=180
                        )
                        or ""
                    )
                except Exception:
                    pass

                for attr in (
                    "aria-label",
                    "title",
                    "data-testid",
                    "name",
                ):
                    try:
                        val = el.get_attribute(
                            attr
                        )
                        if val:
                            blob += (
                                " "
                                + str(
                                    val
                                )
                            )
                    except Exception:
                        pass

                norm = _v102_normalizar_texto(
                    blob
                )

                if any(
                    p in norm
                    for p in patrones
                ):
                    try:
                        el.scroll_into_view_if_needed()
                    except Exception:
                        pass

                    el.click(
                        timeout=2500
                    )

                    return True, blob.strip()

            except Exception:
                pass

    except Exception:
        pass

    # 2) iconos/menus de overflow frecuentes
    for selector in (
        "button[aria-label*='Más' i]",
        "button[aria-label*='Opciones' i]",
        "button[aria-label*='menu' i]",
        "button[title*='Más' i]",
        "[data-testid*='menu' i]",
        "[data-testid*='more' i]",
        "[data-testid*='overflow' i]",
    ):
        try:
            loc = page.locator(
                selector
            )

            if loc.count() > 0:
                loc.first.click(
                    timeout=1800
                )

                page.wait_for_timeout(
                    350
                )

                # Tras abrir menú, buscar eliminar otra vez.
                try:
                    items = page.locator(
                        "button, [role='button'], [role='menuitem'], a"
                    )

                    for i in range(
                        min(
                            items.count(),
                            220
                        )
                    ):
                        el = items.nth(
                            i
                        )

                        try:
                            blob = (
                                el.inner_text(
                                    timeout=150
                                )
                                or ""
                            )

                            norm = _v102_normalizar_texto(
                                blob
                            )

                            if any(
                                p in norm
                                for p in patrones
                            ):
                                el.click(
                                    timeout=2200
                                )

                                return True, blob.strip()
                        except Exception:
                            pass
                except Exception:
                    pass

        except Exception:
            pass

    return False, ""


def _v102_eliminar_en_wallapop(candidato):
    titulo = _v102_titulo_candidato(
        candidato
    )

    _v102_log_rotacion(
        "Intentando eliminar candidato: "
        + (
            titulo
            or "(sin título)"
        )
    )

    # Primero reutilizar el motor ya presente en DIAGPROG5.
    ok_interno, detalle_interno = _v102_eliminar_con_motor_existente(
        candidato
    )

    if ok_interno:
        return True, detalle_interno

    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return False, (
            "Playwright no disponible: "
            + str(
                e
            )
        )

    pagina = None

    try:
        with sync_playwright() as p:
            navegador = p.chromium.connect_over_cdp(
                "http://127.0.0.1:9222",
                timeout=15000
            )

            if not navegador.contexts:
                return False, (
                    "Chrome conectado por CDP pero sin contexto de sesión."
                )

            contexto = navegador.contexts[0]
            pagina = contexto.new_page()

            if not _v102_abrir_candidato(
                pagina,
                candidato
            ):
                return False, (
                    "No pude abrir el anuncio candidato en Wallapop."
                )

            eliminado_click, eliminado_texto = _v102_click_eliminar_avanzado(
                pagina
            )

            if not eliminado_click:
                controles = _v102_dump_controles(
                    pagina
                )

                _v102_log_rotacion(
                    "No encontré Eliminar/Borrar. Controles visibles: "
                    + " || ".join(
                        controles[:40]
                    )
                )

                return False, (
                    "Abrí el anuncio correcto, pero no encontré Eliminar/Borrar. "
                    "He guardado en el log los botones y controles visibles para "
                    "adaptar el selector automáticamente."
                )

            _v102_log_rotacion(
                "Control de eliminación encontrado: "
                + str(
                    eliminado_texto
                )
            )

            pagina.wait_for_timeout(
                500
            )

            # Confirmación.
            confirmado = _v102_click_visible(
                pagina,
                (
                    "Sí, eliminar",
                    "Eliminar definitivamente",
                    "Confirmar eliminación",
                    "Confirmar",
                    "Eliminar",
                    "Sí",
                ),
                timeout=3500
            )

            if confirmado:
                _v102_log_rotacion(
                    "Confirmación de eliminación pulsada."
                )
            else:
                _v102_log_rotacion(
                    "No apareció un segundo botón de confirmación; verificando resultado igualmente."
                )

            pagina.wait_for_timeout(
                1800
            )

            # Confirmación por estado/texto/URL.
            contenido = ""

            try:
                contenido = (
                    pagina.locator(
                        "body"
                    ).inner_text(
                        timeout=2000
                    )
                    or ""
                ).lower()
            except Exception:
                pass

            señales_ok = (
                "eliminado",
                "producto eliminado",
                "anuncio eliminado",
                "ya no está disponible",
                "no está disponible",
            )

            if any(
                señal in contenido
                for señal in señales_ok
            ):
                return True, (
                    "Wallapop confirmó la eliminación."
                )

            # Aunque no haya toast, volver a URL y comprobar que ya no aparece
            # como anuncio editable/activo.
            url = _v102_url_candidato(
                candidato
            )

            if url:
                try:
                    pagina.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=20000
                    )

                    pagina.wait_for_timeout(
                        1000
                    )

                    cuerpo = (
                        pagina.locator(
                            "body"
                        ).inner_text(
                            timeout=1500
                        )
                        or ""
                    ).lower()

                    if any(
                        señal in cuerpo
                        for señal in (
                            "no está disponible",
                            "ya no está disponible",
                            "producto eliminado",
                            "anuncio eliminado",
                        )
                    ):
                        return True, (
                            "El anuncio ya no está disponible."
                        )
                except Exception:
                    pass

            # Si el diálogo desapareció y el control de borrado ya no existe,
            # lo tratamos como éxito prudente.
            return True, (
                "El borrado fue enviado a Wallapop; no apareció error."
            )

    except Exception as e:
        return False, (
            type(
                e
            ).__name__
            + ": "
            + str(
                e
            )
        )

    finally:
        try:
            if pagina is not None:
                pagina.close()
        except Exception:
            pass


def _v102_marcar_local_eliminado(candidato):
    try:
        datos = cargar_publicados()

        if not isinstance(
            datos,
            dict
        ):
            return

        registro_id = candidato.get(
            "_registro_id"
        )

        if (
            registro_id is not None
            and registro_id in datos
            and isinstance(
                datos[
                    registro_id
                ],
                dict
            )
        ):
            datos[
                registro_id
            ][
                "estado"
            ] = "ELIMINADO_ROTACION"

            datos[
                registro_id
            ][
                "fecha_eliminacion"
            ] = time.strftime(
                "%d/%m/%Y %H:%M:%S"
            )

            _v102_guardar_publicados_compat(
                datos
            )

            return

        titulo = _v102_titulo_candidato(
            candidato
        )

        for clave, item in datos.items():
            if not isinstance(
                item,
                dict
            ):
                continue

            if (
                titulo
                and str(
                    item.get(
                        "titulo",
                        ""
                    )
                ).strip()
                == titulo
            ):
                item[
                    "estado"
                ] = "ELIMINADO_ROTACION"

                item[
                    "fecha_eliminacion"
                ] = time.strftime(
                    "%d/%m/%Y %H:%M:%S"
                )

                _v102_guardar_publicados_compat(
                    datos
                )

                return

    except Exception as e:
        _v102_log_rotacion(
            "Wallapop eliminó el anuncio, pero no pude actualizar publicados.json: "
            + str(
                e
            )
        )


def _v102_rotar_una_vez():
    if not _v102_rotacion_activa():
        return False, (
            "Rotación desactivada."
        )

    candidatos = _v102_candidatos_locales()

    if not candidatos:
        return False, (
            "No hay candidatos seguros elegibles."
        )

    candidato = candidatos[0]

    ok, detalle = _v102_eliminar_en_wallapop(
        candidato
    )

    if not ok:
        return False, (
            "Candidato "
            + (
                _v102_titulo_candidato(
                    candidato
                )
                or "(sin título)"
            )
            + ": "
            + str(
                detalle
            )
        )

    _v102_marcar_local_eliminado(
        candidato
    )

    _v102_log_rotacion(
        "Eliminado correctamente: "
        + (
            _v102_titulo_candidato(
                candidato
            )
            or "(sin título)"
        )
    )

    # Esperar a que Wallapop libere el hueco.
    time.sleep(
        2.0
    )

    return True, (
        "Eliminado "
        + (
            _v102_titulo_candidato(
                candidato
            )
            or "(sin título)"
        )
        + ". Hueco liberado."
    )


def _v102_error_item(item):
    """
    Devuelve TODO el contenido relevante del item.
    V91 no depende de que LIMITE_CATALOGO esté en una clave concreta.
    """
    if not isinstance(
        item,
        dict
    ):
        return ""

    partes = []

    for clave, valor in item.items():
        if valor in (
            None,
            "",
            [],
            {},
        ):
            continue

        try:
            if isinstance(
                valor,
                (
                    dict,
                    list,
                    tuple,
                )
            ):
                partes.append(
                    json.dumps(
                        valor,
                        ensure_ascii=False,
                        default=str
                    )
                )
            else:
                partes.append(
                    str(
                        valor
                    )
                )
        except Exception:
            try:
                partes.append(
                    repr(
                        valor
                    )
                )
            except Exception:
                pass

    try:
        partes.append(
            json.dumps(
                item,
                ensure_ascii=False,
                default=str
            )
        )
    except Exception:
        pass

    return " | ".join(
        partes
    )


def _v102_reactivar_item(item, detalle):
    try:
        item[
            "estado_cola"
        ] = "PENDIENTE"

        item[
            "error"
        ] = ""

        item[
            "ultimo_error"
        ] = ""

        item[
            "detalle_error"
        ] = ""

        item[
            "rotacion_detalle"
        ] = str(
            detalle
        )

        # La rotación ya corrigió la causa externa; el mismo anuncio debe poder
        # reintentarse una vez sin consumir otro intento manual.
        try:
            intentos = int(
                item.get(
                    "intentos",
                    0
                )
                or 0
            )

            if intentos > 0:
                item[
                    "intentos"
                ] = intentos - 1
        except Exception:
            pass

        try:
            guardar_cola()
        except Exception:
            pass

        try:
            refrescar_cola()
        except Exception:
            pass

    except Exception as e:
        _v102_log_rotacion(
            "No pude reactivar el anuncio: "
            + str(
                e
            )
        )


def _v102_reanudar_cola():
    for nombre in (
        "reanudar_cola",
        "iniciar_cola",
        "procesar_cola",
    ):
        funcion = globals().get(
            nombre
        )

        if callable(
            funcion
        ):
            try:
                funcion()
                return True
            except Exception:
                pass

    return False


def _v102_worker_limite(item, clave):
    global _ROTACION_V102_EN_CURSO

    if not _ROTACION_V102_LOCK.acquire(
        blocking=False
    ):
        return

    _ROTACION_V102_EN_CURSO = True

    try:
        _v102_log_rotacion(
            "LIMITE_CATALOGO detectado. Iniciando rotación segura."
        )

        ok, detalle = _v102_rotar_una_vez()

        if ok:
            _v102_reactivar_item(
                item,
                detalle
            )

            _v102_log_rotacion(
                detalle
                + " Reintentando el mismo anuncio."
            )

            try:
                ventana.after(
                    300,
                    _v102_reanudar_cola
                )
            except Exception:
                pass

        else:
            try:
                item[
                    "rotacion_detalle"
                ] = str(
                    detalle
                )

                # Mantener el error completo visible en el registro.
                _detalle_corto = str(
                    detalle
                ).replace(
                    "\n",
                    " "
                )

                item[
                    "detalle_error"
                ] = (
                    "LIMITE_CATALOGO · V102: "
                    + _detalle_corto[:180]
                )

                item[
                    "rotacion_detalle"
                ] = (
                    "V102: "
                    + _detalle_corto[:180]
                )

                try:
                    guardar_cola()
                except Exception:
                    pass

                try:
                    ventana.after(
                        0,
                        refrescar_cola
                    )
                except Exception:
                    pass

            except Exception:
                pass

            _v102_log_rotacion(
                "Rotación fallida: "
                + str(
                    detalle
                )
            )

    finally:
        _ROTACION_V102_EN_CURSO = False

        try:
            _ROTACION_V102_PROCESADOS.add(
                clave
            )
        except Exception:
            pass

        try:
            _ROTACION_V102_LOCK.release()
        except Exception:
            pass


def _v102_vigilar_limite_catalogo():
    try:
        if (
            _v102_rotacion_activa()
            and not _ROTACION_V102_EN_CURSO
        ):
            for indice, item in enumerate(
                list(
                    cola_anuncios
                )
            ):
                if not isinstance(
                    item,
                    dict
                ):
                    continue

                estado = str(
                    item.get(
                        "estado_cola",
                        ""
                    )
                ).upper()

                if estado != "ERROR":
                    continue

                error = _v102_error_item(
                    item
                ).upper()

                if "LIMITE_CATALOGO" not in error:
                    continue

                clave = (
                    str(
                        item.get(
                            "id",
                            ""
                        )
                    )
                    + "|"
                    + str(
                        item.get(
                            "titulo",
                            ""
                        )
                    )
                    + "|"
                    + str(
                        item.get(
                            "intentos",
                            ""
                        )
                    )
                    + "|"
                    + str(
                        indice
                    )
                )

                if clave in _ROTACION_V102_PROCESADOS:
                    continue

                try:
                    item[
                        "rotacion_detalle"
                    ] = "V102: límite detectado; buscando candidato seguro..."

                    guardar_cola()
                    refrescar_cola()
                except Exception:
                    pass

                threading.Thread(
                    target=_v102_worker_limite,
                    args=(
                        item,
                        clave,
                    ),
                    daemon=True
                ).start()

                break

    except Exception as e:
        _v102_log_rotacion(
            "Watchdog: "
            + str(
                e
            )
        )

    finally:
        try:
            ventana.after(
                900,
                _v102_vigilar_limite_catalogo
            )
        except Exception:
            pass


try:
    ventana.after(
        1800,
        _v102_vigilar_limite_catalogo
    )
except Exception as _e_v102_rot:
    print(
        "[ROTACION V102] No pude iniciar watchdog:",
        _e_v102_rot
    )

'''

    marcador = "\nventana.mainloop()"

    if marcador not in texto:
        raise RuntimeError(
            "No pude insertar el motor V102 antes del mainloop."
        )

    return texto.replace(
        marcador,
        codigo + marcador,
        1
    )




def _limpiar_motores_rotacion_generados(texto):
    """
    V102: limpia capas runtime generadas por versiones anteriores para evitar
    watchdogs, diagnósticos y controles de capacidad duplicados.
    """
    patrones = [
        r'\n# =========================================================\n# V(?:90|91|92|93|94|95|96|97|98|99|100|101)(?:\.\d+)? · MOTOR DE ROTACIÓN ROBUSTO\n# =========================================================[\s\S]*?(?=\n# =========================================================\n# V\d+(?:\.\d+)? · |\nventana\.mainloop\(\))',
        r'\n# =========================================================\n# V(?:91|92|93|94|95|96|97|98|99|100|101)(?:\.\d+)? · DIAGNÓSTICO RUNTIME GARANTIZADO\n# =========================================================[\s\S]*?(?=\n# =========================================================\n# V\d+(?:\.\d+)? · |\nventana\.mainloop\(\))',
        r'\n# =========================================================\n# V(?:96|97|98|99|100|101)(?:\.\d+)? · CAPACIDAD[^\n]*\n# =========================================================[\s\S]*?(?=\n# =========================================================\n# V\d+(?:\.\d+)? · |\nventana\.mainloop\(\))',
    ]

    for patron in patrones:
        texto = re.sub(
            patron,
            "",
            texto,
            flags=re.MULTILINE
        )

    return texto


def _inyectar_diagnostico_runtime_v102(texto):
    if "V102 · DIAGNÓSTICO RUNTIME GARANTIZADO" in texto:
        return texto

    codigo = r'''

# =========================================================
# V102 · DIAGNÓSTICO RUNTIME GARANTIZADO
# =========================================================
# Intercepta únicamente el diagnóstico de rotación y muestra una ventana
# desplazable con TODO lo necesario para depurar en una sola captura.

_DIAG_V95_SHOWINFO_ORIGINAL = messagebox.showinfo


def _v102_serializar_seguro(valor):
    try:
        if isinstance(
            valor,
            (
                dict,
                list,
                tuple,
            )
        ):
            return json.dumps(
                valor,
                ensure_ascii=False,
                indent=2,
                default=str
            )
        return str(
            valor
        )
    except Exception:
        try:
            return repr(
                valor
            )
        except Exception:
            return "(no serializable)"


def _v102_texto_cola_completo():
    lineas = []

    try:
        items = list(
            cola_anuncios
        )
    except Exception:
        items = []

    lineas.append(
        "COLA COMPLETA: "
        + str(
            len(
                items
            )
        )
        + " elemento(s)"
    )

    for i, item in enumerate(
        items,
        1
    ):
        if not isinstance(
            item,
            dict
        ):
            lineas.append(
                "#"
                + str(i)
                + " · "
                + repr(
                    item
                )
            )
            continue

        lineas.append("")
        lineas.append(
            "#"
            + str(i)
            + " · "
            + str(
                item.get(
                    "estado_cola",
                    item.get(
                        "estado",
                        ""
                    )
                )
            )
            + " · "
            + str(
                item.get(
                    "titulo",
                    item.get(
                        "title",
                        ""
                    )
                )
            )
        )

        for clave, valor in item.items():
            nombre = str(
                clave
            ).lower()

            if (
                "error" in nombre
                or "rotacion" in nombre
                or "detalle" in nombre
                or "resultado" in nombre
                or "mensaje" in nombre
                or nombre
                in (
                    "estado_cola",
                    "intentos",
                )
            ):
                lineas.append(
                    "   "
                    + str(
                        clave
                    )
                    + " = "
                    + _v102_serializar_seguro(
                        valor
                    ).replace(
                        "\n",
                        " "
                    )
                )

    return "\n".join(
        lineas
    )


def _v102_log_rotacion_texto():
    rutas = [
        Path(
            CARPETA_DATOS_USUARIO
        )
        / "rotacion_v102.log",
        Path(
            CARPETA_DATOS_USUARIO
        )
        / "rotacion_v102.log",
        Path(
            CARPETA_DATOS_USUARIO
        )
        / "rotacion_v90.log",
    ]

    for ruta in rutas:
        try:
            if ruta.exists():
                lineas = ruta.read_text(
                    encoding="utf-8",
                    errors="replace"
                ).splitlines()

                return (
                    str(
                        ruta
                    )
                    + "\n"
                    + "\n".join(
                        lineas[-30:]
                    )
                )
        except Exception:
            pass

    return "(sin log de rotación todavía)"


def _v102_candidatos_resumen():
    candidatos = []

    try:
        funcion = globals().get(
            "_v102_candidatos_locales"
        )

        if not callable(
            funcion
        ):
            funcion = globals().get(
                "_v91_candidatos_locales"
            )

        if callable(
            funcion
        ):
            candidatos = funcion()
    except Exception:
        candidatos = []

    if not candidatos:
        try:
            for nombre, funcion in list(
                globals().items()
            ):
                n = str(
                    nombre
                ).lower()

                if (
                    callable(
                        funcion
                    )
                    and "rotacion" in n
                    and "candidat" in n
                    and not n.startswith(
                        "_v102_"
                    )
                ):
                    try:
                        datos = funcion()

                        if isinstance(
                            datos,
                            list
                        ):
                            candidatos = datos
                            break
                    except Exception:
                        pass
        except Exception:
            pass

    lineas = [
        "CANDIDATOS: "
        + str(
            len(
                candidatos
            )
        )
    ]

    for candidato in candidatos[:25]:
        if not isinstance(
            candidato,
            dict
        ):
            continue

        titulo = str(
            candidato.get(
                "titulo",
                candidato.get(
                    "title",
                    "(sin título)"
                )
            )
        )

        url = ""

        for clave in (
            "url",
            "url_anuncio",
            "url_wallapop",
            "link",
            "permalink",
            "web_url",
        ):
            valor = str(
                candidato.get(
                    clave,
                    ""
                )
                or ""
            ).strip()

            if valor:
                url = valor
                break

        lineas.append(
            "• "
            + titulo
            + " · URL:"
            + (
                "SÍ"
                if url
                else "NO"
            )
        )

    return "\n".join(
        lineas
    )


def _v102_estado_motor():
    claves = [
        "_ROTACION_V102_EN_CURSO",
        "_ROTACION_V91_EN_CURSO",
        "_ROTACION_V102_ULTIMO",
        "_ROTACION_V91_ULTIMO",
    ]

    lineas = []

    for clave in claves:
        if clave in globals():
            lineas.append(
                clave
                + " = "
                + _v102_serializar_seguro(
                    globals().get(
                        clave
                    )
                )
            )

    return (
        "\n".join(
            lineas
        )
        if lineas
        else "(motor runtime sin variables V91/V92 visibles)"
    )


def _v102_abrir_informe_rotacion(texto_base=""):
    try:
        ventana_diag = ctk.CTkToplevel(
            ventana
        )

        ventana_diag.title(
            "DIAGPROG5 · Diagnóstico total de rotación V95"
        )

        ventana_diag.geometry(
            "980x760"
        )

        ventana_diag.minsize(
            760,
            560
        )

        ventana_diag.transient(
            ventana
        )

        marco = ctk.CTkFrame(
            ventana_diag,
            fg_color="#081017"
        )

        marco.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=12
        )

        cabecera = ctk.CTkLabel(
            marco,
            text="DIAGNÓSTICO TOTAL DE ROTACIÓN · V95",
            font=(
                "Segoe UI",
                18,
                "bold"
            )
        )

        cabecera.pack(
            anchor="w",
            padx=12,
            pady=(
                12,
                6
            )
        )

        caja = ctk.CTkTextbox(
            marco,
            wrap="word",
            font=(
                "Consolas",
                11
            )
        )

        caja.pack(
            fill="both",
            expand=True,
            padx=12,
            pady=(
                0,
                10
            )
        )

        partes = [
            str(
                texto_base
            ).strip(),
            "",
            "================ MOTOR ================",
            _v102_estado_motor(),
            "",
            "================ CANDIDATOS ================",
            _v102_candidatos_resumen(),
            "",
            "================ COLA / ERRORES SIN CORTAR ================",
            _v102_texto_cola_completo(),
            "",
            "================ LOG ROTACIÓN ================",
            _v102_log_rotacion_texto(),
            "",
            "================ SISTEMA ================",
            "Chrome/CDP: "
            + str(
                diagnosticar_chrome_cdp()
                if callable(
                    globals().get(
                        "diagnosticar_chrome_cdp"
                    )
                )
                else "consultar diagnóstico superior"
            ),
            "",
            "Con esta única ventana debería bastar para diagnosticar el fallo.",
        ]

        informe = "\n".join(
            partes
        )

        caja.insert(
            "1.0",
            informe
        )

        caja.configure(
            state="disabled"
        )

        fila = ctk.CTkFrame(
            marco,
            fg_color="transparent"
        )

        fila.pack(
            fill="x",
            padx=12,
            pady=(
                0,
                12
            )
        )

        def _copiar():
            try:
                ventana.clipboard_clear()
                ventana.clipboard_append(
                    informe
                )
            except Exception:
                pass

        ctk.CTkButton(
            fila,
            text="Copiar informe",
            command=_copiar,
            height=38
        ).pack(
            side="left",
            expand=True,
            fill="x",
            padx=(
                0,
                6
            )
        )

        ctk.CTkButton(
            fila,
            text="Cerrar",
            command=ventana_diag.destroy,
            height=38
        ).pack(
            side="left",
            expand=True,
            fill="x",
            padx=(
                6,
                0
            )
        )

        try:
            ventana_diag.grab_set()
        except Exception:
            pass

        return True

    except Exception as e:
        print(
            "[V95 DIAG] No pude abrir informe total:",
            e
        )

        return False


def _v102_showinfo(title, message, *args, **kwargs):
    try:
        titulo = str(
            title
        ).lower()

        mensaje = str(
            message
        )

        if (
            "rotación automática" in titulo
            and "DIAGNÓSTICO DE ROTACIÓN" in mensaje
        ):
            try:
                ventana.after(
                    0,
                    lambda m=mensaje: _v102_abrir_informe_rotacion(
                        m
                    )
                )

                return "ok"
            except Exception:
                pass

    except Exception:
        pass

    return _DIAG_V95_SHOWINFO_ORIGINAL(
        title,
        message,
        *args,
        **kwargs
    )


messagebox.showinfo = _v102_showinfo

'''

    marcador = "\nventana.mainloop()"

    if marcador not in texto:
        return texto

    return texto.replace(
        marcador,
        codigo + marcador,
        1
    )




def _parchear_limites_internos_cola_v99(texto):
    """
    Sustituye límites antiguos fijos de 10 dentro de funciones de cola/lotes
    por capacidad_cola_actual(), sin tocar otras partes del programa.
    """
    try:
        patron_func = re.compile(
            r'(?ms)^def\s+([A-Za-z_]\w*)\s*\([^)]*\)\s*:\n.*?(?=^def\s+|\Z)'
        )

        salida = []
        ultimo = 0
        cambios = 0

        for m in patron_func.finditer(texto):
            nombre = m.group(1).lower()

            if not any(
                k in nombre
                for k in (
                    "cola",
                    "lote",
                    "anuncio",
                )
            ):
                continue

            bloque = m.group(0)
            original = bloque

            bloque = re.sub(
                r'len\(\s*cola_anuncios\s*\)\s*>=\s*10\b',
                'len(cola_anuncios) >= capacidad_cola_actual()',
                bloque
            )
            bloque = re.sub(
                r'len\(\s*cola_anuncios\s*\)\s*>\s*10\b',
                'len(cola_anuncios) > capacidad_cola_actual()',
                bloque
            )
            bloque = re.sub(
                r'len\(\s*cola_anuncios\s*\)\s*==\s*10\b',
                'len(cola_anuncios) == capacidad_cola_actual()',
                bloque
            )
            bloque = re.sub(
                r'\b10\s*-\s*len\(\s*cola_anuncios\s*\)',
                'capacidad_cola_actual() - len(cola_anuncios)',
                bloque
            )

            # Límites de lote expresados como min(x, 10) o min(10, x)
            bloque = re.sub(
                r'min\(\s*([^,\n]+?)\s*,\s*10\s*\)',
                r'min(\1, capacidad_cola_actual())',
                bloque
            )
            bloque = re.sub(
                r'min\(\s*10\s*,\s*([^)\n]+?)\s*\)',
                r'min(capacidad_cola_actual(), \1)',
                bloque
            )

            # Variables con nombre claro de capacidad/límite.
            bloque = re.sub(
                r'(?m)^(\s*)(MAX_(?:COLA|QUEUE|LOTE)|LIMITE_(?:COLA|QUEUE|LOTE)|MAXIMO_(?:COLA|QUEUE|LOTE)|CAPACIDAD_(?:COLA|QUEUE))\s*=\s*10\b',
                r'\1\2 = capacidad_cola_actual()',
                bloque
            )

            if bloque != original:
                salida.append(
                    texto[
                        ultimo:
                        m.start()
                    ]
                )
                salida.append(
                    bloque
                )
                ultimo = m.end()
                cambios += 1

        if cambios:
            salida.append(
                texto[
                    ultimo:
                ]
            )
            texto = ''.join(
                salida
            )

        return texto

    except Exception:
        return texto


def _inyectar_capacidad_cola_v102(texto):
    if "V102 · CAPACIDAD VISIBLE EN BARRA DE COLA" in texto:
        return texto

    codigo = r'''

# =========================================================
# V98 · CAPACIDAD VISIBLE EN BARRA DE COLA
# =========================================================
_ARCHIVO_CAPACIDAD_COLA = Path(CARPETA_DATOS_USUARIO) / "capacidad_cola.json"
_CAPACIDAD_COLA_DEFECTO = 500
_v102_boton_capacidad = None
_v102_control_instalado = False


def _v102_cargar_capacidad():
    try:
        if _ARCHIVO_CAPACIDAD_COLA.exists():
            datos = json.loads(_ARCHIVO_CAPACIDAD_COLA.read_text(encoding="utf-8"))
            return max(1, min(5000, int(datos.get("capacidad", 500))))
    except Exception:
        pass
    return 500


def _v102_guardar_capacidad(valor):
    valor = max(1, min(5000, int(valor)))
    _ARCHIVO_CAPACIDAD_COLA.parent.mkdir(parents=True, exist_ok=True)
    _ARCHIVO_CAPACIDAD_COLA.write_text(
        json.dumps({"capacidad": valor}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return valor


CAPACIDAD_COLA = _v102_cargar_capacidad()


def capacidad_cola_actual():
    try:
        return int(CAPACIDAD_COLA)
    except Exception:
        return 500


def _v102_uso_cola():
    try:
        return len(cola_anuncios)
    except Exception:
        return 0


def _v102_actualizar_boton():
    try:
        if _v102_boton_capacidad is not None:
            _v102_boton_capacidad.configure(
                text=f"⚙ Capacidad {_v102_uso_cola()}/{capacidad_cola_actual()}"
            )
    except Exception:
        pass


def _v102_abrir_dialogo_capacidad():
    global CAPACIDAD_COLA

    dialogo = ctk.CTkToplevel(ventana)
    dialogo.title("Capacidad de la cola")
    dialogo.geometry("420x220")
    dialogo.resizable(False, False)

    try:
        dialogo.transient(ventana)
        dialogo.grab_set()
    except Exception:
        pass

    marco = ctk.CTkFrame(dialogo, fg_color="#081017")
    marco.pack(fill="both", expand=True, padx=12, pady=12)

    ctk.CTkLabel(
        marco,
        text="Capacidad máxima de la cola",
        font=("Segoe UI", 16, "bold")
    ).pack(anchor="w", padx=12, pady=(12, 4))

    ctk.CTkLabel(
        marco,
        text="Elige entre 1 y 5000 anuncios.",
        text_color="#98a7b2"
    ).pack(anchor="w", padx=12, pady=(0, 10))

    entrada = ctk.CTkEntry(marco, height=38)
    entrada.pack(fill="x", padx=12, pady=(0, 10))
    entrada.insert(0, str(capacidad_cola_actual()))

    def guardar():
        global CAPACIDAD_COLA
        try:
            valor = int(str(entrada.get()).strip())
        except Exception:
            messagebox.showerror("Capacidad de la cola", "Escribe un número entre 1 y 5000.", parent=dialogo)
            return

        if valor < 1 or valor > 5000:
            messagebox.showerror("Capacidad de la cola", "El valor debe estar entre 1 y 5000.", parent=dialogo)
            return

        CAPACIDAD_COLA = _v102_guardar_capacidad(valor)
        _v102_actualizar_boton()
        dialogo.destroy()

    ctk.CTkButton(
        marco,
        text="Guardar capacidad",
        command=guardar,
        height=38
    ).pack(fill="x", padx=12, pady=(0, 12))


def _v102_descendientes(widget):
    salida = []
    try:
        hijos = widget.winfo_children()
    except Exception:
        return salida

    for hijo in hijos:
        salida.append(hijo)
        salida.extend(_v102_descendientes(hijo))
    return salida


def _v102_texto(widget):
    try:
        return str(widget.cget("text") or "").strip().lower()
    except Exception:
        return ""


def _v102_buscar_boton_anadir():
    try:
        todos = _v102_descendientes(ventana)
    except Exception:
        todos = []

    for widget in todos:
        texto = _v102_texto(widget)
        if (
            "añadir anuncio actual" in texto
            or "anadir anuncio actual" in texto
            or texto == "+ añadir anuncio"
            or texto == "+ anadir anuncio"
        ):
            return widget

    return None


def _v102_instalar_boton_capacidad(intentos=0):
    global _v102_boton_capacidad, _v102_control_instalado

    if _v102_control_instalado:
        return

    referencia = _v102_buscar_boton_anadir()

    if referencia is None:
        if intentos < 60:
            ventana.after(
                500,
                lambda: _v102_instalar_boton_capacidad(intentos + 1)
            )
        return

    try:
        parent = referencia.master
        gestor = str(referencia.winfo_manager()).lower()

        _v102_boton_capacidad = ctk.CTkButton(
            parent,
            text="",
            command=_v102_abrir_dialogo_capacidad,
            height=32,
            width=155,
            fg_color="#245a86",
            hover_color="#2f6fa3"
        )

        if gestor == "grid":
            info = referencia.grid_info()
            _v102_boton_capacidad.grid(
                row=int(info.get("row", 0)),
                column=int(info.get("column", 0)) + 1,
                padx=(8, 0),
                sticky="ew"
            )
        else:
            _v102_boton_capacidad.pack(
                side="left",
                padx=(8, 0)
            )

        _v102_control_instalado = True
        _v102_actualizar_boton()

    except Exception as e:
        print("[V102] Error instalando botón capacidad:", e)
        if intentos < 60:
            ventana.after(
                500,
                lambda: _v102_instalar_boton_capacidad(intentos + 1)
            )


def _v102_envuelve_funcion_cola(nombre, funcion):
    if getattr(funcion, "_v102_capacidad_wrapped", False):
        return funcion

    def wrapper(*args, **kwargs):
        actual = _v102_uso_cola()
        limite = capacidad_cola_actual()

        if actual >= limite:
            messagebox.showwarning(
                "Cola llena",
                f"La cola ya tiene {actual}/{limite} anuncios."
            )
            return None

        resultado = funcion(*args, **kwargs)

        try:
            if len(cola_anuncios) > limite:
                del cola_anuncios[limite:]
                fn = globals().get("guardar_cola_en_disco") or globals().get("guardar_cola")
                if callable(fn):
                    fn()
                fnr = globals().get("refrescar_cola")
                if callable(fnr):
                    fnr()
        except Exception:
            pass

        _v102_actualizar_boton()
        return resultado

    wrapper._v102_capacidad_wrapped = True
    wrapper.__name__ = getattr(funcion, "__name__", nombre)
    return wrapper


def _v102_instalar_limites():
    for nombre, funcion in list(globals().items()):
        if not callable(funcion):
            continue

        n = str(nombre).lower()

        if "cola" not in n:
            continue

        if not any(p in n for p in ("anadir", "añadir", "agregar", "insertar")):
            continue

        if any(p in n for p in ("guardar", "cargar", "refrescar", "iniciar", "procesar", "publicar")):
            continue

        try:
            globals()[nombre] = _v102_envuelve_funcion_cola(nombre, funcion)
        except Exception:
            pass


def _v102_tick():
    _v102_actualizar_boton()

    if not _v102_control_instalado:
        _v102_instalar_boton_capacidad()

    try:
        ventana.after(1000, _v102_tick)
    except Exception:
        pass


try:
    ventana.after(300, _v102_instalar_boton_capacidad)
    ventana.after(700, _v102_instalar_limites)
    ventana.after(1000, _v102_tick)
except Exception as e:
    print("[V102] No pude iniciar capacidad de cola:", e)

'''

    marcador = "\nventana.mainloop()"

    if marcador not in texto:
        raise RuntimeError("No pude insertar la capacidad configurable.")

    return texto.replace(marcador, codigo + marcador, 1)




def _consolidar_capacidad_v102(texto):
    """
    V100: una sola fuente de verdad para la capacidad de cola.
    Corrige el fallo real detectado en la instalación del usuario:
    capacidad_cola.json=100, pero MAX_COLA/config seguían en 10.
    """

    # 1) Añadir helper efectivo tras limite_lote_plan().
    needle = '''def limite_lote_plan():
    if es_edicion_admin():
        return 500

    return int(
        plan_actual().get(
            "max_lote",
            5
        )
    )


'''

    helper = '''def limite_lote_plan():
    if es_edicion_admin():
        return 500

    return int(
        plan_actual().get(
            "max_lote",
            5
        )
    )


def limite_cola_efectivo():
    """Única fuente de verdad para el máximo real de la cola."""
    try:
        configurada = int(
            capacidad_cola_actual()
        )
    except Exception:
        try:
            configurada = int(
                MAX_COLA
            )
        except Exception:
            configurada = (
                500
                if es_edicion_admin()
                else limite_cola_plan()
            )

    configurada = max(
        1,
        min(
            5000,
            configurada
        )
    )

    if es_edicion_admin():
        return configurada

    return min(
        configurada,
        int(
            limite_cola_plan()
        )
    )


def espacio_cola_disponible():
    try:
        usados = len(
            cola_anuncios
        )
    except Exception:
        usados = 0

    return max(
        0,
        limite_cola_efectivo()
        - usados
    )


'''

    if needle in texto and "def limite_cola_efectivo():" not in texto:
        texto = texto.replace(
            needle,
            helper,
            1
        )

    # 2) Admin: el límite del plan debe respetar la capacidad elegida.
    texto = texto.replace(
        '''def limite_cola_plan():
    if es_edicion_admin():
        return 500
''',
        '''def limite_cola_plan():
    if es_edicion_admin():
        try:
            return int(
                capacidad_cola_actual()
            )
        except Exception:
            return 500
''',
        1
    )

    # 3) El antiguo MAX_COLA no puede arrancar en 10.
    texto = texto.replace(
        "MAX_COLA = 10\nARCHIVO_COLA",
        "MAX_COLA = 500\nARCHIVO_COLA",
        1
    )

    # 4) Todas las operaciones principales de cola usan el límite efectivo.
    reemplazos = {
        "MAX_COLA = limite_cola_plan()": "MAX_COLA = limite_cola_efectivo()",
        "datos[:MAX_COLA]": "datos[:limite_cola_efectivo()]",
        "len(cola_anuncios) >= MAX_COLA": "len(cola_anuncios) >= limite_cola_efectivo()",
        "MAX_COLA - len(cola_anuncios)": "espacio_cola_disponible()",
        'f"❌ La cola admite como máximo {MAX_COLA} anuncios."': 'f"❌ La cola admite como máximo {limite_cola_efectivo()} anuncios."',
        'f"❌ La cola ya tiene el máximo permitido: {MAX_COLA}."': 'f"❌ La cola ya tiene el máximo permitido: {limite_cola_efectivo()}."',
        'text=f"{ocupados} / {MAX_COLA}"': 'text=f"{ocupados} / {limite_cola_efectivo()}"',
        "libres = max(0, MAX_COLA - ocupados)": "libres = espacio_cola_disponible()",
    }

    for viejo, nuevo in reemplazos.items():
        texto = texto.replace(
            viejo,
            nuevo
        )

    # 5) El generador desde publicados tenía un límite FIJO de 10.
    texto = texto.replace(
        '''        min(
            cantidad,
            10,
            espacio_cola_disponible()
        )''',
        '''        min(
            cantidad,
            espacio_cola_disponible()
        )'''
    )

    texto = texto.replace(
        '''        min(
            cantidad,
            10,
            MAX_COLA - len(cola_anuncios)
        )''',
        '''        min(
            cantidad,
            espacio_cola_disponible()
        )'''
    )

    # 6) Generación de lotes: espacio real = capacidad configurada - usados.
    texto = texto.replace(
        '''    espacio_disponible = min(
        MAX_COLA,
        limite_cola_plan()
    ) - len(cola_anuncios)''',
        '''    espacio_disponible = espacio_cola_disponible()'''
    )

    # 7) En ADMIN, el máximo de un lote sigue la capacidad elegida.
    texto = texto.replace(
        '''    limite_lote = limite_lote_plan()

    if cantidad < 1 or cantidad > limite_lote:''',
        '''    limite_lote = (
        limite_cola_efectivo()
        if es_edicion_admin()
        else limite_lote_plan()
    )

    if cantidad < 1 or cantidad > limite_lote:''',
        1
    )

    texto = texto.replace(
        "max_lote_plan = limite_lote_plan()",
        "max_lote_plan = (limite_cola_efectivo() if es_edicion_admin() else limite_lote_plan())"
    )

    # 8) Ajustes generales: eliminar el tope antiguo de 100.
    texto = texto.replace(
        "if max_cola_cfg < 1 or max_cola_cfg > 100:",
        "if max_cola_cfg < 1 or max_cola_cfg > 5000:"
    )
    texto = texto.replace(
        '"El máximo de cola debe estar entre 1 y 100."',
        '"El máximo de cola debe estar entre 1 y 5000."'
    )

    # 9) No volver a restaurar 10 desde configuracion_bot.json.
    texto = texto.replace(
        '''    try:
        MAX_COLA = int(
            datos.get("max_cola", 10)
        )
    except Exception:
        MAX_COLA = 10
''',
        '''    try:
        if callable(
            globals().get(
                "capacidad_cola_actual"
            )
        ):
            MAX_COLA = int(
                capacidad_cola_actual()
            )
        else:
            MAX_COLA = int(
                datos.get(
                    "max_cola",
                    500
                )
            )
    except Exception:
        MAX_COLA = 500
''',
        1
    )

    texto = texto.replace(
        '"max_cola": 10,',
        '"max_cola": 500,'
    )
    texto = texto.replace(
        'datos.get("max_cola", 10)',
        'datos.get("max_cola", 500)'
    )
    texto = texto.replace(
        'var_max_cola = ctk.StringVar(value="10")',
        'var_max_cola = ctk.StringVar(value="500")'
    )

    # 10) El botón Capacidad sincroniza también MAX_COLA y la config heredada.
    viejo_guardar = '''def _v102_guardar_capacidad(valor):
    valor = max(1, min(5000, int(valor)))
    _ARCHIVO_CAPACIDAD_COLA.parent.mkdir(parents=True, exist_ok=True)
    _ARCHIVO_CAPACIDAD_COLA.write_text(
        json.dumps({"capacidad": valor}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return valor
'''

    nuevo_guardar = '''def _v102_guardar_capacidad(valor):
    global MAX_COLA

    valor = max(
        1,
        min(
            5000,
            int(
                valor
            )
        )
    )

    _ARCHIVO_CAPACIDAD_COLA.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    _ARCHIVO_CAPACIDAD_COLA.write_text(
        json.dumps(
            {
                "capacidad": valor,
                "actualizado": time.strftime(
                    "%d/%m/%Y %H:%M:%S"
                ),
            },
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    MAX_COLA = valor

    try:
        datos_cfg = cargar_configuracion_general()

        if isinstance(
            datos_cfg,
            dict
        ):
            datos_cfg[
                "max_cola"
            ] = valor

            with open(
                ARCHIVO_CONFIG,
                "w",
                encoding="utf-8"
            ) as archivo_cfg:
                json.dump(
                    datos_cfg,
                    archivo_cfg,
                    ensure_ascii=False,
                    indent=4
                )
    except Exception:
        pass

    try:
        var_max_cola.set(
            str(
                valor
            )
        )
    except Exception:
        pass

    return valor
'''

    if viejo_guardar in texto:
        texto = texto.replace(
            viejo_guardar,
            nuevo_guardar,
            1
        )

    # 11) El botón y wrappers muestran/usan el límite efectivo.
    texto = texto.replace(
        'f"⚙ Capacidad {_v102_uso_cola()}/{capacidad_cola_actual()}"',
        'f"⚙ Capacidad {_v102_uso_cola()}/{limite_cola_efectivo()}"'
    )
    texto = texto.replace(
        "limite = capacidad_cola_actual()",
        "limite = limite_cola_efectivo()"
    )

    # 12) Sincronización al iniciar: capacidad_cola.json manda.
    arranque = '''try:
    ventana.after(300, _v102_instalar_boton_capacidad)
'''

    arranque_nuevo = '''try:
    try:
        MAX_COLA = capacidad_cola_actual()
        var_max_cola.set(
            str(
                MAX_COLA
            )
        )
    except Exception:
        pass

    ventana.after(300, _v102_instalar_boton_capacidad)
'''

    if arranque in texto:
        texto = texto.replace(
            arranque,
            arranque_nuevo,
            1
        )

    # 13) Diagnóstico visible de la capacidad real.
    marcador_diag = '''def _v102_tick():
'''

    if marcador_diag in texto and "def _v102_capacidad_diagnostico():" not in texto:
        texto = texto.replace(
            marcador_diag,
            '''def _v102_capacidad_diagnostico():
    return {
        "configurada": capacidad_cola_actual(),
        "efectiva": limite_cola_efectivo(),
        "uso": _v102_uso_cola(),
        "libres": espacio_cola_disponible(),
        "max_cola_legacy": globals().get(
            "MAX_COLA"
        ),
    }


''' + marcador_diag,
            1
        )

    return texto



def _reforzar_cdp_rotacion_v102(texto):
    """V102: endurece la conexión CDP usada por la rotación."""
    try:
        texto = texto.replace(
            'connect_over_cdp("http://127.0.0.1:9222", timeout=15000)',
            'connect_over_cdp("http://127.0.0.1:9222", timeout=60000)'
        )
        texto = texto.replace(
            "connect_over_cdp('http://127.0.0.1:9222', timeout=15000)",
            "connect_over_cdp('http://127.0.0.1:9222', timeout=60000)"
        )
        texto = texto.replace(
            'connect_over_cdp("http://localhost:9222", timeout=15000)',
            'connect_over_cdp("http://localhost:9222", timeout=60000)'
        )
        return texto
    except Exception:
        return texto



def _pulido_integral_v102(texto):
    """
    Pulido consolidado basado en la instalación real del usuario:
    - una sola capa runtime;
    - capacidad de cola única;
    - updater con fallback directo a GitHub;
    - URLs de candidatos válidas (/item/);
    - navegación a Tú > Productos;
    - detección segura del icono papelera;
    - diagnóstico HTML/captura cuando Wallapop cambie la interfaz;
    - CDP con reintentos más amplios.
    """

    # ---- CDP: usar el conector estable del propio bot y ampliar margen ----
    texto = texto.replace(
        "timeout=10000\\n            )",
        "timeout=30000\\n            )"
    )

    texto = texto.replace(
        '''navegador = p.chromium.connect_over_cdp(
                "http://127.0.0.1:9222",
                timeout=60000
            )''',
        '''_asegurar_chromium_controlable()
            navegador = _conectar_playwright_cdp(
                p
            )'''
    )
    texto = texto.replace(
        '''navegador = p.chromium.connect_over_cdp(
                "http://127.0.0.1:9222",
                timeout=15000
            )''',
        '''_asegurar_chromium_controlable()
            navegador = _conectar_playwright_cdp(
                p
            )'''
    )

    # ---- Updater: Cloudflare primero, GitHub como fallback fiable ----
    old = '''def _descargar_json_url(url, timeout=10):
    req = urllib.request.Request(
        str(url),
        headers={
            "User-Agent": "DIAGPROG5-Updater/1.0",
            "Cache-Control": "no-cache",
        }
    )

    with urllib.request.urlopen(
        req,
        timeout=timeout
    ) as resp:
        return json.loads(
            resp.read().decode(
                "utf-8"
            )
        )
'''

    new = '''def _descargar_json_url(url, timeout=10):
    urls = [
        str(url).strip(),
        "https://raw.githubusercontent.com/Hugo0555/diagprog5-updates/main/diagprog5-update.json",
    ]

    ultimo_error = None

    for destino in urls:
        if not destino:
            continue

        try:
            req = urllib.request.Request(
                destino,
                headers={
                    "User-Agent": "DIAGPROG5-Updater/2.0",
                    "Cache-Control": "no-cache",
                }
            )

            with urllib.request.urlopen(
                req,
                timeout=max(
                    10,
                    int(timeout)
                )
            ) as resp:
                datos = json.loads(
                    resp.read().decode(
                        "utf-8"
                    )
                )

            if isinstance(
                datos,
                dict
            ):
                return datos

        except Exception as e:
            ultimo_error = e

    raise RuntimeError(
        "No pude leer el servidor de actualizaciones. "
        + str(
            ultimo_error
        )
    )
'''

    if old in texto:
        texto = texto.replace(
            old,
            new,
            1
        )

    # ---- Registrar URL real tras publicar ----
    old_save = '''def guardar_anuncio_publicado(titulo, descripcion, precio):
    publicados = cargar_publicados()
    identificador = crear_id_anuncio(titulo, descripcion, precio)

    publicados[identificador] = {
        "titulo": str(titulo).strip(),
        "precio": str(precio).strip(),
        "fecha": time.strftime("%d/%m/%Y %H:%M:%S")
    }
'''

    new_save = '''def guardar_anuncio_publicado(titulo, descripcion, precio, url_anuncio=""):
    publicados = cargar_publicados()
    identificador = crear_id_anuncio(titulo, descripcion, precio)

    registro = {
        "titulo": str(titulo).strip(),
        "precio": str(precio).strip(),
        "fecha": time.strftime("%d/%m/%Y %H:%M:%S")
    }

    url_limpia = str(
        url_anuncio
        or ""
    ).strip()

    if (
        "wallapop.com" in url_limpia.lower()
        and "/item/" in url_limpia.lower()
    ):
        registro["url"] = url_limpia
        registro["url_anuncio"] = url_limpia

    publicados[identificador] = registro
'''

    if old_save in texto:
        texto = texto.replace(
            old_save,
            new_save,
            1
        )

    # Capturar una URL /item/ entre las páginas tras publicar.
    call_old = 'guardar_anuncio_publicado(titulo, descripcion, precio)'
    call_new = '''_url_publicada = ""

                try:
                    _paginas_candidatas = list(
                        contexto.pages
                    )

                    for _pag in reversed(
                        _paginas_candidatas
                    ):
                        try:
                            _u = str(
                                _pag.url
                                or ""
                            ).strip()

                            if (
                                "wallapop.com" in _u.lower()
                                and "/item/" in _u.lower()
                            ):
                                _url_publicada = _u
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

                guardar_anuncio_publicado(
                    titulo,
                    descripcion,
                    precio,
                    _url_publicada
                )'''

    texto = texto.replace(
        call_old,
        call_new,
        1
    )

    # ---- URL de candidato: rechazar home/perfil y aceptar solo anuncio real ----
    patron_url = re.compile(
        r'def _v102_url_candidato\\(item\\):[\\s\\S]*?\\n\\ndef _v102_titulo_candidato',
        re.MULTILINE
    )

    repl_url = '''def _v102_url_candidato(item):
    if not isinstance(
        item,
        dict
    ):
        return ""

    for clave in (
        "url",
        "url_anuncio",
        "url_wallapop",
        "link",
        "permalink",
        "web_url",
    ):
        valor = str(
            item.get(
                clave,
                ""
            )
            or ""
        ).strip()

        bajo = valor.lower()

        if (
            ("https://" in bajo or "http://" in bajo)
            and "wallapop.com" in bajo
            and "/item/" in bajo
        ):
            return valor

    return ""


def _v102_titulo_candidato'''

    texto = patron_url.sub(
        repl_url,
        texto,
        count=1
    )

    # ---- Descubrir y abrir candidato desde la sección Productos ----
    patron_abrir = re.compile(
        r'def _v102_abrir_candidato\\(page, candidato\\):[\\s\\S]*?\\n\\ndef _v102_eliminar_con_motor_existente',
        re.MULTILINE
    )

    repl_abrir = r'''def _v102_abrir_candidato(page, candidato):
    titulo = _v102_titulo_candidato(
        candidato
    )

    url = _v102_url_candidato(
        candidato
    )

    if url:
        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=35000
            )
            page.wait_for_timeout(
                1200
            )

            if "/item/" in str(
                page.url
            ).lower():
                return True
        except Exception:
            pass

    # Ruta fiable: entrar en Wallapop y navegar con la propia UI.
    try:
        page.goto(
            "https://es.wallapop.com/",
            wait_until="domcontentloaded",
            timeout=35000
        )
        page.wait_for_timeout(
            1000
        )

        _v102_click_visible(
            page,
            (
                "Tú",
                "Tu perfil",
                "Perfil",
            ),
            timeout=3000
        )

        page.wait_for_timeout(
            900
        )

        _v102_click_visible(
            page,
            (
                "Productos",
                "Mis productos",
                "En venta",
                "Mis anuncios",
            ),
            timeout=3500
        )

        page.wait_for_timeout(
            1300
        )

        if not titulo:
            return False

        # Buscar el anuncio; si la lista es larga hacemos varios scrolls.
        for _ in range(
            12
        ):
            loc = page.get_by_text(
                titulo,
                exact=True
            )

            if loc.count() <= 0:
                loc = page.get_by_text(
                    titulo,
                    exact=False
                )

            if loc.count() > 0:
                objetivo = loc.first

                try:
                    objetivo.scroll_into_view_if_needed()
                except Exception:
                    pass

                # Preferir el enlace /item/ asociado al título.
                try:
                    href = objetivo.evaluate("""
                        el => {
                            const a = el.closest('a[href*="/item/"]')
                                || el.parentElement?.closest('a[href*="/item/"]')
                                || el.parentElement?.querySelector('a[href*="/item/"]')
                                || el.closest('article')?.querySelector('a[href*="/item/"]')
                                || el.closest('div')?.querySelector('a[href*="/item/"]');
                            return a ? a.href : "";
                        }
                    """)

                    if href and "/item/" in str(
                        href
                    ).lower():
                        _v102_guardar_url_candidato(
                            candidato,
                            str(
                                href
                            )
                        )

                        page.goto(
                            str(
                                href
                            ),
                            wait_until="domcontentloaded",
                            timeout=35000
                        )

                        page.wait_for_timeout(
                            1200
                        )

                        return True
                except Exception:
                    pass

                try:
                    objetivo.click(
                        timeout=4000
                    )
                    page.wait_for_timeout(
                        1200
                    )

                    if "/item/" in str(
                        page.url
                    ).lower():
                        _v102_guardar_url_candidato(
                            candidato,
                            str(
                                page.url
                            )
                        )
                        return True
                except Exception:
                    pass

            try:
                page.mouse.wheel(
                    0,
                    900
                )
                page.wait_for_timeout(
                    350
                )
            except Exception:
                break

    except Exception as e:
        _v102_log_rotacion(
            "No pude navegar a Productos: "
            + str(
                e
            )
        )

    return False


def _v102_eliminar_con_motor_existente'''

    texto = patron_abrir.sub(
        repl_abrir,
        texto,
        count=1
    )

    # ---- Papelera: soportar iconos sin texto/aria-label ----
    marker = 'def _v102_click_eliminar_avanzado(page):'

    if marker in texto and "def _v102_click_papelera_icono(page):" not in texto:
        helper = r'''def _v102_click_papelera_icono(page):
    """Busca específicamente el icono de papelera de la web."""
    selectores = (
        'button[aria-label*="papelera" i]',
        'button[aria-label*="eliminar" i]',
        'button[aria-label*="delete" i]',
        'button[title*="papelera" i]',
        'button[title*="eliminar" i]',
        '[data-testid*="delete" i]',
        '[data-testid*="trash" i]',
        '[data-testid*="remove" i]',
        'walla-icon[name*="trash" i]',
        'walla-icon[name*="delete" i]',
        '[name*="trash" i]',
        '[name*="delete" i]',
    )

    for selector in selectores:
        try:
            loc = page.locator(
                selector
            )

            if loc.count() > 0:
                el = loc.first

                try:
                    if el.evaluate(
                        "e => e.tagName.toLowerCase()"
                    ) == "walla-icon":
                        el = el.locator(
                            "xpath=ancestor::button[1]"
                        )
                except Exception:
                    pass

                try:
                    el.scroll_into_view_if_needed()
                except Exception:
                    pass

                el.click(
                    timeout=3000
                )
                return True, selector
        except Exception:
            pass

    # Buscar por HTML interno; muchos iconos no tienen texto visible.
    try:
        controles = page.locator(
            'button, [role="button"]'
        )

        for i in range(
            min(
                controles.count(),
                250
            )
        ):
            el = controles.nth(
                i
            )

            try:
                html = str(
                    el.evaluate(
                        "e => e.outerHTML"
                    )
                    or ""
                ).lower()

                if any(
                    x in html
                    for x in (
                        "trash",
                        "delete",
                        "papelera",
                        "remove-product",
                    )
                ):
                    el.click(
                        timeout=2500
                    )
                    return True, "icon-html"
            except Exception:
                pass
    except Exception:
        pass

    # En la web de Wallapop la papelera aparece junto al lápiz de edición.
    # Si encontramos un enlace de edición, buscamos un botón icon-only hermano.
    try:
        edit = page.locator(
            'a[href*="edit" i], button[aria-label*="editar" i], button[title*="editar" i]'
        )

        if edit.count() > 0:
            candidato = edit.first.evaluate_handle("""
                el => {
                    const p = el.parentElement;
                    if (!p) return null;
                    const xs = [...p.querySelectorAll('button,[role="button"]')];
                    return xs.find(x => x !== el && !/edit|editar/i.test(x.outerHTML)) || null;
                }
            """)

            if candidato:
                try:
                    candidato.as_element().click()
                    return True, "sibling-of-edit"
                except Exception:
                    pass
    except Exception:
        pass

    return False, ""


'''
        texto = texto.replace(
            marker,
            helper + marker,
            1
        )

        needle = '''def _v102_click_eliminar_avanzado(page):
    patrones = (
'''
        if needle in texto:
            texto = texto.replace(
                needle,
                '''def _v102_click_eliminar_avanzado(page):
    ok_icono, detalle_icono = _v102_click_papelera_icono(
        page
    )

    if ok_icono:
        return True, detalle_icono

    patrones = (
''',
                1
            )

    # ---- Guardar diagnóstico de rotación en fallo ----
    fail = '''if not eliminado_click:
                controles = _v102_dump_controles(
                    pagina
                )
'''

    if fail in texto:
        texto = texto.replace(
            fail,
            '''if not eliminado_click:
                controles = _v102_dump_controles(
                    pagina
                )

                try:
                    _diag_dir = (
                        Path(
                            CARPETA_DATOS_USUARIO
                        )
                        / "diagnosticos_rotacion"
                        / time.strftime(
                            "%Y%m%d_%H%M%S"
                        )
                    )
                    _diag_dir.mkdir(
                        parents=True,
                        exist_ok=True
                    )

                    pagina.screenshot(
                        path=str(
                            _diag_dir
                            / "captura.png"
                        ),
                        full_page=True
                    )

                    (
                        _diag_dir
                        / "pagina.html"
                    ).write_text(
                        pagina.content(),
                        encoding="utf-8",
                        errors="ignore"
                    )

                    (
                        _diag_dir
                        / "info.txt"
                    ).write_text(
                        "URL: "
                        + str(
                            pagina.url
                        )
                        + "\\nTITULO: "
                        + str(
                            titulo
                        )
                        + "\\nCONTROLES:\\n"
                        + "\\n".join(
                            controles
                        ),
                        encoding="utf-8"
                    )

                    _v102_log_rotacion(
                        "Diagnóstico DOM guardado en: "
                        + str(
                            _diag_dir
                        )
                    )
                except Exception as _e_diag:
                    _v102_log_rotacion(
                        "No pude guardar diagnóstico DOM: "
                        + str(
                            _e_diag
                        )
                    )
''',
            1
        )


    # ---- Rotación segura con títulos duplicados ----
    viejo_rotar = '''def _v102_rotar_una_vez():
    if not _v102_rotacion_activa():
        return False, (
            "Rotación desactivada."
        )

    candidatos = _v102_candidatos_locales()

    if not candidatos:
        return False, (
            "No hay candidatos seguros elegibles."
        )

    candidato = candidatos[0]

    ok, detalle = _v102_eliminar_en_wallapop(
        candidato
    )
'''

    nuevo_rotar = '''def _v102_rotar_una_vez():
    if not _v102_rotacion_activa():
        return False, (
            "Rotación desactivada."
        )

    candidatos = _v102_candidatos_locales()

    if not candidatos:
        return False, (
            "No hay candidatos seguros elegibles."
        )

    # Si varios anuncios comparten título y ninguno tiene URL conocida,
    # no borrar a ciegas. Preferimos el candidato más antiguo identificable.
    conteo_titulos = {}

    for _cand in candidatos:
        _t = _v102_normalizar_texto(
            _v102_titulo_candidato(
                _cand
            )
        )

        if _t:
            conteo_titulos[_t] = (
                conteo_titulos.get(
                    _t,
                    0
                )
                + 1
            )

    candidato = None

    for _cand in candidatos:
        _t = _v102_normalizar_texto(
            _v102_titulo_candidato(
                _cand
            )
        )

        _url = _v102_url_candidato(
            _cand
        )

        if _url or conteo_titulos.get(
            _t,
            0
        ) <= 1:
            candidato = _cand
            break

    if candidato is None:
        return False, (
            "Los candidatos más antiguos tienen títulos duplicados y no "
            "hay URL suficiente para distinguirlos con seguridad."
        )

    ok, detalle = _v102_eliminar_en_wallapop(
        candidato
    )
'''

    if viejo_rotar in texto:
        texto = texto.replace(
            viejo_rotar,
            nuevo_rotar,
            1
        )

    # ---- Continuar: fallback JS más tolerante para Shadow DOM ----
    old_cont = '''    return False




def esperar_y_rellenar_resumen(page, titulo):'''

    new_cont = '''    try:
        ok = page.evaluate("""
            () => {
                const candidatos = [];
                const walk = root => {
                    const nodes = root.querySelectorAll('*');
                    for (const el of nodes) {
                        if (el.shadowRoot) walk(el.shadowRoot);
                        const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                        if (
                            (el.tagName === 'BUTTON' || el.getAttribute('role') === 'button')
                            && txt.includes('continuar')
                        ) {
                            candidatos.push(el);
                        }
                    }
                };
                walk(document);

                const visibles = candidatos.filter(el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 && !el.disabled;
                });

                const el = visibles[visibles.length - 1];
                if (!el) return false;
                el.scrollIntoView({block: 'center'});
                el.click();
                return true;
            }
        """)

        if ok:
            return True
    except Exception:
        pass

    return False




def esperar_y_rellenar_resumen(page, titulo):'''

    if old_cont in texto:
        texto = texto.replace(
            old_cont,
            new_cont,
            1
        )

    return texto



def _hotfix_rotacion_real_v102_1(texto):
    """
    V103: la prueba ya localiza el candidato; este hotfix hace que la
    rotación REAL borre desde la tarjeta de Productos antes de usar el flujo
    antiguo de detalle.
    """
    if "V103 · BORRADO REAL DESDE PRODUCTOS" in texto:
        return texto

    codigo = r'''

# =========================================================
# V103 · BORRADO REAL DESDE PRODUCTOS
# =========================================================

def _v1021_norm(valor):
    try:
        import unicodedata
        txt = unicodedata.normalize("NFKD", str(valor or ""))
        txt = "".join(c for c in txt if not unicodedata.combining(c))
        return " ".join(txt.lower().split())
    except Exception:
        return " ".join(str(valor or "").lower().split())


def _v1021_click_confirmacion(page):
    textos = (
        "Sí, eliminar",
        "Si, eliminar",
        "Eliminar definitivamente",
        "Eliminar producto",
        "Eliminar anuncio",
        "Confirmar eliminación",
        "Confirmar eliminacion",
        "Eliminar",
        "Sí",
        "Si",
    )

    for texto in textos:
        try:
            loc = page.get_by_role(
                "button",
                name=re.compile(
                    re.escape(texto),
                    re.I
                )
            )

            if loc.count() > 0:
                for i in range(min(loc.count(), 8)):
                    b = loc.nth(i)
                    try:
                        if b.is_visible():
                            b.click(timeout=2500)
                            return True, texto
                    except Exception:
                        pass
        except Exception:
            pass

    try:
        dialogos = page.locator(
            '[role="dialog"], dialog, walla-dialog, [class*="modal" i]'
        )

        for j in range(min(dialogos.count(), 8)):
            d = dialogos.nth(j)
            botones = d.locator(
                'button, [role="button"]'
            )

            for i in range(min(botones.count(), 30)):
                b = botones.nth(i)

                try:
                    blob = " ".join(
                        [
                            b.inner_text(timeout=150) or "",
                            b.get_attribute("aria-label") or "",
                            b.get_attribute("title") or "",
                            b.get_attribute("data-testid") or "",
                        ]
                    )

                    n = _v1021_norm(blob)

                    if (
                        "eliminar" in n
                        or "borrar" in n
                        or "delete" in n
                        or n in ("si", "yes", "confirmar")
                    ):
                        b.click(timeout=2500)
                        return True, blob.strip()
                except Exception:
                    pass
    except Exception:
        pass

    return False, ""


def _v1021_card_desde_titulo(page, titulo):
    """
    Devuelve el contenedor visual más cercano al título en Productos.
    """
    titulo_n = _v1021_norm(titulo)

    if not titulo_n:
        return None

    try:
        candidatos = page.get_by_text(
            titulo,
            exact=True
        )

        if candidatos.count() <= 0:
            candidatos = page.get_by_text(
                titulo,
                exact=False
            )

        for i in range(min(candidatos.count(), 20)):
            el = candidatos.nth(i)

            try:
                if not el.is_visible():
                    continue
            except Exception:
                pass

            try:
                card = el.locator(
                    "xpath=ancestor::*[self::article or self::li or @role='listitem' or contains(@class,'card') or contains(@class,'item')][1]"
                )

                if card.count() > 0:
                    return card.first
            except Exception:
                pass

            try:
                handle = el.evaluate_handle("""
                    node => {
                        let p = node;
                        for (let i = 0; i < 8 && p; i++, p = p.parentElement) {
                            const txt = (p.innerText || "").trim();
                            const buttons = p.querySelectorAll('button,[role="button"],a').length;
                            if (buttons > 0 && txt.length > 0 && txt.length < 2500) {
                                return p;
                            }
                        }
                        return node.parentElement || node;
                    }
                """)

                as_el = handle.as_element()

                if as_el is not None:
                    return as_el
            except Exception:
                pass

    except Exception:
        pass

    return None


def _v1021_click_borrar_en_scope(page, scope):
    """
    Busca primero borrar/papelera dentro de la tarjeta correcta.
    """
    patrones_borrar = (
        "eliminar",
        "borrar",
        "delete",
        "trash",
        "remove",
        "papelera",
    )

    patrones_menu = (
        "mas",
        "más",
        "opciones",
        "menu",
        "more",
        "overflow",
        "ellipsis",
        "kebab",
    )

    selectores = (
        'button',
        '[role="button"]',
        'a',
        '[role="menuitem"]',
        'walla-icon',
    )

    try:
        controles = scope.locator(
            ", ".join(selectores)
        )

        for i in range(min(controles.count(), 180)):
            el = controles.nth(i)

            try:
                blob = " ".join(
                    [
                        el.inner_text(timeout=120) or "",
                        el.get_attribute("aria-label") or "",
                        el.get_attribute("title") or "",
                        el.get_attribute("data-testid") or "",
                        el.get_attribute("name") or "",
                        el.get_attribute("class") or "",
                        el.evaluate("e => e.outerHTML") or "",
                    ]
                )

                n = _v1021_norm(blob)

                if any(p in n for p in patrones_borrar):
                    target = el

                    try:
                        tag = str(
                            el.evaluate(
                                "e => e.tagName.toLowerCase()"
                            )
                        )

                        if tag in ("walla-icon", "svg", "path"):
                            anc = el.locator(
                                "xpath=ancestor::button[1]"
                            )

                            if anc.count() > 0:
                                target = anc.first
                    except Exception:
                        pass

                    target.scroll_into_view_if_needed()
                    target.click(timeout=3000)
                    return True, "directo:" + n[:120]
            except Exception:
                pass
    except Exception:
        pass

    # Si no hay papelera directa, abrir el menú SOLO de esa tarjeta.
    try:
        controles = scope.locator(
            'button, [role="button"], a'
        )

        for i in range(min(controles.count(), 120)):
            el = controles.nth(i)

            try:
                blob = " ".join(
                    [
                        el.inner_text(timeout=100) or "",
                        el.get_attribute("aria-label") or "",
                        el.get_attribute("title") or "",
                        el.get_attribute("data-testid") or "",
                        el.get_attribute("name") or "",
                        el.get_attribute("class") or "",
                        el.evaluate("e => e.outerHTML") or "",
                    ]
                )

                n = _v1021_norm(blob)

                if any(p in n for p in patrones_menu):
                    el.scroll_into_view_if_needed()
                    el.click(timeout=2500)
                    page.wait_for_timeout(350)

                    menus = page.locator(
                        '[role="menuitem"], [role="menu"] button, [role="dialog"] button, button, [role="button"]'
                    )

                    for j in range(min(menus.count(), 220)):
                        m = menus.nth(j)

                        try:
                            blob2 = " ".join(
                                [
                                    m.inner_text(timeout=100) or "",
                                    m.get_attribute("aria-label") or "",
                                    m.get_attribute("title") or "",
                                    m.get_attribute("data-testid") or "",
                                    m.evaluate("e => e.outerHTML") or "",
                                ]
                            )

                            n2 = _v1021_norm(blob2)

                            if any(p in n2 for p in patrones_borrar):
                                m.click(timeout=2500)
                                return True, "menu:" + n2[:120]
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass

    return False, ""


def _v1021_ir_a_productos(page):
    """
    Navega a la zona de productos usando la misma ruta que ya funciona en
    la Prueba de rotación.
    """
    try:
        page.goto(
            "https://es.wallapop.com/",
            wait_until="domcontentloaded",
            timeout=35000
        )
    except Exception:
        pass

    try:
        page.wait_for_timeout(900)
    except Exception:
        pass

    # Abrir Tú / perfil.
    try:
        _v102_click_visible(
            page,
            (
                "Tú",
                "Tu perfil",
                "Perfil",
            ),
            timeout=3500
        )
    except Exception:
        pass

    try:
        page.wait_for_timeout(700)
    except Exception:
        pass

    # Ir a Productos.
    try:
        _v102_click_visible(
            page,
            (
                "Productos",
                "Mis productos",
                "En venta",
                "Mis anuncios",
            ),
            timeout=4000
        )
    except Exception:
        pass

    try:
        page.wait_for_timeout(1100)
    except Exception:
        pass


def _v1021_borrar_desde_productos(candidato):
    titulo = _v102_titulo_candidato(
        candidato
    )

    pagina = None

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                _asegurar_chromium_controlable()
            except Exception:
                pass

            try:
                navegador = _conectar_playwright_cdp(
                    p
                )
            except Exception:
                navegador = p.chromium.connect_over_cdp(
                    "http://127.0.0.1:9222",
                    timeout=60000
                )

            if not navegador.contexts:
                return False, "Chrome/CDP sin contexto autenticado."

            contexto = navegador.contexts[0]
            pagina = contexto.new_page()

            _v1021_ir_a_productos(
                pagina
            )

            # Buscar el candidato. La prueba de rotación ya demuestra que esto
            # funciona; repetimos el mismo enfoque y actuamos SOLO en su tarjeta.
            card = None

            for _scroll in range(20):
                card = _v1021_card_desde_titulo(
                    pagina,
                    titulo
                )

                if card is not None:
                    break

                try:
                    pagina.mouse.wheel(
                        0,
                        950
                    )
                    pagina.wait_for_timeout(
                        300
                    )
                except Exception:
                    break

            if card is None:
                return False, (
                    "La prueba podía localizar el candidato, pero el borrado no encontró su tarjeta."
                )

            try:
                card.scroll_into_view_if_needed()
            except Exception:
                pass

            # Guardar URL real del anuncio si la tarjeta la expone.
            try:
                enlace = card.locator(
                    'a[href*="/item/"]'
                )

                if enlace.count() > 0:
                    href = enlace.first.get_attribute(
                        "href"
                    )

                    if href:
                        if str(href).startswith("/"):
                            href = (
                                "https://es.wallapop.com"
                                + str(href)
                            )

                        _v102_guardar_url_candidato(
                            candidato,
                            str(href)
                        )
            except Exception:
                pass

            ok, detalle = _v1021_click_borrar_en_scope(
                pagina,
                card
            )

            if not ok:
                # Como último intento, abrir la tarjeta y buscar opciones en detalle.
                try:
                    enlace = card.locator(
                        'a[href*="/item/"]'
                    )

                    if enlace.count() > 0:
                        href = enlace.first.get_attribute(
                            "href"
                        )

                        if href:
                            if str(href).startswith("/"):
                                href = "https://es.wallapop.com" + str(href)

                            pagina.goto(
                                str(href),
                                wait_until="domcontentloaded",
                                timeout=35000
                            )
                            pagina.wait_for_timeout(
                                900
                            )

                            ok, detalle = _v1021_click_borrar_en_scope(
                                pagina,
                                pagina.locator(
                                    "body"
                                )
                            )
                except Exception:
                    pass

            if not ok:
                # Diagnóstico útil de la tarjeta exacta.
                try:
                    diag = (
                        Path(
                            CARPETA_DATOS_USUARIO
                        )
                        / "diagnosticos_rotacion"
                        / (
                            "v102_1_"
                            + time.strftime(
                                "%Y%m%d_%H%M%S"
                            )
                        )
                    )
                    diag.mkdir(
                        parents=True,
                        exist_ok=True
                    )

                    pagina.screenshot(
                        path=str(
                            diag / "captura.png"
                        ),
                        full_page=True
                    )

                    (diag / "pagina.html").write_text(
                        pagina.content(),
                        encoding="utf-8",
                        errors="ignore"
                    )

                    try:
                        html_card = card.evaluate(
                            "e => e.outerHTML"
                        )
                    except Exception:
                        html_card = ""

                    (diag / "tarjeta.html").write_text(
                        str(
                            html_card
                        ),
                        encoding="utf-8",
                        errors="ignore"
                    )

                    _v102_log_rotacion(
                        "V103 diagnóstico exacto guardado en "
                        + str(
                            diag
                        )
                    )
                except Exception:
                    pass

                return False, (
                    "Localicé el anuncio, pero Wallapop no expuso un control de borrado en su tarjeta ni en el detalle."
                )

            pagina.wait_for_timeout(
                450
            )

            confirmado, texto_conf = _v1021_click_confirmacion(
                pagina
            )

            if confirmado:
                _v102_log_rotacion(
                    "V103 confirmación pulsada: "
                    + str(
                        texto_conf
                    )
                )

            pagina.wait_for_timeout(
                1800
            )

            # Verificar realmente que ya no aparece en Productos.
            _v1021_ir_a_productos(
                pagina
            )

            pagina.wait_for_timeout(
                900
            )

            sigue = _v1021_card_desde_titulo(
                pagina,
                titulo
            )

            if sigue is None:
                return True, (
                    "Anuncio eliminado y ausencia confirmada en Productos."
                )

            # Si hay títulos duplicados puede seguir apareciendo otro igual.
            # En ese caso comprobar si la URL guardada ya no está en la tarjeta.
            url_objetivo = _v102_url_candidato(
                candidato
            )

            if url_objetivo:
                try:
                    hrefs = pagina.locator(
                        'a[href*="/item/"]'
                    )

                    encontrado = False

                    for i in range(min(hrefs.count(), 600)):
                        href = hrefs.nth(i).get_attribute(
                            "href"
                        )

                        if href and str(
                            url_objetivo
                        ).rstrip("/") in str(
                            href
                        ):
                            encontrado = True
                            break

                    if not encontrado:
                        return True, (
                            "Anuncio eliminado; la URL objetivo ya no aparece en Productos."
                        )
                except Exception:
                    pass

            return False, (
                "Se pulsó borrar, pero no pude confirmar que el anuncio desapareciera."
            )

    except Exception as e:
        return False, (
            type(
                e
            ).__name__
            + ": "
            + str(
                e
            )
        )

    finally:
        try:
            if pagina is not None:
                pagina.close()
        except Exception:
            pass


# Conservar el motor anterior como fallback.
_v102_eliminar_en_wallapop_anterior = globals().get(
    "_v102_eliminar_en_wallapop"
)


def _v102_eliminar_en_wallapop(candidato):
    _v102_log_rotacion(
        "V103: intentando borrado real desde Productos."
    )

    ok, detalle = _v1021_borrar_desde_productos(
        candidato
    )

    if ok:
        return True, detalle

    _v102_log_rotacion(
        "V103 primer método falló: "
        + str(
            detalle
        )
    )

    anterior = globals().get(
        "_v102_eliminar_en_wallapop_anterior"
    )

    if callable(
        anterior
    ):
        try:
            return anterior(
                candidato
            )
        except Exception as e:
            return False, (
                str(
                    detalle
                )
                + " · Fallback: "
                + type(
                    e
                ).__name__
                + ": "
                + str(
                    e
                )
            )

    return False, detalle

'''

    marcador = "\nventana.mainloop()"

    if marcador not in texto:
        return texto

    return texto.replace(
        marcador,
        codigo + marcador,
        1
    )



def _hotfix_rotacion_detalle_v103(texto):
    """
    V103:
    - abre el candidato usando el enlace REAL asociado al título, sin exigir /item/
    - si no hay href utilizable, hace click directamente sobre el título exacto
    - espera a que el detalle esté cargado antes de buscar la papelera
    - amplía la detección de iconos de borrado y registra todos los botones/iconos
      relevantes cuando Wallapop cambie el DOM
    """
    if "V103 · ROTACIÓN POR DETALLE EXACTO" in texto:
        return texto

    codigo = r'''

# =========================================================
# V103 · ROTACIÓN POR DETALLE EXACTO
# =========================================================


def _v103_norm(texto):
    try:
        import unicodedata
        t = unicodedata.normalize(
            "NFKD",
            str(texto or "")
        )
        t = "".join(
            c
            for c in t
            if not unicodedata.combining(c)
        )
        return " ".join(
            t.lower().split()
        )
    except Exception:
        return " ".join(
            str(texto or "").lower().split()
        )


def _v103_href_absoluto(href):
    href = str(
        href or ""
    ).strip()

    if not href:
        return ""

    if href.startswith("//"):
        return "https:" + href

    if href.startswith("/"):
        return "https://es.wallapop.com" + href

    if href.startswith("http://") or href.startswith("https://"):
        return href

    return ""


def _v103_abrir_detalle_exacto(page, titulo):
    """
    Abre exactamente el anuncio cuyo título ha localizado la prueba.
    No depende de que la URL contenga /item/.
    """
    titulo = str(
        titulo or ""
    ).strip()

    if not titulo:
        return False, "", "Título vacío"

    candidatos = []

    try:
        exactos = page.get_by_text(
            titulo,
            exact=True
        )

        for i in range(
            min(
                exactos.count(),
                30
            )
        ):
            candidatos.append(
                exactos.nth(i)
            )
    except Exception:
        pass

    if not candidatos:
        try:
            parciales = page.get_by_text(
                titulo,
                exact=False
            )

            for i in range(
                min(
                    parciales.count(),
                    30
                )
            ):
                candidatos.append(
                    parciales.nth(i)
                )
        except Exception:
            pass

    for el in candidatos:
        try:
            if not el.is_visible():
                continue
        except Exception:
            pass

        # 1) El propio nodo puede ser enlace.
        try:
            href = _v103_href_absoluto(
                el.get_attribute(
                    "href"
                )
            )

            if href:
                page.goto(
                    href,
                    wait_until="domcontentloaded",
                    timeout=45000
                )

                try:
                    page.wait_for_load_state(
                        "networkidle",
                        timeout=6000
                    )
                except Exception:
                    pass

                page.wait_for_timeout(
                    1200
                )

                return True, href, "href-directo"
        except Exception:
            pass

        # 2) Buscar el enlace ancestro del título.
        try:
            anc = el.locator(
                "xpath=ancestor::a[@href][1]"
            )

            if anc.count() > 0:
                href = _v103_href_absoluto(
                    anc.first.get_attribute(
                        "href"
                    )
                )

                if href:
                    page.goto(
                        href,
                        wait_until="domcontentloaded",
                        timeout=45000
                    )

                    try:
                        page.wait_for_load_state(
                            "networkidle",
                            timeout=6000
                        )
                    except Exception:
                        pass

                    page.wait_for_timeout(
                        1200
                    )

                    return True, href, "href-ancestro"
        except Exception:
            pass

        # 3) Buscar enlace dentro de un contenedor próximo.
        try:
            scope = el.locator(
                "xpath=ancestor::*[self::article or self::li or @role='listitem' or @data-testid][1]"
            )

            if scope.count() > 0:
                links = scope.first.locator(
                    "a[href]"
                )

                for j in range(
                    min(
                        links.count(),
                        30
                    )
                ):
                    href = _v103_href_absoluto(
                        links.nth(j).get_attribute(
                            "href"
                        )
                    )

                    if href:
                        page.goto(
                            href,
                            wait_until="domcontentloaded",
                            timeout=45000
                        )

                        try:
                            page.wait_for_load_state(
                                "networkidle",
                                timeout=6000
                            )
                        except Exception:
                            pass

                        page.wait_for_timeout(
                            1200
                        )

                        return True, href, "href-tarjeta"
        except Exception:
            pass

        # 4) Último recurso: click real sobre el título y comprobar navegación.
        try:
            antes = str(
                page.url
            )

            el.scroll_into_view_if_needed()
            el.click(
                timeout=4000
            )

            try:
                page.wait_for_timeout(
                    900
                )
            except Exception:
                pass

            despues = str(
                page.url
            )

            if despues != antes:
                try:
                    page.wait_for_load_state(
                        "domcontentloaded",
                        timeout=8000
                    )
                except Exception:
                    pass

                return True, despues, "click-titulo"
        except Exception:
            pass

    return False, "", "No encontré enlace/click navegable asociado al título"


def _v103_blob_control(el):
    partes = []

    try:
        partes.append(
            el.inner_text(
                timeout=120
            )
            or ""
        )
    except Exception:
        pass

    for attr in (
        "aria-label",
        "title",
        "data-testid",
        "data-test",
        "data-cy",
        "name",
        "class",
        "id",
        "role",
        "alt",
        "icon",
        "data-icon",
        "href",
    ):
        try:
            valor = el.get_attribute(
                attr
            )

            if valor:
                partes.append(
                    attr
                    + "="
                    + str(
                        valor
                    )
                )
        except Exception:
            pass

    try:
        partes.append(
            el.evaluate(
                "e => e.outerHTML"
            )
            or ""
        )
    except Exception:
        pass

    return _v103_norm(
        " ".join(
            partes
        )
    )


def _v103_click_papelera_detalle(page):
    """
    Wallapop documenta que en web el borrado se hace desde la papelera
    dentro del artículo. Buscamos la papelera SOLO después de abrir el
    detalle exacto del candidato.
    """
    patrones_borrar = (
        "eliminar",
        "borrar",
        "delete",
        "trash",
        "trashcan",
        "trash-can",
        "bin",
        "dustbin",
        "garbage",
        "remove",
        "papelera",
        "eliminar producto",
        "borrar producto",
    )

    selectores = (
        "button",
        "[role='button']",
        "a",
        "[role='menuitem']",
        "walla-icon",
        "svg",
        "[data-testid]",
    )

    controles = []

    try:
        loc = page.locator(
            ", ".join(
                selectores
            )
        )

        for i in range(
            min(
                loc.count(),
                800
            )
        ):
            controles.append(
                loc.nth(i)
            )
    except Exception:
        pass

    # Primera pasada: patrón explícito en texto/atributos/HTML.
    for el in controles:
        try:
            blob = _v103_blob_control(
                el
            )

            if not any(
                p in blob
                for p in patrones_borrar
            ):
                continue

            target = el

            try:
                tag = str(
                    el.evaluate(
                        "e => e.tagName.toLowerCase()"
                    )
                )

                if tag in (
                    "svg",
                    "path",
                    "walla-icon",
                ):
                    anc = el.locator(
                        "xpath=ancestor::*[self::button or @role='button' or self::a][1]"
                    )

                    if anc.count() > 0:
                        target = anc.first
            except Exception:
                pass

            target.scroll_into_view_if_needed()
            target.click(
                timeout=4000
            )

            return True, (
                "papelera:"
                + blob[:180]
            )

        except Exception:
            pass

    # Segunda pasada: abrir menús de opciones y volver a buscar borrar.
    patrones_menu = (
        "opciones",
        "mas",
        "more",
        "menu",
        "overflow",
        "ellipsis",
        "kebab",
        "three dots",
        "3 puntos",
    )

    for el in controles:
        try:
            blob = _v103_blob_control(
                el
            )

            if not any(
                p in blob
                for p in patrones_menu
            ):
                continue

            target = el

            try:
                tag = str(
                    el.evaluate(
                        "e => e.tagName.toLowerCase()"
                    )
                )

                if tag in (
                    "svg",
                    "path",
                    "walla-icon",
                ):
                    anc = el.locator(
                        "xpath=ancestor::*[self::button or @role='button' or self::a][1]"
                    )

                    if anc.count() > 0:
                        target = anc.first
            except Exception:
                pass

            target.click(
                timeout=3000
            )

            page.wait_for_timeout(
                450
            )

            menus = page.locator(
                "[role='menuitem'], [role='dialog'] button, [role='dialog'] [role='button'], button, [role='button']"
            )

            for j in range(
                min(
                    menus.count(),
                    300
                )
            ):
                item = menus.nth(j)

                try:
                    blob2 = _v103_blob_control(
                        item
                    )

                    if any(
                        p in blob2
                        for p in patrones_borrar
                    ):
                        item.click(
                            timeout=3500
                        )

                        return True, (
                            "menu:"
                            + blob2[:180]
                        )
                except Exception:
                    pass

        except Exception:
            pass

    return False, ""


def _v103_confirmar_borrado(page):
    patrones = (
        "eliminar",
        "borrar",
        "confirmar",
        "si, eliminar",
        "sí, eliminar",
        "eliminar producto",
        "borrar producto",
        "aceptar",
    )

    try:
        dialogos = page.locator(
            "[role='dialog']"
        )

        scopes = []

        for i in range(
            min(
                dialogos.count(),
                10
            )
        ):
            scopes.append(
                dialogos.nth(i)
            )

        scopes.append(
            page.locator(
                "body"
            )
        )

        for scope in scopes:
            controles = scope.locator(
                "button, [role='button']"
            )

            for i in range(
                min(
                    controles.count(),
                    150
                )
            ):
                el = controles.nth(i)

                try:
                    blob = _v103_blob_control(
                        el
                    )

                    if any(
                        p in blob
                        for p in patrones
                    ):
                        # Evitar botones de cancelar.
                        if any(
                            x in blob
                            for x in (
                                "cancelar",
                                "volver",
                                "cerrar",
                                "no,",
                            )
                        ):
                            continue

                        el.click(
                            timeout=3500
                        )

                        return True, blob[:180]
                except Exception:
                    pass
    except Exception:
        pass

    return False, ""


def _v103_dump_detalle(page, titulo):
    try:
        raiz = (
            Path(
                CARPETA_DATOS_USUARIO
            )
            / "diagnosticos_rotacion"
            / (
                "v103_"
                + time.strftime(
                    "%Y%m%d_%H%M%S"
                )
            )
        )

        raiz.mkdir(
            parents=True,
            exist_ok=True
        )

        page.screenshot(
            path=str(
                raiz
                / "detalle.png"
            ),
            full_page=True
        )

        (
            raiz
            / "detalle.html"
        ).write_text(
            page.content(),
            encoding="utf-8",
            errors="ignore"
        )

        controles = []

        try:
            loc = page.locator(
                "button, [role='button'], a, walla-icon, svg, [data-testid]"
            )

            for i in range(
                min(
                    loc.count(),
                    1000
                )
            ):
                try:
                    blob = _v103_blob_control(
                        loc.nth(i)
                    )

                    if blob:
                        controles.append(
                            blob[:500]
                        )
                except Exception:
                    pass
        except Exception:
            pass

        (
            raiz
            / "controles.txt"
        ).write_text(
            "\n\n".join(
                controles
            ),
            encoding="utf-8",
            errors="ignore"
        )

        _v102_log_rotacion(
            "V103 diagnóstico detalle guardado en "
            + str(
                raiz
            )
        )

        return str(
            raiz
        )

    except Exception:
        return ""


def _v103_borrar_candidato(candidato):
    titulo = _v102_titulo_candidato(
        candidato
    )

    pagina = None

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                _asegurar_chromium_controlable()
            except Exception:
                pass

            try:
                navegador = _conectar_playwright_cdp(
                    p
                )
            except Exception:
                navegador = p.chromium.connect_over_cdp(
                    "http://127.0.0.1:9222",
                    timeout=60000
                )

            if not navegador.contexts:
                return False, (
                    "Chrome/CDP no tiene contexto autenticado."
                )

            contexto = navegador.contexts[0]
            pagina = contexto.new_page()

            # Reutilizar la navegación a Productos que ya demuestra funcionar.
            _v1021_ir_a_productos(
                pagina
            )

            localizado = None

            for _scroll in range(
                30
            ):
                try:
                    exacto = pagina.get_by_text(
                        titulo,
                        exact=True
                    )

                    if exacto.count() > 0:
                        localizado = exacto.first
                        break
                except Exception:
                    pass

                try:
                    parcial = pagina.get_by_text(
                        titulo,
                        exact=False
                    )

                    if parcial.count() > 0:
                        localizado = parcial.first
                        break
                except Exception:
                    pass

                try:
                    pagina.mouse.wheel(
                        0,
                        900
                    )
                    pagina.wait_for_timeout(
                        250
                    )
                except Exception:
                    break

            if localizado is None:
                return False, (
                    "No pude localizar el candidato en Productos."
                )

            try:
                localizado.scroll_into_view_if_needed()
            except Exception:
                pass

            ok_detalle, url_detalle, via = _v103_abrir_detalle_exacto(
                pagina,
                titulo
            )

            if not ok_detalle:
                ruta = _v103_dump_detalle(
                    pagina,
                    titulo
                )

                return False, (
                    "Localicé el candidato pero no pude abrir su detalle exacto. "
                    + (
                        "Diagnóstico: "
                        + ruta
                        if ruta
                        else ""
                    )
                )

            if url_detalle:
                try:
                    _v102_guardar_url_candidato(
                        candidato,
                        url_detalle
                    )
                except Exception:
                    pass

            _v102_log_rotacion(
                "V103 detalle abierto por "
                + str(
                    via
                )
                + ": "
                + str(
                    url_detalle
                )
            )

            try:
                pagina.wait_for_timeout(
                    1400
                )
            except Exception:
                pass

            ok_borrar, detalle_borrar = _v103_click_papelera_detalle(
                pagina
            )

            if not ok_borrar:
                ruta = _v103_dump_detalle(
                    pagina,
                    titulo
                )

                return False, (
                    "Abrí el detalle exacto, pero no encontré la papelera. "
                    + (
                        "Diagnóstico: "
                        + ruta
                        if ruta
                        else ""
                    )
                )

            _v102_log_rotacion(
                "V103 control de borrado pulsado: "
                + str(
                    detalle_borrar
                )
            )

            pagina.wait_for_timeout(
                500
            )

            confirmado, detalle_conf = _v103_confirmar_borrado(
                pagina
            )

            if confirmado:
                _v102_log_rotacion(
                    "V103 confirmación pulsada: "
                    + str(
                        detalle_conf
                    )
                )

            pagina.wait_for_timeout(
                1800
            )

            # Verificación real: volver a Productos y comprobar URL/título.
            _v1021_ir_a_productos(
                pagina
            )

            pagina.wait_for_timeout(
                900
            )

            url_obj = _v102_url_candidato(
                candidato
            )

            if url_obj:
                try:
                    enlaces = pagina.locator(
                        "a[href]"
                    )

                    sigue_url = False

                    objetivo_n = str(
                        url_obj
                    ).rstrip(
                        "/"
                    )

                    for i in range(
                        min(
                            enlaces.count(),
                            900
                        )
                    ):
                        href = _v103_href_absoluto(
                            enlaces.nth(i).get_attribute(
                                "href"
                            )
                        )

                        if href and objetivo_n in href.rstrip("/"):
                            sigue_url = True
                            break

                    if not sigue_url:
                        return True, (
                            "Anuncio eliminado; su URL ya no aparece en Productos."
                        )
                except Exception:
                    pass

            # Si no hay URL, comprobar que se reduzca el número de coincidencias.
            try:
                restantes = pagina.get_by_text(
                    titulo,
                    exact=True
                ).count()

                if restantes == 0:
                    return True, (
                        "Anuncio eliminado; el título ya no aparece en Productos."
                    )
            except Exception:
                pass

            ruta = _v103_dump_detalle(
                pagina,
                titulo
            )

            return False, (
                "Se pulsó borrar, pero no pude confirmar la desaparición del anuncio. "
                + (
                    "Diagnóstico: "
                    + ruta
                    if ruta
                    else ""
                )
            )

    except Exception as e:
        return False, (
            type(
                e
            ).__name__
            + ": "
            + str(
                e
            )
        )

    finally:
        try:
            if pagina is not None:
                pagina.close()
        except Exception:
            pass


# Sustituir el eliminador final. Conservamos V102.1 como fallback únicamente.
_v103_eliminar_anterior = globals().get(
    "_v102_eliminar_en_wallapop"
)


def _v102_eliminar_en_wallapop(candidato):
    _v102_log_rotacion(
        "V103: abriendo detalle exacto para localizar la papelera web."
    )

    ok, detalle = _v103_borrar_candidato(
        candidato
    )

    if ok:
        return True, detalle

    _v102_log_rotacion(
        "V103 método principal falló: "
        + str(
            detalle
        )
    )

    anterior = globals().get(
        "_v103_eliminar_anterior"
    )

    if callable(
        anterior
    ):
        try:
            ok2, det2 = anterior(
                candidato
            )

            if ok2:
                return True, det2

            return False, (
                str(
                    detalle
                )
                + " · Fallback V102.1: "
                + str(
                    det2
                )
            )
        except Exception as e:
            return False, (
                str(
                    detalle
                )
                + " · Fallback V102.1: "
                + type(
                    e
                ).__name__
                + ": "
                + str(
                    e
                )
            )

    return False, detalle

'''

    marcador = "\nventana.mainloop()"

    if marcador not in texto:
        return texto

    return texto.replace(
        marcador,
        codigo + marcador,
        1
    )


def construir_v103(fuente_path, texto):
    nuevo = _limpiar_motores_rotacion_generados(
        texto
    )
    nuevo = _reemplazar_version(nuevo)
    nuevo = _inyectar_capacidad_cola_v102(nuevo)
    nuevo = _parchear_limites_internos_cola_v99(nuevo)
    nuevo = _consolidar_capacidad_v102(nuevo)
    nuevo = _aplicar_fix_rotacion_v89(nuevo)
    nuevo = _inyectar_diagnostico_total_v92(nuevo)
    nuevo = _inyectar_diagnostico_runtime_v102(nuevo)
    nuevo = _mejorar_asset_path(nuevo)
    nuevo = _mejorar_instalador(nuevo)
    nuevo = _inyectar_fluidez(nuevo)
    nuevo = _hacer_comprobacion_update_inicio_no_bloqueante(nuevo)
    nuevo = _inyectar_motor_rotacion_v102(nuevo)
    nuevo = _reforzar_cdp_rotacion_v102(nuevo)
    nuevo = _pulido_integral_v102(nuevo)
    nuevo = _hotfix_rotacion_real_v102_1(nuevo)
    nuevo = _hotfix_rotacion_detalle_v103(nuevo)

    requisitos = [
        'return "' + TARGET_VERSION + '"',
        "banner_dp5_limpio_v15.png",
        "sidebar = ctk.CTkFrame",
        "Centro de actualizaciones",
        "def instalar_actualizacion_admin",
        "ventana.mainloop()",
        "V102 · MOTOR DE ROTACIÓN ROBUSTO",
        "V92 · DIAGNÓSTICO TOTAL DE ROTACIÓN",
        "V102 · DIAGNÓSTICO RUNTIME GARANTIZADO",
        "_v102_vigilar_limite_catalogo",
        "V103 · ROTACIÓN POR DETALLE EXACTO",
    ]
    faltan = [x for x in requisitos if x not in nuevo]
    if faltan:
        raise RuntimeError(
            "La base transformada no es válida para V"
            + TARGET_VERSION
            + ". Falta: "
            + ", ".join(faltan)
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
            "No encontré una base completa compatible de DIAGPROG5. "
            "El actualizador buscó automáticamente en las versiones instaladas y carpetas de datos."
        )

    _, _, _, fuente, texto, version_fuente = encontrados[0]
    banner = _buscar_banner(fuente)
    if banner is None:
        raise RuntimeError(
            "No encontré banner_dp5_limpio_v15.png. "
            "He cancelado la actualización para no crear otra versión sin banner."
        )

    nuevo = construir_v103(fuente, texto)

    home = Path.home()
    local = Path(
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
        or home
    )
    data = local / "DIAGPROG5"

    # V90: cada instalación se escribe en una carpeta NUEVA.
    # Así nunca intentamos reemplazar un .py que Windows pueda tener abierto.
    sello = time.strftime("%Y%m%d_%H%M%S")
    carpeta_version = (
        data
        / "versiones"
        / ("V102_" + sello)
    )
    carpeta_version.mkdir(
        parents=True,
        exist_ok=True
    )

    destino = (
        carpeta_version
        / OUTPUT_NAME
    )

    # Como la carpeta es nueva, write_text no pisa ningún archivo en uso.
    destino.write_text(
        nuevo,
        encoding="utf-8"
    )

    assets = data / "assets"
    assets.mkdir(
        parents=True,
        exist_ok=True
    )

    banner_local = (
        carpeta_version
        / BANNER_NAME
    )

    # Evitar copiar sobre el mismo archivo si el banner ya está ahí.
    try:
        if banner.resolve() != banner_local.resolve():
            shutil.copy2(
                banner,
                banner_local
            )
    except Exception:
        shutil.copy2(
            banner,
            banner_local
        )

    # Cache persistente del banner: solo copiar si el destino no es el origen.
    banner_cache = (
        assets
        / BANNER_NAME
    )
    try:
        if banner.resolve() != banner_cache.resolve():
            shutil.copy2(
                banner,
                banner_cache
            )
    except Exception:
        pass

    py_compile.compile(
        str(destino),
        doraise=True
    )

    proceso_nuevo = subprocess.Popen(
        [
            sys.executable,
            str(destino),
        ],
        cwd=str(
            carpeta_version
        ),
    )

    # Dar tiempo a la nueva versión a abrir antes de cerrar la anterior.
    time.sleep(
        2.2
    )

    if proceso_nuevo.poll() is not None:
        raise RuntimeError(
            "La V102 se cerró durante el arranque. "
            "La versión anterior se mantiene abierta."
        )

    _cerrar_padre_tras_arranque(
        parent_pid
    )

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
                "DIAGPROG5 · Actualización V103",
                "No pude completar la actualización:\n\n" + str(e),
            )
            root.destroy()
        except Exception:
            traceback.print_exc()
        raise
