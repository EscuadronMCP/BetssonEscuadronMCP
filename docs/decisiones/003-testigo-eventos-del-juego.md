# 003. Quinto testigo: eventos que el juego envía al casino (postMessage)

- **Fecha:** 2026-10-15
- **Estado:** aceptada (amplía la [decisión 001](001-enfoque-testigos-y-perfiles.md))
- **Origen:** sugerencia de un mentor de Betsson: "hay algo más escondido en el navegador que no habéis usado".

## Contexto

Teníamos cuatro testigos: pantalla del juego (OCR), movimiento de los rodillos, cabecera de Betsson y tráfico de red del juego. Para encontrar la capa que faltaba instrumentamos el navegador durante una tirada real (sin modificar nada) y registramos mensajes entre ventanas, WebSockets, consola y almacenamiento.

## Hallazgo

El juego de Pragmatic Play, dentro de su iframe, **comunica a la página de Betsson cada paso de la ronda por `window.postMessage`**. Es el canal de integración juego ↔ casino, distinto de la pantalla y de la red:

| Evento | Contenido (tirada real, 15/10) |
|---|---|
| `gameLoadingEnded` | El juego terminó de cargar |
| `gameRoundStart` / `gameRoundStarted` | `betAmount: 0.2`, `balanceBefore: 198.25`, `lang: "ES"` |
| `spinStarted` / `spinEnded` | Uno por cascada, con `winAmount` acumulado y `roundTripMs` |
| `visualBalanceUpdate` | `currency: "€"`, `newAmount`, `win` |
| `gameRoundEnded` / `balanceChanged` / `resultShown` | `winAmount: 1.5`, `balanceAfter: 199.55` (= 198,25 − 0,20 + 1,50) |
| `balanceTooLow` (cuenta sin saldo) | `betAmount: 0.2`, `balanceBefore: 0`, y ningún `gameRoundStart` |
| `betChanged` | Cada cambio de apuesta |

Descartados como testigo: los WebSockets (sesión y métricas de Betsson), la consola (depuración del cliente) y el almacenamiento (preferencias).

## Decisión

Nuevo testigo **"eventos del juego"** (corroborante, como la red):

- Grabador **genérico** (`game/events.py`): un script de solo lectura escucha `message` en la página del casino y guarda los objetos con `name` o `event` que no vienen del propio casino (así quedan fuera, por ejemplo, los del servicio antifraude).
- Intérprete **por proveedor** (`providers/pragmatic/events.py`), igual que el testigo de red.
- Corrobora las 9 comprobaciones: ronda completa, apuesta usada, divisa, **idioma del mensaje** (`lang`), saldo del juego, conciliación de Betsson, rechazo por saldo (`balanceTooLow`) y saldo sin cambios.

**Eficiencia:** el evento `gameLoadingEnded` también evita llamadas inútiles a la IA. Antes, una carga lenta dejaba la pantalla quieta y parecía un cambio de interfaz.

## Consecuencias

- Una discrepancia entre lo que el juego comunica a Betsson y lo que ve el jugador es exactamente un fallo de integración, y ahora se detecta. En la investigación apareció una: la pantalla mostraba 199,50 € y el juego comunicaba 199,55 €. Era el contador del premio aún animándose, y por eso la lectura final del HUD espera ahora a que el crédito sea estable.
- Si un proveedor no envía eventos, el testigo queda "no disponible" y no impide el PASS.
