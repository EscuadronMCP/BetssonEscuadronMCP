# Guía de la demo (7 minutos)

Pensada para que cualquier miembro del equipo pueda presentar sin conocer el código.

## Antes de empezar (10 minutos antes)

- [ ] **Nadie juega con la cuenta con saldo** durante la demo: si otra sesión gasta dinero a la vez, el validador lo detecta (correctamente) como discrepancia y el escenario sale FAIL.
- [ ] Hay saldo en la cuenta con saldo (≥ 1 €) y la cuenta sin saldo está a 0 €.
- [ ] El portátil tiene red española (betsson.es bloquea otros países) y el `.env` con las cuentas.
- [ ] Runner de GitHub en línea (si se va a enseñar Actions): `gh api repos/EscuadronMCP/BetssonEscuadronMCP/actions/runners --jq '.runners[].status'` → `online`. Si no: `cd ~/actions-runner-betsson && nohup ./run.sh &`.
- [ ] Tener abierto un **informe bueno de respaldo** (por si falla la red en directo) y este guion.

## Guion

| Tiempo | Qué contar | Qué enseñar |
|---|---|---|
| 0:00–0:45 | **El problema**: el juego es una caja negra del proveedor; pulsar *Spin* no prueba nada. Hay que demostrar lo que ve el jugador y que el dinero cuadra. | README, "En pocas palabras" |
| 0:45–1:45 | **Lanzar en directo** los dos escenarios (≈ 70 s, en paralelo y sin intervención humana). Mientras corre, explicar los **cinco testigos**. | `uv run python -m betsson_validator run --headed` |
| 1:45–3:15 | **El informe**: resumen en lenguaje llano; cada comprobación en verde con lo que dijo cada testigo; capturas. Destacar que el escenario 2 lee el mensaje completo en español y que el juego confirma el idioma (`lang: "ES"`). | `reports/<fecha>/index.html` |
| 3:15–4:15 | **Detecta fallos reales**: enseñar un FAIL por discrepancia (p. ej. el día 15 se detectaron 2,10 € que salieron de la cuenta por otra sesión durante la tirada: pantalla, Betsson y servidor decían una cosa, la ronda del juego otra). | Informe guardado de ese caso |
| 4:15–5:15 | **Se adapta a juegos y proveedores**: perfiles aprendidos por IA en un minuto y validados. Dos juegos con interfaces distintas, sin código. Si el proveedor mueve un botón, se reencuentra solo. | `profiles/` (imágenes de los botones), `learn` |
| 5:15–6:00 | **Es barato y eficiente**: 0 € de IA por ejecución, ≈ 0,001 $ por juego nuevo, informe < 1 MB, ≈ 70 s. | README, "Es barato" |
| 6:00–7:00 | **GitHub Actions y seguridad**: workflow con runner en España, informe publicado; secretos nunca en evidencias (escáner), salvaguardas de dinero. Cierre. | Pestaña Actions, resumen de la ejecución |

## Si algo falla en directo

- **La red o la web van lentas**: enseñar el informe de respaldo y el vídeo (`run --video` genera uno).
- **Sale FAIL**: leer el motivo de la fila; precisamente demuestra que el validador no aprueba sin pruebas.

## Preguntas probables del jurado

| Pregunta | Respuesta corta |
|---|---|
| ¿Por qué no basta con leer el DOM? | El juego se dibuja en un canvas dentro de un iframe del proveedor: no hay DOM útil. Leemos la pantalla como un jugador. |
| ¿Qué pasa si el proveedor cambia su interfaz? | Los botones se buscan por su aspecto en toda la pantalla; si cambian del todo, la IA reaprende el perfil una vez (≈ 0,002 $) y queda anotado. Hay tests que simulan botones movidos, rediseñados y textos cambiados. |
| ¿Cuánto cuesta? | 0 € de IA por ejecución; ≈ 0,001 $ por juego nuevo; la tirada de 0,20 € devuelve de media ~94,5 %. |
| ¿Por qué cinco testigos? | Para no aprobar solo con un clic y para detectar fallos de integración: si el jugador ve una cosa y el sistema registra otra, es FAIL por discrepancia. |
| ¿De dónde sale el quinto testigo? | El juego envía mensajes `postMessage` a la web de Betsson con cada ronda (apuesta, premio, saldo, idioma). Lo encontramos instrumentando el navegador. |
| ¿Por qué un runner propio? | betsson.es bloquea las IP de fuera de España; los runners de GitHub están en EE. UU. En producción: Oracle Cloud Madrid. |
| ¿Cómo protegéis las credenciales? | Solo en `.env` o GitHub Secrets; difuminadas en vídeo; traza limpiada; un escáner retira cualquier evidencia con secretos. |
| ¿Y el antibots? | betsson.es usa AWS WAF; el navegador se lanza sin la marca de automatización y teclea a ritmo humano, con las cuentas de prueba que nos dio Betsson. |
