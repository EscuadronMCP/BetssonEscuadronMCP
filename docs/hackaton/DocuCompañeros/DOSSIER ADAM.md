

# **DOSSIER TÉCNICO Y PLANIFICACIÓN DE EJECUCIÓN**

**Reto:** Intelligent Game Validation — Betsson Group (Malackathon 2026, ETSII Málaga) **Fecha:** 15 de octubre de 2026 (Cierre de entrega: 20:00 CEST) **Objetivo general:** Validar la experiencia visible de un jugador humano en un juego de casino de Pragmatic Play integrado en Betsson en modo Real Play, sin depender de clics a ciegas ni de acceso al DOM interno del juego.  
**Leyenda de trazabilidad de datos:**

* **\[Dato verificado \- PDF\]:** Requisito o dato extraído literalmente de las bases oficiales del reto.  
* **\[Dato verificado \- Web\]:** Información técnica contrastada en documentación y fuentes web públicas (listadas en la Sección 5).  
* **\[Inferencia técnica / Suposición\]:** Deducción de arquitectura basada en el funcionamiento estándar de proveedores iGaming (HTML5/WebGL) y entornos CI/CD.

## **1\. Extracción exhaustiva de requisitos del PDF**

### **1.1 Checklist de requisitos obligatorios (Escenario × Mercado)**

El reto exige validar dos escenarios de usuario en dos mercados distintos (betsson.com y betsson.pe), utilizando cualquier juego de Pragmatic Play disponible en dicho mercado en modo **Real Play**. Hacer clic en el botón de giro por sí solo no constituye una validación válida.

| ID | Escenario | Mercado | Requisito obligatorio verificable | Criterio de Pass / Fail |
| :---- | :---- | :---- | :---- | :---- |
| **S1-COM-01** | 1: Tirada completada | betsson.com  | Abrir el lobby de casino de Betsson y autenticar con la cuenta de prueba con fondos suministrada. | **PASS** si inicia sesión correctamente en betsson.com sin exponer credenciales. |
| **S1-COM-02** | 1: Tirada completada | betsson.com  | Lanzar cualquier juego de Pragmatic Play disponible en el mercado y entrar en modo **Real Play**. | **PASS** si el juego carga en modo dinero real y muestra la interfaz principal lista para jugar. |
| **S1-COM-03** | 1: Tirada completada | betsson.com  | Leer el saldo de Betsson antes de la tirada, el saldo dentro del juego y la apuesta mostrada. | **PASS** si se registran los valores numéricos iniciales de ambos saldos y la apuesta antes de girar. |
| **S1-COM-04** | 1: Tirada completada | betsson.com  | Verificar que la divisa mostrada en pantalla coincide con el mercado objetivo (EUR). | **PASS** si se identifica visualmente el símbolo € o código EUR. |
| **S1-COM-05** | 1: Tirada completada | betsson.com  | Localizar los controles dentro del juego, disparar un giro y verificar desde la pantalla que el juego reaccionó y la tirada **empezó y se completó**. | **PASS** si se demuestra visualmente que los rodillos se pusieron en movimiento y posteriormente se detuvieron (un simple clic es **FAIL**). |
| **S1-COM-06** | 1: Tirada completada | betsson.com  | Verificar que la apuesta mostrada en pantalla es la apuesta utilizada para la tirada. | **PASS** si el descuento aplicado al saldo coincide exactamente con el importe de apuesta mostrado. |
| **S1-COM-07** | 1: Tirada completada | betsson.com  | Leer el resultado liquidado (payout) y comprobar que el saldo dentro del juego es consistente con la tirada completada. | **PASS** si el saldo in-game posterior cumple la relación con saldo previo, apuesta y premio (no es obligatorio que la tirada sea ganadora). |
| **S1-COM-08** | 1: Tirada completada | betsson.com  | Reconciliar el saldo de Betsson antes y después del giro con la apuesta y el premio observado. | **PASS** si se cumple exactamente que saldo\_después \= saldo\_antes \- apuesta \+ premio en la cuenta de Betsson. |
| **S1-PE-01** | 1: Tirada completada | betsson.pe  | Abrir el lobby de casino de Perú y autenticar con la cuenta de prueba con fondos suministrada. | **PASS** si inicia sesión correctamente en betsson.pe sin exponer credenciales. |
| **S1-PE-02** | 1: Tirada completada | betsson.pe  | Lanzar cualquier juego de Pragmatic Play disponible en Perú en modo **Real Play**. | **PASS** si el juego carga en modo dinero real con la configuración de mercado peruana (español). |
| **S1-PE-03** | 1: Tirada completada | betsson.pe  | Leer el saldo de Betsson antes de la tirada, el saldo dentro del juego y la apuesta mostrada. | **PASS** si se registran todos los importes iniciales antes de girar. |
| **S1-PE-04** | 1: Tirada completada | betsson.pe  | Verificar que la divisa mostrada coincide con el mercado peruano (PEN / soles). | **PASS** si se identifica visualmente PEN o S/ en pantalla. |
| **S1-PE-05** | 1: Tirada completada | betsson.pe  | Localizar controles dentro del juego, disparar un giro y verificar visualmente que empezó y terminó. | **PASS** si hay prueba visual del inicio y fin de la animación de giro. |
| **S1-PE-06** | 1: Tirada completada | betsson.pe  | Verificar que la apuesta mostrada es la apuesta utilizada en la tirada. | **PASS** si el descuento aplicado corresponde a la apuesta mostrada. |
| **S1-PE-07** | 1: Tirada completada | betsson.pe  | Leer el resultado liquidado (payout) y verificar consistencia del saldo dentro del juego tras el giro. | **PASS** si el saldo dentro del juego tras el giro concuerda con la apuesta y el premio observado. |
| **S1-PE-08** | 1: Tirada completada | betsson.pe  | Reconciliar el saldo de Betsson antes y después del giro en soles (PEN). | **PASS** si saldo\_después \= saldo\_antes \- apuesta \+ premio en la billetera de Betsson. |
| **S2-COM-01** | 2: Saldo insuficiente | betsson.com  | Abrir lobby, autenticar con cuenta sin saldo utilizable para la tirada y abrir juego Pragmatic Play en Real Play. | **PASS** si accede en modo Real Play con saldo inferior a la apuesta que se va a intentar. |
| **S2-COM-02** | 2: Saldo insuficiente | betsson.com  | Leer el saldo antes de intentar la tirada y comprobar que la divisa mostrada es EUR. | **PASS** si se registran los saldos previos (Betsson e in-game) y la divisa es EUR. |
| **S2-COM-03** | 2: Saldo insuficiente | betsson.com  | Intentar una tirada y verificar que es **rechazada** en lugar de completarse como una tirada pagada. | **PASS** si no se ejecuta ni liquida un giro de pago. |
| **S2-COM-04** | 2: Saldo insuficiente | betsson.com  | Verificar que el jugador recibe un mensaje visible de saldo insuficiente en el idioma esperado (**inglés**). | **PASS** si se detecta y captura en pantalla el aviso de fondos insuficientes en inglés (incluso si se renderiza dentro del propio juego). |
| **S2-COM-05** | 2: Saldo insuficiente | betsson.com  | Leer los saldos después del intento y comprobar que **ni el saldo de Betsson ni el saldo dentro del juego cambian**. | **PASS** si el saldo de Betsson y el saldo in-game permanecen idénticos antes y después del intento. |
| **S2-PE-01** | 2: Saldo insuficiente | betsson.pe  | Abrir lobby de Perú, autenticar con cuenta sin saldo utilizable y abrir juego Pragmatic Play en Real Play. | **PASS** si accede en Real Play en betsson.pe con saldo insuficiente para la apuesta. |
| **S2-PE-02** | 2: Saldo insuficiente | betsson.pe  | Leer el saldo antes de intentar la tirada y comprobar que la divisa mostrada es PEN (soles). | **PASS** si se registran ambos saldos previos y la divisa es PEN / S/. |
| **S2-PE-03** | 2: Saldo insuficiente | betsson.pe  | Intentar una tirada y verificar que es **rechazada** en lugar de completarse como tirada pagada. | **PASS** si el giro es rechazado. |
| **S2-PE-04** | 2: Saldo insuficiente | betsson.pe  | Verificar que aparece un mensaje visible de saldo insuficiente en el idioma esperado (**español**). | **PASS** si se detecta y captura en pantalla el aviso de saldo insuficiente en español. |
| **S2-PE-05** | 2: Saldo insuficiente | betsson.pe  | Leer los saldos después del intento y comprobar que ni el saldo de Betsson ni el saldo dentro del juego cambian. | **PASS** si ambos saldos permanecen inalterados tras el rechazo. |

