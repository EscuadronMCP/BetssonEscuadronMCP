"""Web de Betsson: todo lo que no es el juego del proveedor (DOM accesible, igual para todos)."""

import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import FrameLocator, Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from betsson_validator.config.market import Credentials, MarketConfig
from betsson_validator.config.provider import ProviderConfig
from betsson_validator.domain.money import Money
from betsson_validator.domain.parsing import parse_money

_COOKIE_ACCEPT = "#onetrust-accept-btn-handler"
_WAF_COOKIE = "aws-waf-token"
_AUTH_ENDPOINT = "/api/v2/authentication-transaction"
_LOGIN_OK = 201
_BALANCE_BUTTON = re.compile(r"^\s*\d[\d.\s]*,\d{2}\s*€\s*$")
_GAME_LAUNCHER = "Gamelauncher"
_GAME_IFRAME = f"iframe[src*='{_GAME_LAUNCHER}']"
# Difumina los campos de login para que las credenciales no salgan en el vídeo.
_HIDE_LOGIN_FIELDS_CSS = (
    "input[name=email], input[name=password] "
    "{ filter: blur(8px) !important; -webkit-text-security: disc !important; }"
)
_BALANCE_SETTLE_MS = 2000
_COOKIE_TIMEOUT_MS = 15_000
_NAVIGATION_TIMEOUT_MS = 60_000
_FILTER_PANEL_SETTLE_MS = 3000
_LOBBY_MAX_SCROLLS = 80
_SESSION_TIMEOUT_S = 90
_CLICK_TIMEOUT_MS = 5000
_DIALOG_CLOSE_TIMEOUT_MS = 15_000
# Las fichas de juego enlazan a /casino/<categoría>/<juego>; el menú lateral, a /casino/<x>.
# Se evalúa sobre un localizador de Playwright porque las fichas viven en shadow DOM.
_COUNT_GAME_TILES_JS = """links => links.filter(a => {
    const path = new URL(a.href, location.href).pathname;
    return path.split("/").filter(Boolean).length >= 3;
}).length"""
_LOBBY_SCROLL_PX = 1200
_LOBBY_SCROLL_WAIT_MS = 600


class CasinoError(RuntimeError):
    """Fallo en la web de Betsson con un mensaje apto para el informe (sin secretos)."""


@dataclass(frozen=True)
class GameHandle:
    """Juego lanzado: el iframe (para capturas y clics) y su contenido."""

    iframe: Locator
    frame: FrameLocator
    url: str


