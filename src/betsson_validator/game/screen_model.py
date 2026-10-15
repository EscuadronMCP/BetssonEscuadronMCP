"""Lo que el validador sabe de la pantalla de un juego: leer el HUD y encontrar sus controles.

Usa el perfil aprendido del juego (profiles.py). Si el perfil deja de encajar (botón movido,
texto cambiado), se reaprende con la IA de visión una única vez, se valida antes de adoptarlo y
queda anotado. Las acciones sobre el juego (pulsar, girar, esperar) están en player.py.
"""

from dataclasses import dataclass, field, replace

import numpy as np
import numpy.typing as npt

from betsson_validator.perception.hud import HudLabels, HudReading, find_amount, read_hud
from betsson_validator.perception.learner import Box, LearnerError, ScreenAnalysis, ScreenLearner
from betsson_validator.perception.ocr import TextBox, TextReader
from betsson_validator.perception.templates import TemplateMatch, crop, find_template
from betsson_validator.profiles import GameProfile

Image = npt.NDArray[np.uint8]
Point = tuple[float, float]

_TEMPLATE_INNER = 0.7  # fracción central del control que se guarda como plantilla
# Lo que la IA proponga como control debe parecer un botón: ni un punto ni media pantalla, y
# con contenido (un recorte uniforme encajaría en cualquier zona lisa).
_MIN_CONTROL_PX = 8
_MAX_CONTROL_SHARE = 0.1
_MIN_TEMPLATE_STD = 4.0
# Distancia relativa máxima entre un control de apuesta y el botón de girar (medido: <= 0,08 en
# Sweet Bonanza y Big Bass; un falso "-" en Big Bass apareció a 0,6).
_BET_NEAR_SPIN = 0.2


class GameError(RuntimeError):
    pass


