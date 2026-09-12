from pathlib import Path
import os
import re
import sys
import time
import shutil
import subprocess
import py_compile
import traceback

TARGET_VERSION = "93"
OUTPUT_NAME = "bot_wallapop_profesional_v93_ADMIN_DIAGNOSTICO_TOTAL.py"
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
# V93 · CAPA DE FLUIDEZ DE INTERFAZ
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
    print("[V93] Capa de fluidez dashboard no aplicada:", _e_v89_ui)

"""


def _inyectar_fluidez(texto):
    if "V93 · CAPA DE FLUIDEZ DE INTERFAZ" in texto:
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
    nuevo = """# Comprobación silenciosa del servidor de actualizaciones (V93, no bloqueante).
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
                "V93 ya migró automáticamente los publicados.json antiguos. "
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
        _diag_log_path = Path(CARPETA_DATOS_USUARIO) / "rotacion_v93.log"
        if not _diag_log_path.exists():
            _diag_log_path = Path(CARPETA_DATOS_USUARIO) / "rotacion_v93.log"

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
                "_ROTACION_V93_EN_CURSO",
                globals().get(
                    "_ROTACION_V93_EN_CURSO",
                    False
                )
            )
        )
        _diag_motor_ultimo = str(
            globals().get(
                "_ROTACION_V93_ULTIMO",
                globals().get(
                    "_ROTACION_V93_ULTIMO",
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


def _inyectar_motor_rotacion_v93(texto):
    if "V93 · MOTOR DE ROTACIÓN ROBUSTO" in texto:
        return texto

    codigo = r'''

# =========================================================
# V93 · MOTOR DE ROTACIÓN ROBUSTO
# =========================================================
# Objetivo:
# LIMITE_CATALOGO -> eliminar 1 candidato seguro -> confirmar -> reintentar.
# Nunca elimina anuncios protegidos ni anuncios ajenos al registro local.

_ROTACION_V93_LOCK = threading.Lock()
_ROTACION_V93_PROCESADOS = set()
_ROTACION_V93_ULTIMO = ""
_ROTACION_V93_EN_CURSO = False


def _v93_log_rotacion(texto):
    global _ROTACION_V93_ULTIMO

    _ROTACION_V93_ULTIMO = str(
        texto
    )

    try:
        ruta = (
            Path(
                CARPETA_DATOS_USUARIO
            )
            / "rotacion_v93.log"
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
        "[ROTACION V93]",
        texto
    )


def _v93_rotacion_activa():
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


def _v93_es_protegido(item):
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


def _v93_fecha_epoch(item):
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


def _v93_candidatos_locales():
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
                "_v93_"
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
                        and not _v93_es_protegido(
                            x
                        )
                    ]

                    if seguros:
                        seguros.sort(
                            key=_v93_fecha_epoch
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

        if _v93_es_protegido(
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

        if _v93_fecha_epoch(
            candidato
        ) > limite_epoch:
            continue

        candidatos.append(
            candidato
        )

    candidatos.sort(
        key=_v93_fecha_epoch
    )

    return candidatos


def _v93_url_candidato(item):
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


def _v93_titulo_candidato(item):
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


def _v93_click_visible(page, textos, timeout=2500):
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


def _v93_abrir_candidato(page, candidato):
    url = _v93_url_candidato(
        candidato
    )

    titulo = _v93_titulo_candidato(
        candidato
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

    # Sin URL guardada: entrar en el área propia y localizarlo por título.
    rutas = (
        "https://es.wallapop.com/app/user",
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


def _v93_eliminar_con_motor_existente(candidato):
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
            "_v93_"
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
            _v93_log_rotacion(
                "Motor interno "
                + nombre
                + " no pudo usarse: "
                + str(
                    e
                )
            )

    return False, ""


def _v93_eliminar_en_wallapop(candidato):
    titulo = _v93_titulo_candidato(
        candidato
    )

    _v93_log_rotacion(
        "Intentando eliminar candidato: "
        + (
            titulo
            or "(sin título)"
        )
    )

    # Primero reutilizar el motor ya presente en DIAGPROG5.
    ok_interno, detalle_interno = _v93_eliminar_con_motor_existente(
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

            if not _v93_abrir_candidato(
                pagina,
                candidato
            ):
                return False, (
                    "No pude abrir el anuncio candidato en Wallapop."
                )

            # Algunos diseños esconden borrar en un menú.
            _v93_click_visible(
                pagina,
                (
                    "Más opciones",
                    "Opciones",
                    "Más",
                ),
                timeout=1800
            )

            pagina.wait_for_timeout(
                350
            )

            eliminado_click = _v93_click_visible(
                pagina,
                (
                    "Eliminar producto",
                    "Eliminar anuncio",
                    "Borrar producto",
                    "Borrar anuncio",
                    "Eliminar",
                ),
                timeout=3500
            )

            if not eliminado_click:
                # Fallback: botones/elementos cuyo texto contenga eliminar/borrar.
                try:
                    loc = pagina.locator(
                        "button, [role='button'], a"
                    )

                    total = min(
                        loc.count(),
                        250
                    )

                    for i in range(
                        total
                    ):
                        el = loc.nth(
                            i
                        )

                        try:
                            txt = (
                                el.inner_text(
                                    timeout=300
                                )
                                or ""
                            ).strip().lower()

                            if (
                                "eliminar" in txt
                                or "borrar" in txt
                            ):
                                el.click(
                                    timeout=2000
                                )
                                eliminado_click = True
                                break
                        except Exception:
                            pass
                except Exception:
                    pass

            if not eliminado_click:
                return False, (
                    "Abrí el anuncio pero no encontré el control Eliminar/Borrar."
                )

            pagina.wait_for_timeout(
                500
            )

            # Confirmación.
            _v93_click_visible(
                pagina,
                (
                    "Sí, eliminar",
                    "Eliminar definitivamente",
                    "Confirmar",
                    "Eliminar",
                    "Sí",
                ),
                timeout=3500
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
            url = _v93_url_candidato(
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


def _v93_marcar_local_eliminado(candidato):
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

            guardar_publicados(
                datos
            )

            return

        titulo = _v93_titulo_candidato(
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

                guardar_publicados(
                    datos
                )

                return

    except Exception as e:
        _v93_log_rotacion(
            "Wallapop eliminó el anuncio, pero no pude actualizar publicados.json: "
            + str(
                e
            )
        )


def _v93_rotar_una_vez():
    if not _v93_rotacion_activa():
        return False, (
            "Rotación desactivada."
        )

    candidatos = _v93_candidatos_locales()

    if not candidatos:
        return False, (
            "No hay candidatos seguros elegibles."
        )

    candidato = candidatos[0]

    ok, detalle = _v93_eliminar_en_wallapop(
        candidato
    )

    if not ok:
        return False, (
            "Candidato "
            + (
                _v93_titulo_candidato(
                    candidato
                )
                or "(sin título)"
            )
            + ": "
            + str(
                detalle
            )
        )

    _v93_marcar_local_eliminado(
        candidato
    )

    _v93_log_rotacion(
        "Eliminado correctamente: "
        + (
            _v93_titulo_candidato(
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
            _v93_titulo_candidato(
                candidato
            )
            or "(sin título)"
        )
        + ". Hueco liberado."
    )


def _v93_error_item(item):
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


def _v93_reactivar_item(item, detalle):
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
        _v93_log_rotacion(
            "No pude reactivar el anuncio: "
            + str(
                e
            )
        )


def _v93_reanudar_cola():
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


def _v93_worker_limite(item, clave):
    global _ROTACION_V93_EN_CURSO

    if not _ROTACION_V93_LOCK.acquire(
        blocking=False
    ):
        return

    _ROTACION_V93_EN_CURSO = True

    try:
        _v93_log_rotacion(
            "LIMITE_CATALOGO detectado. Iniciando rotación segura."
        )

        ok, detalle = _v93_rotar_una_vez()

        if ok:
            _v93_reactivar_item(
                item,
                detalle
            )

            _v93_log_rotacion(
                detalle
                + " Reintentando el mismo anuncio."
            )

            try:
                ventana.after(
                    300,
                    _v93_reanudar_cola
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
                    "LIMITE_CATALOGO · V93: "
                    + _detalle_corto[:180]
                )

                item[
                    "rotacion_detalle"
                ] = (
                    "V93: "
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

            _v93_log_rotacion(
                "Rotación fallida: "
                + str(
                    detalle
                )
            )

    finally:
        _ROTACION_V93_EN_CURSO = False

        try:
            _ROTACION_V93_PROCESADOS.add(
                clave
            )
        except Exception:
            pass

        try:
            _ROTACION_V93_LOCK.release()
        except Exception:
            pass


def _v93_vigilar_limite_catalogo():
    try:
        if (
            _v93_rotacion_activa()
            and not _ROTACION_V93_EN_CURSO
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

                error = _v93_error_item(
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

                if clave in _ROTACION_V93_PROCESADOS:
                    continue

                try:
                    item[
                        "rotacion_detalle"
                    ] = "V93: límite detectado; buscando candidato seguro..."

                    guardar_cola()
                    refrescar_cola()
                except Exception:
                    pass

                threading.Thread(
                    target=_v93_worker_limite,
                    args=(
                        item,
                        clave,
                    ),
                    daemon=True
                ).start()

                break

    except Exception as e:
        _v93_log_rotacion(
            "Watchdog: "
            + str(
                e
            )
        )

    finally:
        try:
            ventana.after(
                900,
                _v93_vigilar_limite_catalogo
            )
        except Exception:
            pass


try:
    ventana.after(
        1800,
        _v93_vigilar_limite_catalogo
    )
except Exception as _e_v93_rot:
    print(
        "[ROTACION V93] No pude iniciar watchdog:",
        _e_v93_rot
    )

'''

    marcador = "\nventana.mainloop()"

    if marcador not in texto:
        raise RuntimeError(
            "No pude insertar el motor V93 antes del mainloop."
        )

    return texto.replace(
        marcador,
        codigo + marcador,
        1
    )



def _inyectar_diagnostico_runtime_v93(texto):
    if "V93 · DIAGNÓSTICO RUNTIME GARANTIZADO" in texto:
        return texto

    codigo = r'''

# =========================================================
# V93 · DIAGNÓSTICO RUNTIME GARANTIZADO
# =========================================================
# Intercepta únicamente el diagnóstico de rotación y muestra una ventana
# desplazable con TODO lo necesario para depurar en una sola captura.

_DIAG_V93_SHOWINFO_ORIGINAL = messagebox.showinfo


def _v93_serializar_seguro(valor):
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


def _v93_texto_cola_completo():
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
                    + _v93_serializar_seguro(
                        valor
                    ).replace(
                        "\n",
                        " "
                    )
                )

    return "\n".join(
        lineas
    )


def _v93_log_rotacion_texto():
    rutas = [
        Path(
            CARPETA_DATOS_USUARIO
        )
        / "rotacion_v93.log",
        Path(
            CARPETA_DATOS_USUARIO
        )
        / "rotacion_v93.log",
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


def _v93_candidatos_resumen():
    candidatos = []

    try:
        funcion = globals().get(
            "_v93_candidatos_locales"
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
                        "_v93_"
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


def _v93_estado_motor():
    claves = [
        "_ROTACION_V93_EN_CURSO",
        "_ROTACION_V91_EN_CURSO",
        "_ROTACION_V93_ULTIMO",
        "_ROTACION_V91_ULTIMO",
    ]

    lineas = []

    for clave in claves:
        if clave in globals():
            lineas.append(
                clave
                + " = "
                + _v93_serializar_seguro(
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


def _v93_abrir_informe_rotacion(texto_base=""):
    try:
        ventana_diag = ctk.CTkToplevel(
            ventana
        )

        ventana_diag.title(
            "DIAGPROG5 · Diagnóstico total de rotación V93"
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
            text="DIAGNÓSTICO TOTAL DE ROTACIÓN · V93",
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
            _v93_estado_motor(),
            "",
            "================ CANDIDATOS ================",
            _v93_candidatos_resumen(),
            "",
            "================ COLA / ERRORES SIN CORTAR ================",
            _v93_texto_cola_completo(),
            "",
            "================ LOG ROTACIÓN ================",
            _v93_log_rotacion_texto(),
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
            "[V93 DIAG] No pude abrir informe total:",
            e
        )

        return False


def _v93_showinfo(title, message, *args, **kwargs):
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
                    lambda m=mensaje: _v93_abrir_informe_rotacion(
                        m
                    )
                )

                return "ok"
            except Exception:
                pass

    except Exception:
        pass

    return _DIAG_V93_SHOWINFO_ORIGINAL(
        title,
        message,
        *args,
        **kwargs
    )


messagebox.showinfo = _v93_showinfo

'''

    marcador = "\nventana.mainloop()"

    if marcador not in texto:
        return texto

    return texto.replace(
        marcador,
        codigo + marcador,
        1
    )


def construir_v93(fuente_path, texto):
    nuevo = _reemplazar_version(texto)
    nuevo = _aplicar_fix_rotacion_v89(nuevo)
    nuevo = _inyectar_diagnostico_total_v92(nuevo)
    nuevo = _inyectar_diagnostico_runtime_v93(nuevo)
    nuevo = _mejorar_asset_path(nuevo)
    nuevo = _mejorar_instalador(nuevo)
    nuevo = _inyectar_fluidez(nuevo)
    nuevo = _hacer_comprobacion_update_inicio_no_bloqueante(nuevo)
    nuevo = _inyectar_motor_rotacion_v93(nuevo)

    requisitos = [
        'return "' + TARGET_VERSION + '"',
        "banner_dp5_limpio_v15.png",
        "sidebar = ctk.CTkFrame",
        "Centro de actualizaciones",
        "def instalar_actualizacion_admin",
        "ventana.mainloop()",
        "V93 · MOTOR DE ROTACIÓN ROBUSTO",
        "V92 · DIAGNÓSTICO TOTAL DE ROTACIÓN",
        "V93 · DIAGNÓSTICO RUNTIME GARANTIZADO",
        "_v93_vigilar_limite_catalogo",
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
            "No encontré una instalación completa de DIAGPROG5 para actualizar. "
            "Conserva abierta una versión completa de DIAGPROG5 y vuelve a pulsar Actualizar."
        )

    _, _, _, fuente, texto, version_fuente = encontrados[0]
    banner = _buscar_banner(fuente)
    if banner is None:
        raise RuntimeError(
            "No encontré banner_dp5_limpio_v15.png. "
            "He cancelado la actualización para no crear otra versión sin banner."
        )

    nuevo = construir_v93(fuente, texto)

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
        / ("V89_3_" + sello)
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
            "La V90 se cerró durante el arranque. "
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
                "DIAGPROG5 · Actualización V93",
                "No pude completar la actualización:\n\n" + str(e),
            )
            root.destroy()
        except Exception:
            traceback.print_exc()
        raise
