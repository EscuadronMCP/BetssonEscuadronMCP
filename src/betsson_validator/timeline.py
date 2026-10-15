"""Cronología de una ejecución: cuándo terminó cada etapa (segundos desde el inicio).

Se guarda con lo observado y el informe la dibuja: así se ve dónde se va el tiempo (sesión,
lobby, carga del juego, giro, saldo final) sin herramientas externas.
"""

import time


class StageClock:
    def __init__(self) -> None:
        self._start = time.monotonic()
        self.stages: list[dict[str, object]] = []

    def mark(self, name: str) -> None:
        self.stages.append({"name": name, "s": round(time.monotonic() - self._start, 1)})
