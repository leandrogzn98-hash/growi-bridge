# Fase 6 — Seguridad avanzada en Linux: intermediario de root y contenedores por proyecto

Diseño de la fase **tal como se implementó**, y contrato de aceptación
de la misma. Sigue el patrón de las Fases 1 a 5: módulos puros con
lógica testeable + cableado fino en el monolito. Rama:
`fase-6-seguridad`. Es la última fase del plan.

> Este documento se reescribió el 2026-11-16, a petición del dueño,
> para dejar una sola descripción coherente del sistema: la de la
> arquitectura que el código hace. La primera versión del diseño
> describía otra arquitectura (un despachador residente como root
> con vales firmados) que la revisión de Opus 5.5 tumbó y nunca se
> implementó; su historia, con los bloqueantes que la descartaron,
> está en el Anexo A. Nada de lo que el cuerpo de este documento
> describe como comportamiento difiere del código: donde el diseño
> original y el código se separaron, manda el código.

Piezas de la fase:

- `raiz.py` — el lado de la app del intermediario: el **registro
  cerrado de acciones en código**, la validación, la huella de
  parámetros, los topes de ritmo, las órdenes de un solo uso, la
  detección de vía y la composición de la regla de sudoers.
- `growi-ayudante.py` — el ejecutable que la regla de sudoers
  autoriza por su ruta exacta. **Sin privilegios propios y sin
  importar nada del proyecto**: trae su propia copia de la
  especificación del registro y revalida todo antes de ejecutar.
- `instalar-raiz.py` — el generador de reglas que ejecuta **el
  dueño, en su terminal**: compone la regla desde el registro, la
  verifica con `visudo` si está, la muestra entera y dice los
  comandos exactos de instalación. La app jamás instala nada ni ve
  una contraseña.
- `contenedores.py` — detección del runtime, ciclo de vida y
  envoltura de ejecución de los contenedores por proyecto.
- `permission-layer.py` gana `registrar_sistema()` (el asiento de
  auditoría por cuenta Muse de cada acción del intermediario) y
  `git_trabajo.py` los campos de contenedor de `proyectos.json`,
  validados en `guardar_proyecto()`.
- El monolito gana el cableado fino `_f6_*`: la interceptación de
  las tareas `sistema` en el runner, el gancho de contenedor en la
  preparación de la Fase 3 y la sección «Seguridad avanzada» de la
  página Cuentas.

Todos los `.py` nuevos son LF; el monolito solo gana cableado fino,
conservando su CRLF.

La fase tiene dos mitades independientes que comparten filosofía
(fail-closed, confirmación humana por el circuito que ya existe,
auditoría por cuenta y degradación honesta):

1. **Intermediario de root.** Ninguna Muse conoce ni usa la clave
   de root — ni la del usuario con sudo — jamás; de hecho **no hay
   ninguna clave de root guardada en ningún sitio** ni ningún
   componente residente como root. Lo privilegiado nace como
   declaración estructurada en una tarea, lo valida código contra
   un registro cerrado, lo confirma una persona por el circuito de
   aprobaciones de siempre y lo ejecuta el ayudante, elevado solo
   para esa invocación por la regla que el dueño instaló. Cada
   ejecución deja asiento en dos auditorías: la de la cuenta que
   lo pidió y la del propio ayudante.
2. **Contenedores por proyecto.** Un contenedor por proyecto con
   los dos worktrees dentro (decisión registrada en la Fase 3, §9
   de su diseño), como caja de arena **opcional y por proyecto**
   para ejecutar los motores. Las credenciales de git no entran
   nunca: la subida sigue siendo la puerta `subir` de la Fase 3,
   desde fuera.

Lo que esta fase NO hace: tocar Windows (el intermediario es Linux;
en Windows las acciones de sistema quedan «no disponibles» y se
declara, y el gancho de contenedores del monolito solo se activa en
POSIX), dar a ningún agente una shell privilegiada o un comando
libre, ni permitir editar el registro o la lista del dueño desde la
app (el registro es código; la lista la edita el dueño, fuera de la
app).

===

## 1. Principios

1. **El agente nunca toca la palanca.** Una acción privilegiada
   nace como declaración estructurada en una tarea
   (`tipo: "sistema"`, §3.4), la clasifica código, la confirma una
   persona y la ejecuta el ayudante. No existe ningún camino «el
   motor ejecuta sudo»: el entorno del motor no gana ningún
   privilegio nuevo en esta fase, y el prompt de la tarea no manda
   — manda el registro.
2. **Registro cerrado en código, argv exactos, nada de shell.** Las
   únicas acciones que existen están escritas en `raiz.py` (y
   espejadas en el ayudante): plantillas de argv cuyos huecos
   ocupan **elementos enteros** y se rellenan con parámetros
   validados contra dominios cerrados. Un parámetro nunca se
   concatena dentro de un elemento ni se interpreta. Lo que no
   está en el registro no existe, y pedirlo se **rechaza en
   validación**: fail-closed, nunca fail-hang.
3. **Ampliar lo permitido es un acto del dueño, fuera de la app.**
   Qué acciones existen lo fija el código. Qué unidades de systemd
   puede tocar el intermediario lo fija la lista del dueño
   (`raiz-config.json`, §3.3), que la app solo lee: una entrada
   inválida se descarta y **estrecha**, nunca amplía.
4. **La confirmación es la de siempre.** No se crea ningún circuito
   nuevo: las tareas `sistema` pasan por la puerta de aprobaciones
   del monolito con el nivel que sale del registro, y la decisión
   humana es la del circuito existente (`permission-layer.py` +
   aprobaciones). Tras la aprobación, el runner deja una **orden
   de un solo uso** que el ayudante exige y consume (§3.5). La
   orden no es una credencial criptográfica y este diseño no la
   presenta como tal: su valor es de consumo y de auditoría, y el
   control real es el circuito.
5. **El ayudante no importa código del proyecto.** Es un único
   archivo de biblioteca estándar. Si importara módulos de la
   carpeta de la app, quien escriba ahí tendría root: por eso trae
   su propia copia de la especificación y la **revalida entera**
   (la doble validación: la app validó al pedir, el ayudante
   revalida al ejecutar). Una prueba verifica que ambas copias del
   registro coinciden.
6. **Fail-closed y degradación honesta.** Sin intermediario
   instalado, las acciones privilegiadas **no están disponibles**
   y las tareas que las piden esperan con ese motivo, **sin gastar
   ninguna aprobación**. Sin runtime de contenedores, un proyecto
   que lo exige no corre fuera «porque no haya» contenedor (§4.7).
   Todo lo no disponible se dice, en la UI y en el resultado de la
   tarea.
7. **Doble auditoría contrastable.** La app asienta cada acción en
   el audit-log de la cuenta Muse que la pidió (§3.8). El
   ayudante asienta lo que ejecutó de verdad en su propio log
   encadenado por hashes. Ambas entradas comparten la huella de
   los parámetros: si difieren, la diferencia es en sí misma una
   señal de alarma.
8. **Frontera declarada, sin maquillaje.** Como la bóveda de la
   Fase 1, esto es una frontera frente al **motor** (el LLM y sus
   herramientas, acotados por la capa de permisos: sin forma de
   crear órdenes ni de invocar la confirmación humana), no frente
   a un proceso arbitrario corriendo como el propio dueño — el
   mismo límite declarado desde la Fase 1. La orden de un solo uso
   vive en el dominio del usuario y no autentica nada entre
   procesos del mismo uid; lo que impide es que una petición
   suelta, sin aprobación previa viva, se ejecute, y lo que
   garantiza es que cada ejecución quema su aprobación y deja
   doble asiento.

## 2. Mapa general

El camino de una acción de sistema:

