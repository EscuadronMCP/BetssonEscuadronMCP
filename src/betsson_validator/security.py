"""Las evidencias no pueden contener credenciales ni tokens (requisito del reto).

La traza de Playwright guarda respuestas de red: algunas incluyen el correo de la cuenta o
tokens de sesión del juego. Aquí se limpian y, al final de cada ejecución, se escanea todo lo
generado (textos, archivos comprimidos y capturas, leídas con OCR). Lo que no se pueda limpiar
se borra antes de publicar, y el informe lo indica.
"""

import html
import json
import re
import unicodedata
import zipfile
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np

from betsson_validator.perception.ocr import TextReader

REDACTED = b"<REDACTED>"
_TOKEN = re.compile(
    rb"(mgckey|AUTHTOKEN|token|ssid|SESSION|sessionId|accessToken|refreshToken)"
    rb"([\"']?\s*[=:@~]\s*[\"']?)"
    rb"(?!<REDACTED>)[A-Za-z0-9._\-%@]{8,}",
    re.IGNORECASE,
)
_TEXT_SUFFIXES = {".json", ".html", ".txt", ".trace", ".network", ".dat", ".js", ".css", ".xml"}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_MIN_VISIBLE_SECRET = 5  # una parte de un secreto más corta daría falsos positivos en capturas


def _variants(secret: str) -> set[bytes]:
    """Formas en que un secreto puede aparecer: tal cual, en minúsculas, codificado en URL,
    escapado en JSON (con y sin ASCII) o escapado en HTML."""
    forms: set[str] = set()
    for base in (secret, secret.lower()):
        forms |= {
            base,
            quote(base, safe=""),
            json.dumps(base)[1:-1],
            json.dumps(base, ensure_ascii=False)[1:-1],
            html.escape(base),
        }
    return {form.encode() for form in forms if form}


def scrub(data: bytes, secrets: Iterable[str]) -> bytes:
    for secret in secrets:
        if secret:
            for variant in _variants(secret):
                data = data.replace(variant, REDACTED)
    return _TOKEN.sub(rb"\1\2" + REDACTED, data)


def scrub_text(text: str, secrets: Iterable[str]) -> str:
    """Versión de `scrub` para mensajes (p. ej. errores con URLs que llevan `?token=…`)."""
    return scrub(text.encode(), secrets).decode(errors="replace")


def find_leaks(data: bytes, secrets: Iterable[str]) -> list[str]:
    leaks = [
        "credencial"
        for secret in secrets
        if secret and any(variant in data for variant in _variants(secret))
    ]
    if _TOKEN.search(data):
        leaks.append("token de sesión")
    return leaks


def _squash(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", plain).lower()


def visible_forms(secrets: Iterable[str]) -> set[str]:
    """Lo que delataría un secreto en una captura: el secreto y, si es un correo, su usuario."""
    forms: set[str] = set()
    for secret in secrets:
        forms.add(_squash(secret))
        if "@" in secret:
            forms.add(_squash(secret.split("@", 1)[0]))
    return {form for form in forms if len(form) >= _MIN_VISIBLE_SECRET}


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


def _zip_leaks(path: Path, secrets: tuple[str, ...]) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return any(
                find_leaks(archive.read(name), secrets)
                for name in archive.namelist()
                if _is_text(name)
            )
    except (zipfile.BadZipFile, OSError):
        return True  # un archivo que no se puede revisar no se publica


def _image_leaks(path: Path, forms: set[str], reader: TextReader) -> bool:
    image = cv2.imread(str(path))
    if image is None:
        return True
    pixels = np.asarray(image, dtype=np.uint8)
    text = _squash(" ".join(box.text for box in reader.read(pixels)))
    return any(form in text for form in forms)


def audit_and_quarantine(
    root: Path, secrets: tuple[str, ...], reader: TextReader | None = None
) -> list[str]:
    """Escanea las evidencias; borra cualquier archivo con fugas y devuelve qué se borró.

    Con `reader`, también se leen las capturas con OCR por si mostraran una credencial.
    """
    forms = visible_forms(secrets)
    removed: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        suffix = path.suffix.lower()
        try:
            if suffix == ".zip":
                leaked = _zip_leaks(path, secrets)
            elif suffix in _TEXT_SUFFIXES:
                leaked = bool(find_leaks(path.read_bytes(), secrets))
            elif suffix in _IMAGE_SUFFIXES and reader is not None and forms:
                leaked = _image_leaks(path, forms, reader)
            else:
                continue
        except Exception:  # p. ej. el OCR falla: sin revisar no se publica
            leaked = True
        if leaked:
            path.unlink(missing_ok=True)
            removed.append(path.relative_to(root).as_posix())
    return removed


def scrub_files(paths: Iterable[Path], secrets: tuple[str, ...]) -> None:
    """Limpia en su sitio archivos de texto que deben publicarse sí o sí (p. ej. el informe)."""
    for path in paths:
        if path.is_file():
            data = path.read_bytes()
            cleaned = scrub(data, secrets)
            if cleaned != data:
                path.write_bytes(cleaned)
