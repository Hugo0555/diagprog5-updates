from pathlib import Path
import sys, subprocess, py_compile, json, time, traceback

OUTPUT_NAME = "bot_wallapop_profesional_v87_ADMIN_AUTOUPDATE_REAL.py"

HELPERS = r'''
def _registrar_actualizacion_historial(
    accion,
    version="",
    detalle=""
):
    try:
        ruta = Path(
            ARCHIVO_HISTORIAL_ACTUALIZACIONES
        )

        historial = []

        if ruta.exists():
            try:
                datos = json.loads(
                    ruta.read_text(
                        encoding="utf-8"
                    )
                )
                if isinstance(datos, list):
                    historial = datos
            except Exception:
                historial = []

        historial.append({
            "fecha": time.strftime(
                "%d/%m/%Y %H:%M:%S"
            ),
            "accion": str(accion),
            "version": str(version),
            "detalle": str(detalle),
        })

        historial = historial[-200:]

        ruta.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        ruta.write_text(
            json.dumps(
                historial,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )
    except Exception:
        pass


def _limpiar_carpeta_conservar_ultimos(
    carpeta,
    patron="*",
    conservar=3
):
    try:
        ruta = Path(carpeta)

        if not ruta.exists():
            return 0

        archivos = [
            p for p in ruta.glob(patron)
            if p.is_file()
        ]

        archivos.sort(
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        eliminados = 0

        for antiguo in archivos[
            max(0, int(conservar)):
        ]:
            try:
                antiguo.unlink()
                eliminados += 1
            except Exception:
                pass

        return eliminados

    except Exception:
        return 0


def limpiar_archivos_actualizacion_antiguos():
    eliminados = 0

    eliminados += _limpiar_carpeta_conservar_ultimos(
        CARPETA_ACTUALIZACIONES,
        patron="*.py",
        conservar=MAX_VERSIONES_ACTUALIZACION_GUARDADAS
    )

    carpeta_backup = (
        Path(
            CARPETA_DATOS_USUARIO
        )
        / "backups_actualizaciones"
    )

    eliminados += _limpiar_carpeta_conservar_ultimos(
        carpeta_backup,
        patron="*.py",
        conservar=MAX_BACKUPS_ACTUALIZACION_GUARDADOS
    )

    if eliminados:
        _registrar_actualizacion_historial(
            "LIMPIEZA",
            version_actual_bot(),
            f"Eliminados {eliminados} archivo(s) antiguo(s)."
        )

    return eliminados


def _archivo_descargado_es_valido(
    ruta,
    sha_esperado=""
):
    ruta = Path(ruta)

    if not ruta.exists() or not ruta.is_file():
        return False

    if sha_esperado:
        try:
            return (
                _sha256_archivo(
                    ruta
                ).lower()
                == str(
                    sha_esperado
                ).strip().lower()
            )
        except Exception:
            return False

    if ruta.suffix.lower() == ".py":
        try:
            compile(
                ruta.read_text(
                    encoding="utf-8"
                ),
                str(ruta),
                "exec"
            )
            return True
        except Exception:
            return False

    return True


'''

def require_replace(text, old, new, label):
    if old not in text:
        raise RuntimeError(
            f"No encontré el bloque necesario: {label}"
        )
    return text.replace(
        old,
        new,
        1
    )


