# Diseño — Conexión por MQTT entre las Muses y Growi Bridge

Propuesta del dueño (2026-11-16), evaluada en diseño antes de implementar.
Estado: **diseño con viabilidad verificada** (§2). No hay código de
producción todavía; la implementación espera el visto bueno del dueño.

## 1. La idea, en llano

Hoy la conexión «servidor» usa Tailscale: la Muse entra al PC por una
red privada y necesita la dirección 100.x del PC, que el dueño no
encontraba en la interfaz y que solo existe si Tailscale está encendido
en su PC. La propuesta le da la vuelta:

- **Nadie entra a ningún sitio.** El programa y cada Muse se conectan
  **saliendo** a un punto de encuentro en internet: un **broker MQTT**.
- El broker es un cartero: recibe mensajes de texto en «temas» (como
  apartados de correos) y los entrega a quien está suscrito a ese tema.
- A cada Muse se le pasa **un solo paquete de datos** (§9) y con eso
  queda conectada: sin IPs, sin abrir puertos, sin tocar el router.
- **Solo texto.** Tareas, resultados, tablero, presencia y decisiones
  viajan por MQTT. Los archivos y el código siguen viajando por GitHub
  (worktrees y push, Fase 3), como hasta ahora. Las imágenes *podrían*
  viajar, pero comen el cupo de datos del broker: quedan fuera por
  decisión del dueño.

## 2. Viabilidad verificada (2026-11-16, desde el espacio de Lu)

La pieza crítica era si una Muse puede hablar MQTT **desde su
espacio**. Se probó de verdad, no en papel: dos clientes reales
(paho-mqtt en Python) haciendo de «programa» y de «Muse» contra el
broker público de pruebas de EMQX (`broker.emqx.io`, sin cuenta: solo
valida el mecanismo; el broker real será el del dueño, con
credenciales). Código de la prueba: `~/workspace/mqtt-prueba/`
(`prueba_mqtt.py` + `tunel_local.py`), fuera del repo.

Resultados sobre **MQTT por WebSocket seguro (WSS)**:

| Prueba | Resultado |
|---|---|
| Presencia retenida: la Muse se conecta tarde y ve el estado del programa | ✅ |
| Programa → Muse: una tarea llega | ✅ |
| Muse → programa: un resultado llega (con su % de tokens) | ✅ |
| Última voluntad (LWT): si la Muse cae sin despedirse, el broker avisa solo | ✅ |
| Cola offline: encargo publicado con la Muse «apagada»; lo recibe al volver (sesión persistente, QoS 1) | ✅ |

Hallazgos que el diseño tiene que respetar:

1. **La salida de los espacios Muse pasa por un proxy CONNECT** del
   entorno. La conexión directa está interceptada (el TLS falla) y
   PySocks no negoció bien con este proxy; el túnel CONNECT abierto a
   mano —el mismo patrón que el proyecto ya usa para su SSH a GitHub—
   funcionó a la primera. El ayudante del lado Muse (§3) debe respetar
   las variables de proxy del entorno y, si hace falta, abrir ese
   túnel local. En el PC del dueño no hay proxy: conexión directa.
2. **MQTT por TCP+TLS (puerto 8883) no se pudo verificar desde el
   espacio**: el saludo TLS se quedaba colgado a través del túnel, en
   dos intentos. No es un límite de MQTT —es de esta salida—; por eso
   el transporte del lado Muse es **WSS** (que además atraviesa mejor
   cualquier cortafuegos). El lado del programa puede usar WSS o
   TCP+TLS, según el broker.
3. El TLS va extremo a extremo con el broker incluso a través del
   túnel: el proxy solo ve el CONNECT y texto cifrado.

## 3. Arquitectura

- **El programa** gana un módulo nuevo, `mqtt_enlace.py` (patrón de
  los módulos chicos del repo): un cliente MQTT por cuenta con
  conexión `mqtt`, conectado al broker configurado. Publica las tareas
  de esa cuenta y recibe sus resultados/avisos; al recibir, entrega la
  tarea a la cola de siempre (la tarea entra por la misma puerta que
  hoy: validación, capa de permisos, tablero, presencia — MQTT es
  transporte, no una vía lateral).
- **Cada Muse** usa en su espacio un ayudante chico (el mismo patrón
  que su conexión actual: un script con paho-mqtt que ella deja
  corriendo) suscrito a sus temas: recibe tareas, publica resultados,
  presencia y su % de tokens. Respaldo donde el broker lo ofrezca: su
  API HTTP de publicación para avisos sueltos sin cliente permanente.
