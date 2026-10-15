"""Cerrojo por cuenta: dos ejecuciones en este ordenador nunca usan la misma cuenta a la vez.

Dos sesiones con la misma cuenta se pisan (la web cierra una, o la otra gasta saldo durante la
tirada) y el resultado sería un FAIL que no es del juego. El cerrojo es un archivo cuyo nombre es
un hash de la cuenta (no la expone), en la carpeta del usuario: lo comparten las ejecuciones
locales y el runner de GitHub Actions de la misma máquina.

Limitación: no protege frente a otro ordenador que use la misma cuenta; eso se coordina en el
equipo (y si ocurre, el validador lo detecta como discrepancia).
"""

import hashlib
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_LOCK_DIR = Path.home() / ".cache" / "betsson_validator" / "locks"
STALE_AFTER_S = 30 * 60  # una ejecución dura ~2 min: un cerrojo así de viejo está abandonado


class AccountBusyError(RuntimeError):
    """Otra ejecución de este ordenador está usando la misma cuenta."""


@contextmanager
def account_lock(
    identity: str, directory: Path = DEFAULT_LOCK_DIR, stale_after_s: float = STALE_AFTER_S
) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(identity.strip().lower().encode()).hexdigest()[:16]
    path = directory / f"cuenta-{digest}.lock"
    _acquire(path, stale_after_s)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def _acquire(path: Path, stale_after_s: float) -> None:
    for _ in range(2):
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _is_stale(path, stale_after_s):
                path.unlink(missing_ok=True)
                continue
            raise AccountBusyError(
                "Otra ejecución de este ordenador está usando la misma cuenta; espera a que "
                "termine (dos sesiones a la vez se pisan)."
            ) from None
        with os.fdopen(descriptor, "w", encoding="utf-8") as lock:
            lock.write(f"{os.getpid()} {time.time():.0f}")
        return
    raise AccountBusyError("No se pudo tomar el cerrojo de la cuenta.")


def _is_stale(path: Path, stale_after_s: float) -> bool:
    try:
        pid_text, started_text = path.read_text(encoding="utf-8").split()
        pid, started = int(pid_text), float(started_text)
    except (OSError, ValueError):
        return True  # cerrojo ilegible: lo dejó un proceso interrumpido al escribirlo
    if time.time() - started > stale_after_s:
        return True
    return not _process_alive(pid)


def _process_alive(pid: int) -> bool:
    if sys.platform == "win32":
        return True  # en Windows os.kill(pid, 0) terminaría el proceso: solo cuenta la edad
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