### **1.2 Entregables obligatorios y restricciones de seguridad**

| Entregable | Contenido requerido | Restricción estricta |
| :---- | :---- | :---- |
| **1\. Repositorio en GitHub**  | Código del validador organizado de forma clara, con configuración separada para cada mercado (p. ej. specs, page objects, fixtures y utilidades). | Prohibido incluir credenciales o secretos en el repositorio. |
| **2\. Workflow de GitHub Actions**  | Un flujo de CI que ejecute ambos escenarios una vez por mercado y publique el informe resultante. | Las credenciales deben inyectarse de forma segura sin exponerse en logs ni en el código. |
| **3\. Informe y evidencias**  | Resultado pass/fail para cada comprobación, identificado por escenario y mercado, incluyendo las validaciones del saldo de Betsson, respaldado con capturas de pantalla, trace o vídeo. | Prohibido mostrar credenciales o secretos en el informe, en las capturas de pantalla o en las grabaciones de vídeo. |
| **4\. Presentación (solo finalistas)**  | Presentación de 7 minutos el 16 de octubre mostrando una ejecución funcional y explicando las decisiones técnicas del equipo. | Prohibido exponer credenciales o secretos durante la presentación. |

### **1.3 Mapeo a criterios de evaluación y reparto de puntos (Base 100 \+ Bonus 10\)**

Cada uno de los seis criterios se puntúa de 1 a 5, otorgando $(puntuación\div 5)\times peso$ puntos, hasta un máximo base de 100 puntos más hasta 10 puntos de bonus.

| Criterio | Peso | Qué demuestra un resultado excelente (5/5) | Estrategia directa para asegurar el máximo |
| :---- | :---- | :---- | :---- |
| **Scenarios work**  | **30 pts**  | Ambos escenarios funcionan en ambos mercados, incluyendo las comprobaciones del saldo de Betsson. | Prioridad absoluta: lograr que las 4 ejecuciones (Escenario 1 y 2 × .com y .pe) terminen sin caerse y verifiquen la ecuación del saldo. |
| **Sees like a player**  | **20 pts**  | Lee la pantalla visible y verifica la reacción del juego en lugar de tratar clics hardcodeados como prueba (OCR, visión e IA son ejemplos, no obligatorios). | Usar visión artificial para localizar controles, medir el movimiento de los rodillos frame a frame y leer en la imagen los importes y mensajes de error. |
| **Code and architecture**  | **15 pts**  | Organización clara y mantenible adaptada al enfoque elegido, configuración por mercado y sin secretos en el repositorio. | Separar configuración declarativa por mercado, módulos de navegador, motor de visión y generador de informes, manteniendo cero secretos en Git. |
| **Report and evidence**  | **15 pts**  | Resultados pass/fail claros para cada check, respaldados por capturas de pantalla, un trace o vídeo centrados en el jugador. | Generar una tabla automática que enlace cada uno de los 26 checks con su captura exacta (antes, girando, después, modal de error) y vídeo. |
| **GitHub workflow**  | **10 pts**  | Se ejecuta en GitHub Actions para cada mercado y publica el informe. | Configurar matriz por mercado en GitHub Actions y publicar el reporte tanto en el resumen de ejecución como en artefactos/GitHub Pages. |
| **Demo**  | **10 pts**  | Una demostración clara y funcional junto con la explicación de las decisiones técnicas del equipo. | Preparar ejecución en vivo respaldada por vídeo grabado y justificar la arquitectura híbrida elegida. |
| **Bonus**  | **0–10 pts**  | Trabajo sobresaliente no cubierto por los seis criterios base; cada punto de bonus exige una **justificación escrita** del jurado. | Añadir mejoras diferenciales (ej. capturas anotadas con cajas de visión y censura automática de datos sensibles) y redactar la justificación en el propio informe. |

