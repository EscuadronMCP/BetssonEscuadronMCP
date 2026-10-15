# 001. Stack de automatización e IA

- **Fecha:** 2026-10-15
- **Estado:** propuesta — **validar con las bases de `docs/hackaton/` antes de aceptarla**

## Contexto

La aplicación debe, sola y en webs reales de Betsson: (1) encontrar un juego nuevo en el lobby, (2) lanzarlo, (3) jugar una partida y (4) dejar capturas y un veredicto.

Hay dos problemas de naturaleza distinta:
- **Lobby y lanzamiento:** páginas web con DOM y accesibilidad → se pueden automatizar de forma determinista.
- **La partida:** los juegos de casino suelen renderizarse en un `<canvas>` dentro de un `iframe` de un proveedor externo, sin marcado HTML útil. Los selectores no sirven; hace falta visión (captura → coordenadas → clic) o perfiles por proveedor. Las fuentes consultadas señalan que la visión pura da falsos positivos, por lo que hay que verificar cada acción.

## Opciones evaluadas

| Opción | A favor | En contra |
|---|---|---|
| **Playwright** | Estándar actual para proyectos nuevos; Chromium/Firefox/WebKit con una API; auto-waiting (sin `sleep`); `frameLocator` para iframes; capturas y trazas integradas; modo visión para canvas en Playwright MCP / CLI | Selectores frágiles si la web cambia (mitigable con IA) |
| Selenium | Máxima compatibilidad (Grid, Java/C#, Appium) | Más lento y propenso a tests inestables; no aporta nada que necesitemos |
| Puppeteer | Ligero, buen control de Chrome | Prácticamente solo Chromium y Node; menos utilidades de testing |
| Stagehand (sobre Playwright) | Primitivas IA (`act`, `extract`, `observe`) para elementos variables; cachea selectores tras la primera ejecución | Dependencia y proveedor extra; menos control |
| Browser Use (agente autónomo) | Máxima autonomía | Re-razona en cada paso: más varianza, coste y latencia; peor para un veredicto reproducible |

## Decisión propuesta

1. **Playwright como base** para navegación, lobby, lanzamiento, capturas y trazas (determinista, rápido, reproducible).
2. **Modelo de visión (Claude con capacidad de *computer use*/coordenadas)** solo donde el DOM no llega: interactuar con el canvas del juego y evaluar visualmente cada paso para el veredicto. Detrás de una interfaz propia (inversión de dependencias), con verificación tras cada acción (captura antes/después).
3. **Stagehand** queda como opción a evaluar si los selectores del lobby resultan demasiado variables entre webs de Betsson.
4. **Oracle Cloud:** no necesario de entrada; el flujo corre en local. Reevaluar si las bases exigen una demo desplegada o ejecución programada.
5. **Lenguaje (TypeScript o Python):** pendiente. Ambos tienen Playwright oficial. Elegir según la experiencia del equipo y lo que pidan las bases.

## Preguntas abiertas (resolver con las bases)

- ¿Qué webs de Betsson y qué juegos? ¿Hay cuentas de prueba o modo demo sin login?
- ¿Cómo se define "juego nuevo" (lista dada, detección automática)?
- ¿Formato esperado de las capturas y del veredicto? ¿Criterios de evaluación?
- ¿Restricciones de herramientas, proveedores de IA o despliegue?

## Consecuencias

- La lógica de negocio depende de interfaces (`LobbyNavigator`, `GameLauncher`, `GamePlayer`, `EvidenceRecorder`, `VerdictEmitter`…), no de Playwright ni del proveedor de IA: se puede cambiar cualquiera sin tocar el resto.
- El coste de IA se limita a la partida y al veredicto visual.

## Fuentes

- [Playwright vs Puppeteer vs Selenium 2026 (Apify)](https://use-apify.com/blog/playwright-vs-puppeteer-vs-selenium-2026)
- [Playwright vs Selenium (AIMultiple)](https://aimultiple.com/playwright-vs-selenium)
- [Stagehand vs Browser Use vs Playwright (pkgpulse)](https://www.pkgpulse.com/guides/stagehand-vs-playwright-ai-vs-browser-use-ai-web-2026)
- [Playwright MCP — Vision Mode](https://playwright.dev/mcp/vision-mode)
- [Playwright MCP vs CLI (morphllm)](https://morphllm.com/playwright-mcp)