```text
tarea {"tipo": "sistema", "sistema": [{"accion": …, "params": {…}}, …]}
  │  (el runner la intercepta: no pasa por process_one, no hay motor)
  ▼
_f6_procesar_sistema ── forma estricta ──► ¿permiso ya aprobado?
  │                                            │ sí: se consume al
  │ no                                         │ recoger y se ejecuta
  ▼                                            ▼
¿vía? ── ninguna ──► la tarea ESPERA (sin gastar aprobación)
  │ sudoers / pkexec
  ▼
nivel_de(): valida todo contra el registro ── desconocida ──►
  │                                            necesita_decision
  ▼
¿nivel < nivel de guardia del dueño? ── sí ──► ejecutar
  │ no
  ▼
puerta de aprobaciones (_park_for_approval) ── el dueño decide ──►
  la tarea vuelve, el permiso se consume al recoger y se ejecuta

ejecutar = por cada acción, en orden (se para en el primer fallo):
  crear_orden(raiz-ordenes/) ─► raiz.ejecutar ─► sudo -n / pkexec
  ─► growi-ayudante.py ejecutar: revalida, exige y consume la
     orden, impone su ritmo, ejecuta el argv exacto, asienta en
     su log ─► resultado + asiento en la auditoría de la cuenta
```

El camino de un contenedor:

```text
tarea con proyecto (preparación de la Fase 3, _f3_preparar)
  │  alquileres y worktree ya preparados; solo si el proyecto
  │  pide contenedor (contenedor_modo != "no") y no es Windows
  ▼
_f6_asegurar_contenedor ─► contenedores.asegurar()
  ├─ listo     ─► prep["contenedor"] ─► al lanzar el motor,
  │               _f4_envolver_cmd lo envuelve con argv_exec
  │               (sin systemd-run: el tope va en el contenedor)
  ├─ degradado ─► (modo opcional) la tarea corre fuera, con aviso
  └─ esperar   ─► (modo requerido) se sueltan los alquileres y
                  la tarea espera, como con un alquiler ocupado
al cerrar: el resultado anota contenedor, runtime y aviso
```

Archivos y lugares:

| Qué | Dónde |
|---|---|
| Registro, validación, órdenes, detección, reglas | `raiz.py` (app) y su espejo en `growi-ayudante.py` |
| Ayudante instalado (el que autoriza sudoers) | `/usr/local/libexec/growi-ayudante.py` |
| Regla de sudoers (la instala el dueño) | `/etc/sudoers.d/growi-bridge` |
| Lista del dueño (unidades autorizadas) | `raiz-config.json`, carpeta compartida |
| Ritmo de la app | `raiz-estado.json`, carpeta compartida |
| Órdenes de un solo uso | `raiz-ordenes/`, carpeta compartida |
| Log del ayudante (encadenado por hashes) | `raiz-ayudante.jsonl`, carpeta compartida |
| Auditoría por cuenta | `audit-log-<cuenta>.json` (Fase 1), vía `registrar_sistema()` |
| Estado vivo del contenedor | campo `contenedor` en `proyectos.json` |

===

## 3. El intermediario de root

### 3.1 Las piezas y los privilegios de cada una

No hay ningún demonio residente y ninguna clave guardada. Hay tres
piezas, y solo una se ejecuta alguna vez como root:

- **`raiz.py`** corre dentro de la app, sin privilegios: valida,
  clasifica, crea órdenes, detecta la vía, invoca y audita.
- **`growi-ayudante.py`** es un ejecutable sin privilegios propios
  al que la regla de sudoers del dueño autoriza **por su ruta
  exacta** (`/usr/local/libexec/growi-ayudante.py`). Solo actúa
  cuando llega elevado por el circuito (`sudo -n` o `pkexec`) y
  con una orden viva: invocarlo a mano, incluso como root, no
  ejecuta nada, porque exige `SUDO_UID`/`PKEXEC_UID` en el entorno
  (los pone el circuito de elevación, no el llamante). Tiene dos
  modos y ningún otro: `sonda` (responde versión y acciones; es
  como la app detecta la vía) y `ejecutar` (el camino de §3.6).
- **`instalar-raiz.py`** corre cuando el dueño quiere, en su
  terminal, sin privilegios (§5.1).

La petición viaja al ayudante como **JSON por stdin** (nunca texto
libre por argv): `{v, accion, params, huella, cuenta, raiz}`. La
respuesta es un JSON por stdout; la app lee la última línea.

### 3.2 El registro cerrado de acciones

El registro vive **en código**, idéntico en `raiz.py` y en el
ayudante (una prueba verifica que las dos copias coinciden: mismos
ids, mismos argv, mismos timeouts). Es esto, entero:

| Acción | argv (los `{…}` ocupan un elemento entero) | Nivel | Timeout |
|---|---|---|---|
| `servicio-estado` | `/usr/bin/systemctl status {unidad} --no-pager` | R1 | 30 s |
| `servicio-arrancar` | `/usr/bin/systemctl start {unidad}` | R2 | 120 s |
| `servicio-parar` | `/usr/bin/systemctl stop {unidad}` | R2 | 120 s |
| `servicio-reiniciar` | `/usr/bin/systemctl restart {unidad}` | R2 | 180 s |
| `apt-actualizar` | `/usr/bin/apt-get update` | R2 | 600 s |
| `apt-instalar` | `/usr/bin/apt-get install -y {paquete}` | R2 | 600 s |

Dominios cerrados, los únicos que existen:

- **`unidad`**: debe pasar la regex estricta
  `^[a-z0-9][a-z0-9._@-]{0,80}$` (minúscula o dígito inicial — jamás
  podrá leerse como una opción de systemctl —, sin espacios ni
  metacaracteres) **y** estar en la lista del dueño (§3.3). La
  regex es defensa en profundidad; la puerta de verdad es la
  pertenencia a la lista.
- **`paquete`**: regex de nombre Debian
  `^[a-z0-9][a-z0-9+.-]{1,80}$` (nunca empieza por guión: no puede
  convertirse en un flag de `apt-get`).

La validación (`validar_peticion` en la app, `validar` en el
ayudante, la misma especificación) exige además que el conjunto de
parámetros sea **exactamente** el declarado: ni sobrantes ni
faltantes. Una acción que no está en el registro produce
`acción de sistema desconocida: <id>` y se rechaza ahí — en
validación, antes de cualquier puerta — de modo que no existe el
estado «esperando una decisión sobre algo inclasificable».

El **nivel** de una acción es el del registro, con una única
subida posible: la lista del dueño puede declarar un nivel mayor
para una unidad concreta, y entonces manda el mayor (nunca se
baja). El nivel de una tarea es el mayor de sus acciones
(`nivel_de()`), calculado validándolo todo: si alguna acción no
existe o no valida, la tarea no se clasifica a ciegas.

La **huella** de unos parámetros es el SHA-256 del JSON canónico
(claves ordenadas, separadores fijos), primeros 16 hex
(`huella_params`, la misma función en las dos piezas). Liga lo
aprobado con lo ejecutado y es la clave de cruce entre las dos
auditorías y el nombre de la orden.

### 3.3 La lista del dueño (`raiz-config.json`)

En la carpeta compartida vive la única parte «configurable» del
intermediario: qué unidades puede tocar.

```json
{"unidades": ["ssh", {"nombre": "growi-vigilante", "nivel": "R3"}]}
```

- Cada entrada es un nombre o un `{nombre, nivel}` (el nivel solo
  puede subir el del registro, §3.2).
- Sin archivo: ninguna unidad permitida (las acciones de paquetes
  siguen disponibles, no dependen de la lista).
- Una entrada con nombre inválido o nivel desconocido se descarta
  y marca la config como **degradada**; una config degradada
  bloquea la generación de reglas (§5.1) hasta que el dueño la
  arregle. Leer la lista nunca falla en silencio a favor de
  permitir más: lo dudoso estrecha.
- El ayudante **relee la lista en cada petición** (solo los
  nombres; los niveles son cosa de la clasificación, en la app):
  si el dueño retira una unidad, la siguiente petición ya no la
  encuentra.

