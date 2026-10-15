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
- [x] **E7. Extensibilidad:** segundo juego de Pragmatic con interfaz muy distinta (Big Bass Halloween Splash 1000), aprendido por 0,0006–0,0011 $ sin escribir código: **PASS en ambos escenarios** (15/10). Para hacerlo posible se generalizaron el movimiento (umbrales adaptativos al fondo animado y reposo relativo al giro) y la lectura del HUD (etiquetas repetidas). Sweet Bonanza sigue en PASS (regresión). En todas, cero llamadas a la IA.

## Funciona
- **Flujo completo automático** (`python -m betsson_validator run`): navegador → cookies → login → saldo → lobby → filtro → juego → sesión de juego → bienvenida → apuesta mínima → giro → informe.
- **Cinco testigos** por comprobación y regla del veredicto (`scenarios/evaluation.py`).
- **Perfiles aprendidos** (`profiles/`, comando `learn`) con validación por efecto: el OCR lee crédito y apuesta, el crédito coincide con el saldo de Betsson, y "+" sube y "−" baja la apuesta.
- **Readaptación probada** con capturas reales: botón movido, rediseñado, otra resolución, etiquetas cambiadas y controles ambiguos ("+" frente a "−", "girar" frente a "continuar").
- **Seguridad:** credenciales difuminadas en el vídeo, traza ligera y limpiada, escáner que retira evidencias con secretos, salvaguardas de dinero (`max_bet` y un único giro).
- **Rendimiento (15/10):** ambos escenarios en paralelo en ≈ 65–71 s (antes ≈ 3 min), informe < 1 MB (antes ≈ 73 MB), cero llamadas a la IA en ejecuciones normales. **PASS en GitHub Actions** (runner propio) el 15/10.
- **Informe** HTML/JSON con PASS/FAIL por comprobación, testigos, capturas y enlaces a vídeo, traza, eventos y tráfico; resumen Markdown en GitHub Actions.
- **Fallo intencionado para demostraciones** (`run --inject-fault <escenario>`, también en Actions con `inject_fault`): suma 0,01 € al saldo final de Betsson leído antes de evaluar; el informe lo anuncia y marca FAIL por discrepancia.
- **Auditoría del equipo corregida (15/10)** con tests de regresión: condiciones previas antes de girar (la cuenta "sin saldo" con fondos no gira), apuesta aceptada por el servidor y premio declarado (`tw`), eventos atribuidos al marco del juego (también dentro de shadow DOM) y marcados como incoherentes si se repiten o desordenan, OCR sin importes de otra etiqueta ni lecturas dudosas, divisa obligatoria en el HUD, valores mezclados = FAIL, un PASS duplicado no oculta un FAIL, secretos escapados en JSON/HTML y en URLs de errores, OCR de capturas, informe final auditado, enlaces POSIX (Windows) y testigos por proveedor en un registro (`providers/registry.py`). También: un empate entre dos controles es ambiguo y no se pulsa, nunca hay clics a ciegas en el centro, "girar" solo se usa como "continuar" si el OCR no ve el marcador, el saldo final de Betsson exige dos lecturas iguales, la lectura final del juego exige crédito y premio estables (si no, se marca "no se estabilizó" y no vale como prueba) y el coste de IA se suma con cerrojo entre hilos.
- Documentación: [`betsson-es-flujo.md`](betsson-es-flujo.md) (cómo es la web por dentro) y la carpeta [`mentores/`](../mentores/) (informe del proyecto en PDF e informe generado por el programa).

## En curso
| Tarea | Responsable | Desde |
|-------|-------------|-------|
| — | — | — |

## Siguiente paso
1. **Entrega en Campus Virtual antes de las 20:00** (enlace al repositorio; la carpeta `mentores/` tiene el informe del proyecto en PDF y un informe real del programa).
2. Decidir la **visibilidad del repositorio** para el jurado (hoy es privado en la organización `EscuadronMCP`): invitar al jurado o hacerlo público (contiene los PDF del reto).
3. Runner en línea y nadie usando la cuenta con saldo durante la demostración.

## Última verificación (15/10, 17:30)
- **GitHub Actions** (runner propio, run 38760353066, código final): **ambos escenarios PASS en 74 s**, informe publicado como artefacto, sin llamadas a la IA.
- **Local** (17:23): escenario 1 PASS con los cinco testigos confirmando; escenario 2 con el **fallo intencionado** → FAIL «Lo que ve el jugador lo contradice: cabecera de Betsson: saldo de Betsson 0.00 EUR → 0.01 EUR». Es el informe de `mentores/`. 0 fugas de secretos (texto, zip y OCR de capturas).
- **GitHub Actions con `inject_fault`** (run 38760962455, solo escenario 2, sin gastar dinero): FAIL por el fallo intencionado, con el aviso en el resumen y el informe publicado igualmente como artefacto.
- Antes, Sweet Bonanza 2500 y Big Bass Halloween Splash 1000 en PASS en ambos escenarios.
- CI: formato, lint, tipos y 174 tests en verde.

## Problemas conocidos
- **betsson.es bloquea las IP de fuera de España** ("no disponible en este país"), así que los runners de GitHub no sirven. Se resuelve con un runner propio: este Mac, etiqueta `betsson-es`, variable `VALIDATION_RUNS_ON`. En producción sería Oracle Cloud Madrid, en x86 porque Chrome no tiene build ARM64 para Linux. Si el Mac pierde la red, el runner se cae: relanzarlo con `cd ~/actions-runner-betsson && nohup ./run.sh &`.
- **Demasiados logins seguidos** → la web responde HTTP 400 temporalmente. No lanzar ejecuciones en bucle; esperar unos minutos.
- **La web recuerda el filtro de proveedor de la cuenta**: se pulsa "Limpiar" antes de elegir el chip.
- **El juego recuerda la última apuesta**: en el mínimo, "−" aparece desactivado y no se busca con IA.
- **Avisos tardíos con la red lenta** (cookies, sesión de juego): las cookies se aceptan cuando aparezcan y la sesión se da por abierta cuando el juego del proveedor ya cargó.
- **El contador de crédito se anima** tras un premio: la lectura final espera a que el crédito sea estable.
- **Sesión del juego expirada (15/10, 17:22):** al pulsar girar, Pragmatic mostró «Sesión expirada» (probablemente la cuenta se abrió en otro dispositivo). El validador dio FAIL «el juego no reaccionó al botón de girar», sin gastar dinero. Evidencias en `reports/sesion-expirada-1722` (local). Resuelto: el motivo del informe cita ahora cualquier aviso del juego (`ui.game_notice_pattern`), sin confundirlo con el de saldo insuficiente.
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
