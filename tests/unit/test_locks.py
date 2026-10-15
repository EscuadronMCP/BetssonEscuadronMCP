"""Dos ejecuciones de este ordenador no usan la misma cuenta a la vez."""

import os
import time
from pathlib import Path

import pytest

from betsson_validator.locks import AccountBusyError, account_lock

ACCOUNT = "jugador.prueba@example.com"


def test_the_same_account_cannot_be_used_twice_at_once(tmp_path: Path) -> None:
    with (
        account_lock(ACCOUNT, tmp_path),
        pytest.raises(AccountBusyError),
        account_lock(ACCOUNT.upper(), tmp_path),
    ):
        pass


def test_the_lock_is_released_and_other_accounts_are_free(tmp_path: Path) -> None:
    with account_lock(ACCOUNT, tmp_path), account_lock("otra@example.com", tmp_path):
        pass
    with account_lock(ACCOUNT, tmp_path):
        pass
    assert list(tmp_path.iterdir()) == []


def test_the_lock_file_does_not_reveal_the_account(tmp_path: Path) -> None:
    with account_lock(ACCOUNT, tmp_path):
        (lock,) = tmp_path.iterdir()
        assert "jugador" not in lock.name
        assert "jugador" not in lock.read_text(encoding="utf-8")


def test_a_lock_whose_owner_died_is_recovered(tmp_path: Path) -> None:
    with account_lock(ACCOUNT, tmp_path):
        (lock,) = tmp_path.iterdir()
        lock.write_text("999999 otro-token", encoding="utf-8")  # PID que no existe
    assert list(tmp_path.iterdir()) == [lock]  # no se libera un cerrojo ajeno
    with account_lock(ACCOUNT, tmp_path):
        pass


def test_lock_does_not_expire_while_owner_is_alive(tmp_path: Path) -> None:
    """La antigüedad no basta; el propietario sigue vivo."""
    with account_lock(ACCOUNT, tmp_path):
        (lock,) = tmp_path.iterdir()
        os.utime(lock, (time.time() - 3 * 3600, time.time() - 3 * 3600))
        with pytest.raises(AccountBusyError), account_lock(ACCOUNT, tmp_path):
            pass


def test_an_unreadable_lock_is_never_taken_as_abandoned(tmp_path: Path) -> None:
    """Un cerrojo vacío o a medio escribir no se considera abandonado."""
    with account_lock(ACCOUNT, tmp_path):
        (lock,) = tmp_path.iterdir()
    lock.write_text("", encoding="utf-8")
    with pytest.raises(AccountBusyError), account_lock(ACCOUNT, tmp_path):
        pass


def test_another_process_cannot_take_a_held_lock(tmp_path: Path) -> None:
    """Procesos distintos: el hijo no puede entrar mientras el padre tiene la cuenta."""
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    script = (
        "import sys; from pathlib import Path; "
        "from betsson_validator.locks import account_lock, AccountBusyError\n"
        "try:\n"
        f"    with account_lock({ACCOUNT!r}, Path({str(tmp_path)!r})): print('dentro')\n"
        "except AccountBusyError: print('ocupada')\n"
    )
    with account_lock(ACCOUNT, tmp_path):
        held = subprocess.run(  # noqa: S603
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        )
    free = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert held.stdout.strip() == "ocupada"
    assert free.stdout.strip() == "dentro"