Ampliar la lista es editar ese archivo, un acto del dueño fuera
de la app. La UI la muestra (las unidades autorizadas, en la
sección «Seguridad avanzada») pero no la edita.

### 3.4 Cómo nace una petición: la tarea `sistema` y su camino

Una tarea de sistema se declara así, sin forma libre:

```json
{"tipo": "sistema",
 "sistema": [{"accion": "servicio-reiniciar",
              "params": {"unidad": "growi-vigilante"}}],
 "prompt": "texto para el humano, no manda"}
```

El runner la intercepta en el bucle de candidatas (tras la puerta
del tablero) y **no pasa por `process_one`**: no hay motor. El
camino es `_f6_procesar_sistema`, en este orden, que es el del
código:

1. **Forma estricta** (`_f6_acciones_de`): `sistema` debe ser una
   lista no vacía de objetos con las claves `accion` (texto) y
   `params` (objeto) y **ninguna clave más** — no hay campo
   «comando» ni nada parecido. Si la forma no vale, la tarea se
   cierra como `necesita_decision` sin ejecutar nada.
2. **¿Permiso ya aprobado?** Si la cola de aprobaciones tiene una
   fila `aprobada` para esta tarea con «sistema» entre sus
   acciones, el permiso **se consume al recoger** (pasa a
   `consumida`, un solo uso, como el de las pruebas físicas de la
   Fase 4) y se ejecuta directamente. Es el camino de vuelta de
   una tarea aparcada y aprobada.
3. **¿Hay intermediario?** Se detecta la vía (§5.3). Si es
   «ninguna», la tarea **espera**: queda en la cola con reintento
   a los 120 s y el motivo «intermediario de root no instalado
   (…)», se emite el aviso `sistema_sin_intermediario` y **no se
   gasta ninguna aprobación** — si el dueño lo instala después,
   la tarea sigue su curso.
4. **Clasificación**: `nivel_de()` valida todas las acciones
   contra el registro y la lista. Una desconocida o inválida
   cierra la tarea como `necesita_decision` con el motivo exacto
   («acción de sistema desconocida o inválida: …»): puede ser un
   registro recién editado o un intento de pedir lo que no
   existe; decide el dueño, pero nada queda colgado.
5. **La puerta**: si el nivel de la tarea queda por debajo del
   **nivel de guardia del dueño** (el mismo umbral de la tabla de
   riesgos que gobierna el resto de aprobaciones de Growi), corre
   sin preguntar — es la política del dueño, como en
   `_approval_needed`. Si no, se aparca con
   `_park_for_approval`: el pedido lleva por acción su tipo
   `sistema:<id>`, su nivel, su descripción legible («Reiniciar
   el servicio «growi-vigilante»») y su huella, y se emite el
   aviso `sistema_pendiente`. La decisión es la del circuito de
   siempre, con sus orígenes humanos y sus canales (incluido el
   de la Fase 5, con su muro R3).
6. **Ejecución** (`_f6_ejecutar_acciones`): las acciones se
   ejecutan **en orden y parando en el primer fallo**. De cada
   una: se revalida, se crea su orden (§3.5) justo antes de
   ejecutarla y se llama a `raiz.ejecutar`. El resultado de la
   tarea trae la lista por acción (argv, rc, salida, motivo) y
   queda `terminada` solo si todas salieron bien; se emiten los
   avisos `sistema_ejecutada`/`sistema_fallida`.

Dos notas de encaje con el resto del sistema:

- **Exención de la puerta dual.** `_f4_dual_aplica` devuelve
  falso para las tareas `sistema`, como para `consulta` y
  `encargo`: son tareas de control y de **esta** máquina, se
  procesan en local siempre. Enviar una acción de root de este PC
  a la sesión del servidor la dejaría `por_confirmar` para
  siempre (defecto cazado en las pruebas físicas, §8.2).
- **Sin vía en Windows**: la interceptación existe, pero la
  detección declara la vía no disponible en Windows y la tarea
  espera con ese motivo, como manda el principio 6.

### 3.5 La confirmación y la orden de un solo uso

La aprobación la da el circuito existente; lo que esta fase añade
es cómo una aprobación se convierte en exactamente una ejecución.

Tras la decisión humana (o tras la política que exime de
preguntar, §3.4 paso 5), y solo entonces, el runner crea la orden
con `raiz.crear_orden()`:

```text
raiz-ordenes/<accion>--<huella>.json
{"v": 1, "cuenta": …, "accion": …, "huella": …,
 "approval_id": …, "ts": …, "vence_ts": ts + 900}
```

- Vive **15 minutos** desde la aprobación.
- El ayudante la exige: la lee, comprueba que es de la misma
  cuenta que la petición y que no caducó, y **la borra antes de
  ejecutar** (consumida: un solo uso; si no puede borrarla, no
  ejecuta). Una petición sin orden viva se rechaza con «sin orden
  viva del circuito de aprobaciones: el ayudante no ejecuta
  peticiones sueltas», venga de donde venga.
- Cada acción de una tarea con varias tiene **su propia orden**
  (su propia huella), creada justo antes de ejecutarla: aprobar
  la tarea no deja una ventana abierta para «otras cosas con la
  misma huella», porque la huella es de esos parámetros exactos.

**Honestidad sobre la orden** (principio 4): la orden vive en la
carpeta compartida, en el dominio del usuario. No es una
credencial criptográfica y no autentica nada entre procesos del
mismo uid — un proceso arbitrario del dueño podría escribir una,
igual que podría escribir en `confirmaciones.json`, y ese es el
límite declarado de todo el sistema de confirmaciones desde la
Fase 1. Su valor es triple y es el que es: **consumo** (cada
aprobación se quema en una ejecución), **liga** (acción + huella +
cuenta + `approval_id` quedan atados en un solo objeto) y
**auditoría** (el ayudante asienta la huella que consumió). El
control de que haya un humano detrás es el circuito de
aprobaciones, no este archivo.

### 3.6 El ayudante por dentro

`procesar_peticion()` hace, en orden y todo fail-closed:

1. Forma de la petición: JSON, `v == 1`, acción y cuenta
   presentes. La entrada por stdin está acotada a 64 KiB.
2. **Circuito de elevación**: sin `SUDO_UID` ni `PKEXEC_UID` en el
   entorno, rechazo («el ayudante solo actúa elevado por el
   circuito, nunca invocado a mano»). Ni siquiera root a mano lo
   hace correr.
3. **Revalidación completa** contra su propia copia del registro
   y la lista del dueño releída: acción existe, parámetros
   exactos, dominios cumplidos.
4. **Huella recalculada**: si la huella de la petición no coincide
   con la de sus parámetros, rechazo («petición manipulada»).
5. **La orden** (§3.5): existe, es de esta cuenta, no caducó; se
   consume.
6. **Su propio ritmo** (§3.7), calculado desde su propio log.
7. **Ejecución** del argv exacto con `subprocess`: `shell=False`,
   stdin cerrado (`DEVNULL`), **entorno mínimo construido desde
   cero** (`PATH` fijo de sistema, `LANG`/`LC_ALL` C.UTF-8,
   `HOME=/root`), `cwd=/`, grupo de procesos propio. Al vencer el
   timeout del registro, mata **el grupo entero** (`SIGKILL`) y
   responde rc 124. La salida se trunca a 64 KiB.

La respuesta (`{ok, rc, salida, motivo, duracion_s}`) es el
resultado: cuando el ayudante llegó a pronunciarse, la app no lo
reinterpreta. La app lo invoca con `sudo -n -- <ayudante>
ejecutar` (vía sudoers) o `pkexec --disable-internal-agent
<ayudante> ejecutar` (vía pkexec), con un timeout propio de
timeout del registro + 30 s.

