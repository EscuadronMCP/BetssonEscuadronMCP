# Estado del proyecto

Memoria compartida del equipo: **por dónde vamos y hacia dónde**. Se actualiza en cada commit que cierra un paso (ver `CLAUDE.md`, sección 2). Si eres una IA que acaba de hacer pull, lee esto primero.

## Rumbo

**Enfoque aceptado:** testigos independientes (D) con perfiles aprendidos (C), en Python. Detalle en [`decisiones/001-enfoque-testigos-y-perfiles.md`](decisiones/001-enfoque-testigos-y-perfiles.md).

**Mercado:** solo betsson.es (español, EUR). Proveedor: PragmaticPlay (pestaña Casino → filtro de proveedores al final de la página).

## Hoja de ruta

Cada etapa deja una versión entregable. Marca `[x]` al terminar y apunta en "En curso" quién está con cuál.

- [ ] **E0. Esqueleto:** proyecto Python, Playwright, pytest, linter, tipado, configuración de mercado y un workflow básico de CI. No necesita credenciales.
- [ ] **E1. Web de Betsson:** login, Casino, filtro PragmaticPlay, lanzar un juego en Real Play, leer el saldo de Betsson. Necesita las cuentas de prueba.
- [ ] **E2. Escenario 1 de principio a fin** con el testigo de pantalla leído por IA de visión. **Primer entregable completo.**
- [ ] **E3. Resto de testigos (D):** saldo de Betsson, historial de transacciones y red del juego; regla del veredicto con discrepancias.
- [ ] **E4. Escenario 2:** saldo insuficiente.
- [ ] **E5. Workflow de GitHub Actions** que ejecuta ambos escenarios y publica el informe.
- [ ] **E6. Perfiles aprendidos (C):** modo aprendizaje, ejecución determinista con OCR y plantillas, autorreparación.
- [ ] **E7. Demo de extensibilidad:** incorporar un segundo proveedor (bonus).

## Funciona
- Repositorio, normas del equipo (`CLAUDE.md`) y estructura de documentación.
- `.claude/settings.json`: Claude Code hace commit/pull/push a `main` sin pedir permiso; `push --force` y leer `.env` bloqueados.
- Documentación oficial en `docs/hackaton/` y requisitos del reto resumidos en `CLAUDE.md`.
- `.env.example` con las variables de las cuentas de prueba de betsson.es (el `.env` real es local).

## En curso
| Tarea | Responsable | Desde |
|-------|-------------|-------|
| — | — | — |

## Siguiente paso
1. E0: esqueleto del proyecto (se puede hacer ya, sin credenciales).
2. Recibir las cuentas de prueba de Betsson y rellenar `.env`.
3. Preguntar a los mentores: captcha o verificación en dos pasos en el login, bloqueo de IP de GitHub Actions, tráfico de red como testigo, número de tiradas permitidas, preparación de la cuenta sin saldo, y si el historial muestra cada tirada.

## Problemas conocidos
- Sin comprobar si betsson.es deja jugar desde los runners de GitHub Actions (EE. UU.). Si no, hará falta IP española (p. ej. runner propio en la región de Oracle Cloud en Madrid).

## Cambios de rumbo
Registro de pivotes, errores de enfoque y cambios de dirección, el más reciente primero. Cada uno enlaza a su decisión en `docs/decisiones/`.

| Fecha | Cambio | Motivo | Decisión |
|---|---|---|---|
| 2026-10-15 | Mercados reducidos a solo betsson.es | Betsson lo indica porque no todos los equipos tienen VPN | — |
| 2026-10-15 | betsson.pe sustituido por betsson.es | Indicación de Betsson | — |
| 2026-10-15 | Enfoque elegido: D sobre C | Fiabilidad y extensibilidad, lo más valorado | [001](decisiones/001-enfoque-testigos-y-perfiles.md) |
