# Estado del proyecto

Memoria compartida del equipo: **por dónde vamos y hacia dónde**. Se actualiza en cada commit que cierra un paso (ver `CLAUDE.md`, sección 2). Si eres una IA que acaba de hacer pull, lee esto primero.

## Rumbo

**Enfoque aceptado:** testigos independientes con perfiles aprendidos, en Python:
- [001](decisiones/001-enfoque-testigos-y-perfiles.md): testigos independientes; la pantalla es obligatoria y cualquier discrepancia es FAIL.
- [002](decisiones/002-perfiles-aprendidos-y-coste.md): pantalla readaptable. La IA aprende un perfil por juego una vez; cada ejecución es local, sin IA.
- [003](decisiones/003-testigo-eventos-del-juego.md): quinto testigo, los eventos `postMessage` que el juego envía al casino.

**Mercado:** solo betsson.es (español, EUR). Proveedor: PragmaticPlay (Casino → Filtros → chip "Pragmatic Play" → Resultados). Juego por defecto: Sweet Bonanza 2500.

## Hoja de ruta

Cada etapa deja una versión entregable. Marca `[x]` al terminar y apunta en "En curso" quién está con cuál.

- [x] **E0. Esqueleto:** Python 3.13 con uv, Playwright, pytest, ruff, mypy estricto y CI.
- [x] **E1. Web de Betsson:** cookies, login (con antibots AWS WAF), saldo, filtro de proveedor, sesión de juego obligatoria y lanzamiento en Real Play.
- [x] **E2. Escenario 1 de principio a fin:** PASS real en betsson.es.
- [x] **E3. Testigos:** pantalla (OCR), movimiento, cabecera de Betsson, red del juego y eventos del juego. El historial de transacciones de Betsson queda fuera: los otros cuatro ya corroboran cada comprobación.
- [x] **E4. Escenario 2:** saldo insuficiente, PASS real.
- [x] **E5. Workflow de GitHub Actions:** PASS en el runner propio (15/10).
- [x] **E6. Perfiles aprendidos:** perfil real de Sweet Bonanza aprendido y validado (0,0019–0,0075 $). PASS de principio a fin en ambos escenarios con los cinco testigos y **cero llamadas a la IA** (15/10, `reports/e2e-v5`).
- [ ] **E7. Demo de extensibilidad:** `learn` sobre un segundo juego y, si da tiempo, de otro proveedor (bonus).

## Funciona
- **Flujo completo automático** (`python -m betsson_validator run`): navegador → cookies → login → saldo → lobby → filtro → juego → sesión de juego → bienvenida → apuesta mínima → giro → informe.
- **Cinco testigos** por comprobación y regla del veredicto (`scenarios/evaluation.py`).
- **Perfiles aprendidos** (`profiles/`, comando `learn`) con validación por efecto: el OCR lee crédito y apuesta, el crédito coincide con el saldo de Betsson, y "+" sube y "−" baja la apuesta.
- **Readaptación probada** con capturas reales: botón movido, rediseñado, otra resolución, etiquetas cambiadas y controles ambiguos ("+" frente a "−", "girar" frente a "continuar").
- **Seguridad:** credenciales difuminadas en el vídeo, traza ligera y limpiada, escáner que retira evidencias con secretos, salvaguardas de dinero (`max_bet` y un único giro).
- **Informe** HTML/JSON con PASS/FAIL por comprobación, testigos, capturas y enlaces a vídeo, traza, eventos y tráfico; resumen Markdown en GitHub Actions.
- Documentación: [`betsson-es-flujo.md`](betsson-es-flujo.md) (cómo es la web por dentro) e [`investigacion-equipo.md`](investigacion-equipo.md).

## En curso
| Tarea | Responsable | Desde |
|-------|-------------|-------|
| Workflow de validación en el runner + E7 (segundo juego) | Claude (sesión de xXErDaniXx06) | 2026-10-15 |

## Siguiente paso
1. Lanzar el workflow de validación en el runner propio y comprobar el informe publicado.
2. E7: `learn --game <otro juego>` y ejecución para demostrar la extensibilidad.
3. Preparar la demo de 7 minutos.

## Problemas conocidos
- **betsson.es bloquea las IP de fuera de España** ("no disponible en este país"), así que los runners de GitHub no sirven. Se resuelve con un runner propio: este Mac, etiqueta `betsson-es`, variable `VALIDATION_RUNS_ON`. En producción sería Oracle Cloud Madrid, en x86 porque Chrome no tiene build ARM64 para Linux. Si el Mac pierde la red, el runner se cae: relanzarlo con `cd ~/actions-runner-betsson && nohup ./run.sh &`.
- **Demasiados logins seguidos** → la web responde HTTP 400 temporalmente. No lanzar ejecuciones en bucle; esperar unos minutos.
- **La web recuerda el filtro de proveedor de la cuenta**: se pulsa "Limpiar" antes de elegir el chip.
- **El juego recuerda la última apuesta**: en el mínimo, "−" aparece desactivado y no se busca con IA.
- **Avisos tardíos con la red lenta** (cookies, sesión de juego): las cookies se aceptan cuando aparezcan y la sesión se da por abierta cuando el juego del proveedor ya cargó.
- **El contador de crédito se anima** tras un premio: la lectura final espera a que el crédito sea estable.
- **⚠️ Nadie debe usar la cuenta con saldo mientras corren las pruebas.** El 15/10 una ejecución dio FAIL por discrepancia: con una apuesta de 0,20 € sin premio, el saldo bajó 2,30 €; los propios eventos del juego lo muestran (otra sesión gastó 2,10 € a la vez). El validador lo detectó correctamente.
- **Saldo de la cuenta con saldo**: bajó de 64 € a 0,35 € por un uso ajeno a este programa. Betsson la recargó. Cada ejecución del escenario 1 gasta una tirada de 0,20 €.
- **Trazas enormes (hasta 900 MB)** con instantáneas: ahora la traza es ligera (solo acciones).
- **Resuelto: login rechazado (403) por AWS WAF.** Se lanza Chrome sin la marca de automatización, se espera el token y se teclea a ritmo humano.

## Cambios de rumbo
Registro de pivotes, errores de enfoque y cambios de dirección, el más reciente primero. Cada uno enlaza a su decisión en `docs/decisiones/`.

| Fecha | Cambio | Motivo | Decisión |
|---|---|---|---|
| 2026-10-15 | Quinto testigo: eventos `postMessage` del juego | Sugerencia de un mentor; capa del navegador sin usar | [003](decisiones/003-testigo-eventos-del-juego.md) |
| 2026-10-15 | De coordenadas y textos fijos a perfiles aprendidos por IA con ejecución local | Que no se rompa si el proveedor cambia la interfaz y sea extensible sin encarecer | [002](decisiones/002-perfiles-aprendidos-y-coste.md) |
| 2026-10-15 | Validación en runner propio con IP española | betsson.es bloquea los runners de GitHub (EE. UU.) | [002](decisiones/002-perfiles-aprendidos-y-coste.md) |
| 2026-10-15 | Mercados reducidos a solo betsson.es | Betsson lo indica porque no todos los equipos tienen VPN | — |
| 2026-10-15 | betsson.pe sustituido por betsson.es | Indicación de Betsson | — |
| 2026-10-15 | Enfoque elegido: D sobre C | Fiabilidad y extensibilidad, lo más valorado | [001](decisiones/001-enfoque-testigos-y-perfiles.md) |