@dataclass
class ScreenModel:
    """Interpreta capturas: lee el HUD, localiza controles y reaprende el perfil si no encaja."""

    profile: GameProfile
    reader: TextReader
    currency: str
    learner: ScreenLearner | None = None
    # Etiquetas de premio habituales en el idioma del mercado: el premio solo aparece cuando hay
    # ganancia, así que no siempre se puede aprender de la pantalla de juego.
    win_candidates: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)
    _learned: bool = False

    def labels(self) -> HudLabels:
        return HudLabels(
            credit=self.profile.credit_label, bet=self.profile.bet_label, win=self.profile.win_label
        )

    def read(self, image: Image) -> tuple[HudReading, list[TextBox]]:
        boxes = self.reader.read(image)
        height, width = image.shape[:2]
        anchors = {
            name: (rx * width, ry * height) for name, (rx, ry) in self.profile.hud_positions.items()
        }
        hud = read_hud(boxes, self.labels(), self.currency, anchors)
        if hud.win is None and not self.profile.win_label:
            for candidate in self.win_candidates:
                win = find_amount(
                    boxes,
                    candidate,
                    self.currency,
                    anchors.get("win"),
                    (self.profile.credit_label, self.profile.bet_label),
                )
                if win is not None:
                    return replace(hud, win=win), boxes
        return hud, boxes

    def locate(self, control: str, image: Image) -> Point | None:
        """Busca el control por su aspecto. Si otro control del perfil encaja igual o mejor en ese
        mismo sitio (p. ej. '+' cuando '-' está desactivado, o 'girar' en lugar de 'continuar'), la
        localización es ambigua y se rechaza: pulsar el control equivocado puede costar dinero."""
        template = self.profile.template(control)
        if template is None:
            return None
        match = find_template(image, template)
        if match is None:
            return None
        for other, other_template in self.profile.templates.items():
            if other == control:
                continue
            rival = find_template(image, other_template)
            if rival is not None and rival.score >= match.score and _overlap(match, rival):
                return None
        height, width = image.shape[:2]
        center_x, center_y = match.center
        return center_x / width, center_y / height

    def locate_near(self, control: str, image: Image, around: Point | None) -> Point | None:
        """Como `locate`, pero solo en la zona alrededor de `around` (los botones de apuesta están
        junto al de girar): otros elementos parecidos de la pantalla no cuentan (15/10, Big Bass:
        los «-» verdes del panel de apuesta encajaban mejor que el del marcador)."""
        if around is None:
            return None
        height, width = image.shape[:2]
        x0, x1 = (
            max(int((around[0] - _BET_NEAR_SPIN) * width), 0),
            min(int((around[0] + _BET_NEAR_SPIN) * width), width),
        )
        y0, y1 = (
            max(int((around[1] - _BET_NEAR_SPIN) * height), 0),
            min(int((around[1] + _BET_NEAR_SPIN) * height), height),
        )
        point = self.locate(control, image[y0:y1, x0:x1])
        if point is None:
            return None
        return (x0 + point[0] * (x1 - x0)) / width, (y0 + point[1] * (y1 - y0)) / height

    def locate_or_learn(self, control: str, image: Image) -> Point:
        point = self.locate(control, image)
        if point is None and self.learn(image, f"no se encontró el control '{control}'"):
            point = self.locate(control, image)
        if point is None:
            raise GameError(f"No se encuentra el control '{control}' en la pantalla del juego.")
        return point

    def learn(self, image: Image, reason: str) -> ScreenAnalysis | None:
        """Reaprende con la IA (una vez por ejecución) y aplica el resultado en memoria."""
        if self.learner is None or self._learned:
            return None
        self._learned = True
        try:
            analysis = self.learner.analyze(image)
        except LearnerError as error:  # sin IA disponible el perfil activo sigue intacto
            self.notes.append(f"No se pudo reaprender con IA ({error}): {reason}.")
            return None
        problems = self.apply(analysis, image)
        cost = f"{self.learner.cost_usd:.4f} $"
        if problems:
            self.notes.append(
                f"Propuesta de la IA rechazada ({cost}): {'; '.join(problems)}. Se mantiene el "
                f"perfil anterior ({reason})."
            )
            return None
        self.notes.append(f"Perfil reaprendido con IA de visión ({cost}): {reason}.")
        return analysis

    def apply(self, analysis: ScreenAnalysis, image: Image) -> list[str]:
        """Aplica la propuesta de la IA a una COPIA del perfil y solo la adopta si es válida.

        La salida de la IA es un dato no confiable: cada caja debe caber en la captura, tener un
        tamaño de control y contenido, y cada control propuesto debe reencontrarse sin
        ambigüedad. Si algo falla, el perfil activo queda intacto y se devuelven los motivos.
        """
        height, width = image.shape[:2]
        candidate = replace(self.profile, templates=dict(self.profile.templates))
        problems: list[str] = []
        proposed = [
            (control, box)
            for control, box in (
                ("continue", analysis.continue_button),
                ("spin", analysis.spin_button),
                ("bet_down", analysis.bet_decrease_button),
                ("bet_up", analysis.bet_increase_button),
            )
            if box is not None
        ]
        for control, box in proposed:
            if problem := _control_box_problem(box, width, height):
                problems.append(f"{control}: {problem}")
                continue
            template = control_template(image, box.as_tuple())
            if float(np.std(template)) < _MIN_TEMPLATE_STD:
                problems.append(f"{control}: el recorte no tiene contenido")
                continue
            candidate.templates[control] = template
        candidate.credit_label = analysis.credit_label or candidate.credit_label
        candidate.bet_label = analysis.bet_label or candidate.bet_label
        candidate.win_label = analysis.win_label or candidate.win_label
        if (area := analysis.reels_area) is not None:
            x, y, w, h = area.as_tuple()
            if x + w > width or y + h > height:
                problems.append("zona de rodillos fuera de la captura")
            else:
                candidate.reels_area = (x / width, y / height, (x + w) / width, (y + h) / height)
        if not problems:
            problems = self._adopt_if_relocatable(candidate, [c for c, _ in proposed], image)
        return problems

    def _adopt_if_relocatable(
        self, candidate: GameProfile, controls: list[str], image: Image
    ) -> list[str]:
        """Adopta el candidato solo si cada control propuesto se reencuentra sin ambigüedad."""
        previous, self.profile = self.profile, candidate
        lost = [control for control in controls if self.locate(control, image) is None]
        if lost:
            self.profile = previous
            return [f"{control}: no se reencuentra sin ambigüedad" for control in lost]
        return []

    def remember_hud_positions(self, hud: HudReading, image: Image) -> None:
        """Guarda dónde se leyeron crédito y apuesta (solo con lecturas ya validadas)."""
        height, width = image.shape[:2]
        for name, reading in (("credit", hud.credit), ("bet", hud.bet), ("win", hud.win)):
            if reading is not None:
                self.profile.hud_positions[name] = (reading.x / width, reading.y / height)

    def reels(self, image: Image) -> Image:
        if self.profile.reels_area is None:
            return image
        x1, y1, x2, y2 = self.profile.reels_area
        height, width = image.shape[:2]
        return image[int(height * y1) : int(height * y2), int(width * x1) : int(width * x2)]


def control_template(image: Image, box: tuple[int, int, int, int]) -> Image:
    """Imagen de un control para reencontrarlo: solo su interior, sin el fondo del juego.

    El fondo cambia entre sesiones (animaciones, paneles) y con él la coincidencia bajaba de
    0,97 a 0,72; con el interior del botón se mantiene por encima de 0,9 (medido en capturas
    reales de sesiones distintas).
    """
    x, y, w, h = box
    dx, dy = round(w * (1 - _TEMPLATE_INNER) / 2), round(h * (1 - _TEMPLATE_INNER) / 2)
    return crop(image, (x + dx, y + dy, w - 2 * dx, h - 2 * dy))


def _overlap(a: TemplateMatch, b: TemplateMatch) -> bool:
    (ax, ay), (bx, by) = a.center, b.center
    return abs(ax - bx) < max(a.width, b.width) / 2 and abs(ay - by) < max(a.height, b.height) / 2


def _control_box_problem(box: Box, width: int, height: int) -> str | None:
    """Una caja de control válida: dentro de la captura y del tamaño de un botón."""
    x, y, w, h = box.as_tuple()
    if x + w > width or y + h > height:
        return "caja fuera de la captura"
    if min(w, h) < _MIN_CONTROL_PX:
        return "caja demasiado pequeña"
    if w * h > _MAX_CONTROL_SHARE * width * height:
        return "caja demasiado grande para ser un botón"
    return None