- **El broker no se incrusta en el programa.** «Agregar el broker al
  programa» se cumple como: el programa trae el cliente, la pantalla
  de configuración y la generación del paquete de datos por cuenta.
  Un broker embebido en la app no serviría de punto de encuentro (las
  Muses no podrían llegar a él sin abrir el PC a internet, que es lo
  que se quiere evitar). El broker vive fuera: servicio en la nube o
  autoalojado (§8).

## 4. Temas

Raíz configurable; por defecto `growi/<id-pc>/<cuenta>/…`, donde
`<id-pc>` distingue el PC del dueño de cualquier otro y `<cuenta>` es
el identificador de la cuenta Muse:

| Tema | Quién publica | Quién escucha | Uso |
|---|---|---|---|
| `…/<cuenta>/tareas` | programa | la Muse | encargos y tareas (QoS 1) |
| `…/<cuenta>/resultados` | la Muse | programa | resultados y cierres (QoS 1) |
| `…/<cuenta>/avisos` | la Muse | programa | avisos, % de tokens, consultas |
| `…/<cuenta>/presencia` | la Muse (retenido + LWT) | programa | en línea / fuera |
| `…/programa/presencia` | programa (retenido + LWT) | las Muses | el PC está en línea |
| `…/programa/tablero` | programa (retenido) | las Muses | último tablero publicado |

En el broker, la credencial de cada cuenta solo puede publicar y
suscribirse **dentro de su propia rama** (ACL por tema): la cuenta de
Rayo no puede leer ni escribir en la rama de Lu, aunque conozca el
nombre.

## 5. QoS y fiabilidad

- **QoS 1** (al menos una vez) en tareas y resultados; **sesión
  persistente** en ambos extremos (el broker guarda lo publicado
  mientras el otro extremo está apagado y lo entrega al volver —
  verificado en §2). QoS 2 no compensa su coste: la entrega
  exactamente-una-vez ya la garantiza el sistema por dentro.
- **Idempotencia por id**: cada mensaje lleva el id de su tarea o
  encargo; el receptor descarta duplicados por id (QoS 1 puede
  repetir). Es la misma regla que el traspaso y la entrada de canales:
  marcador antes que efecto.
- **Retenidos**: presencia de ambos lados y el último tablero. Al
  conectar, cada extremo ve al instante el último estado del otro.
- **LWT**: si un extremo cae sin despedirse, el broker publica su
  «fuera» retenido. El tablero y la presencia se alimentan de ahí.
- **Tope de tamaño por mensaje: 64 KB** de texto. Lo que no cabe no se
  trocea: va por GitHub. (Los brokers gratuitos admiten mensajes
  mucho mayores; el tope es nuestro, para cuidar el cupo.)

## 6. Seguridad

- **TLS siempre** (WSS en el lado Muse; WSS o TCP+TLS en el
  programa). Sin TLS no hay conexión: el cliente se niega.
- **Credencial de broker por cuenta** (usuario y clave propios, o
  token, según el broker), guardada en la bóveda como `mqtt:<cuenta>`
  y mostrada una sola vez al generarla, igual que la clave de la
  cuenta. El programa también guarda la suya en la bóveda.
- **La clave de Growi de la cuenta sigue mandando**: viaja *dentro* de
  la carga y autentica extremo a extremo, como hoy autentica ante el
  puente. El broker es transporte, no autoridad: si alguien roba la
  credencial del broker de una cuenta, puede molestar en su rama de
  temas, pero no puede hacerse pasar por la Muse ante el programa
  sin la clave de Growi.
- **Cifrado de carga (opcional, segunda capa)**: cifrar el texto con
  una clave derivada de la clave de la cuenta (HKDF → AES-GCM), de
  modo que el broker solo reenvíe texto cifrado y ni el proveedor
  pueda leer las tareas. Coste: el broker ya no puede inspeccionar
  nada (tampoco hace falta) y depurar es más difícil. Se propone como
  opción por cuenta, apagada por defecto en la primera versión.
- **Nada de archivos ni secretos de trabajo por MQTT**: solo texto de
  tareas y resultados. Las credenciales que una tarea necesite siguen
  saliendo de la bóveda compartida en el PC, nunca viajan al broker.

