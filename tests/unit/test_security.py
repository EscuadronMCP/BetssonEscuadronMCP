import zipfile
from pathlib import Path

from betsson_validator.security import (
    audit_and_quarantine,
    find_leaks,
    scrub,
    scrub_trace,
)

SECRETS = ("Jugador.Prueba@example.com", "Clave-Muy-Secreta-123")


def test_scrub_removes_credentials_in_every_form() -> None:
    raw = (
        b'{"email":"Jugador.Prueba@example.com","user":"jugador.prueba@example.com",'
        b'"q":"Jugador.Prueba%40example.com","p":"Clave-Muy-Secreta-123"}'
    )
    clean = scrub(raw, SECRETS)
    assert find_leaks(clean, SECRETS) == []
    assert b"example.com" not in clean


def test_scrub_removes_session_tokens() -> None:
    raw = b"mgckey=AUTHTOKEN@9a962031cb180f31e8e2~stylename@btsn&token=62a94242-0c16-4eeb"
    clean = scrub(raw, ())
    assert b"9a962031" not in clean
    assert b"62a94242" not in clean
    assert find_leaks(clean, ()) == []


def test_find_leaks_detects_raw_secret_and_token() -> None:
    assert "credencial" in find_leaks(b"hola Clave-Muy-Secreta-123", SECRETS)
    assert "token de sesión" in find_leaks(b'"accessToken": "abcdefghijk123"', ())
    assert find_leaks(b"saldo 64,70 EUR", SECRETS) == []


def test_trace_is_scrubbed_in_place(tmp_path: Path) -> None:
    trace = tmp_path / "trace.zip"
    with zipfile.ZipFile(trace, "w") as archive:
        archive.writestr("resources/abc.json", '{"email":"Jugador.Prueba@example.com"}')
        archive.writestr("resources/frame.jpeg", b"\xff\xd8binary")
    scrub_trace(trace, SECRETS)
    with zipfile.ZipFile(trace) as archive:
        assert b"example.com" not in archive.read("resources/abc.json")
        assert archive.read("resources/frame.jpeg") == b"\xff\xd8binary"


def test_audit_quarantines_leaking_files(tmp_path: Path) -> None:
    (tmp_path / "ok.json").write_text('{"saldo": "64.70"}')
    (tmp_path / "leak.json").write_text('{"email": "Jugador.Prueba@example.com"}')
    removed = audit_and_quarantine(tmp_path, SECRETS)
    assert removed == ["leak.json"]
    assert (tmp_path / "ok.json").exists()
    assert not (tmp_path / "leak.json").exists()