### **1.4 Preguntas inmediatas para los mentores de Betsson**

El documento oficial indica expresamente que hay soporte de mentores durante la ventana de construcción (10:15–20:00) y pide coordinarse con ellos para preparar el estado de la cuenta sin saldo del Escenario 2:

> 1. **Preparación de la cuenta sin saldo (Escenario 2):** ¿Se entregan dos cuentas distintas por mercado (una con saldo para el Escenario 1 y otra a cero para el Escenario 2), o se utiliza una misma cuenta subiendo la apuesta dentro del juego por encima del saldo disponible? *(Si os permiten subir la apuesta con el botón \+ por encima del saldo actual, ambos escenarios pueden ejecutarse en cualquier orden sin agotar los fondos de prueba)*.  
> 2. **Geobloqueo en GitHub Actions:** Los runners estándar en la nube de GitHub se ejecutan desde direcciones IP de centros de datos en EE. UU. ¿Están habilitadas esas IPs en el entorno de betsson.com y betsson.pe, o recomendáis conectar nuestro propio portátil como **Self-Hosted Runner** de GitHub Actions para salir desde la red autorizada de la ETSII?  
> 3. **Título de Pragmatic Play recomendado:** Dado que se permite cualquier juego de Pragmatic Play disponible en el mercado, ¿cuál recomendáis que esté presente tanto en .com como en .pe y tenga animaciones cortas sin rondas largas de cascadas (p. ej., *Joker's Jewels*, *888 Dragons* o *Big Bass Bonanza*)?  
> 4. **Visibilidad del saldo de Betsson durante el juego:** En la vista de escritorio de betsson.com y betsson.pe, ¿el saldo de la cuenta de Betsson permanece visible en la cabecera superior mientras el iframe del juego está abierto, o es necesario volver al lobby para leer el saldo de Betsson posterior al giro?  
> 5. **Evidencia secundaria de red/DOM:** Además de realizar toda la validación visual obligatoria sobre la pantalla, ¿valoráis positivamente para los puntos de Bonus que incluyamos una verificación cruzada midiendo la latencia de red de la billetera?

## **2\. Prerrequisitos y riesgos técnicos**

### **2.1 Cómo se integran los juegos de Pragmatic Play en Betsson**

* **Aislamiento en Iframe y renderizado en Canvas \[Dato verificado \- PDF\]:** Los juegos de estudios externos se integran en el lobby, cuenta y billetera de Betsson renderizándose dentro de un iframe o canvas, lo que impide inspeccionar sus controles, saldos, mensajes y estados internos mediante selectores DOM convencionales.  
* **Catálogo multi-mercado HTML5 \[Dato verificado \- Web\]:** Betsson agrupa los títulos del proveedor bajo su sección de casino de Pragmatic Play, y Pragmatic Play sirve sus juegos en HTML5 soportando 33 idiomas y todas las divisas desde una única integración.  
* **Ausencia de árbol DOM interno \[Inferencia técnica\]:** Dentro del iframe del proveedor (dominio cruzado cross-origin), toda la interfaz gráfica se dibuja mediante **WebGL / PixiJS** sobre un único nodo \<canvas\>. Los botones de giro, selectores de apuesta, textos de saldo y ventanas emergentes de error son texturas gráficas rasterizadas en píxeles, por lo que herramientas como Playwright o Selenium no encuentran elementos HTML dentro del área de juego.

### **2.2 Distribución típica de la interfaz (UI) de Pragmatic Play**

* **\[Inferencia técnica\] Pantalla de bienvenida ("Splash / Intro Screen"):** Al terminar la barra de carga inicial con el logotipo de Pragmatic Play, el juego muestra una pantalla informativa con las características de la slot y un botón parpadeante para continuar (*"Press anywhere to continue"* / *"Pulsa en cualquier lugar para continuar"*). Es imprescindible detectar visualmente esta pantalla y hacer clic para entrar al tablero principal antes de intentar leer el saldo o girar.  
* **\[Inferencia técnica\] Barra inferior de estado (HUD en formato escritorio 16:9):**  
  * **Zona inferior izquierda:** Iconos de menú/ajustes, sonido e información (i), seguidos de los indicadores numéricos de **Saldo en el juego** (CREDIT en inglés / CRÉDITO en español) y **Apuesta total** (BET en inglés / APUESTA en español).  
  * **Zona inferior central:** Indicador de **Premio** (WIN en inglés / GANANCIA en español), que permanece vacío o muestra mensajes informativos hasta que se liquida una tirada con premio.  
  * **Zona inferior derecha:** El **botón circular de Spin** (con dos flechas curvas concéntricas), flanqueado por los botones \- y \+ para ajustar el valor de la apuesta.  
* **\[Inferencia técnica\] Animación de tirada:** Al accionar el botón de Spin, el indicador de CREDIT/CRÉDITO descuenta inmediatamente el valor de la apuesta, los rodillos verticales entran en movimiento durante 1,5 a 3 segundos y se detienen secuencialmente de izquierda a derecha. Si hay ganancia, se suma al contador de crédito tras una breve animación numérica.  
* **Mensaje de saldo insuficiente \[Dato verificado \- Web \+ Inferencia técnica\]:** El protocolo de integración de Pragmatic Play contempla el código de estado 4: Insufficient Balance cuando la billetera rechaza una jugada sin fondos. Visualmente, el giro no llega a realizarse como tirada pagada y se superpone un cuadro de diálogo modal en el centro del canvas con un mensaje en inglés (*"Not enough money to play"* / *"Insufficient funds"*) para betsson.com o en español (*"No tienes suficiente dinero para jugar"* / *"Saldo insuficiente"*) para betsson.pe.

### **2.3 Riesgos de entorno y mitigaciones concretas**

| Riesgo técnico | Impacto | Causa raíz | Mitigación concreta |
| :---- | :---- | :---- | :---- |
| **Geobloqueo de betsson.pe o betsson.com** | Crítico | Restricciones regionales de acceso desde España o bloqueo de IPs de centros de datos de EE. UU. (runners estándar de GitHub Actions). | Comprobar conectividad al inicio; si el runner en la nube de GitHub recibe bloqueo HTTP 403, registrar el portátil del equipo como **GitHub Actions Self-Hosted Runner** para ejecutar el pipeline oficial desde la red del hackathon. |
| **Detección antibot / Cloudflare** | Alto | **\[Dato verificado \- Web\]:** Chromium en modo headless expone banderas de automatización (navigator.webdriver), User-Agent HeadlessChrome y firmas gráficas que bloquean el login. | Ejecutar el navegador en modo **headed** (con pantalla virtual xvfb-run en Linux CI) y desactivar las banderas de control de automatización de Chromium. |
| **Bloqueo por CAPTCHA o límite de logins** | Alto | Iniciar sesión repetidamente en cada prueba unitaria durante el desarrollo puede disparar sistemas de protección en la cuenta de prueba. | Guardar el estado de sesión autenticado en local durante las pruebas de desarrollo (excluido de Git) y ejecutar el flujo completo desde el login únicamente en las validaciones integrales. |
| **Banners de Cookies (+18) y Pop-ups** | Medio | **\[Dato verificado \- Web\]:** Los portales de Betsson y Pragmatic Play muestran avisos de aceptación de cookies, verificación de edad y modales promocionales. | Incorporar un paso previo de limpieza de interfaz que cierre banners de cookies y diálogos emergentes antes de interactuar con el lobby o capturar el juego. |

### **2.4 Renderizado WebGL en CI y consistencia del Viewport**

* **Problema de WebGL en CI \[Dato verificado \- Web\]:** En servidores de integración continua sin tarjeta gráfica dedicada (como los runners de GitHub Actions), Chromium desactiva la aceleración por hardware o recurre a un renderizado por software lento (SwiftShader), lo que puede provocar que el \<canvas\> de un juego WebGL quede en negro o tarde más de 30 segundos en inicializar.  
* **Mitigación en CI \[Dato verificado \- Web\]:** Ejecutar las pruebas dentro de un servidor gráfico virtual (xvfb-run) en modo *headed* forzando las banderas de compatibilidad WebGL/ANGLE de Chromium.  
* **Tamaño de Viewport fijo \[Inferencia técnica\]:** Fijar una resolución invariable (por ejemplo, 1280 × 720 píxeles con factor de escala 1.0) en todos los entornos garantiza que la proporción del \<canvas\> y la posición relativa de los elementos visuales sean idénticas en desarrollo local y en GitHub Actions.

### **2.5 Formatos de moneda y número (EUR vs PEN)**

* **Requisitos por mercado \[Dato verificado \- PDF\]:**  
  * betsson.com: Idioma **inglés**, divisa **EUR**.  
  * betsson.pe: Idioma **español**, divisa **PEN (soles)**.  
* **Reglas de normalización y parseo tras OCR/Visión \[Inferencia técnica\]:**  
  * En betsson.com los valores pueden mostrarse con el símbolo € antes o después de la cifra (€10.50, 10,50 € o EUR 10.50).  
  * En betsson.pe los soles peruanos se representan habitualmente como S/ 10.50, S/. 10.50 o PEN 10.50.  
  * **Fallo clásico de OCR:** Los motores de OCR tradicionales suelen confundir el prefijo S/ con los dígitos 5/, 51 o \$1, alterando el número leído (p. ej. convirtiendo S/ 20.00 en 5120.00). Para evitarlo, el parser debe recortar primero cualquier etiqueta textual (CREDIT, CRÉDITO, BET, APUESTA, S/, PEN, EUR, €), normalizar el último separador (. o , seguido de dos dígitos) como separador decimal y operar exclusivamente con aritmética decimal exacta (sin coma flotante binaria).

## **3\. Posibles soluciones, comparadas**

### **3.1 Comparativa de enfoques tecnológicos**

| Enfoque | Funcionamiento | Ventajas | Inconvenientes | Tiempo estimado | Puntuación en "Sees like a player" (20 pts) PDF |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **1\. Automatización DOM \+ Clics por coordenadas fijas** | Usa Playwright para el lobby y el login; dentro del juego hace clic en una coordenada fija y espera un tiempo estático. | Rápido de implementar para la navegación por el lobby de Betsson. | No lee el interior del canvas ni comprueba si la tirada ocurrió o fue rechazada; incumple la premisa central del reto. | 1,5 h | **1 / 5 (4 pts)** — Penalizado expresamente en las bases. |
| **2\. OCR Clásico (Tesseract / EasyOCR / PaddleOCR)** | Recorta rectángulos fijos de la parte inferior del canvas y aplica reconocimiento óptico de caracteres local. | Sin coste por API y baja latencia de ejecución local. | Alta tasa de error con tipografías de videojuegos o fondos animados; confunde S/ con números; no detecta dónde están los botones ni entiende modales. | 3 – 4 h | **3,5 / 5 (14 pts)** — Frágil ante cualquier variación visual. |
| **3\. Visión Clásica con OpenCV (Template Matching \+ Diferencia de Frames)** | Localiza botones por coincidencia de plantillas y compara fotogramas consecutivos para medir cuándo empiezan y terminan de moverse los rodillos. | **Prueba matemática objetiva** de que el giro comenzó (alto cambio de píxeles) y terminó (imagen estabilizada). | No puede leer saldos numéricos por sí solo ni verificar si el mensaje de error está en inglés o en español. | 1,5 h | **4 / 5 (16 pts)** — Excelente para movimiento, incompleto para texto. |
| **4\. LLM Multimodal con Visión (Gemini / Claude / GPT)** | Analiza la captura del juego y devuelve una estructura JSON con los saldos leídos, la apuesta, la divisa, el texto/idioma de los modales y las coordenadas del botón Spin. | Comprende perfectamente € vs S/, valida el idioma del error (inglés/español) y funciona en cualquier juego de Pragmatic Play sin plantillas previas. | Latencia de 1,5 a 3 segundos por consulta; no es adecuado para muestrear movimiento continuo a 10 fotogramas por segundo. | 1,5 h | **5 / 5 (20 pts)** — Inspecciona la pantalla igual que un jugador. |
| **5\. Enfoque Híbrido Recomendado (Playwright \+ OpenCV \+ LLM Vision)** | Playwright navega el lobby; **LLM Vision** lee importes, divisas, mensajes de error y localiza controles; **OpenCV** mide en tiempo real la animación de inicio y parada de los rodillos. | Combina la precisión semántica del modelo multimodal con la verificación temporal continua de OpenCV. | Requiere gestionar una clave de API mediante GitHub Secrets. | **2,5 – 3 h** | **5 / 5 (20 pts) \+ potencial de Bonus**. |

### **3.2 Funcionamiento del Enfoque Híbrido Recomendado**

> 1. **Navegación y Login seguro (Playwright):**  
   * Abre el portal del mercado correspondiente (betsson.com o betsson.pe), cierra avisos de cookies y realiza el login inyectando las credenciales desde variables de entorno, activando el enmascaramiento visual del campo de contraseña para que nunca aparezca en capturas ni vídeos.  
> 2. **Detección de carga y paso de pantalla de Intro (OpenCV \+ LLM Vision):**  
   * Verifica que el \<canvas\> del juego haya terminado de cargar (comprobando que la imagen no sea negra ni estática en la barra de progreso) y utiliza el modelo de visión (apoyado por una cuadrícula visual de coordenadas superpuesta en la captura) para detectar y pulsar el botón de continuar de la pantalla de introducción.  
> 3. **Lectura Pre-Spin (Visión Multimodal \+ Verificación cruzada):**  
   * **Evidencia principal (Visual):** A partir de la captura antes del giro, el modelo de visión extrae de forma estructurada el saldo de Betsson, el saldo dentro del juego (CREDIT/CRÉDITO), la apuesta mostrada (BET/APUESTA), la divisa (EUR o PEN) y la posición del botón de Spin.  
   * **Evidencia secundaria opcional (DOM/Red):** Se registra en paralelo el valor textual del saldo en el DOM de la cabecera de Betsson y los eventos de red únicamente como contraste secundario en el informe, sin sustituir en ningún caso a la lectura visual exigida por el reto.  
> 4. **Ejecución del Giro y Verificación de Reacción (OpenCV Frame Differencing):**  
   * Tras pulsar el botón de Spin en las coordenadas detectadas visualmente, el sistema captura fotogramas de la región central de los rodillos cada 150 milisegundos y mide el porcentaje de píxeles que cambian entre un fotograma y el siguiente:  
     * **En el Escenario 1 (Tirada completada):** Certifica primero que **el giro ha comenzado** (el cambio entre fotogramas supera el umbral de movimiento activo y se guarda la captura del giro en curso) y luego espera hasta que **el giro se ha completado** (la diferencia entre fotogramas cae por debajo del umbral de reposo durante más de un segundo consecutivo).  
     * **En el Escenario 2 (Saldo insuficiente):** Comprueba que los rodillos no completan un ciclo de giro pagado y que emerge en pantalla el mensaje de rechazo; el modelo multimodal lee el mensaje visible y certifica que informa de saldo insuficiente en el idioma del mercado (**inglés** en .com, **español** en .pe).

### **3.3 Aplicación de la regla de reconciliación de saldos y sincronización**

El documento del reto exige verificar en el Escenario 1 la siguiente identidad financiera:

$$balance\_after=balance\_before-wager+payout$$

Donde payout corresponde al importe acreditado por la tirada completada según el resultado observado en pantalla (la tirada no tiene que ser ganadora para dar por superada la prueba, pudiendo ser payout \= 0).  
**Protocolo para evitar fallos por sincronización o animaciones:**

* **Estabilización del contador de premios dentro del juego:** Cuando una tirada obtiene premio (payout \> 0), las slots de Pragmatic Play incrementan gradualmente el número en pantalla durante 1 a 3 segundos. Antes de tomar la captura final post-giro, el validador debe comprobar que dos lecturas consecutivas separadas por 1 segundo muestran el mismo valor estático.  
* **Espera activa (Polling) para la actualización del saldo de Betsson:** La billetera general de Betsson puede tardar unos instantes en reflejar la liquidación enviada por el servidor de Pragmatic Play tras detenerse los rodillos. Si la primera lectura posterior al giro sigue mostrando el saldo antiguo (balance\_after \== balance\_before habiendo existido una apuesta neta distinta de cero), el sistema debe reintentar la lectura visual cada 1,5 segundos (con un límite de 10 segundos) hasta que la billetera de Betsson se sincronice y cumpla la ecuación.  
* **Invarianza en el Escenario 2:** En el escenario de saldo insuficiente, la validación comprueba que tras el rechazo se cumple simultáneamente que el saldo de Betsson no ha variado (betsson\_after \== betsson\_before) y que el saldo dentro del juego tampoco ha variado (in\_game\_after \== in\_game\_before).

## **4\. Recomendación final y plan de ejecución**

### **4.1 Arquitectura recomendada del repositorio (sin código)**

Se recomienda estructurar el repositorio en cinco bloques modulares claramente diferenciados para asegurar los **15 puntos de Code and architecture**:

* **1\. Carpeta de Configuración (config/):**  
  * Archivo declarativo por mercado (betsson.com y betsson.pe) que define la URL base, el idioma esperado (en / es), la divisa esperada (EUR / PEN), el nombre del juego objetivo de Pragmatic Play y los nombres de las variables de entorno de donde leer las credenciales.  
* **2\. Módulo de Navegador y Page Objects (src/browser/):**  
  * **Gestor de sesión:** Inicializa Chromium con resolución fija 1280×720, banderas de compatibilidad WebGL, ocultación de huellas de automatización y grabación automática de vídeo y trazas con censura del campo de contraseña.  
  * **Page Object del Lobby de Betsson:** Encapsula el cierre de banners de cookies, el inicio de sesión seguro, la lectura del saldo de Betsson y la búsqueda y apertura del juego de Pragmatic Play en modo Real Play.  
* **3\. Módulo de Visión Artificial (src/vision/):**  
  * **Monitor de Canvas (OpenCV):** Verifica la carga del lienzo WebGL, superpone la rejilla de referencia espacial y ejecuta el algoritmo de diferencia de fotogramas para probar cuándo empieza y cuándo termina un giro.  
  * **Inspector Multimodal (LLM Vision):** Envía las capturas clave del juego y devuelve los importes leídos, la divisa detectada, las coordenadas de interacción y la validación lingüística de los mensajes de error.  
  * **Anotador de Evidencias:** Dibuja sobre las capturas de pantalla los recuadros de los elementos detectados y difumina cualquier identificador de usuario para proteger la privacidad.  
  * **Parser Financiero:** Convierte las cadenas de texto leídas en valores decimales exactos e identifica la moneda (EUR vs PEN).  
* **4\. Módulo de Validación y Reglas (src/validators/):**  
  * Evalúa secuencialmente los 8 checks del Escenario 1 y los 5 checks del Escenario 2 para cada mercado, aplicando la fórmula de reconciliación de saldos y registrando el estado PASS o FAIL de cada fila.  
* **5\. Generador de Informes y Flujo CI/CD (src/reporting/ y .github/workflows/):**  
  * Compila los resultados en un informe visual (Markdown y HTML) con enlaces directos a las capturas, trazas y vídeos generados en cada ejecución.

### **4.2 Diseño del Workflow de GitHub Actions**

Para obtener los **10 puntos de GitHub workflow** y los **15 puntos de Report and evidence**, el flujo automatizado debe seguir esta secuencia de etapas:

| Etapa del Workflow | Configuración y acciones que realiza | Garantía de cumplimiento |
| :---- | :---- | :---- |
| **1\. Disparadores (Triggers)** | Ejecución manual bajo demanda (workflow\_dispatch) y automática en cada actualización de la rama principal (push). | Permite lanzarlo en directo ante el jurado o automáticamente al entregar. |
| **2\. Matriz de Mercados (Strategy Matrix)** | Dos trabajos en paralelo o secuencia (betsson\_com y betsson\_pe) con la opción fail-fast desactivada para que un fallo en un mercado no cancele la ejecución del otro. | Garantiza que ambos escenarios se ejecuten una vez por mercado. |
| **3\. Inyección de Secretos (GitHub Secrets)** | Carga las credenciales de las cuentas de prueba (con y sin saldo para .com y .pe) y la clave de la API de visión desde el almacén cifrado de GitHub Secrets hacia variables de entorno. | Cumple la prohibición estricta de no almacenar secretos en el repositorio. |
| **4\. Entorno Gráfico Virtual (Xvfb \+ WebGL)** | Instala Python, las dependencias de visión y el navegador Chromium, lanzando los tests dentro de un monitor virtual (xvfb-run a 1280×720×24). | Evita que el \<canvas\> WebGL de Pragmatic Play falle por falta de monitor en CI. |
| **5\. Publicación del Informe y Artefactos** | Con condición always() (se ejecuta incluso si algún check falla): vuelca la tabla resumen en GITHUB\_STEP\_SUMMARY, sube las capturas/vídeos/traces como artefactos descargables y despliega el informe HTML unificado en **GitHub Pages**. | Publica el informe y las evidencias de forma accesible e inmediata para los evaluadores. |

### **4.3 Formato del Informe de Validación (Plantilla lista para el entregable)**

El informe generado por vuestra herramienta debe presentar dos tablas claras sin exponer ninguna credencial:

#### **A. Resumen Ejecutivo por Escenario y Mercado**

| Mercado | Escenario | Idioma / Divisa esperada | Saldo Betsson Inicial | Apuesta (Wager) | Premio (Payout) | Saldo Betsson Final | Saldo In-Game (Antes → Después) | Resultado Global | Evidencias Multimedia |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| **betsson.com**  | **Escenario 1: Tirada completada**  | Inglés / EUR  | 10.00 EUR | 0.20 EUR | 0.00 EUR | 9.80 EUR | €10.00 → €9.80 | **PASS** (8/8) | Capturas / Vídeo / Trace |
| **betsson.com**  | **Escenario 2: Saldo insuficiente**  | Inglés / EUR  | 0.00 EUR | 0.20 EUR | *Rechazado* | 0.00 EUR | €0.00 → €0.00 | **PASS** (5/5) | Capturas / Vídeo / Trace |
| **betsson.pe**  | **Escenario 1: Tirada completada**  | Español / PEN  | 50.00 PEN | 1.00 PEN | 2.00 PEN | 51.00 PEN | S/ 50.00 → S/ 51.00 | **PASS** (8/8) | Capturas / Vídeo / Trace |
| **betsson.pe**  | **Escenario 2: Saldo insuficiente**  | Español / PEN  | 0.00 PEN | 1.00 PEN | *Rechazado* | 0.00 PEN | S/ 0.00 → S/ 0.00 | **PASS** (5/5) | Capturas / Vídeo / Trace |

#### **B. Desglose de Evidencias por Check (Ejemplo representativo de filas del informe)**

| ID Check | Mercado | Escenario | Qué se verifica | Valor observado por el motor de visión | Estado | Evidencia enlazada |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| S1-COM-04 | betsson.com | Escenario 1 | La divisa mostrada coincide con EUR  | Símbolo € y código EUR detectados en HUD y cabecera | **PASS** | s1\_com\_pre\_spin.png |
| S1-COM-05 | betsson.com | Escenario 1 | El giro comenzó y se completó visualmente | Movimiento óptico en rodillos: pico del 24,8% en $t=0,6s$ y estabilización al 0,1% en $t=2,8s$ | **PASS** | s1\_com\_spinning.png |
| S1-COM-08 | betsson.com | Escenario 1 | Regla after \= before \- wager \+ payout en Betsson | 9.80 \= 10.00 \- 0.20 \+ 0.00 (Diferencia: 0.00 EUR) | **PASS** | s1\_com\_post\_spin.png |
| S2-PE-04 | betsson.pe | Escenario 2 | Mensaje visible de saldo insuficiente en español | Modal detectado en español: *"No tienes suficiente dinero para jugar"* | **PASS** | s2\_pe\_error\_modal.png |
| S2-PE-05 | betsson.pe | Escenario 2 | Saldos de Betsson e in-game no cambian | Betsson: 0.00 PEN → 0.00 PEN | In-game: S/ 0.00 → S/ 0.00 | **PASS** | s2\_pe\_post\_attempt.png |

### **4.4 Planning hora a hora hasta las 20:00 (Ventana de desarrollo)**

El horario oficial establece la ventana de construcción entre las **10:15 y las 20:00** del 15 de octubre, seguida del anuncio de finalistas a las **21:45** en el Campus Virtual. A partir de las **11:45**, el plan de trabajo por bloques es el siguiente:

| Horario | Fase / Hito | Tareas accionables y reparto en el equipo | Criterio de salida (Definition of Done) |
| :---- | :---- | :---- | :---- |
| **11:45 – 12:30** *(45 min)* | **Fase 1: Toma de datos y validación con mentores** | • Consultar a los mentores las 5 dudas de la Sección 1.4 (cuentas para Escenario 2, IPs y juego recomendado). • Entrar manualmente en betsson.com y betsson.pe, abrir el juego de Pragmatic Play elegido y guardar 4 capturas estáticas (Intro, HUD listo, Rodillos girando, Modal sin saldo) para desarrollar el módulo de visión sin consumir saldo real. | Credenciales probadas y 4 capturas reales guardadas en local para pruebas offline. |
| **12:30 – 14:00** *(1h 30m)* | **Fase 2: Construcción en paralelo (Lobby \+ Visión)** | • **Subequipo Navegación:** Automatizar login con ocultación de contraseña, cierre de cookies, lectura de saldo Betsson y apertura del juego en betsson.com. • **Subequipo Visión:** Configurar el inspector multimodal (lectura de saldos/divisa/coordenadas sobre las 4 capturas), el parser de EUR/PEN y el detector de movimiento por diferencia de fotogramas. | El navegador abre el juego solo y el módulo de visión extrae un JSON perfecto de las capturas de prueba. |
| **14:00 – 15:15** *(1h 15m)* | **Fase 3 (HITO MVP): Escenario 1 completo en betsson.com** | • Integrar navegación y visión. • Ejecutar una tirada real completa en betsson.com, verificando inicio y fin del giro y comprobando la ecuación balance\_after \= balance\_before \- wager \+ payout. | Los 8 checks del Escenario 1 en betsson.com (S1-COM-01..08) pasan en verde y generan sus capturas. |
| **15:15 – 16:30** *(1h 15m)* | **Fase 4: Escalado a betsson.pe \+ Escenario 2 en ambos mercados** | • Añadir la configuración de betsson.pe (español / PEN) y ejecutar el Escenario 1\. • Implementar el Escenario 2 (intento sin saldo, captura y lectura del modal de rechazo en inglés y español, y comprobación de que los saldos no varían). | Los **26 checks** (2 escenarios × 2 mercados) funcionan en ejecución local. |
| **16:30 – 17:45** *(1h 15m)* | **Fase 5: Generador de Informes y GitHub Actions** | • Conectar el generador automático de informes (tablas pass/fail \+ enlaces a capturas y vídeo). • Subir secretos a GitHub Secrets y lanzar el workflow en GitHub Actions para ambos mercados (en runner en la nube o self-hosted runner según la prueba de red). | Workflow de GitHub Actions en verde publicando el informe automáticamente. |
| **17:45 – 19:00** *(1h 15m)* | **Fase 6: Puntos de Bonus y Auditoría Cero Secretos** | • Activar la superposición visual de cajas delimitadoras (*bounding boxes*) sobre las capturas de evidencia. • Activar el difuminado automático de nombres de usuario en capturas. • Auditar el historial de Git, capturas, vídeos y logs para confirmar que no aparece ninguna credencial ni secreto. | Capturas anotadas listas y verificación de seguridad completada al 100%. |
| **19:00 – 19:45** *(45 min)* | **Fase 7: Ejecución dorada en CI y Documentación** | • Lanzar la ejecución limpia definitiva desde GitHub Actions. • Redactar el README.md explicando la arquitectura, cómo leer el reporte y la sección de justificación escrita de los puntos de Bonus para el jurado. | Repositorio documentado, reporte publicado y artefactos descargados de respaldo. |
| **19:45 – 20:00** *(15 min)* | **Fase 8: Congelación y cierre de entrega** | • No tocar más código funcional. • Comprobar permisos del repositorio y guardar una copia local de los vídeos de las 4 ejecuciones para la presentación del día siguiente. | Entrega cerrada antes de las 20:00. |

### **4.5 Tres propuestas para ganar los \+10 puntos de Bonus**

Las bases indican que se pueden conceder de **0 a 10 puntos adicionales** por trabajo sobresaliente no cubierto por los seis criterios estándar, y que **cada concesión de bonus requiere una razón escrita** por parte del evaluador. Incluid en vuestro informe y en el README una sección titulada **"Bonus Justifications"** con estas tres aportaciones listas para que el jurado las anote:

> 1. **Telemetría Visual Anotada sobre las Evidencias ("Explainable Computer Vision Overlay"):**  
   * *En qué consiste:* En lugar de guardar capturas de pantalla en bruto, el sistema dibuja sobre las imágenes de evidencia recuadros de colores alrededor del saldo leído, la apuesta, el mensaje de error y el punto exacto donde hizo clic en el botón de Spin, junto con el porcentaje de movimiento óptico medido en los rodillos y la fórmula matemática reconciliada.  
   * *Justificación escrita para el jurado:* *"El equipo implementó una capa de explicabilidad visual sobre las capturas y vídeos que permite auditar de un vistazo qué regiones exactas leyó la visión artificial y cómo midió el movimiento físico del juego."*  
> 2. **Censura Visual Automática de Credenciales y Datos de Cuenta ("Zero-Leak Visual Sanitizer"):**  
   * *En qué consiste:* Para blindar la regla de no mostrar secretos ni credenciales en capturas, grabaciones ni presentaciones, el sistema enmascara automáticamente los campos de login y aplica un desenfoque gaussiano sobre la zona de perfil/identificador de usuario en todas las capturas antes de guardarlas en disco o subirlas a GitHub Actions.  
   * *Justificación escrita para el jurado:* *"El equipo diseñó un filtro preventivo de privacidad y seguridad que anonimiza automáticamente cualquier rastro de cuenta o credencial en las evidencias visuales antes de su publicación en CI."*  
> 3. **Auditoría de Latencia de Sincronización de Billetera ("Wallet Sync Telemetry"):**  
   * *En qué consiste:* Manteniendo la validación visual como prueba principal, el informe añade una métrica de rendimiento que mide cuántos milisegundos tarda la billetera de Betsson en actualizar su saldo en pantalla desde el instante exacto en que OpenCV detecta que los rodillos se han detenido.  
   * *Justificación escrita para el jurado:* *"El validador aporta métricas de observabilidad sobre el tiempo de sincronización entre el fin de la animación visual del proveedor (Pragmatic Play) y la actualización del saldo en la plataforma de Betsson."*

### **4.6 Guion para la Demo de 7 minutos (Finalistas — 16 de octubre, 10:00h)**

Los equipos finalistas (anunciados el 15 de octubre a las 21:45 en Campus Virtual) realizan su check-in el **16 de octubre a las 09:30** en el Salón de Actos y disponen de **7 minutos** a partir de las **10:00** para mostrar una ejecución funcional y explicar sus decisiones técnicas:

* **Minuto 0:00 – 1:00 | El reto real: por qué la automatización tradicional falla en iGaming:**  
  * Mostrad una captura del inspector de navegador sobre el juego de Pragmatic Play demostrando que todo el juego es un único elemento \<canvas\> opaco dentro de un iframe. Explicad por qué un script que solo hace clic en coordenadas fijas daría por buena una pantalla congelada o un giro fallido.  
* **Minuto 1:00 – 3:30 | Demostración funcional en vivo (con vídeo sincronizado de respaldo):**  
  * Ejecutad la validación mostrando en paralelo la ventana del juego y las capturas anotadas que genera vuestro sistema. Enseñad cómo detecta los importes en EUR (betsson.com) y en PEN (betsson.pe), cómo mide el movimiento de los rodillos en el Escenario 1 y cómo captura y valida el idioma del aviso de saldo insuficiente en el Escenario 2\.  
* **Minuto 3:30 – 5:30 | Justificación de las decisiones técnicas (Arquitectura Híbrida):**  
  * Explicad por qué combinasteis **Visión Multimodal (LLM)** con **Visión Clásica (OpenCV)** en lugar de usar solo OCR tradicional: el modelo multimodal aporta comprensión semántica independiente de la tipografía del juego y valida el idioma del mensaje de error, mientras que la diferencia de fotogramas de OpenCV ofrece una prueba matemática en tiempo real de que la animación de giro empezó y terminó.  
* **Minuto 5:30 – 7:00 | Ejecución en GitHub Actions, Seguridad y Escalabilidad:**  
  * Mostrad el pipeline ejecutado en GitHub Actions con la tabla de 26 checks publicada automáticamente, explicad cómo protegisteis las credenciales en código, logs y vídeos, y destacad cómo el sistema puede validar cualquier otro título de Pragmatic Play cambiando únicamente el nombre del juego en el archivo de configuración.

## **5\. Fuentes y referencias verificadas**

### **5.1 Fuente primaria oficial (Documento del reto adjunto)**

> 1. **Betsson Group — *Intelligent Game Validation (Student Challenge, Malackathon 2026, 15–16 October, ETSII Málaga)*:**  
   * **Página 1:** Contexto de integración de juegos de terceros en iframe/canvas, definición del reto en modo Real Play con juegos de Pragmatic Play, libertad de enfoque tecnológico, salvaguardas de credenciales y pasos/verificaciones del Escenario 1 (*Completed Real Play spin*).  
   * **Página 2:** Regla matemática de reconciliación del saldo (balance after \= balance before \- wager \+ payout), pasos y verificaciones del Escenario 2 (*Insufficient balance*), tabla de mercados objetivo (betsson.com en inglés/EUR y betsson.pe en español/PEN) y tabla de los cuatro entregables obligatorios.  
   * **Página 3:** Rúbrica de evaluación con pesos (30 / 20 / 15 / 15 / 10 / 10), criterio de hasta 10 puntos de bonus con requisito de justificación escrita y cronograma oficial del reto los días 15 y 16 de octubre.

### **5.2 Fuentes técnicas web consultadas**

> 2. **Catálogo e integración de Pragmatic Play en Betsson:**  
   * Portal de proveedor en Betsson: \[https\://www\.betsson.com/en/casino/providers/pragmatic-play\](https\://www\.betsson.com/en/casino/providers/pragmatic-play) *(Verificación de disponibilidad del catálogo de Pragmatic Play, avisos de cookies y estructura del lobby de casino).*  
> 3. **Arquitectura HTML5 multi-divisa y multi-idioma de Pragmatic Play:**  
   * Sitio oficial de Pragmatic Play: \[https\://www\.pragmaticplay.com/en/\](https\://www\.pragmaticplay.com/en/) *(Verificación de distribución de slots en HTML5 compatibles con 33 idiomas y todas las divisas mediante integración API única).*  
> 4. **Especificación de códigos de error de billetera en Pragmatic Play:**  
   * Documentación de códigos de respuesta de integración de Pragmatic Play (Error Code 4: Insufficient Balance): \[https\://www\.scribd.com/document/925207124/Error-Codes\](https\://www\.scribd.com/document/925207124/Error-Codes) *(Verificación del rechazo de tirada por saldo insuficiente cuando el jugador no dispone de fondos para cubrir la apuesta).*  
> 5. **Renderizado de Canvas / WebGL en entornos Headless y GitHub Actions:**  
   * Guía técnica de pruebas WebGL y GPU en CI con Playwright y Xvfb (*Running WebGL / GPU Tests in GitHub Actions*): \[https\://www\.davesnider.com/gputests\](https\://www\.davesnider.com/gputests) *(Verificación del comportamiento de SwiftShader en runners Linux sin GPU, tiempos de inicialización de WebGL y uso de xvfb-run con modo headed y banderas ANGLE).*  
> 6. **Huellas de automatización en Chromium y detección antibot:**  
   * Documentación técnica de vectores de detección en Playwright (navigator.webdriver, HeadlessChrome User-Agent y parámetros WebGL): \[https\://github.com/managedcode/playwright\_stealth\](https\://github.com/managedcode/playwright\_stealth) *(Verificación de las propiedades inspeccionadas por sistemas anti-bot en navegadores automatizados).*