## 7. Convivencia con lo que ya existe

- Nuevo valor de conexión por cuenta: **`mqtt`**, junto a `servidor`
  (Tailscale), `local` y `ambas`. El alta de la reforma no cambia:
  «Cómo se conecta» gana la opción «Por internet con punto de
  encuentro (MQTT)» con su línea llana. No se quita ningún modo.
- **A efectos del modo dual, MQTT es la pata «servidor»**: si el
  broker no responde, la cuenta cae a local con la histéresis de
  siempre; al volver el broker, reconciliación con el protocolo
  `por_confirmar` existente (lo que ya salió no se repite en local).
  La sonda del vigía dual pasa a ser el estado de la conexión MQTT.
- El puente HTTP por Tailscale queda intacto para quien lo prefiera;
  MQTT y Tailscale son dos caminos al mismo sitio y pueden convivir
  por cuenta.
- Tablero, consultas, encargos, traspaso y canales no cambian: reciben
  las tareas por la misma cola. La presencia por MQTT (retenido + LWT)
  alimenta el mismo `presencia.py`.

## 8. Brokers: agnóstico por diseño

La configuración (dirección WSS, puerto, raíz de temas, credenciales)
vive en Ajustes y **no se casa con ningún proveedor**:

- **HiveMQ Cloud Serverless (gratis)**: 100 conexiones, 10 GB/mes,
  mensajes hasta 5 MB. Sobra para texto. ⚠️ **Ese plan gratis se
  retira el 2026-12-31** y los clústeres se borran: sirve para probar,
  no como cimiento.
- **EMQX Serverless (gratis)**: 1 GB/mes. Estimación con holgura: una
  tarea con su resultado ≈ pocos KB; incluso con latidos de presencia
  cada minuto, dos cuentas quedan muy por debajo de 1 GB/mes.
- **Autoalojado**: Mosquitto o EMQX en el propio PC no sirve de punto
  de encuentro (las Muses no llegan sin abrir el PC), pero sí en un
  VPS barato del dueño o en un servicio suyo ya existente: cupo
  propio y ningún tercero leyendo metadatos.
- Cambiar de broker = cambiar la configuración y regenerar las
  credenciales por cuenta. Ningún dato vive en el broker: si el
  broker desaparece, se pierde como mucho lo que estuviera en cola en
  ese momento, y la reconciliación del modo dual cubre ese hueco.

## 9. Qué se le pasa a cada Muse (el paquete del dueño)

El programa genera por cuenta un solo bloque de texto, para pegarlo en
el chat de esa Muse, con cuatro datos:

1. La dirección del broker (WSS).
2. Su usuario y clave **del broker** (solo valen en su rama de temas).
3. Su raíz de temas (`growi/<id-pc>/<cuenta>`).
4. Su **clave de Growi** de siempre (la que autentica ante el
programa).

Con eso, la Muse deja su ayudante conectado y queda en línea en su
puesto. Nada de IPs: la dirección del broker es un nombre fijo que da
el proveedor, igual para las dos cuentas.

## 10. Límites honestos

- Se depende de un tercero (o de un VPS propio): si el broker cae,
  las cuentas `mqtt` caen a local por el modo dual; no se pierde
  trabajo, pero la pata remota espera al broker.
- La retención de la cola offline depende del plan del broker (en los
  gratuitos, la sesión persistente guarda los mensajes QoS 1 mientras
  dura la sesión; hay que confirmarlo al elegir proveedor).
- La prueba de §2 usó un broker público **sin credenciales**: el
  mecanismo quedó probado; la prueba con el broker real del dueño
  (sus credenciales, sus ACL por cuenta) queda para su PC, como pasó
  con Telegram.
- MQTT no mueve archivos: un encargo que produzca archivos los sube
  por GitHub desde el espacio de la Muse o desde el PC, como hoy.

## 11. Implementación propuesta (si el dueño lo aprueba)

- **M1**: `mqtt_enlace.py` en el programa + modo `mqtt` en una cuenta
  + ayudante del lado Muse + paquete de datos por cuenta. Prueba
  real: un encargo ida y vuelta por el broker del dueño.
- **M2**: presencia y tablero por MQTT (retenidos + LWT) y la sonda
  del vigía dual sobre la conexión MQTT.
- **M3**: cifrado de carga opcional por cuenta y pantalla de
  configuración del broker en Ajustes (con botón de prueba).