**La carpeta base del ayudante** se deriva como hace la app pero
desde el usuario que elevó: el `pw_dir` del `SUDO_UID`/
`PKEXEC_UID` (no el hogar de root), con `XDG_DATA_HOME` si está, y
`GrowiBridge` — porque sudo recorta el entorno y una base que
viniera del llamante sería movible por él. Existe además una
costura de entorno, `GROWI_RAIZ_BASE`, que el propio código
reconoce antes que esa derivación. Límite conocido y declarado
(§8.2): con un `XDG_DATA_HOME` no estándar, la app y el ayudante
podrían mirar carpetas distintas y una unidad parecería «fuera de
la lista»; en una instalación estándar (XDG por defecto)
coinciden.

### 3.7 Ritmo: dos topes independientes

Las acciones de sistema tienen tope de ritmo en las dos capas,
con los mismos números:

- **La app** (`raiz.comprobar_ritmo`, desde `raiz-estado.json`):
  **10 por hora por cuenta** y **30 por hora en total**. Superarlo
  es un `ErrorRaiz` previo a cualquier invocación.
- **El ayudante**, desde su propio log (solo cuenta las entradas
  que ejecutaron): los mismos 10/30 por hora. Su tope no depende
  de que la app lleve bien sus cuentas.

Detalle fiel del orden de §3.6: la orden se consume (paso 5)
**antes** del chequeo de ritmo del ayudante (paso 6). Si el tope
del ayudante rechaza, la orden ya está quemada y hay que volver a
aprobar. Es deliberado en un sentido: la orden nunca sobrevive a
una invocación del ayudante, ni siquiera a una rechazada.

### 3.8 Auditoría: dos asientos con la misma huella

- **La de la cuenta** (la app): `raiz.ejecutar` recibe un
  `auditar` que el monolito conecta con
  `permission-layer.registrar_sistema()` → entra en el
  audit-log **de la cuenta Muse** que pidió la acción, con
  herramienta `raiz` y acción `sistema:<accion>:<huella>`, su
  resultado y su motivo. Es código de la capa, no una tool del
  agente: ningún motor puede llamarla. Los fallos previos a que el
  ayudante se pronuncie (validación, ritmo o sin vía en
  `raiz.ejecutar`) se asientan como `bloqueado`. El log es el de
  la Fase 1: append-only, encadenado por hashes y con su ancla en
  `audit-indice.json`.
- **La del ayudante**: `raiz-ayudante.jsonl`, en la carpeta
  compartida, una línea por petición **pronunciada** (ejecutada o
  rechazada): ts, resultado, si ejecutó, acción, cuenta, huella,
  rc, motivo y el uid que elevó. Encadenada por hashes
  (`prev_hash`/`hash` sobre el JSON canónico);
  `verificar_cadena()` comprueba su integridad.

Cruzarlas es comparar huella y hora: lo que la cuenta pidió, lo
que el ayudante hizo. Si un asiento existe en una y no en la
otra, eso ya es el hallazgo.

===

## 4. Contenedores por proyecto

### 4.1 Qué se decidió ya y qué decide este diseño

La Fase 3 (su §9) registró la decisión: **un contenedor por
proyecto, con los dos worktrees dentro**, y `"contenedores":
"por_cuenta"` en `proyectos.json` como opt-in para código no
confiable. Esta fase la implementa sin reabrirla, y decide lo
demás: runtime, montajes, red, ciclo de vida e integración con la
preparación de la Fase 3.

### 4.2 Runtime: Podman preferente, Docker si es lo que hay

`contenedores.detectar_runtime()` sondea en este orden:

1. **Podman** (`podman` en el PATH + `podman info` responde en
   ≤ 5 s): preferente porque es rootless y sin demonio — el
   contenedor corre como el propio usuario, que es exactamente la
   frontera que queremos (dentro parece root; fuera es el dueño).
2. **Docker** (`docker` + `docker info`): si el demonio responde y
   el usuario puede usarlo. La detección devuelve el matiz
   declarado: «Docker: el socket da acceso de root al anfitrión;
   Podman rootless no», y la UI lo muestra junto a la vía.
3. Ninguno → no disponible, y cada proyecto degrada según su modo
   (§4.7).

La sonda es real (ejecuta `info`), como la sonda de `systemd-run`
de `recursos.py` en la Fase 4: estar en el PATH no basta. El
resultado se cachea 60 s; el botón «Probar sonda» de la UI limpia
la caché y re-sondea.

### 4.3 Campos en `proyectos.json`

Sobre el esquema de la Fase 3 (que ya trae
`contenedores: "proyecto"|"por_cuenta"`), esta fase añade cuatro
campos, validados en `git_trabajo.guardar_proyecto()`:

```json
"contenedor_modo": "no",
"contenedor_imagen": null,
"contenedor_red": "saliente",
"contenedor": null
```

- `contenedor_modo`: `"no"` (defecto: el proyecto corre como en
  la Fase 3, el contenedor ni se menciona), `"opcional"` (se usa
  si se puede; si no, la tarea corre fuera **con aviso**) o
  `"requerido"` (sin contenedor no hay tarea: §4.7). El defecto
  `"no"` es el opt-in que pide el encargo: nada cambia para los
  proyectos que no lo activen. Un valor desconocido se trata como
  `"no"`.
- `contenedor_imagen`: la imagen a usar (p. ej.
  `docker.io/library/python:3.12-slim` o la imagen propia del
  proyecto con sus dependencias). **Sin imagen declarada no hay
  contenedor**: el diseño no inventa una imagen por el dueño,
  porque la imagen ES el entorno de su proyecto (su juego pedirá
  Godot, otro proyecto pedirá Node). La UI la pide al activar el
  modo.
- `contenedor_red`: `"saliente"` (la red normal del usuario; los
  motores necesitan hablar con sus APIs) o `"ninguna"`
  (`--network none`). En modo `por_cuenta` — la caja para código
  no confiable — conviene pensar el defecto con cuidado: con red
  ninguna, los motores de nube no operan dentro (ni APIs ni
  credenciales, por §4.5), así que `por_cuenta` sirve para motores
  locales y trabajo sin red. No hay opción de puertos publicados:
  **nunca** se pasa `-p`/`--publish`; el contenedor no escucha
  nada hacia fuera.
- `contenedor`: el estado vivo que escribe `contenedores.py` (no
  lo edita el dueño): `{runtime, nombre, huella, creado, estado}`
  o `null`.

### 4.4 Montajes: las áreas de worktrees y el `.git`, nada más

El contenedor ve del anfitrión solo esto, montado en **sus mismas
rutas absolutas** (montaje espejo, para que los punteros `.git` de
los worktrees — que contienen la ruta absoluta del almacén
principal — resuelvan dentro sin traducción):

| Montaje | Modo | Porqué |
|---|---|---|
| Las áreas de worktrees del proyecto | lectura-escritura | el área hermana `<repo>.worktrees/` (el diseño de la Fase 3) y, si existe, el área de reserva bajo la carpeta compartida (`worktrees/<repo_id>`). En modo `por_cuenta` el montaje se estrecha a `<área>/<cuenta>/` |
| `<repo>/.git/` | lectura-escritura en modo `proyecto`; **solo lectura** en `por_cuenta` | sin el almacén, git no funciona en un worktree |

Y **no** se monta: el directorio raíz del repo (el checkout de
trabajo del dueño no existe para el contenedor: solo ve el almacén
y los worktrees), el HOME, `~/.ssh`, la carpeta de la app (con la
bóveda y los audit-logs), la carpeta compartida de Growi (tablero,
cuentas) ni ningún otro proyecto.

Más decisiones de la construcción (`argv_crear`), todas por
construcción y no por disciplina:

- Nombre determinista: `growi-<repo_id>` en modo proyecto,
  `growi-<repo_id>-<cuenta>` en `por_cuenta`; etiquetas
  `growi.proyecto=<repo_id>` y `growi.modo=...`.
