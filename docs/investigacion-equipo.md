# Lo útil de la investigación del equipo

Resumen de los informes de `docs/hackaton/DocuCompañeros/`, cruzado con lo comprobado en la web real (ver `betsson-es-flujo.md`). **Verificado** = comprobado por nosotros; **por verificar** = hipótesis de los informes.

## Aplicamos

| Idea | Estado | Dónde |
|---|---|---|
| Red de Pragmatic: `POST …/gs2c/ge/v4/gameService`, cuerpo y respuesta `k=v&k=v`; `action` doInit/doSpin/doCollect; `c` moneda, `l` líneas, `balance`, `tw` premio, `na` siguiente acción (`s` listo, `c` falta cobrar) | Verificado doInit (`balance`, `sc`, `defc`, `na=s`); doSpin/doCollect por verificar | Testigo de red |
| Un giro solo está liquidado cuando la última respuesta trae `na=s` | Por verificar | Testigo de red |
| Apuesta = `c × l` | Por verificar (`defc=0.10` y APUESTA en pantalla 2,00 € → 20 líneas) | Testigo de red |
| El juego dibuja con WebGL y fuentes de mapa de bits: no sirve interceptar `fillText`; capturar el iframe con Playwright | Verificado que la captura del iframe en headless muestra el juego | Testigo de pantalla |
| OCR del HUD: recorte → ampliar 3× (INTER_CUBIC) → gris → invertir → sin umbralizar → regex `\d+[,.]\d{2}` | Por verificar | Percepción |
| Búsqueda del botón de giro: `TM_CCOEFF_NORMED` en gris, umbral 0,80, multiescala, máscara circular | Por verificar | Percepción |
| Movimiento solo dentro de la zona de los rodillos, con línea base previa | Por verificar | `perception/motion.py` (umbrales en el perfil) |
| Validar lo que aprenda la IA: un recorte se guarda solo si se reencuentra con `maxVal ≥ 0,90` y el CRÉDITO leído coincide con el saldo de Betsson | Adoptado como regla | Perfiles aprendidos (E6) |
| Ocultar credenciales en capturas (`mask`) y en vídeo y traza | `mask` verificado | Evidencias |
| Historial de transacciones: "Mi cuenta" → "Historial de transacciones" / "Historial de juego" | Por verificar en betsson.es | Testigo de historial |
| En CI headless sin GPU el canvas puede salir negro → `xvfb-run` + modo con ventana | Por verificar en GitHub Actions | Workflow |

## Descartado o corregido

- **"El antibots es Cloudflare o Akamai"**: es **AWS WAF**, y además del flag hay que teclear a ritmo humano y esperar su token.
- **Mercados betsson.com + betsson.pe**: Betsson los ha sustituido por **solo betsson.es**.
- **Runner en Oracle Cloud ARM (A1)**: Google Chrome estable no tiene build para Linux ARM64 y el login depende de Chrome → si se usa Oracle, máquina x86.
- **Texto exacto del mensaje de saldo insuficiente**: nadie lo ha visto. Se capturará en vivo con la cuenta sin saldo. Mientras, el patrón de búsqueda es `(?i)(saldo\s+insuficiente|fondos\s+insuficientes|suficiente\s+(saldo|dinero)|recargue)`.

## Ideas para valorar

- **Juego sin cascadas**: Big Bass Splash (`/casino/tragaperras-slots/big-bass-splash`, 5×3, apuesta mínima citada 0,10 €). Simplifica la conciliación frente a Sweet Bonanza 2500, que tiene cascadas. Por verificar en betsson.es.
- **Bonus**: medir la latencia entre el fin del giro, la respuesta `na=s` y el cambio de saldo en la cabecera de Betsson; capturas anotadas con las regiones leídas y la ecuación de conciliación; sección "Justificación del bonus" en el README.
