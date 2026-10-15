# 004. Endurecimiento: atribución, dinero real, lecturas y prueba de fallo

- **Fecha:** 2026-10-15
- **Estado:** aceptada (completa las decisiones [001](001-enfoque-testigos-y-perfiles.md), [002](002-perfiles-aprendidos-y-coste.md) y [003](003-testigo-eventos-del-juego.md); no las sustituye)

## Contexto

Revisiones internas atacaron el validador con casos adversariales: lecturas ambiguas, eventos o tráfico de otros marcos, cuentas compartidas, perfiles mal aprendidos o lecturas tomadas antes de tiempo. Además, en las ejecuciones reales del 15/10 aparecieron fallos que solo se ven en la web: una tirada en cascada leída antes del cobro, un «−» falso que abrió el panel de tirada automática y sesiones cerradas porque otra persona usaba la misma cuenta. Por último, los mentores pidieron ver en cada informe una prueba que falle.

## Opciones evaluadas

- **Parchear cada caso** según aparezca: es rápido, pero deja el mismo tipo de fallo abierto en otros sitios.
- **Fijar contratos generales**, con un test de regresión por caso: qué se puede atribuir al juego, cuándo es seguro girar, cuándo una lectura vale como prueba y cómo se demuestra un fallo.

## Decisión

Contratos generales, cada uno con su test de regresión:

1. **Atribución al juego.** El tráfico de red cuenta si viene del marco real del juego que da el navegador o de sus descendientes; nunca por parecido de dominio. Los eventos `postMessage` cuentan si vienen de la ventana del juego (también dentro de shadow DOM) y de los orígenes de su árbol de marcos tomados con el juego listo. Una respuesta HTTP de error, vacía o con otro esquema es ilegible, y entonces la ausencia de tirada no prueba nada.
2. **Antes de girar** (`scenarios/preconditions.py`):
   - la apuesta debe leerse, ser positiva, en la divisa **vista** en pantalla, sin superar el tope y ser la mínima conocida del juego (perfil);
   - la cuenta con saldo debe tener fondos, y la cuenta «sin saldo» no debe tenerlos;
   - los botones de apuesta solo se buscan junto al botón de girar;
   - si algo falla, no se gira y el informe dice por qué.
3. **Lectura final.** Se espera a que el servidor y los eventos cierren la ronda (cascadas y cobro). Después, el crédito y el premio deben coincidir en dos lecturas seguidas. Un premio que desaparece no es «sin premio», y una lectura no estabilizada nunca confirma un saldo.
4. **Perfiles.** Lo que propone la IA es un dato no confiable: se valida (geometría, contenido, reencontrar sin ambigüedad) sobre una copia antes de adoptarlo, y se guarda de forma atómica.
5. **Cuentas.** Hay un cerrojo atómico por cuenta en `run` y en `learn`, que solo se recupera si su propietario murió. Entre ordenadores hay que coordinarse, porque el validador no lo puede impedir, aunque sí lo detecta como discrepancia.
6. **Prueba que falla a propósito.** Cada `run` vuelve a evaluar el escenario 1 con lo observado de verdad y el saldo final de Betsson desviado 0,01 €. Se muestra aparte, debe salir FAIL y no cuenta en el veredicto ni en el código de salida (`--no-demo-fault` la quita).
7. **Sonda de accesibilidad** (`--ax-probe`), de diagnóstico. Medido en Sweet Bonanza: árbol ARIA vacío. Confirma que el juego no expone semántica y que hay que leer la pantalla.

## Consecuencias

- **Más FAIL honestos y ningún PASS sin prueba:** ante datos incompletos el resultado es «no disponible» o FAIL, nunca un valor inventado.
- **Más tiempo en algunos casos:** se espera al cierre de la ronda, como mucho 30 s, solo si la ronda sigue abierta.
- **Distinguir un fallo del validador de uno del juego** se ve en el informe: notas, avisos del juego («Sesión expirada», «¡Acceda a su cuenta!»), captura del fallo y anomalías del canal.
- **Validado en real con el código 8d54ae0:** Sweet Bonanza 2500 y Big Bass Halloween Splash 1000, ambos escenarios PASS con los cinco testigos confirmando y la prueba a propósito detectada (ver `mentores/`).