- El comando que mantiene vivo el contenedor es `sleep infinity`.
- El usuario dentro es el del dueño: `--user <uid>:<gid>` cuando
  el runtime es Docker; en Podman rootless el mapeo por defecto
  ya hace que los archivos creados sean del dueño. Así los
  archivos del worktree siguen siendo suyos y git no protesta por
  la propiedad.
- La función que construye el argv **no tiene forma de emitir**
  `--publish`, `--privileged` ni `--device`: no son opciones
  rechazadas, son imposibles.
- El directorio de trabajo de cada ejecución es el worktree de la
  tarea (su ruta espejo es la misma dentro y fuera).

Dos consecuencias, dichas en claro como manda el proyecto:

- **El almacén de objetos es compartido.** Cada cuenta puede leer
  los commits de la otra, porque son worktrees del mismo repo;
  son las dos cuentas del mismo dueño y la UI lo dice al activar
  el modo, en vez de prometer un aislamiento que no existe.
- **En `por_cuenta`, dentro git es de lectura.** Con el `.git` en
  solo lectura, los archivos del worktree se pueden tocar y el
  código se puede ejecutar, pero git no puede escribir su
  metadata (índice, HEAD: viven en el almacén). `argv_exec` fija
  `GIT_OPTIONAL_LOCKS=0` en ese modo para que `status`/`diff`/
  `log` no intenten ni el lock optimista. Es el modo de
  inspeccionar y correr código no confiable, no el de comitear
  desde dentro; los commits de ese flujo se hacen desde el
  anfitrión, como todo lo demás de git en este sistema.

### 4.5 Las credenciales no entran

- **El entorno del exec va filtrado** (`filtrar_entorno`): parte
  del entorno del motor ya sin credenciales de git (Fase 3,
  `aplicar_entorno_sin_credenciales`) y quita **toda** variable
  cuyo nombre tenga pinta de credencial — la regex cubre `KEY`,
  `TOKEN`, `SECRET`, `PASSW`, `CREDENCIAL`, `BEARER`, `COOKIE`,
  `SSH`, `GH_`, `GITHUB`, `AWS_`, `PRIVATE`, sin distinción de
  mayúsculas. La regla es por nombre, que es lo comprobable, y
  **no tiene excepción**: no hay ningún campo que deje pasar
  credenciales «a propósito» en esta versión. Se añaden solo dos
  marcas: `GROWI_EN_CONTENEDOR=1` y, en `por_cuenta`,
  `GIT_OPTIONAL_LOCKS=0`.
- **Antes de crear**, se comprueba que `<repo>/.git/config` no
  esconda credenciales en la URL del remoto (un
  `https://token@github.com/…`): ese archivo lo leería el
  contenedor, así que si las hay **no se crea nada** y el motivo
  dice cómo limpiarlo (la subida usa la puerta de la Fase 3, no
  esa URL).
- La subida sigue haciéndose desde el anfitrión con
  `git_trabajo.subir()` y su escaneo de secretos, con el entorno
  de push que solo existe en ese momento. Quien comprometa el
  contenedor no puede subir nada (sin credenciales y con la
  puerta fuera), no ve otros proyectos ni el sistema de archivos
  del dueño, y los alquileres, la mezcla y las propuestas siguen
  gobernados desde el anfitrión.

### 4.6 Ciclo de vida (`asegurar`)

`contenedores.asegurar()` deja el contenedor listo o explica qué
pasa, y devuelve uno de estos estados: `sin_contenedor`,
`listo`, `degradado` (modo `opcional`) o `esperar` (modo
`requerido`).

- **Modo `no`**: devuelve `sin_contenedor` **sin tocar nada** —
  ni una sonda. El flujo de la Fase 3 queda exactamente como
  estaba.
- **Comprobaciones previas**, en orden: hay runtime (§4.2); el
  proyecto declara imagen; `.git/config` no esconde un token
  (§4.5). Cada fallo sale por `degradado`/`esperar` según el modo,
  con su motivo.
- **Huella de configuración**: SHA-256 (16 hex) de (runtime,
  imagen, montajes con su modo, red, usuario), guardada en el
  campo `contenedor` de `proyectos.json`. Es la identidad viva
  del contenedor: lo que la UI muestra y contra lo que se decide
  reutilizar o recrear.
- **Reutilizar**: si un `inspect` confirma que el contenedor con
  ese nombre existe **y** la huella guardada coincide con la
  calculada, se reutiliza (se arranca si estaba parado).
- **Recrear**: si existe pero la huella difiere (el dueño cambió
  la imagen, la red o los montajes), se destruye (`rm -f`) y se
  crea de nuevo. `asegurar` admite un callable `en_curso` que, si
  informa de tareas dentro, pospone la recreación y sigue con el
  contenedor viejo avisándolo en el resultado
  (`recreacion_pospuesta`); el cableado actual del monolito no lo
  pasa, así que en la práctica la recreación ocurre en la
  preparación de la siguiente tarea tras el cambio.
- **Crear**: si la imagen no está (`image inspect` falla), se
  baja con `pull` (timeout de 600 s); crear tiene 120 s y arrancar
  60 s. Al crear bien, el estado `{runtime, nombre, huella,
  creado, estado: "en_marcha"}` se guarda en `proyectos.json`.
- **Destruir** (`destruir`): `rm -f` y el campo `contenedor`
  vuelve a `null`. Los worktrees y el `.git` no se tocan (son
  montajes, no volúmenes). La confirmación la pone quien llama:
  la UI pide un sí explícito en un diálogo antes de llamar.
  Destruir nunca es automático por inactividad en esta fase: un
  contenedor parado no cuesta casi nada y destruir por sorpresa
  rompería la reutilización.

### 4.7 Sin runtime o sin contenedor: la degradación por modo

| Modo del proyecto | Sin runtime / sin imagen / creación imposible | Contenedor muere a mitad de tarea |
|---|---|---|
| `no` | ni se intenta | — |
| `opcional` | la tarea corre fuera, con aviso en su resultado (`contenedor_aviso`) y en el log | el `exec` devuelve error y la tarea falla con ese error; la siguiente preparación vuelve a asegurar |
| `requerido` | la tarea **no corre**: el gancho suelta los alquileres y la tarea espera (~60 s) con el motivo, como con un alquiler ocupado, y cada reintento vuelve a asegurar | la tarea falla con el error del `exec`; nunca se reejecuta fuera en silencio |

La asimetría es deliberada: `requerido` existe para código que el
dueño no quiere ejecutar en su sistema ni una vez; degradarlo en
silencio sería exactamente el fallo que el modo promete evitar.

### 4.8 Recursos: el % de la Fase 4 manda también aquí

Los límites se fijan **al crear**, desde el presupuesto de la
Fase 4: el gancho del monolito calcula
`recursos.limites(specs, asignación del modo de presencia actual,
1)` y `asegurar` lo traduce a `--cpus` (de `nucleos_equiv`) y
`--memory` (de `bytes_por_tarea`). Con contenedor activo **no**
se envuelve además con `systemd-run`: el tope se aplica una sola
vez, en el contenedor (§6).

Declarado como límite de esta versión: los límites **no** forman
parte de la huella (§4.6) y el barrido de supervisión no los
actualiza en vivo — `contenedores.argv_update_limites()` construye
el argv de `update`, pero nadie lo llama. Si el dueño cambia su
% con el contenedor vivo, el contenedor conserva los límites de
su creación hasta que se recree por otro cambio de configuración.

===

## 5. Instalación y detección

### 5.1 Lo que el dueño hace una vez (intermediario)

Instalar el intermediario es un acto del dueño en su terminal,
para siempre. La app no instala nada, no ejecuta sudo y no ve
ninguna contraseña en ningún paso.

1. **Escribir su lista** en `raiz-config.json` (carpeta
   compartida): las unidades que el intermediario podrá tocar
   (§3.3). Sin lista, solo habrá acciones de paquetes.