def find_v86(data_dir):
    """
    Busca específicamente la V86 que contiene la interfaz aprobada.
    Evita usar backups antiguos/sin banner.
    """
    backups = data_dir / "backups_actualizaciones"
    candidates = []

    if backups.exists():
        candidates += list(
            backups.glob("*.py")
        )

    # También buscar junto a la carpeta de datos, por si la copia válida
    # quedó en una ubicación distinta durante una actualización anterior.
    try:
        candidates += list(
            data_dir.rglob("*v86*.py")
        )
    except Exception:
        pass

    unicos = []
    vistos = set()

    for p in candidates:
        try:
            rp = p.resolve()
        except Exception:
            rp = p

        if str(rp) in vistos:
            continue

        vistos.add(
            str(rp)
        )

        if p.is_file():
            unicos.append(
                p
            )

    # Más reciente primero.
    unicos.sort(
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    for p in unicos:
        try:
            t = p.read_text(
                encoding="utf-8"
            )

            # Exigimos tanto V86 como las marcas de la interfaz aprobada.
            if (
                'return "86"' in t
                and "DIAGPROG5" in t
                and "banner_dp5_limpio_v15.png" in t
                and "UI V86 · DISEÑO APROBADO" in t
                and "ACTUALIZACIONES · ADMIN" in t
            ):
                return p

        except Exception:
            pass

    return None


def copiar_banner_interfaz(source, target_dir):
    """
    Copia el banner aprobado junto a la nueva versión.
    """
    nombre = "banner_dp5_limpio_v15.png"

    candidatos = [
        source.parent / nombre,
        source.parent.parent / nombre,
        Path.cwd() / nombre,
    ]

    try:
        candidatos += list(
            source.parent.parent.rglob(
                nombre
            )
        )
    except Exception:
        pass

    for ruta in candidatos:
        try:
            if ruta.is_file():
                destino = (
                    target_dir
                    / nombre
                )

                if (
                    not destino.exists()
                    or destino.stat().st_size
                    != ruta.stat().st_size
                ):
                    import shutil

                    shutil.copy2(
                        ruta,
                        destino
                    )

                return destino

        except Exception:
            pass

    return None


def construir_v87(original):
    text = original

    text = require_replace(
        text,
        'def version_actual_bot():\n    return "86"',
        'def version_actual_bot():\n    return "87"',
        "version_actual_bot"
    )

    marker = '''CARPETA_ACTUALIZACIONES = os.path.join(
    CARPETA_DATOS_USUARIO,
    "actualizaciones"
)
'''

    extra = marker + '''
MAX_VERSIONES_ACTUALIZACION_GUARDADAS = 3
MAX_BACKUPS_ACTUALIZACION_GUARDADOS = 3

ARCHIVO_HISTORIAL_ACTUALIZACIONES = os.path.join(
    CARPETA_DATOS_USUARIO,
    "historial_actualizaciones.json"
)
'''

    text = require_replace(
        text,
        marker,
        extra,
        "constantes del actualizador"
    )

    text = require_replace(
        text,
        'def descargar_actualizacion_admin(\n',
        HELPERS + 'def descargar_actualizacion_admin(\n',
        "helpers del actualizador"
    )

    needle = '''        destino = carpeta / nombre

        estado.configure(
            text=f"⬇ Descargando actualización V{version}..."
        )
'''

    repl = '''        destino = carpeta / nombre

        sha_esperado = str(
            manifest.get(
                "sha256",
                ""
            )
        ).strip().lower()

        if _archivo_descargado_es_valido(
            destino,
            sha_esperado
        ):
            estado.configure(
                text=(
                    f"✅ V{version} ya estaba descargada y verificada."
                )
            )

            _registrar_actualizacion_historial(
                "REUTILIZADA",
                version,
                str(destino)
            )

            return str(
                destino
            )

        estado.configure(
            text=f"⬇ Descargando actualización V{version}..."
        )
'''

    text = require_replace(
        text,
        needle,
        repl,
        "reutilización de descarga"
    )

    duplicate_sha = '''        sha_esperado = str(
            manifest.get(
                "sha256",
                ""
            )
        ).strip().lower()

        if sha_esperado:
'''

    text = require_replace(
        text,
        duplicate_sha,
        '''        if sha_esperado:
''',
        "SHA duplicado"
    )

    needle = '''        estado.configure(
            text=(
                f"✅ Actualización V{version} descargada y verificada."
            )
        )

        return str(
            destino
        )
'''

    repl = '''        estado.configure(
            text=(
                f"✅ Actualización V{version} descargada y verificada."
            )
        )

        _registrar_actualizacion_historial(
            "DESCARGADA",
            version,
            str(destino)
        )

        limpiar_archivos_actualizacion_antiguos()

        return str(
            destino
        )
'''

    text = require_replace(
        text,
        needle,
        repl,
        "registro de descarga"
    )

    old_backup = '''    # Copia de seguridad de la versión actual.
    try:
        actual = Path(
            __file__
        ).resolve()

        carpeta_backup = (
            Path(
                CARPETA_DATOS_USUARIO
            )
            / "backups_actualizaciones"
        )

        carpeta_backup.mkdir(
            parents=True,
            exist_ok=True
        )

        backup = (
            carpeta_backup
            / (
                actual.stem
                + "_"
                + time.strftime(
                    "%Y%m%d_%H%M%S"
                )
                + actual.suffix
            )
        )

        shutil.copy2(
            actual,
            backup
        )

    except Exception:
        backup = None
'''

    new_backup = '''    # Copia de seguridad: solo una copia por versión actual.
    try:
        actual = Path(
            __file__
        ).resolve()

        carpeta_backup = (
            Path(
                CARPETA_DATOS_USUARIO
            )
            / "backups_actualizaciones"
        )

        carpeta_backup.mkdir(
            parents=True,
            exist_ok=True
        )

        backup = (
            carpeta_backup
            / (
                actual.stem
                + "_backup"
                + actual.suffix
            )
        )

        if not backup.exists():
            shutil.copy2(
                actual,
                backup
            )

            _registrar_actualizacion_historial(
                "BACKUP",
                version_actual_bot(),
                str(backup)
            )

    except Exception:
        backup = None
'''

    text = require_replace(
        text,
        old_backup,
        new_backup,
        "backup único"
    )

    needle = '''        estado.configure(
            text=(
                f"✅ Nueva versión V{version} abierta. "
                "Puedes cerrar esta versión cuando compruebes que funciona."
            )
        )
'''

    repl = '''        _registrar_actualizacion_historial(
            "ABIERTA",
            version,
            str(destino_path)
        )

        limpiar_archivos_actualizacion_antiguos()

        estado.configure(
            text=(
                f"✅ Nueva versión V{version} abierta. "
                "Puedes cerrar esta versión cuando compruebes que funciona."
            )
        )
'''

    text = require_replace(
        text,
        needle,
        repl,
        "registro de apertura"
    )

    text = text.replace(
        "DIAGPROG5 - WALLAPOP BOT (ADMIN) · V86",
        "DIAGPROG5 - WALLAPOP BOT (ADMIN) · V87"
    )

    text = text.replace(
        "DIAGPROG5 · WALLAPOP BOT · V86",
        "DIAGPROG5 · WALLAPOP BOT · V87"
    )

    text = text.replace(
        '''"Este es el puente de actualización de tu versión ADMIN. "
        "Cuando conectemos una URL de actualizaciones, podrás comprobar, "
        "descargar y abrir nuevas versiones desde el propio programa."''',
        '''"Actualizador ADMIN conectado. Comprueba, descarga, verifica y abre "
        "nuevas versiones sin acumular archivos indefinidamente. "
        "Se conservan solo las últimas versiones y copias de seguridad."'''
    )

    return text


def main():
    here = Path(
        __file__
    ).resolve()

    target = (
        here.parent
        / OUTPUT_NAME
    )

    # Si V87 ya fue generada correctamente, no intentar reconstruirla otra vez.
    if target.exists() and target.resolve() != here:
        try:
            existente = target.read_text(
                encoding="utf-8"
            )

            if (
                'def version_actual_bot()' in existente
                and 'return "87"' in existente
                and "DIAGPROG5" in existente
            ):
                py_compile.compile(
                    str(target),
                    doraise=True
                )

                subprocess.Popen(
                    [
                        sys.executable,
                        str(target),
                    ],
                    cwd=str(
                        target.parent
                    )
                )

                return target

        except Exception:
            pass

    data_dir = here.parent.parent

    source = find_v86(
        data_dir
    )

    if source is None:
        raise RuntimeError(
            "No encontré el backup V86 y tampoco existe una V87 válida ya instalada."
        )

    original = source.read_text(
        encoding="utf-8"
    )

    updated = construir_v87(
        original
    )

    target = (
        here.parent
        / OUTPUT_NAME
    )

    # Comprobación extra: nunca publicar una V87 sin la UI aprobada.
    if (
        "banner_dp5_limpio_v15.png" not in updated
        or "UI V86 · DISEÑO APROBADO" not in updated
        or "ACTUALIZACIONES · ADMIN" not in updated
    ):
        raise RuntimeError(
            "La V86 encontrada no contiene la interfaz/banner aprobados."
        )

    target.write_text(
        updated,
        encoding="utf-8"
    )

    copiar_banner_interfaz(
        source,
        target.parent
    )

    py_compile.compile(
        str(target),
        doraise=True
    )

    subprocess.Popen(
        [
            sys.executable,
            str(target),
        ],
        cwd=str(
            target.parent
        )
    )

    return target


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
                "DIAGPROG5 · Actualización V87",
                (
                    "No pude completar la actualización:\n\n"
                    + str(e)
                )
            )

            root.destroy()

        except Exception:
            traceback.print_exc()

        raise
