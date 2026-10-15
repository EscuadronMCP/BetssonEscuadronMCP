"""Dos ejecuciones de este ordenador no usan la misma cuenta a la vez (auditoría R02, ACC-003)."""

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


def test_an_abandoned_lock_is_recovered(tmp_path: Path) -> None:
    with account_lock(ACCOUNT, tmp_path):
        (lock,) = tmp_path.iterdir()
        old = time.time() - 3600
        lock.write_text(f"{os.getpid()} {old:.0f}", encoding="utf-8")
    with account_lock(ACCOUNT, tmp_path):  # el anterior ya no estaba; y uno viejo se recupera
        (lock,) = tmp_path.iterdir()
        lock.write_text(f"{os.getpid()} {old:.0f}", encoding="utf-8")
        with account_lock(ACCOUNT, tmp_path):
            pass
