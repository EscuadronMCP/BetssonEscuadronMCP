# 001. Enfoque: testigos independientes (D) con perfiles aprendidos (C)

- **Fecha:** 2026-10-15
- **Estado:** aceptada
- **Origen:** documento de opciones A–E, [Opciones de solución](https://claude.ai/code/artifact/2ef1bc9e-a713-4523-b95a-7ccbcfe4690b). Elegida por el equipo.

## Contexto

El reto (`docs/hackaton/2026-10-15_malackathon-student-challenge.pdf`, con los cambios recogidos en `CLAUDE.md`) pide validar en **betsson.es** un juego de **PragmaticPlay** en Real Play con dos escenarios: tirada completada y saldo insuficiente. El juego es una **caja negra**: un iframe con canvas, sin DOM útil y con código del proveedor desconocido. Se valoran sobre todo la **fiabilidad**, que la solución **"vea como un jugador"** y que sea **extensible a otros proveedores**, todo sin intervención humana.

Solo el juego es caja negra. La web de Betsson (login, Casino, filtro de proveedor, lanzamiento, saldo, historial) tiene DOM accesible y es igual para cualquier proveedor.

## Opciones evaluadas

| Opción | Resumen | Por qué no sola |
|---|---|---|
| A. Agente de visión IA | Un modelo multimodal mira capturas y actúa | No determinista, puede leer mal números, caro por ejecución |
| B. Visión clásica + perfiles | OCR, plantillas y movimiento con un perfil calibrado a mano | No escala: cada juego se calibra a mano |
| C. Perfiles aprendidos | La IA genera el perfil de B una vez; se ejecuta B; si falla, la IA lo regenera | Lee bien, pero un único testigo no detecta discrepancias |
| **D. Testigos independientes** | Cada hecho se confirma con varias fuentes independientes | Necesita un testigo visual: lo aporta C |
| E. Instrumentar el render | Interceptar el texto que pinta el canvas | Experimental; puede no cubrir el motor del juego |

## Decisión

**D como columna vertebral y C como forma de leer el juego.** Lenguaje: **Python** (Playwright, pytest, OpenCV, OCR).

### Testigos

| Testigo | Qué aporta | ¿Lo ve el jugador? | Depende del proveedor |
|---|---|---|---|
| **Pantalla del juego** (C) | Apuesta, divisa, saldo del juego, inicio y fin del giro, premio, mensaje | Sí | Sí (perfil por proveedor) |
| **Saldo de Betsson** (DOM) | Saldo antes y después | Sí | No |
| **Historial de transacciones de Betsson** | Apuesta y premio registrados por la cuenta | Sí | No |
| **Red del juego** (observación pasiva, sin modificar) | Petición y respuesta de cada giro (en Pragmatic Play, según análisis no oficial, `balance` y `tw`) | No | Sí (adaptador opcional) |

### Regla del veredicto

1. Cada comprobación del PDF se evalúa con todos los testigos disponibles.
2. **El testigo de pantalla es obligatorio** (criterio "ve como un jugador"). Sin lectura visual fiable no hay PASS.
3. **PASS** solo si la pantalla lo confirma y ningún otro testigo lo contradice.
4. **FAIL por discrepancia** si los testigos no coinciden: el jugador ve una cosa y el sistema registra otra. Es un hallazgo de integración y el informe lo explica.
5. Si un testigo no está disponible, se indica en el informe con menor confianza, pero no impide el PASS si la pantalla y los demás coinciden.

### Perfiles aprendidos (C)

- Un **perfil por proveedor o juego** (archivo versionado en el repositorio) guarda las regiones de saldo, apuesta y premio, las imágenes de referencia del botón de giro y del mensaje de error, y la secuencia de pasos.
- **Modo aprendizaje:** la IA de visión explora el juego una vez y genera el perfil.
- **Modo ejecución:** determinista (búsqueda de plantillas, OCR, detección de movimiento), rápido y sin coste de IA.
- **Autorreparación:** si el perfil no encaja (no encuentra el botón o el OCR no está seguro), se recurre a la IA para esa lectura y se propone un perfil nuevo. En CI se adjunta a la ejecución; nunca se sube solo al repositorio.
- **Añadir un proveedor** = un adaptador nuevo + ejecutar el modo aprendizaje. No se toca nada más.

### Arquitectura

```
config/markets/        Un archivo por mercado (URL, idioma, divisa, variables de credenciales)
profiles/<proveedor>/  Perfiles aprendidos por juego
src/…/casino/          Web de Betsson: login, Casino, filtro, lanzamiento, saldo, historial
src/…/providers/       Interfaz de adaptador de proveedor + PragmaticPlay
src/…/perception/      OCR, plantillas, movimiento, IA de visión (intercambiables)
src/…/witnesses/       Testigos: pantalla, saldo Betsson, historial, red
src/…/scenarios/       Giro completado, saldo insuficiente (solo contra interfaces)
src/…/report/          Veredicto por comprobación + evidencias (capturas sin credenciales, traza, vídeo)
.github/workflows/     Ejecución de ambos escenarios y publicación del informe
```

Es la estructura objetivo; si cambia durante la implementación, se actualiza aquí y en el `README.md`.

## Consecuencias

- **A favor:** máxima fiabilidad y auditabilidad; detecta fallos reales de integración; extensible a otros proveedores con poco trabajo; coste de IA bajo en el día a día.
- **En contra:** más piezas que una opción única, así que se construye por etapas (ver `docs/ESTADO.md`) para tener siempre algo entregable.
- **Riesgos abiertos:** captcha o verificación en dos pasos en el login; que betsson.es no deje jugar desde los servidores de GitHub Actions (alternativa: ejecutar desde Oracle Cloud en Madrid); que el historial no muestre cada tirada; que el formato de red no coincida con el análisis no oficial.
