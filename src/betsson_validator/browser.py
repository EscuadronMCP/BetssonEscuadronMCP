"""Arranque del navegador con grabación de evidencias (vídeo y traza).

betsson.es usa AWS WAF con control de bots, que rechaza el login (403) si el navegador
anuncia que está automatizado. Por eso Chrome se lanza sin esa marca. Es una decisión del
equipo: Betsson nos pide automatizar su propia web con sus cuentas de prueba
(ver docs/betsson-es-flujo.md).
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import BrowserContext, sync_playwright

_ANTI_AUTOMATION_FLAG_ARGS = ["--disable-blink-features=AutomationControlled"]
_IGNORED_DEFAULT_ARGS = ["--enable-automation"]


@dataclass(frozen=True)
class BrowserSettings:
    headless: bool = True
    channel: str | None = "chrome"
    locale: str = "es-ES"
    timezone: str = "Europe/Madrid"
    width: int = 1440
    height: int = 900
    slow_typing_ms: int = 90


@contextmanager
def browser_context(settings: BrowserSettings, evidence_dir: Path) -> Iterator[BrowserContext]:
    """Abre un contexto que graba vídeo en evidence_dir y lo cierra al salir."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=settings.headless,
            channel=settings.channel,
            args=_ANTI_AUTOMATION_FLAG_ARGS,
            ignore_default_args=_IGNORED_DEFAULT_ARGS,
        )
        context = browser.new_context(
            viewport={"width": settings.width, "height": settings.height},
            locale=settings.locale,
            timezone_id=settings.timezone,
            record_video_dir=str(evidence_dir / "video"),
            record_video_size={"width": settings.width, "height": settings.height},
        )
        try:
            yield context
        finally:
            context.close()
            browser.close()


@contextmanager
def tracing(context: BrowserContext, path: Path) -> Iterator[None]:
    """Traza ligera de Playwright: solo acciones, sin instantáneas ni recursos de red.

    Con instantáneas, la traza pesaba cientos de MB (cada captura y todos los recursos del juego)
    y guardaba respuestas con datos de la cuenta. La evidencia visual son el vídeo y las capturas.
    Se abre DESPUÉS del login: la traza guarda el texto tecleado.
    """
    context.tracing.start(screenshots=False, snapshots=False, sources=False)
    try:
        yield
    finally:
        context.tracing.stop(path=str(path))
