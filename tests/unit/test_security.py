import html
import json
import zipfile
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

from betsson_validator.perception.ocr import TextBox
from betsson_validator.security import (
    audit_and_quarantine,
    find_leaks,
    scrub,
    scrub_text,
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


# --- Regresiones: casos adversariales --------------------


def test_json_and_html_escaped_secrets_are_found_and_scrubbed() -> None:
    secret = 'Cl"ave\\ñ<1>'  # noqa: S105 (secreto de prueba)
    for form in (json.dumps(secret), json.dumps(secret, ensure_ascii=False), html.escape(secret)):
        data = form.encode()
        assert find_leaks(data, (secret,)) == ["credencial"]
        assert find_leaks(scrub(data, (secret,)), (secret,)) == []


def test_tokens_in_error_urls_are_removed() -> None:
    message = "TimeoutError: https://game.example/launch?token=abcdef123456789&lang=es falló"
    clean = scrub_text(message, ())
    assert "abcdef123456789" not in clean
    assert "lang=es" in clean


def test_screenshots_showing_the_account_are_quarantined(tmp_path: Path) -> None:
    image = np.zeros((40, 200, 3), dtype=np.uint8)
    cv2.imwrite(str(tmp_path / "00_cabecera.jpg"), image)
    cv2.imwrite(str(tmp_path / "01_juego.jpg"), image)

    class FakeReader:
        def read(self, pixels: npt.NDArray[np.uint8]) -> list[TextBox]:
            return [TextBox("Hola jugador.prueba", 0.9, 0, 0, 10, 10)]

    removed = audit_and_quarantine(tmp_path, SECRETS, FakeReader())
    assert removed == ["00_cabecera.jpg", "01_juego.jpg"]


def test_unreadable_archives_are_not_published(tmp_path: Path) -> None:
    (tmp_path / "trace.zip").write_bytes(b"no es un zip")
    assert audit_and_quarantine(tmp_path, SECRETS) == ["trace.zip"]


def test_an_ocr_failure_never_publishes_the_image_nor_breaks_the_run(tmp_path: Path) -> None:
    """La excepción del OCR durante la limpieza escapaba."""
    cv2.imwrite(str(tmp_path / "01_juego.jpg"), np.zeros((20, 20, 3), dtype=np.uint8))

    class BrokenReader:
        def read(self, pixels: npt.NDArray[np.uint8]) -> list[TextBox]:
            raise RuntimeError("OCR roto")

    assert audit_and_quarantine(tmp_path, SECRETS, BrokenReader()) == ["01_juego.jpg"]