class BetssonCasino:
    def __init__(self, page: Page, market: MarketConfig, typing_delay_ms: int = 90) -> None:
        self._page = page
        self._market = market
        self._ui = market.ui
        self._typing_delay_ms = typing_delay_ms

    @property
    def page(self) -> Page:
        return self._page

    def _url(self, path: str) -> str:
        return urljoin(str(self._market.base_url), path)

    def open(self) -> None:
        # El aviso de cookies puede aparecer tarde (red lenta): se acepta cuando aparezca.
        self._page.add_locator_handler(
            self._page.locator(_COOKIE_ACCEPT),
            lambda button: button.dispatch_event("click"),
            no_wait_after=True,
        )
        self._page.goto(
            self._url("/"), wait_until="domcontentloaded", timeout=_NAVIGATION_TIMEOUT_MS
        )
        self._accept_cookies()

    def _accept_cookies(self) -> None:
        button = self._page.locator(_COOKIE_ACCEPT)
        try:
            button.wait_for(timeout=_COOKIE_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            return  # el aviso no siempre aparece (p. ej. consentimiento ya guardado)
        # El botón está siempre animado y Playwright nunca lo considera estable.
        button.dispatch_event("click")

    def login(self, credentials: Credentials) -> None:
        self._wait_for_waf_token()
        self._page.get_by_role("button", name=self._ui.login_button).first.click()
        email = self._page.locator("input[name=email]")
        password = self._page.locator("input[name=password]")
        email.wait_for()
        self._page.add_style_tag(content=_HIDE_LOGIN_FIELDS_CSS)
        email.press_sequentially(credentials.email.get_secret_value(), delay=self._typing_delay_ms)
        password.press_sequentially(
            credentials.password.get_secret_value(), delay=self._typing_delay_ms
        )
        with self._page.expect_response(lambda r: _AUTH_ENDPOINT in r.url) as response_info:
            self._page.get_by_role("button", name=self._ui.login_button, exact=True).last.click()
        status = response_info.value.status
        if status != _LOGIN_OK:
            raise CasinoError(f"Login rechazado por betsson.es (HTTP {status}).")
        self._dismiss_passkey_prompt()

    def _wait_for_waf_token(self, timeout_s: float = 30) -> None:
        deadline = time.monotonic() + timeout_s
        context = self._page.context
        while not any(c["name"] == _WAF_COOKIE for c in context.cookies()):
            if time.monotonic() > deadline:
                raise CasinoError("El antibots de la web no emitió su token a tiempo.")
            self._page.wait_for_timeout(250)

    def _dismiss_passkey_prompt(self) -> None:
        dismiss = self._page.get_by_role("button", name=self._ui.passkey_dismiss, exact=True).first
        try:
            dismiss.wait_for(timeout=10_000)
        except PlaywrightTimeoutError:
            return  # el diálogo es opcional: si no aparece, no hay nada que cerrar
        try:
            dismiss.click(timeout=_CLICK_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            dismiss.dispatch_event("click")  # el diálogo sigue animándose: clic directo

    def balance_locator(self) -> Locator:
        return self._page.get_by_role("button", name=_BALANCE_BUTTON).first

    def capture_balance(self, path: Path) -> Path:
        """Recorte de la cabecera alrededor del saldo, tal y como lo ve el jugador."""
        box = self.balance_locator().bounding_box()
        if box is None:
            raise CasinoError("El saldo de Betsson no está visible.")
        margin = 40
        self._page.screenshot(
            path=str(path),
            clip={
                "x": max(box["x"] - margin * 4, 0),
                "y": max(box["y"] - margin, 0),
                "width": box["width"] + margin * 6,
                "height": box["height"] + margin * 2,
            },
        )
        return path

    def read_balance(self) -> Money:
        """Saldo de Betsson tal y como lo ve el jugador en la cabecera."""
        locator = self.balance_locator()
        locator.wait_for(timeout=30_000)
        return parse_money(locator.inner_text())

    def read_balance_after(self, previous: Money, timeout_s: float = 20) -> Money:
        """Vuelve al casino y lee el saldo cuando la cabecera deja de cambiar.

        No se espera ningún valor concreto: se espera a que el saldo cambie respecto al anterior
        (o a que pase el tiempo límite) y a que dos lecturas seguidas coincidan.
        """
        self._page.goto(
            self._url("/casino"), wait_until="domcontentloaded", timeout=_NAVIGATION_TIMEOUT_MS
        )
        deadline = time.monotonic() + timeout_s
        current = self.read_balance()
        while current == previous and time.monotonic() < deadline:
            self._page.wait_for_timeout(_BALANCE_SETTLE_MS)
            self._page.reload(wait_until="domcontentloaded")
            current = self.read_balance()
        self._page.wait_for_timeout(_BALANCE_SETTLE_MS)
        confirmed = self.read_balance()
        return confirmed

    def launch_game(self, provider: ProviderConfig, game: str) -> GameHandle:
        """Casino → Filtros → proveedor → Resultados → juego, como lo haría el jugador."""
        self._page.goto(
            self._url("/casino"), wait_until="domcontentloaded", timeout=_NAVIGATION_TIMEOUT_MS
        )
        self._page.get_by_role("button", name=self._ui.filters_button).click()
        # La web recuerda los filtros de la cuenta: se limpian para que pulsar el chip lo active.
        clear = self._page.get_by_role("button", name=self._ui.clear_filters_button, exact=True)
        try:
            clear.first.wait_for(timeout=_FILTER_PANEL_SETTLE_MS)
            clear.first.click(timeout=_CLICK_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass  # no había filtros activos
        self._page.get_by_text(provider.filter_label, exact=True).first.click()
        self._page.get_by_role("button", name=self._ui.results_button).first.click()
        self._find_in_lobby(game, provider.filter_label).click()
        self._start_game_session()
        iframe = self._page.locator(_GAME_IFRAME)
        iframe.wait_for(timeout=provider.game_load_timeout_s * 1000)
        return GameHandle(
            iframe=iframe,
            frame=self._page.frame_locator(_GAME_IFRAME),
            url=self._page.url,
        )

    def _find_in_lobby(self, slug: str, provider_label: str) -> Locator:
        """El listado carga los juegos al bajar: se baja hasta que aparece, como un jugador."""
        game_link = self._page.locator(f"a[href$='/{slug}']").first
        self._wait_for_game_tiles()
        # La rueda actúa donde está el puntero: hay que ponerlo sobre el listado.
        viewport = self._page.viewport_size or {"width": 1440, "height": 900}
        self._page.mouse.move(viewport["width"] / 2, viewport["height"] * 2 / 3)
        for _ in range(_LOBBY_MAX_SCROLLS):
            if game_link.count():
                game_link.scroll_into_view_if_needed()
                return game_link
            self._page.mouse.wheel(0, _LOBBY_SCROLL_PX)
            self._page.wait_for_timeout(_LOBBY_SCROLL_WAIT_MS)
        raise CasinoError(f"El juego '{slug}' no aparece en el lobby de {provider_label}.")

    def _wait_for_game_tiles(self, timeout_s: float = 30) -> None:
        links = self._page.locator("a[href*='/casino/']")
        deadline = time.monotonic() + timeout_s
        while int(links.evaluate_all(_COUNT_GAME_TILES_JS)) == 0:
            if time.monotonic() > deadline:
                raise CasinoError("El lobby no mostró ningún juego a tiempo.")
            self._page.wait_for_timeout(500)

    def _set_loss_limit(self) -> None:
        """Límite de pérdidas, si el diálogo lo pide.

        Con saldo 0 € la web no muestra esta sección (avisa de que no hay saldo), así que es
        opcional. Si el botón del porcentaje no está disponible, se escribe el límite en el campo.
        """
        percentage = self._page.get_by_role("button", name=self._ui.session_loss_limit)
        if percentage.count() and percentage.first.is_visible() and percentage.first.is_enabled():
            percentage.first.click(timeout=_CLICK_TIMEOUT_MS)
            return
        field = self._page.get_by_placeholder(self._ui.session_loss_input_placeholder)
        if field.count() and field.first.is_visible():
            field.first.fill(self._ui.session_loss_limit_fallback, timeout=_CLICK_TIMEOUT_MS)

    def _provider_game_loaded(self) -> bool:
        """El iframe de Betsson ya contiene el juego del proveedor (otro dominio)."""
        casino_host = urlparse(str(self._market.base_url)).hostname or ""
        for frame in self._page.frames:
            parent = frame.parent_frame
            host = urlparse(frame.url).hostname or ""
            if parent is not None and _GAME_LAUNCHER in parent.url and host != casino_host:
                return True
        return False

    def _start_game_session(self) -> None:
        """Sesión de juego obligatoria en España: aviso opcional y diálogo de límites.

        Los avisos se detectan por su texto visible (no siempre son role=dialog). La sesión se da
        por abierta cuando el contenido del juego del proveedor ha cargado dentro del iframe de
        Betsson: con la red lenta los avisos llegan tarde y "unos segundos sin avisos" no basta.
        """
        page = self._page
        warning = page.get_by_text(self._ui.session_warning_text)
        limits = page.get_by_text(self._ui.session_limits_text)
        start = page.get_by_role("button", name=self._ui.login_button, exact=True)
        deadline = time.monotonic() + _SESSION_TIMEOUT_S
        duration = page.get_by_role("button", name=self._ui.session_duration, exact=True)
        while time.monotonic() < deadline:
            if limits.first.is_visible() and duration.first.is_visible():
                duration.first.click(timeout=_CLICK_TIMEOUT_MS)
                self._set_loss_limit()
                start.last.click(timeout=_CLICK_TIMEOUT_MS)
                limits.first.wait_for(state="hidden", timeout=_DIALOG_CLOSE_TIMEOUT_MS)
            elif warning.first.is_visible() and start.last.is_visible():
                start.last.click(timeout=_CLICK_TIMEOUT_MS)
                warning.first.wait_for(state="hidden", timeout=_DIALOG_CLOSE_TIMEOUT_MS)
            elif self._provider_game_loaded():
                return
            page.wait_for_timeout(500)
        raise CasinoError("No se pudo abrir la sesión de juego obligatoria.")