2. **Ejecutar `instalar-raiz.py`** desde la carpeta del programa,
   en su terminal:
   - **Sin TTY se niega** (ni stdin ni stdout de terminal → rc 2
     y un mensaje claro): este guion lo ejecuta el dueño a mano;
     no es una tubería para que otro programa lo conduzca.
   - Lee la lista y compone la regla con
     `raiz.componer_sudoers()`, que **valida antes de componer
     nada**: si el nombre de usuario no tiene forma válida, si la
     config está degradada o si alguna unidad trae un nombre
     inválido, lanza el error y **no se compone ni una línea**
     (rc 1, no se escribió nada).
   - Verifica el texto con `visudo -cf` si visudo está: si lo
     rechaza, rc 1 y no se escribió nada; si no está, avisa y el
     texto queda para revisión a ojo.
   - Escribe el texto en `growi-bridge.sudoers`, junto al propio
     script (un archivo normal, sin privilegios), **lo muestra
     entero** y termina.
3. **Pegar los comandos exactos** que el guion imprime (salen de
   `raiz.comandos_instalacion()`), en esa misma terminal, con su
   contraseña:

   ```text
   sudo install -m 0755 -o root -g root growi-ayudante.py /usr/local/libexec/growi-ayudante.py
   sudo install -m 0440 -o root -g root growi-bridge.sudoers /etc/sudoers.d/growi-bridge
   sudo visudo -cf /etc/sudoers.d/growi-bridge
   ```

La regla compuesta es una sola línea:

```text
<usuario> ALL=(root) NOPASSWD: /usr/local/libexec/growi-ayudante.py
```

Sin comodines: sudoers acota **el programa**; qué acciones
existen y con qué argumentos lo acotan el registro cerrado y la
doble validación (sudoers no puede expresar «uno de estos
paquetes» sin comodines, y un comodín sobre argumentos es una
puerta conocida). Que la regla sea `NOPASSWD` no deja las
acciones «sin humano»: el factor humano es el circuito de
aprobaciones (§3.5) — sin aprobación viva no hay orden, y sin
orden el ayudante no ejecuta, aunque cualquier proceso del uid
pueda *invocarlo*.

La misma ventana de reglas está en la UI («Ver reglas a
instalar», §6) para quien quiera componerla sin pasar por el
guion; la app se limita a mostrarla.

### 5.2 Lo que el dueño hace una vez (contenedores)

Nada por parte de Growi: si quiere contenedores, instala Podman
o Docker con los medios de su distribución. Sin runtime, los
proyectos degradan según su modo (§4.7) y la UI lo dice.

### 5.3 Detección: qué vía hay, de verdad

`raiz.detectar_via()` responde `{via, verificada, motivo,
ayudante, acciones}`, con la sonda cacheada 60 s (no se lanza
sudo en cada latido):

1. **Si existe `/etc/sudoers.d/growi-bridge`**, se sondea:
   `sudo -n -- <ayudante> sonda`, y la última línea de la salida
   debe ser el JSON del ayudante con `ok`. Si responde: vía
   **sudoers, verificada**. Si el archivo existe pero la sonda
   no responde: vía **ninguna** con el motivo honesto («hay un
   archivo de reglas pero la sonda al ayudante no respondió: la
   instalación está incompleta o la regla no autoriza a este
   usuario»).
2. **Si no hay regla pero `pkexec` está en el PATH**: vía
   **pkexec, sin verificar** — sondearlo abriría un diálogo de
   contraseña; se verifica al ejecutar la primera acción delante
   de la PC, y el motivo lo dice así.
3. **Si no**: vía **ninguna**, «intermediario no instalado».

La ruta del ayudante que se sondea e invoca es la instalada
(`/usr/local/libexec/growi-ayudante.py`) si existe; si no, la
copia junto a `raiz.py` (sin la regla no habrá vía igualmente, y
la sonda lo dirá). La app nunca prueba un `sudo` genérico ni
busca reglas anchas: o está **esta** regla o no hay vía.

En Windows la detección no aplica: la UI declara «solo Linux; en
Windows las acciones de sistema no están disponibles» y las
tareas esperan con ese motivo.

## 6. Cableado en el monolito y UI

Todo el cableado es fino y vive tras dos condiciones que, en
falso, dejan el sistema exactamente como estaba: el tipo de tarea
(`sistema`) y el modo del proyecto (`contenedor_modo != "no"`).

**Las tareas `sistema`** (detallado en §3.4):

- En el bucle de candidatas del runner, tras la puerta del
  tablero, `tipo == "sistema"` se despacha a
  `_f6_procesar_sistema()` y la ronda termina: no pasa por
  `process_one` ni por ningún motor.
- `_f4_dual_aplica()` las exime de la puerta dual, como a
  `consulta` y `encargo`: se procesan en local siempre.
- La auditoría entra por `_f6_registrar()`, que carga
  `permission-layer.py` una vez y llama a `registrar_sistema()`
  sin dejar que una excepción de auditoría tumbe la ejecución.
- Los avisos al dueño salen por el canal de avisos de la Fase 4:
  `sistema_sin_intermediario`, `sistema_pendiente`,
  `sistema_ejecutada`, `sistema_fallida`.

**El contenedor** (detallado en §4.6–§4.8):

- En `_f3_preparar()`, **después** de registrar el proyecto, tomar
  los alquileres y preparar el worktree — y solo si hay worktree,
  no es Windows y el proyecto pide contenedor — se llama a
  `_f6_asegurar_contenedor()`. Si devuelve «esperar», el propio
  gancho ya soltó los alquileres y la tarea queda aparcada ~60 s
  con el motivo; si el contenedor degradó (modo `opcional`), el
  aviso queda en `prep["contenedor_aviso"]` y la tarea sigue
  fuera.
- Al lanzar el motor, `_f4_envolver_cmd()` mira la preparación:
  si trae contenedor, el argv se envuelve con
  `contenedores.argv_exec(runtime, nombre, cwd, entorno del
  motor, argv, por_cuenta=…)` **en lugar de** `systemd-run`. El
  harness de la Fase 4 hereda el tratamiento sin código nuevo:
  sus procesos nacen del mismo lanzamiento.
- Al cerrar (`_f3_tras_process_one()`), el resultado anota
  `contenedor`, `contenedor_runtime` y `contenedor_aviso` si lo
  hubo, y el historial de la cola gana la entrada
  `{"fase6": {…}}`, junto a la anotación de worktree y rama de la
  Fase 3.

**La UI: «Seguridad avanzada» en la página Cuentas.**

- El estado del intermediario: vía detectada (con «verificada»
  si lo está), su motivo y las unidades autorizadas por el
  dueño. En Windows, el aviso de no disponible.
- El registro entero, legible: id · nivel · clase · descripción
  de cada acción. Es lo único que se puede pedir, dicho en la
  propia pantalla.
- Botones: **«Probar sonda»** (limpia las cachés de vía y de
  runtime y vuelve a sondear), **«Ver reglas a instalar»**
  (ventana con la regla compuesta desde el registro y los
  comandos exactos; el texto deja claro que la app no lo instala)
  y **«Actualizar»**.
- El editor de contenedor por proyecto: selector de proyecto,
  modo (`no`/`opcional`/`requerido`), red
  (`saliente`/`ninguna`), campo de imagen y el estado vivo del
  contenedor (nombre, runtime, huella); botones **«Guardar
  contenedor»** (vía `guardar_proyecto`, con su validación),
  **«Crear contenedor»** (llama a `asegurar` y dice el estado
  resultante) y **«Destruir contenedor»** (con diálogo de
  confirmación que recuerda que los worktrees y el `.git` no se
  tocan). La línea de runtime muestra la detección y su matiz
  (§4.2).

## 7. Modelo de fallos

