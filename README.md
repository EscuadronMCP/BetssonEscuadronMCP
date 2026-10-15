# BetssonEscuadronMCP

Validador automático de juegos de casino para el reto de **Betsson** en el **Malackathon 2026** (Universidad de Málaga): *Intelligent Game Validation*.

Entra en **betsson.es**, lanza un juego de **PragmaticPlay** en Real Play y comprueba, **como lo vería un jugador**, que:

1. **Una tirada se completa** y los saldos cuadran: `saldo después = saldo antes − apuesta + premio`.
2. **Con saldo insuficiente**, la tirada se rechaza con el mensaje adecuado en español y ningún saldo cambia.

Todo **de principio a fin y sin intervención humana**: la prueba abre el navegador, inicia sesión, abre la sesión de juego obligatoria, lanza el juego, juega y genera el informe sola. Termina con un informe de PASS/FAIL por comprobación y evidencias (capturas, vídeo, traza y tráfico del juego sin tokens).

> **Estado:** qué funciona, qué está en curso y qué viene: [`docs/ESTADO.md`](docs/ESTADO.md).

## Enfoque

El juego es una **caja negra**: lo programa el proveedor y se dibuja en un canvas dentro de un iframe, sin elementos que inspeccionar. Pulsar *Spin* no prueba nada: hay que demostrar lo que ve el jugador.

**Testigos independientes** ([decisión 001](docs/decisiones/001-enfoque-testigos-y-perfiles.md)). Cada comprobación la confirman hasta cinco fuentes, de tres capas distintas (pantalla, red y navegador):

| Testigo | Qué aporta | ¿Lo ve el jugador? |
|---|---|---|
| Pantalla del juego (OCR) | Crédito, apuesta, ganancia, divisa, mensaje | Sí |
| Movimiento de los rodillos | Que el giro empezó y terminó | Sí |
| Cabecera de Betsson | Saldo antes y después | Sí |
| Servidor del juego (tráfico observado, sin modificar) | Apuesta cobrada, premio y saldo según el proveedor | No |
| Eventos del juego (`postMessage` juego → casino, [decisión 003](docs/decisiones/003-testigo-eventos-del-juego.md)) | Inicio y fin de ronda, apuesta, premio, saldo, idioma y divisa que el juego comunica a Betsson | No |

La pantalla es obligatoria: sin lectura visual no hay PASS. Si los testigos discrepan, el resultado es **FAIL por discrepancia**, que es justo un fallo de integración.

**Pantalla readaptable** ([decisión 002](docs/decisiones/002-perfiles-aprendidos-y-coste.md)). Nada de coordenadas ni textos fijos: cada juego tiene un **perfil aprendido** (`profiles/<proveedor>/<juego>/`) con las etiquetas de su HUD y la imagen de sus controles. En cada ejecución los controles se **buscan por su aspecto en toda la pantalla**, así que un botón movido o una resolución distinta no rompen nada. Si el proveedor cambia la interfaz, una **IA de visión** (Claude Haiku 5.5) reaprende el perfil una vez, lo valida y lo anota en el informe.

## Coste para Betsson

| Concepto | Coste |
|---|---|
| Ejecución normal (perfil ya aprendido: todo local) | **0 € de IA** (no se llama a la IA mientras el juego carga) |
| Incorporar un juego nuevo (`learn`) | ≈ 0,002–0,01 $ (medido: 0,0019 $ con Haiku; 0,0075 $ si hace falta Sonnet) |
| Reparación tras un cambio de interfaz | ≈ 0,002 $ |
| Tirada de prueba (0,20 €, RTP ≈ 94,5 %) | ≈ 0,01 € esperado |

Frente a 15–30 minutos de QA manual por juego nuevo. Sin clave de API el producto sigue funcionando con los perfiles ya aprendidos.

## Más allá de lo pedido

Lo que añade valor sobre los requisitos del reto, con su evidencia:

| Aportación | Por qué importa a Betsson | Dónde verlo |
|---|---|---|
| **Cinco testigos de tres capas** (pantalla, red, navegador) con regla de discrepancia | Detecta fallos de integración: el jugador ve una cosa y el sistema registra otra. Un clic nunca basta para un PASS | [decisiones 001](docs/decisiones/001-enfoque-testigos-y-perfiles.md) y [003](docs/decisiones/003-testigo-eventos-del-juego.md); columna "Testigos" del informe |
| **Canal `postMessage` juego → casino** como testigo | Valida la integración con los datos que el proveedor comunica a Betsson (ronda, apuesta, premio, saldo, idioma, divisa) | `eventos_del_juego.json` en cada escenario |
| **Pantalla readaptable** con perfiles aprendidos por IA | Sigue funcionando si el proveedor mueve un botón o cambia un texto; incorporar un juego cuesta ≈ 0,002 $ | [decisión 002](docs/decisiones/002-perfiles-aprendidos-y-coste.md), `tests/unit/test_screen_model.py` |
| **Coste de IA casi nulo y medido** | Las ejecuciones normales no llaman a la IA; cada llamada registra tokens y coste; nunca se llama mientras el juego carga | Notas del informe; salida de `learn` |
| **Seguridad de evidencias** | Credenciales difuminadas en el vídeo, traza ligera y limpiada, escáner que retira cualquier archivo con secretos | `src/betsson_validator/security.py` |
| **Salvaguardas de dinero real** | Apuesta mínima comprobada en pantalla, tope `max_bet`, un giro nunca se repite y botones ambiguos ("+" frente a "−") rechazados | `game/player.py`, `tests/unit/test_learned_profile.py` |
| **Idioma del mensaje verificado** | El mensaje de saldo insuficiente se lee completo y su idioma se contrasta con el que comunica el juego | Escenario 2 del informe |

## Uso

Requisitos: [uv](https://docs.astral.sh/uv/) (instala Python 3.13 por sí solo) y Google Chrome.

```bash
uv sync
cp .env.example .env          # y rellena las credenciales (nunca se suben al repositorio)

uv run python -m betsson_validator run                       # ambos escenarios, juego por defecto
uv run python -m betsson_validator run --scenario completed_spin --game sweet-bonanza-2500
uv run python -m betsson_validator learn --game big-bass-splash   # incorporar un juego nuevo (no gira)
```

El informe queda en `reports/<fecha>/index.html` (más `report.json` y las evidencias por escenario).

**Añadir otro juego:** `learn --game <slug>`. **Añadir otro proveedor:** un YAML en `config/providers/` con el texto de su chip en el filtro y un juego por defecto, y después `learn`. **Añadir otro mercado:** un YAML en `config/markets/`.

### Calidad

```bash
uv run ruff format . && uv run ruff check .   # formato y lint
uv run mypy src tests                         # tipado estricto
uv run pytest -m "not e2e"                    # tests (incluyen capturas reales y cambios de interfaz simulados)
```

## GitHub Actions

- **CI** (`.github/workflows/ci.yml`): formato, lint, tipos y tests en cada push.
- **Validación** (`.github/workflows/validate.yml`): ejecuta ambos escenarios por mercado y publica el informe como artefacto y como resumen de la ejecución. Se lanza a mano (*Run workflow*) porque juega con dinero real.
  - betsson.es **solo responde desde España**: los runners de GitHub (EE. UU.) reciben "no disponible en este país". Por eso se ejecuta en un **runner propio con IP española**, elegido con la variable del repositorio `VALIDATION_RUNS_ON` (hoy `["self-hosted","betsson-es"]`). En producción, una máquina x86 en Oracle Cloud Madrid.
  - Credenciales en *Settings → Secrets and variables → Actions* con los mismos nombres que en `.env.example`.

## Seguridad

- Credenciales solo en `.env` (local) o GitHub Secrets. Los campos de login se difuminan en el vídeo y la traza empieza después del login.
- La traza es ligera (solo acciones) y se limpia de credenciales y tokens; al final de cada ejecución un escáner revisa todas las evidencias y **retira cualquier archivo con secretos** antes de publicarlo.
- Salvaguardas de dinero real: apuesta mínima comprobada en pantalla, tope `max_bet` antes de girar y un giro nunca se repite.

## Estructura

```
config/markets/          Mercado: URL, idioma, divisa, textos de la web, variables de credenciales
config/providers/        Proveedor: chip del filtro, juego por defecto, tope de apuesta, testigo de red
profiles/                Perfiles aprendidos por juego (etiquetas del HUD + imágenes de controles)
src/betsson_validator/
  casino/                Web de Betsson: cookies, login, saldo, filtro, sesión de juego, lanzamiento
  game/                  Jugar mirando la pantalla (genérico para cualquier proveedor)
  perception/            OCR, búsqueda por imagen, movimiento, IA de visión
  providers/pragmatic/   Testigo de red de Pragmatic Play (gameService)
  scenarios/             Comprobaciones oficiales evaluadas con testigos
  domain/                Dinero, regla del veredicto, comprobaciones (lógica pura)
  report/                Informe HTML/JSON y resumen Markdown
docs/                    Estado, decisiones (ADR), flujo real de betsson.es, documentación del reto
```
