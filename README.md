# BetssonEscuadronMCP

Validador automático de juegos de casino para el reto de **Betsson** en el **Malackathon 2026** (Universidad de Málaga): *Intelligent Game Validation*.

Entra en **betsson.es**, lanza un juego de **PragmaticPlay** en Real Play y comprueba, **como lo vería un jugador**, que:

1. **Una tirada se completa** y los saldos cuadran: `saldo después = saldo antes − apuesta + premio`.
2. **Con saldo insuficiente**, la tirada se rechaza con el mensaje adecuado en español y ningún saldo cambia.

Todo sin intervención humana, con un informe de PASS/FAIL por comprobación y evidencias (capturas, traza y vídeo).

> **Estado:** en desarrollo. Qué funciona, qué está en curso y qué viene: [`docs/ESTADO.md`](docs/ESTADO.md).

## Enfoque

El juego es una **caja negra**: lo programa el proveedor y se dibuja en un canvas dentro de un iframe, sin elementos de la página que inspeccionar. Por eso no basta con hacer clic en *Spin*: hay que demostrar lo que ve el jugador.

Elegimos **testigos independientes con perfiles aprendidos** ([decisión 001](docs/decisiones/001-enfoque-testigos-y-perfiles.md)):

- **Cada hecho se confirma con varias fuentes independientes:** la pantalla del juego, el saldo de Betsson, el historial de transacciones de la cuenta y el tráfico de red del juego (solo observado).
- **La pantalla manda:** sin lectura visual fiable no hay PASS. Si los testigos no coinciden, el resultado es FAIL por discrepancia, que es justo un fallo de integración.
- **El juego se lee con perfiles aprendidos:** una IA de visión explora el juego una vez y genera un perfil (dónde están saldo, apuesta, premio y botón de giro). Después se ejecuta de forma determinista con OCR y búsqueda de imágenes; si la interfaz cambia, la IA lo repara.
- **Extensible a otros proveedores:** añadir uno es escribir su adaptador y ejecutar el modo aprendizaje, sin tocar escenarios, testigos ni informe.

## Estructura

```
CLAUDE.md               Normas del equipo para Claude Code (obligatorio leerlo)
docs/ESTADO.md          Estado actual, rumbo y siguientes pasos
docs/decisiones/        Decisiones de arquitectura y cambios de rumbo (ADR)
docs/hackaton/          Enunciado oficial del reto y documentación del Malackathon
.env.example            Variables necesarias (credenciales de las cuentas de prueba)
```

Estructura de código objetivo: ver la [decisión 001](docs/decisiones/001-enfoque-testigos-y-perfiles.md#arquitectura).

## Uso

_Pendiente: se completará con la instalación, la ejecución local y el workflow de GitHub Actions en cuanto exista el esqueleto del proyecto._

Las credenciales nunca se suben al repositorio: van en `.env` (copiando `.env.example`) y, en GitHub Actions, en los Secrets del repositorio.