| Fallo | Qué pasa, exactamente |
|---|---|
| Tarea `sistema` con forma inválida | Se cierra `necesita_decision` sin ejecutar nada (§3.4.1) |
| Acción desconocida o parámetros inválidos | Se cierra `necesita_decision` con el motivo de validación; nunca queda colgada (con vía) |
| Sin intermediario (vía ninguna) | La tarea espera (reintento 120 s) **sin gastar aprobación**, con aviso; si el dueño lo instala, sigue su curso |
| Regla presente pero sonda muda | Vía ninguna con motivo «instalación incompleta»; la UI lo muestra tal cual |
| Ritmo de la app superado | `ErrorRaiz` antes de invocar; la acción se asienta como `bloqueado` |
| El ayudante rechaza (sin elevación, sin orden, orden caducada o de otra cuenta, huella distinta, su ritmo) | Su motivo **es** el resultado de la acción; la tarea lo recoge tal cual |
| La acción sale con rc ≠ 0 | Resultado error con rc y salida (truncada); en una tarea de varias acciones, se para en el primer fallo |
| La acción supera su timeout | El ayudante mata el grupo entero y responde rc 124; la app tiene su propio timeout (el del registro + 30 s) por si el ayudante no responde |
| Una acción de varias falla a mitad | Las anteriores quedaron ejecutadas y asentadas; las siguientes no se intentan; la tarea queda `fallida` con el reporte por acción |
| Sin runtime / sin imagen / token en `.git/config` / `pull` o `create` fallan | Según el modo del proyecto: `degradado` con aviso (opcional) o `esperar` (requerido) (§4.7) |
| El contenedor muere a mitad de tarea | El `exec` devuelve error y la tarea falla; no hay reintento silencioso fuera |
| La auditoría de la app no puede escribir | `_f6_registrar` traga la excepción: la ejecución no se tumba por auditar, y el asiento del ayudante sigue existiendo |
| Divergencia entre las dos auditorías | Es en sí misma el hallazgo: se cruzan por huella y hora (§3.8) |

Y la regla que resume la tabla: ningún fallo de esta fase
convierte una negativa en una ejecución, ni una espera en un
salto silencioso de la puerta.

## 8. Aceptación de la fase

### 8.1 Pruebas unitarias

**64 pruebas nuevas** (`test_raiz.py`, `test_ayudante.py`,
`test_contenedores.py`), con la suite completa en **409 en
verde**. Cubren, entre otras:

- Registro y validación: argv manipulados y nombres con
  metacaracteres rechazados, parámetros sobrantes o faltantes,
  clases no registradas (`accion_desconocida`), la subida de
  nivel por unidad y la huella estable.
- **Acuerdo entre las dos copias del registro**: la app y el
  ayudante coinciden en ids, argv para los casos válidos y
  timeouts (la doble validación no sirve si las copias divergen).
- Ritmos de las dos capas (por cuenta y global).
- El generador de reglas: con un nombre inválido en la lista
  **no compone nada**; la regla sale solo con nombres válidos y
  pasa `visudo` cuando está.
- El ayudante: acepta lo válido y rechaza sin elevación, sin
  orden, con la orden caducada, de otra cuenta o reutilizada;
  huella manipulada; su cadena de log detecta la manipulación.
- **El cruce real app↔ayudante sin mocks entre ellos**: sin orden
  → rechazado; con orden → ejecuta el argv exacto; repetir →
  rechazado; log íntegro.
- Contenedores con ejecutor falso: montajes exactos por modo, el
  **canario de credencial** (una variable con nombre de
  credencial en el entorno del motor) no cruza al `exec`, la
  imposibilidad de emitir `--publish`/`--privileged`/`--device`,
  y el modo `no` que no toca ni el ejecutor.

### 8.2 Pruebas físicas (2026-11-16)

Con la app real (los dos carriles) y la regla instalada **de
verdad** en la máquina de pruebas — regla compuesta desde el
registro, `visudo` OK, ayudante instalado en
`/usr/local/libexec` —:

- La sonda verifica la vía «sudoers». Antes de instalar el
  ayudante, la detección dijo con honestidad «instalación
  incompleta», que es su trabajo.
- Una acción R1 (`servicio-estado`) aprobada **por el canal de
  Telegram** recorrió todo el circuito: el pedido salió por el
  canal, el dueño simulado respondió «aprobar», el permiso se
  consumió al recoger, la orden se creó y se consumió, el
  ayudante ejecutó el argv exacto y el resultado (código 4: la
  máquina de pruebas no corre systemd) quedó asentado **dos
  veces**, en la auditoría de la cuenta y en el log encadenado
  del ayudante, con la misma huella.
- La acción desconocida se rechazó sin colgarse y el parámetro
  manipulado (`ssh; touch …`) se rechazó sin ejecutar nada (el
  archivo del intento no existió nunca).
- `instalar-raiz.py` sin TTY se niega (rc 2).
- Sin Podman ni Docker en la máquina, la detección de
  contenedores dice «ninguna».

Dos defectos reales cazados en estas pruebas y corregidos:

1. **La puerta dual se tragaba las tareas `sistema`.** Con la
   cuenta en modo «ambas» y el vigía en «servidor», la tarea se
   enviaba a la sesión remota y quedaba `por_confirmar` para
   siempre: las acciones de root son de ESTA máquina. Corrección:
   `sistema` se suma a `consulta` y `encargo` en las exenciones
   de `_f4_dual_aplica` (§3.4).
2. **La base del ayudante sale del hogar del uid, no del
   entorno** (§3.6). Con el HOME aislado del entorno de pruebas,
   la app y el ayudante miraban carpetas distintas hasta
   alinearlas; en una instalación estándar coinciden. Queda
   declarado como límite conocido.

### 8.3 Lo que queda para la PC del dueño

Como la lista de la Fase 0, hay cosas que esta máquina no puede
demostrar y no se fingen hechas:

- La regla sudoers con **su usuario real**: en la VM de
  desarrollo todo corre como root, así que la sonda pasa pero la
  frontera de usuario (que sudo pida la contraseña al instalar y
  que `sudo -n` solo alcance al ayudante) solo se prueba en su
  PC.
- Un **contenedor real** con Podman o Docker (en la VM no hay
  ninguno instalado): creación, reutilización, recreación por
  cambio de huella y un motor trabajando dentro.
- La vía **pkexec** con sesión gráfica, si la usa: aquí no hay
  `pkexec` ni `polkitd`.

## 9. Fuera de alcance (explícito)

- Windows y macOS: el intermediario es de Linux y el cableado de
  contenedores del monolito solo se activa en POSIX. En Windows,
  las tareas `sistema` quedan «no disponibles» con su motivo.
- Editar el registro o la lista del dueño desde la app, e
  instalar o desinstalar el intermediario desde la app. Nunca.
  La app solo detecta, muestra y compone el texto de la regla.
- Acciones interactivas (que pidan entrada durante la
  ejecución), acciones con salida en vivo, y cualquier forma de
  terminal privilegiada o «sudo libre», para agentes o para el
  dueño desde la app.
- Guardar la clave de root o la contraseña de sudo en la bóveda,
  en cualquier forma: la revisión lo descartó por inviable
  (Anexo A, B8) y esta arquitectura no la necesita — no hay
  ningún secreto que guardar.
- Contenedores para tareas sin proyecto (consultas, encargos sin
  repo): el contenedor es por proyecto y entra por la preparación
  de la Fase 3; lo demás corre como siempre.
- Red entrante en los contenedores, puertos publicados,
  contenedores privilegiados y dispositivos del anfitrión: el
  argv de creación no puede emitirlos (§4.4).
- La actualización en vivo de los límites de un contenedor
  desde el barrido de supervisión (`argv_update_limites` existe
  sin cablear, §4.8) y el `pull` deduplicado entre carriles:
  trabajo futuro nombrado, no prometido.
- Cambiar `resolver_confirmacion`, la tabla de riesgos o los
  vencimientos: el intermediario se adapta a los circuitos,
  nunca al revés (misma regla que la Fase 5 con las
  aprobaciones).

## 10. Reversión

