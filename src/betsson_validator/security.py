"""Las evidencias no pueden contener credenciales ni tokens (requisito del reto).

La traza de Playwright guarda respuestas de red: algunas incluyen el correo de la cuenta o
tokens de sesión del juego. Aquí se limpian y, al final de cada ejecución, se escanea todo lo
generado. Lo que no se pueda limpiar se borra antes de publicar.
"""

import re
import zipfile
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote

REDACTED = b"<REDACTED>"
_TOKEN = re.compile(
    rb"(mgckey|AUTHTOKEN|token|ssid|SESSION|sessionId|accessToken|refreshToken)"
    rb"([\"']?\s*[=:@~]\s*[\"']?)"
    rb"(?!<REDACTED>)[A-Za-z0-9._\-%@]{8,}",
    re.IGNORECASE,
)
_TEXT_SUFFIXES = {".json", ".html", ".txt", ".trace", ".network", ".dat", ".js", ".css", ".xml"}


def _variants(secret: str) -> set[bytes]:
    """Formas en que un secreto puede aparecer: tal cual, en minúsculas o codificado en URL."""
    forms = {secret, secret.lower(), quote(secret, safe=""), quote(secret.lower(), safe="")}
    return {form.encode() for form in forms if form}


def scrub(data: bytes, secrets: Iterable[str]) -> bytes:
    for secret in secrets:
        for variant in _variants(secret):
            data = data.replace(variant, REDACTED)
    return _TOKEN.sub(rb"\1\2" + REDACTED, data)


def find_leaks(data: bytes, secrets: Iterable[str]) -> list[str]:
    leaks = [
        "credencial"
        for secret in secrets
        if secret and any(variant in data for variant in _variants(secret))
    ]
    if _TOKEN.search(data):
        leaks.append("token de sesión")
    return leaks


def _is_text(name: str) -> bool:
    return Path(name).suffix.lower() in _TEXT_SUFFIXES or "." not in Path(name).name


def scrub_trace(path: Path, secrets: tuple[str, ...]) -> None:
    """Reescribe la traza sustituyendo secretos y tokens en todos sus recursos de texto."""
    if not path.is_file():
        return
    cleaned = path.with_suffix(".clean.zip")
    with (
        zipfile.ZipFile(path) as source,
        zipfile.ZipFile(cleaned, "w", zipfile.ZIP_DEFLATED) as out,
    ):
        for item in source.infolist():
            data = source.read(item.filename)
            out.writestr(item, scrub(data, secrets) if _is_text(item.filename) else data)
    cleaned.replace(path)


def audit_and_quarantine(root: Path, secrets: tuple[str, ...]) -> list[str]:
    """Escanea las evidencias; borra cualquier archivo con fugas y devuelve qué se borró."""
    removed: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                leaked = any(
                    find_leaks(archive.read(name), secrets)
                    for name in archive.namelist()
                    if _is_text(name)
                )
        elif path.suffix.lower() in _TEXT_SUFFIXES:
            leaked = bool(find_leaks(path.read_bytes(), secrets))
        else:
            continue
        if leaked:
            path.unlink()
            removed.append(str(path.relative_to(root)))
    return removed
