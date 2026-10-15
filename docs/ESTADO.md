# Estado del proyecto

Memoria compartida del equipo. Se actualiza en cada commit que cierra un paso (ver `CLAUDE.md`, sección 2).

## Funciona
- Repositorio, normas del equipo (`CLAUDE.md`) y estructura de documentación.
- `.claude/settings.json`: Claude Code hace commit/pull/push a `main` sin pedir permiso; `push --force` y leer `.env` bloqueados.
- Documentación oficial en `docs/hackaton/` y requisitos del reto resumidos en `CLAUDE.md`.
- `.env.example` con las variables de las cuentas de prueba por mercado (el `.env` real es local).

## En curso
| Tarea | Responsable | Desde |
|-------|-------------|-------|
| — | — | — |

## Siguiente paso
1. Rellenar `.env` con las cuentas de prueba cuando Betsson las entregue.
2. Recibir las cuentas de prueba de Betsson.
3. Elegir enfoque entre las opciones A–E de [Opciones de solución](https://claude.ai/code/artifact/2ef1bc9e-a713-4523-b95a-7ccbcfe4690b) (recomendada: C + D) y registrarlo como ADR en `docs/decisiones/`.
4. Preguntar a los mentores: captcha/2FA en login, bloqueo de IP de GitHub Actions, tráfico de red como testigo, nº de tiradas, cuenta sin saldo.

## Problemas conocidos
- Desde España, betsson.com redirige a betsson.es. **Resuelto en local** con Proton VPN Plus → Malta: betsson.com sirve `/en` (comprobado el 15/10).
- betsson.pe se sustituye por betsson.es (indicación de Betsson). betsson.es carga sin redirección también con la VPN de Malta, así que ambos mercados funcionan con la misma conexión (comprobado el 15/10).
- Los runners de GitHub Actions tampoco están en Malta: el workflow necesitará resolver el acceso por región.