- **Intermediario**: el dueño borra, en su terminal, lo que los
  comandos de instalación pusieron (`/etc/sudoers.d/growi-bridge`
  y `/usr/local/libexec/growi-ayudante.py`). La app vuelve a «no
  instalado» sola, por la sonda; las tareas `sistema` que
  quedaran en espera siguen en espera con su motivo — ninguna se
  ejecuta por la reversión. Las órdenes pendientes en
  `raiz-ordenes/` caducan solas en 15 minutos y, sin ayudante
  instalado, nadie puede consumirlas; borrar la carpeta es
  seguro en cualquier momento.
- **Contenedores**: poner `contenedor_modo: "no"` en el proyecto
  (o destruir el contenedor desde la UI) devuelve el proyecto al
  flujo exacto de la Fase 3. Los campos nuevos de
  `proyectos.json` son ignorados por el código anterior.
- **Código**: los módulos de la fase son aditivos; el cableado
  del monolito solo se activa con tareas `sistema` o con
  proyectos que pidan contenedor, así que revertir la fase no
  toca el comportamiento del resto del sistema.

===

## Anexo A — Historial: la primera arquitectura y la revisión de Opus 5.5

Este anexo es el registro honesto de cómo se llegó a la
arquitectura del cuerpo. No describe comportamiento del sistema:
describe un diseño descartado y por qué.

### A.1 La primera arquitectura

El diseño original de esta fase proponía:

- Un **despachador residente como root**,
  `growi-rootbroker.py`, instalado en `/usr/local/libexec`, que
  ejecutaba las acciones.
- Un **catálogo en `/etc/growi-bridge/acciones.json`** con
  plantillas de argv y dominios, leído por la app para clasificar
  y por el despachador para ejecutar.
- **Vales firmados con HMAC**: la decisión humana se materializaba
  en un registro firmado de `permission-layer.py` y el
  despachador ejecutaba contra ese vale.
- Como «último recurso» para lo que sudoers/polkit no expresaran,
  una variante con la contraseña del usuario guardada en la
  bóveda.

### A.2 La revisión

La revisión se pidió a `claude-opus-5-5` vía MWAPI con un anexo
de hechos verificados del código. El gateway cortó las
generaciones largas una y otra vez, así que se hizo en **cuatro
pasadas por secciones** — A: §1–§3.3; B: §3.4–§3.9; C: §5
(contenedores); D: §6–§11 — cuyas salidas completas quedan
guardadas en `~/workspace/revision-fase6/opus-{A,B,C,D}.txt`.
Resultado: **14 bloqueantes y 20 importantes**, más menores.

Los bloqueantes clave, en una línea cada uno:

- **B1. El vale vivía en el dominio del atacante.** La clave HMAC
  y `confirmaciones.json` son del mismo uid que los motores: una
  firma que el solicitante puede calcular no autentica nada, y al
  abrir acciones de root esa clave se convierte en material
  root-equivalente. Sin nonce ni liga a tarea, el vale además era
  reutilizable durante toda su ventana.
- **B2. `NOPASSWD` acota el programa, no al humano.** Cualquier
  proceso del uid invocaría el despachador sin nadie delante,
  contra el principio de confirmación humana previa.
- **B3. TOCTOU de catálogo.** La app clasificaba con su lectura y
  root ejecutaría con la suya; una edición intermedia cambiaba
  el argv o el nivel bajo una aprobación ya dada.
- **B4. Acción desconocida = fail-hang.** Sin entrada en el
  catálogo no hay nivel, luego ni clasificación ni puerta: la
  tarea colgaría para siempre en vez de rechazarse.
- **B5. Plantillas de argv con huecos.** Nada prohibía `{a}{b}`
  (hueco pegado a hueco), un hueco en `argv[0]` (una ruta ahí
  apuntaría a `/bin/sh`) ni caracteres `{`/`}` en los literales.
- **B8. El «último recurso» era inviable.** Un servicio root
  lanzando `sudo -S` no eleva nada (siendo root, sudo no pide
  contraseña), y la contraseña en la bóveda la obtiene cualquier
  proceso del mismo uid: no es una frontera.
- **B9. El `.git` en lectura-escritura anulaba la frontera de
  los contenedores.** Con el almacén montado rw, el código de
  dentro podía reescribir `.git/config` y el anfitrión lo
  ejecutaría después, justo cuando existe el entorno de push.
- **B10. Matar el `exec` no mata el proceso de dentro.** Un
  timeout del runner no garantizaba que el proceso del
  contenedor hubiera muerto.
- **B11. Las credenciales del motor entrarían al contenedor**
  si el entorno del `exec` no se filtraba por nombre.

La corrección que la propia revisión aplicó sobre el papel
intentaba salvar la arquitectura con más maquinaria del lado de
root: que el despachador **sellara** los vales en su propio
dominio (clave propia, nonce por aprobación, consumo atómico),
que R3 exigiera además un acto del dueño en su terminal, y un
servicio con socket y `SO_PEERCRED` en lugar de la contraseña en
la bóveda.

### A.3 Por qué se descartó, y qué se implementó en su lugar

Al consolidar la revisión se vio el patrón: cada bloqueante se
«arreglaba» añadiendo una pieza más del lado de root para
defender un vale que solo existía porque el diseño lo había
creado. La implementación tomó el camino contrario: **quitar el
vale y el componente residente**, y responder a los mismos
bloqueantes por otra vía. El mapeo, destilado de la nota de
divergencia que cerró la revisión:

| Bloqueante | Respuesta de la arquitectura implementada |
|---|---|
| B1 (vale en el dominio del uid) | No hay vales. La **orden** es un token de consumo declarado no criptográfico (§3.5): liga y quema la aprobación; el control es el circuito de aprobaciones, y el límite mismo-uid se declara en vez de disimularse con una firma |
| B2 (NOPASSWD sin humano) | El factor humano se declara como lo que es en todo Growi — el circuito de aprobaciones — y la orden ata cada ejecución a **una** aprobación concreta y viva; sin orden, el ayudante no ejecuta aunque lo invoquen |
| B3 (TOCTOU de catálogo) | No hay catálogo editable: el registro es **código idéntico** en la app y el ayudante (una prueba verifica que coinciden) y la **huella** de parámetros liga lo aprobado con lo ejecutado; la lista del dueño solo puede estrechar |
| B4 (fail-hang) | Igual en ambas arquitecturas: rechazo en validación con `accion_desconocida`; la tarea se cierra `necesita_decision`, nunca cuelga (§3.4) |
| B5 (huecos de plantillas) | Sin plantillas editables: los argv viven en código, con huecos que ocupan elementos enteros y dominios cerrados por regex + pertenencia (§3.2) |
| B8 (último recurso inviable) | Tachado sin sustituto: no hay contraseña guardada en ningún sitio porque la arquitectura no la necesita (§9) |
| B9 (.git rw) | En `por_cuenta` el `.git` va en **solo lectura** y los commits de ese flujo los hace el anfitrión; en `proyecto` (código del propio dueño) se declara el riesgo en vez de prometer lo que no hay (§4.4) |
| B10 (matar el exec) | Queda como **límite declarado**: el timeout del runner mata el `exec`; esta versión no pone el contenedor en cuarentena ni finge que el proceso de dentro haya muerto (§9) |
| B11 (credenciales al contenedor) | El entorno del `exec` se filtra **por nombre** con una regex de credenciales, sin excepciones, y `.git/config` se inspecciona antes de crear (§4.5) |

Los contenedores fueron la parte donde el diseño original y lo
implementado **sí coincidieron** en las decisiones (uno por
proyecto con los dos worktrees, `por_cuenta` para código no
confiable, opt-in por proyecto); las diferencias finales son de
detalle contra el código y están recogidas en el §4 de este
documento, que es el que manda.

Queda registrado también el punto que la revisión dejó abierto
y este documento cierra: entre el cuerpo original corregido
(despachador + vales sellados) y el código, **manda el código** —
es la arquitectura probada (§8) — y este documento, reescrito,
es su descripción.
