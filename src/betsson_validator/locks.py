"""Cerrojo por cuenta: dos ejecuciones en este ordenador nunca usan la misma cuenta a la vez.

Dos sesiones con la misma cuenta se pisan (la web cierra una, o la otra gasta saldo durante la
tirada) y el resultado sería un FAIL que no es del juego. El cerrojo es un archivo cuyo nombre es
un hash de la cuenta (no la expone), en la carpeta del usuario: lo comparten las ejecuciones
locales (`run` y `learn`) y el runner de GitHub Actions de la misma máquina y usuario.

- Se crea de forma atómica y ya completo (un archivo temporal que se enlaza con el nombre del
  cerrojo): otro proceso nunca ve un cerrojo a medio escribir.
- Solo se recupera si su proceso propietario ya no existe; la antigüedad no basta.
- Al terminar se libera solo si sigue siendo el propio (token aleatorio).

Limitaciones: no protege frente a otro ordenador ni frente a otro usuario del sistema que use la
misma cuenta; eso se coordina en el equipo (y si ocurre, el validador lo marca como discrepancia).
"""

import hashlib
import os
import secrets
import sys
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

DEFAULT_LOCK_DIR = Path.home() / ".cache" / "betsson_validator" / "locks"


class AccountBusyError(RuntimeError):
    """Otra ejecución de este ordenador está usando la misma cuenta."""


@contextmanager
def account_lock(identity: str, directory: Path = DEFAULT_LOCK_DIR) -> Iterator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(identity.strip().lower().encode()).hexdigest()[:16]
    path = directory / f"cuenta-{digest}.lock"
    token = secrets.token_hex(8)
    _acquire(path, f"{os.getpid()} {token}")
    try:
        yield
    finally:
        _release(path, token)


def _acquire(path: Path, content: str) -> None:
    for _ in range(2):
        if _create_complete(path, content):
            return
        owner = _owner_pid(path)
        if owner is not None and not _process_alive(owner):
            with suppress(FileNotFoundError):
                path.unlink()  # su propietario ya no existe: cerrojo abandonado
            continue
        raise AccountBusyError(
            "Otra ejecución de este ordenador está usando la misma cuenta; espera a que "
            "termine (dos sesiones a la vez se pisan)."
        )
    raise AccountBusyError("No se pudo tomar el cerrojo de la cuenta.")


def _create_complete(path: Path, content: str) -> bool:
    """Crea el cerrojo ya escrito; False si ya existe."""
    temporary = path.with_name(f"{path.name}.{secrets.token_hex(4)}.tmp")
    temporary.write_text(content, encoding="utf-8")
    try:
        os.link(temporary, path)  # atómico: falla si el cerrojo ya existe
    except FileExistsError:
        return False
    finally:
        temporary.unlink(missing_ok=True)
    return True


def _owner_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return None  # ilegible: no se puede saber de quién es, así que no se toca


def _release(path: Path, token: str) -> None:
    with suppress(OSError):
        if path.read_text(encoding="utf-8").split()[1:2] == [token]:
            path.unlink()


def _process_alive(pid: int) -> bool:
    if sys.platform == "win32":
        return _windows_process_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _windows_process_alive(pid: int) -> bool:
    """En Windows os.kill(pid, 0) terminaría el proceso: se consulta su estado."""
    import ctypes  # noqa: PLC0415 - solo en Windows

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        return code.value == 259  # noqa: PLR2004 - STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
