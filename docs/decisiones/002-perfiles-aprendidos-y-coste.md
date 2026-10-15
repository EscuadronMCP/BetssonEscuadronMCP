# 002. Pantalla readaptable: perfiles aprendidos por IA, ejecución local

- **Fecha:** 2026-10-15
- **Estado:** aceptada (concreta la parte C de la [decisión 001](001-enfoque-testigos-y-perfiles.md))

## Contexto

El equipo pidió que la prueba no dependa de dónde está un botón ni de qué texto muestra, que sea demostrable en más juegos y proveedores, y que el uso de la API no encarezca el producto para Betsson. La primera versión funcionaba con coordenadas y etiquetas fijas de Sweet Bonanza 2500: frágil y no extensible.

## Decisión

Tres capas, de la más barata a la más cara:

| Capa | Cuándo | Coste | Si falla |
|---|---|---|---|
| 1. Perfil aprendido + visión local (OCR por etiquetas, búsqueda del control por su imagen a cualquier posición y escala, detección de movimiento) | Siempre | 0 € | capa 3 |
| 2. Parte de la capa 1: la búsqueda recorre toda la pantalla, así que un botón movido o redimensionado se encuentra sin IA | Botón movido / otra resolución | 0 € | capa 3 |
| 3. IA de visión (Claude Haiku 5.5; Sonnet 5.5 solo si Haiku no supera la validación) | Juego nuevo (`learn`) o perfil que dejó de encajar (una vez por ejecución) | ≈ 0,002 $ por captura | FAIL explicado |

- **Perfil por juego** en `profiles/<proveedor>/<juego>/`: etiquetas del HUD, imagen de cada control y zona de rodillos. Se versiona: cualquiera puede revisar qué aprendió la IA.
- **Validación obligatoria** de lo aprendido antes de guardarlo: el OCR lee crédito y apuesta con las etiquetas aprendidas; el crédito coincide con el saldo de la cabecera de Betsson; pulsar el botón aprendido de bajar apuesta la baja de verdad.
- **Reparación en ejecución**: si el perfil no encaja, se reaprende una vez, se anota en el informe y se guarda un *perfil propuesto* en las evidencias. Nunca se sobrescribe el perfil versionado sin revisión.
- **Sin clave de API** el producto sigue funcionando con los perfiles ya aprendidos; solo pierde la autorreparación.
- **Seguridad del dinero real**: un giro nunca se repite; si no se confirma, es FAIL.

## Coste para Betsson

| Concepto | Coste |
|---|---|
| Incorporar un juego nuevo | ≈ 0,002–0,01 $ (2–3 capturas con Haiku 5.5) |
| Ejecución normal | 0 $ de IA |
| Reparación tras un cambio de interfaz | ≈ 0,002 $ |
| Tirada de prueba (0,20 €, RTP ≈ 94,5 %) | ≈ 0,01 € esperado |
| GitHub Actions / runner propio | Gratis (runner propio) |

Frente a 15–30 minutos de QA manual por juego nuevo.

## Consecuencias

- Añadir un juego: `python -m betsson_validator learn --game <slug>`. Añadir un proveedor: un YAML en `config/providers/` (chip del filtro y juego por defecto) + `learn`.
- Los tests exigentes (`tests/unit/test_screen_model.py`, `test_templates.py`) simulan sobre capturas reales un botón movido, un botón rediseñado, una resolución distinta y unas etiquetas cambiadas.
