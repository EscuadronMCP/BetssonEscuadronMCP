# Flujo real de betsson.es (exploración del 15/10)

Cómo es la web por dentro, comprobado con Playwright. Base para automatizar la etapa E1. Si algo cambia, actualízalo aquí.

## 1. Entrada y cookies
- Aviso de cookies de **OneTrust**: botón `#onetrust-accept-btn-handler` ("Aceptar todas las cookies"). Está siempre animado, así que Playwright no lo considera "estable": hay que lanzar el clic directamente sobre el elemento (`dispatch_event("click")`).

## 2. Login
- Botón "Iniciar sesión" en la cabecera → diálogo con `input[name=email]`, `input[name=password]` y botón "Iniciar sesión".
- Petición: `POST /api/v2/authentication-transaction` → **201** si va bien.
- **Antibots:** AWS WAF con control de bots (`*.edge.sdk.awswaf.com`, cookie `aws-waf-token`) y Group-IB. Con el navegador automatizado tal cual, el login devuelve **403** y la web muestra "Actualiza la página y vuelve a intentarlo en breve. La resolución puede demorar hasta 10 minutos." La misma cuenta entra bien a mano.
- **Lo que funciona (también en headless):** lanzar Chrome sin la marca de automatización (`--disable-blink-features=AutomationControlled` y sin `--enable-automation`), esperar a la cookie `aws-waf-token`, y escribir correo y contraseña tecla a tecla con pausas. Decisión del equipo: Betsson nos pide automatizar su propia web con sus cuentas de prueba.
- **Cuidado:** cada intento fallido puede bloquear temporalmente la cuenta. No repetir logins en bucle.
- Tras el login aparecen un aviso de "último acceso" y un diálogo "Activar la clave de acceso" → botón **"Cancelar"**.
- **Saldo de Betsson:** botón de la cabecera cuyo nombre accesible es el importe, p. ej. `"64,70 €"`. En la página de un juego la cabecera muestra un botón **"Saldo"** que oculta el importe.

## 3. Casino y filtro de proveedor
- Casino en `/casino`. El menú superior usa pestañas (`tab "Casino"`), no enlaces.
- Botón **"Filtros"** → panel "Proveedor (44)" con un chip por proveedor (**"Pragmatic Play"**) → botón **"Resultados N"** (309 juegos de Pragmatic Play) → `/casino/todos-los-juegos` filtrado.
- Cada juego es un enlace `/casino/tragaperras-slots/<slug>`.
- Este mecanismo es igual para cualquier proveedor: cambiar de proveedor es cambiar el texto del chip.

## 4. Sesión de juego (normativa española)
Antes de jugar a tragaperras, la web exige abrir una **sesión de juego**:
1. Puede salir un aviso "Atención — Hace menos de 60 mins. que finalizaste tu sesión de juego" → botón "Iniciar sesión".
2. Diálogo de límites: **tiempo de juego** (15 Min, 30 Min, 1 Hora, …) y **límite de pérdidas** (campo con placeholder "Introduce el límite de pérdidas", en EUR) → botón "Iniciar sesión".
- **Usamos 5 Horas y el botón 100 %** del saldo (indicación del equipo, conforme a la normativa). Es configurable en `config/markets/es.yaml`. Al no haber tope bajo de pérdidas, la protección es hacer una sola tirada con la apuesta mínima.

## 5. El juego
- Iframe de Betsson: `/api/v1/Gamelauncher/?gameId=pragmaticPlaySweetBonanza2500&…&marketCode=es&forReal=true` (`forReal=true` = Real Play).
- Dentro, el cliente de Pragmatic Play en un dominio propio: `…/gs2c/game/load?ssid=…`. Coincide con el análisis no oficial (`gs2c`, `gameService`).
- La carga es lenta (pantalla de Pragmatic Play con barra de progreso): hay que esperar a que termine sin usar esperas fijas.

## 6. Una tirada real (15/10, apuesta mínima)
- Interfaz del juego (Sweet Bonanza 2500): **CRÉDITO** y **APUESTA** abajo a la izquierda; botón de giro abajo a la derecha, con "−" y "+" a los lados. Pulsar "−" abre un panel de apuesta (multiplicador 20×, valor de moneda, total apostado). La apuesta mínima es **0,20 €** (moneda 0,01 € × 20).
- Antes de la interfaz hay una pantalla de bienvenida con un botón circular de "continuar".
- Resultado en pantalla: "GANANCIA 0,15 €", CRÉDITO de 64,70 € a **64,65 €** (= 64,70 − 0,20 + 0,15), y el número de jugada (`#106756765013119`) en la barra inferior.
- Red (`POST …/gs2c/ge/v4/gameService`):
  1. `doSpin` `c=0.01&l=20` → `balance=64.50` (apuesta ya cobrada), `tw=0.15`, `rs_c=1` (cascada en curso).
  2. `doSpin` de continuación de la cascada (no cobra) → `na=c` (falta cobrar).
  3. `doCollect` → `balance=64.65`, `na=s` (liquidada).
- Algunas URL del juego llevan tokens de sesión (`mgckey`, `token`, `SESSION`): se ocultan siempre antes de guardar tráfico (`providers/pragmatic/network.py::redact`).
- La detección de movimiento sobre la zona de los rodillos marca el giro durante unos 5 s y luego reposo (serie real en `tests/unit/test_motion.py`).
