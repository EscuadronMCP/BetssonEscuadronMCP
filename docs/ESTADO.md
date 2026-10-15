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
2. Conseguir acceso a betsson.com desde una IP de Malta (VPN).
3. Decidir el enfoque técnico tras la presentación del reto (ADR en `docs/decisiones/`).

## Problemas conocidos
- Desde España, betsson.com redirige a betsson.es: hace falta una IP de Malta (recomendación de la organización).
- Los runners de GitHub Actions tampoco están en Malta: el workflow necesitará resolver el acceso por región.
