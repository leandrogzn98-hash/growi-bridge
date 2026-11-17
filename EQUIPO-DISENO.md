# Diseño — Trabajo en equipo dentro de Growi: la sala y el reparto conversado

Visión del dueño (dictada el 2026-11-16). Estado: **diseño revisado**
(§11 bis: revisión de Opus 5.5, 8 bloqueantes + 7 importantes +
3 menores, todos aplicados al cuerpo). La implementación espera el
visto bueno del dueño, como la de MQTT. Esta pieza se apoya en lo ya
construido (relevo, tablero, consulta, ramas y mezcla) y no sustituye
nada de eso: lo pone a trabajar en equipo, a la vista.

## 1. La visión, en las palabras del dueño

- Una **sala compartida dentro de Growi** donde caen todas las
  notificaciones y donde él escribe «quiero que hagan X»: **todas las
  cuentas reciben el mismo mensaje** en esa sala.
- El **reparto se conversa**: la principal (Rayo) divide el plan en
  fases dentro de la sala —«yo me quedo con estas, tú con estas»— y la
  otra lee y acepta («ok, me quedo con esa fase»). Variantes que el
  dueño dejó abiertas: que cada Muse **se asigne un peso/preferencia**
  a cada parte y elija, y que un **tercer Muse haga de planificador**.
- **Cada cuenta con su API/motor distinto** (DeepSeek, Kimi, Claude…),
  con su clave en la bóveda.
- Cada quien trabaja su fase **en su rama** y **al final la principal
  unifica las ramas**.
- **Skills por cuenta como «fuertes» declarados**: el reparto sabe el
  fuerte de cada una. A Lu: revisión, perfeccionamiento y una «de
  cuestionar» lo que proponen las demás. A un tercer Muse de ejemplo
  («Groda»): skills de ahorro.
- Su resumen: «un harness completo con todos los Muse y con todas
  las APIs de las otras IA».

## 2. Mapa: qué existe ya y qué es nuevo

| Pieza | Estado |
|---|---|
| Encargos divididos en subtareas con asignación automática (`relevo.py`: `plan_reserva`, `asignar`) | ✅ Existe (Fase 4) |
| Tablero con % de tokens por (motor, cuenta) y elección de cuenta (`tablero.elegir_cuenta`) | ✅ Existe (Fase 2) |
| Consultas entre cuentas con presupuesto por raíz (`consulta.py`) | ✅ Existe (Fase 2) |
| Rama y worktree por cuenta y tarea (`muse/<cuenta>/<tarea>`) | ✅ Existe (Fase 3) |
| Propuestas de mezcla con veredicto y aprobación del dueño (`git_trabajo.py`) | ✅ Existe (Fase 3) |
| Motores por datos (`engines.json`) con `credencial_ref` a la bóveda de claves | ✅ Existe (original) |
| Cuota por (motor, cuenta Muse) | ✅ Existe (Fase 2) |
| Catálogo de skills (carpeta `skills/` + `~/.claude/skills/`); el runner elige hasta 3 por tarea según su descripción | ✅ Existe (original) |
| Página «Chat» 1 a 1 con cada cuenta | ✅ Existe (correcciones) |
| Avisos guardados en el programa (`avisos.py` → `avisos.jsonl`) | ✅ Existe (Fase 4) |
| **La sala**: conversación común dueño + todas las cuentas + notificaciones | 🆕 Nuevo (§3) |
| **Reparto conversado**: propuesta, reclamos con peso, aceptación explícita | 🆕 Nuevo (§4) |
| **Rol planificador** configurable (por defecto, la principal) | 🆕 Nuevo (§4) |
| **Motor por defecto por cuenta** y clave de motor por cuenta | 🆕 Nuevo (§5) |
| **Fuertes (skills) por cuenta** como criterio de reparto y prioridad al ejecutar | 🆕 Nuevo (§6) |
| **La principal como unificadora por defecto** de las ramas | 🆕 Nuevo (§7) |

## 3. La sala

- **Autoridad y vista (B1).** El estado del reparto vive en el bloque
  `reparto` de `encargos.json` (carpeta compartida), con el bloqueo
  entre procesos y la revisión optimista que ya usa `cuentas.py`:
  **esa es la única autoridad**. `sala.jsonl` es vista y registro:
  primero se guarda el estado y después se escribe en la sala el
  mensaje que lo cuenta, con id derivado
  (`<encargo>:<fase>:<ronda>:<tipo>`), idempotente. La sala se
  escribe bajo el mismo bloqueo entre procesos (un «append» desde dos
  procesos no es atómico, en Windows menos), y el lector descarta
  líneas incompletas y deduplica por id.
- **Tipos de mensaje**: `dueno` (lo que escribe el dueño), `cuenta`
  (lo que escribe una Muse), `sistema` (notificaciones: tarea
  terminada, % bajo, propuesta de mezcla, encargo cerrado…) y los del
  reparto (`propuesta`, `reclamo`, `aceptacion`, `resolucion`, §4).
- **Quién crea qué (B3).** Solo la copia cuya UI recibió la escritura
  del dueño crea el encargo: primero persiste el encargo con id = id
  del mensaje (marcador) y después escribe la línea en la sala. Las
  demás copias **nunca** crean encargos por leer la sala. Los
  mensajes `dueno` con efecto (crear un encargo, asignar una fase a
  mano, desempatar) llevan la **firma HMAC del dueño**, la misma que
  la confirmación de mezcla; sin firma válida se muestran marcados
  como «sin verificar» y **no producen efecto** (fail-closed): la
  sala es un archivo plano en la carpeta compartida y cualquier
  proceso con acceso a archivos podría añadir una línea falsa. El
  `autor` de los mensajes `cuenta` lo pone el programa desde el
  carril que produjo la respuesta, nunca desde la salida del modelo.
  Y la capa de permisos deniega a los motores la escritura en la
  carpeta compartida.
- **Un solo punto de escritura, con redacción (B8).** Todo lo que
  entra en `sala.jsonl` (y en `avisos.jsonl`) pasa por una única
  función que redacta antes de guardar: patrones conocidos (cabeceras
  de autorización, claves con forma conocida) **más** coincidencia
  exacta contra los valores guardados en la bóveda. Si tras redactar
  sigue habiendo coincidencia con un valor de la bóveda, el mensaje
  se rechaza y se escribe uno de sustitución con el mismo id
  («mensaje retenido por contener un posible secreto»). Fail-closed:
  la sala es archivo de estado y la regla de la casa es ningún
  secreto en archivos de estado ni en logs.
- **Avisos sin duplicar (I5).** La sala es el registro canónico de
  las notificaciones del equipo; el destino «sala» de `avisos.py`
  sustituye al aviso suelto para esos eventos, no se suma a él: un
  aviso, una escritura, un id. Los canales externos (Telegram) siguen
  recibiendo su copia por su vía, desde el mismo registro.
- **Orden (I4).** La vista ordena por secuencia monótona por escritor
  + id de mensaje; la hora es un dato informativo, no el orden (dos
  procesos no comparten reloj fiable).
- **Retención.** `sala.jsonl` rota por tamaño (al rotar queda
  `sala-<fecha>.jsonl`); como el estado canónico del reparto vive en
  `encargos.json`, rotar la sala no pierde nada del trabajo, solo
  historial de conversación.
- **Página «Sala»** en la barra lateral, junto a «Chat»: la
  conversación entera, un campo para escribir como dueño y el estado
  de cada encargo en curso (fases y quién lleva cada una). «Chat»
  sigue siendo el 1 a 1 con cada cuenta; la sala es la mesa común.
- **«Quiero que hagan X»**: cuando el dueño escribe un encargo en la
  sala (con su firma, ver arriba), se crea **un encargo raíz** (el
  `tipo: "encargo"` de la Fase 4) cuyo primer paso es el reparto
  (§4). Todas las cuentas ven el mensaje en la sala al momento; el
  trabajo no arranca hasta que el reparto se cierra, salvo «empezar
  ya» (§4.2).

## 4. El reparto conversado

### 4.1 Roles

- **Planificadora**: propone el reparto y lo resuelve.
  **Unificadora**: junta las ramas al final (§7). Los campos `roles`
  del registro de cuentas (§8) son solo la **preferencia por
  defecto**; la verdad de cada encargo se fija al crearlo en el
  archivo compartido: `reparto.planificadora` y `reparto.epoca` (B2).
  Nadie lee dos fuentes: para un encargo en curso manda su bloque
  `reparto`.
- Por defecto, planifica y unifica la cuenta **principal**; el dueño
  puede poner a cualquier cuenta habilitada **con carril** (una
  cuenta sin carril no puede ejecutar su propio plan dentro del
  programa; §9).

### 4.2 El protocolo (todo queda escrito en la sala)

0. **Qué mensajes generan tarea (B4) — lista cerrada.** Solo dos:
   un encargo firmado del dueño genera **una** tarea de planificación
   para la planificadora, y una `propuesta` genera **una** tarea de
   respuesta por cuenta con carril. Los mensajes `cuenta` y `sistema`
   **nunca** generan tareas (si no, cada respuesta dispararía tareas
   en las demás y la sala sería un bucle que quema cuota). Cada tarea
   del reparto se descuenta del presupuesto por raíz de `consulta.py`
   y lleva id idempotente `<encargo>:<ronda>:<cuenta>`.
1. **Propuesta.** La planificadora divide el encargo en fases y
   publica en la sala: cada fase con su descripción, sus etiquetas
   (código, revisión, documentación, coste…), la cuenta propuesta y
   el porqué corto («esto es revisión: tu fuerte»). La propuesta es
   un mensaje `propuesta` cuyo bloque estructurado coincide con lo
   guardado en el bloque `reparto` (la autoridad, §3).
2. **Respuesta de cada cuenta**, por fase, con tres formas:
   - `aceptacion`: «ok, me quedo con esa fase».
   - `reclamo`: «esta la quiero yo», con **peso 0–100** y una línea
     de motivo. El peso **efectivo** es el menor entre el declarado y
     el techo que la cuenta puede sostener con sus fuertes, su % y su
     carga (lo calcula el sistema y la sala muestra los dos números):
     declarar 100 sin respaldo no compra ventaja (B7).
   - `rechazo`: «esta no», con motivo (sin tokens, no es mi fuerte,
     estoy con otra cosa).
3. **Candidatas (I1).** Antes de puntuar se filtra: solo cuentas
   **con carril y con presencia en el tablero**. Si el conjunto queda
   vacío para una fase, la fase vuelve a la planificadora y la sala
   lo publica. El mismo filtro aplica al reparto por plazo vencido.
4. **Resolución.** Con todas las respuestas (o vencido el plazo,
   §4.3), la planificadora cierra el reparto:
   - Fase aceptada sin conflicto → queda como estaba.
   - Conflicto → gana la **puntuación mayor**, con todos los
     términos normalizados a [0,1] y coeficientes constantes en
     configuración, publicados junto al resultado:
     `0,4·fuerte + 0,3·(peso_efectivo/100) + 0,2·(tokens_libre/100) +
     0,1·(1 − carga_norm)`. El `fuerte` vale 1, 0,5 o 0 según el
     cruce etiquetas↔fuertes (§6). Desempate determinista y escrito:
     mayor `fuerte`, luego mayor % libre, luego orden estable de
     cuenta (B7).
   - `tokens_libre` (I7) es el `pct_efectivo` que el tablero publica
     para el par (motor actual de la cuenta, cuenta) en el momento de
     resolver — la foto queda guardada en la `resolucion`. Si la
     cuenta cambia de motor después, no se vuelve a puntuar: el
     reparto cerrado no se reabre por un cambio de motor.
   - Fase que nadie quiere → la planificadora la asigna por
     puntuación igualmente, o se la queda ella. Si la asigna a
     alguien que la había **rechazado**, la `resolucion` lo dice tal
     cual: «asignada por puntuación contra el rechazo de X» (menor
     de la revisión, aplicado).
   - La resolución es un **compare-and-swap** sobre
     `(revision, epoca)` del bloque `reparto`, que pasa a
     `estado: "resuelto"`; ese marcador se persiste **antes** de
     materializar nada (B2).
5. **Arranque.** El reparto cerrado se materializa como el encargo de
   la Fase 4: la «asignación acordada» **solo fija el `asignada_a`**
   de cada subtarea; la creación, la reserva y el cierre pasan por
   `relevo` y su buzón como hoy (una sola autoridad de cierre, I2),
   con id de subtarea derivado de `<encargo>:<fase>` para que
   materializar dos veces sea idempotente. El paso a
   `estado: "arrancado"` es el mismo CAS de B2: «empezar ya» del
   dueño compite por ese mismo CAS y, si lo pierde, no hace nada y
   la sala lo dice — nunca hay doble arranque. Cada fase corre en el
   carril de su cuenta, en su rama (§7), con su motor (§5) y sus
   fuertes (§6).
6. **Durante el trabajo**, la sala recibe los hitos (fase empezada,
   fase entregada, consulta entre cuentas, bloqueo) como mensajes
   `sistema`, y el cierre del encargo deja su resumen en la sala,
   como hoy lo devuelve al canal de origen.

### 4.3 Plazos, atascos y relevo de rol

- Plazo de respuesta al reparto: **10 minutos** por defecto
  (configurable). Si una cuenta no responde, la planificadora asigna
  sus fases por puntuación (con el filtro de §4.2.3) y lo anota
  («sin respuesta: asignado por puntuación»). Nadie se queda
  bloqueado por un silencio.
- Máximo **2 rondas** de reclamo por fase; a la tercera palabra la
  tiene el dueño desde la sala (puede asignar a mano cualquier fase
  en cualquier momento, con su firma: su palabra corta el protocolo).
- **Relevo de rol sin doble mando (B2).** Si la planificadora cae
  (sin presencia en el tablero), el rol pasa a la otra cuenta con
  carril **incrementando `reparto.epoca`** y la sala lo anuncia. Toda
  escritura de resolución o arranque con época vieja se rechaza por
  el CAS: una planificadora lenta pero viva puede proponer, pero no
  puede materializar dos veces ni pisar a su relevo.

## 5. Motor por cuenta

- **Campo nuevo `motor`** en la cuenta (opcional; vacío = el motor
  por defecto del programa). Es el motor con el que esa cuenta
  trabaja cuando la tarea no nombra otro. La cuota ya es por (motor,
  cuenta): cada cuenta gasta de su motor y el tablero ya lo sabe
  contar.
- **Motores nuevos = datos, con una condición (B5).** DeepSeek y
  Kimi son APIs compatibles con el formato de OpenAI: su ficha en
  `engines.json` (con `base_url` y `credencial_ref`, igual que
  `gemini` apunta hoy a su clave) basta para *hablar* con ellos,
  pero una API de chat, sola, **no ejecuta una fase**: no edita
  archivos en el worktree, no carga skills del catálogo (su formato
  es el de Claude) y no pasa por la capa de permisos. Por eso la
  ficha declara sus `capacidades` y la regla es fail-closed:
  - Un motor **solo-API** se marca `capacidades: ["texto"]`: sirve
    para planificar, responder en la sala y ser consultado
    (`consulta`), y `relevo` **rechaza** asignarle fases que deban
    producir una rama.
  - Un motor puede ejecutar fases solo si su ficha nombra un
    **runner agéntico** que acepte su `base_url` y pase por permisos
    y skills, como el CLI del caso `gemini`. Nombrarlo es parte de
    dar de alta el motor; sin runner nombrado, el motor es de texto.
- **Clave de motor por cuenta**: resolución en orden — (1) la clave
  propia de la cuenta en la bóveda, `motor:<cuenta>:<motor>`; (2) la
  clave general del motor (Ajustes → Claves, la de `credencial_ref`).
  Así Rayo puede tener *su* DeepSeek y Lu *su* Kimi, o compartir la
  misma clave general si el dueño no separa. Las claves nunca salen
  de la bóveda: el motor las recibe en su entorno, como hoy.
- El reparto puede tener en cuenta el motor (una fase de «código
  largo» encaja con la cuenta cuyo motor rinde ahí), pero el criterio
  principal siguen siendo los fuertes declarados (§4.2): el motor es
  un dato más de la propuesta, no un reparto automático escondido.

## 6. Skills por cuenta: los «fuertes»

- **Campo nuevo `fuertes`** en la cuenta: lista de nombres de skills
  del catálogo existente (la carpeta `skills/` del programa y
  `~/.claude/skills/`).
- **Validación con el tiempo (I3).** Al **guardar**, un nombre que no
  está en el catálogo se rechaza con aviso. Al **cargar**, un fuerte
  cuya skill desapareció después (el catálogo de `~/.claude/skills/`
  es por máquina y cambia sin avisar) **no rompe la cuenta**: se
  advierte, y al repartir ese fuerte cuenta como 0 con aviso en la
  sala. Nunca error de carga.
- **En la página Cuentas**, cada cuenta muestra sus fuertes con un
  selector desde el catálogo y una nota libre («cuestiona lo que
  proponen las demás»). La página Skills gana la vista «por cuenta»:
  qué skills tiene asignadas cada Muse.
- **Al repartir**: las etiquetas de cada fase se cruzan con los
  fuertes de cada cuenta (la descripción de la skill manda, como en
  el selector actual). Ese cruce es el factor `fuerte` de la
  puntuación de §4.2 y el «porqué» que la planificadora escribe.
- **Al ejecutar**: el selector de skills de hoy elige hasta 3 por
  tarea según la descripción. Los fuertes de la cuenta dueña de la
  tarea entran como **candidatas con prioridad** en esa elección (si
  encajan con la tarea, van primero), sin romper la regla de la casa
  («nada de always: true»): una skill fuerte que no encaja con la
  tarea no se fuerza.
- Ejemplos del dueño, tal cual: **Lu** — revisión,
  perfeccionamiento/perfeccionismo y la «de cuestionar» (si esa skill
  no está en el catálogo, se deja caer en `skills/_equipo/` como
  cualquier skill del equipo y ya puede asignarse). **Groda** (un
  tercer Muse futuro) — skills de ahorro/coste.

## 7. Ramas y unificación por la principal

- Cada fase trabaja en la rama de siempre, `muse/<cuenta>/<tarea>`,
  en su worktree (Fase 3, sin cambios).
- Al entregar una fase, su propuesta de mezcla se dirige a la
  **unificadora** (por defecto, la principal): ella revisa el trabajo
  de las demás (veredicto sobre el sha concreto, como hoy) y junta
  las ramas en orden.
- **La unión es una rama con sha propio (B6).** Mezclar produce un
  commit nuevo que ningún veredicto de fase cubre. Por eso la
  unificadora trabaja sobre su propia rama de unión,
  `muse/<unificadora>/<encargo>-union`, y publica en la sala: los
  shas de fase incluidos, los excluidos y por qué, y el **sha de la
  unión**. Su veredicto sobre fases ajenas es el veredicto normal de
  hoy.
- **La aprobación del dueño se ata al sha de unión.** Donde hoy
  `mezclar` exige su confirmación HMAC, la sigue exigiendo, pero
  sobre el sha de unión: cualquier commit posterior en esa rama
  invalida la aprobación y hay que volver a pedirla (el sha se
  quema). La unificadora no tiene la clave HMAC —vive en la bóveda o
  en memoria, nunca en `sala.jsonl` ni en `encargos.json`—, así que
  prepara todo y el dueño firma lo exacto que se va a mezclar, sin
  aprobar a ciegas.
- **Nada de autorrevisión.** Las fases de la propia unificadora las
  revisa otra cuenta con carril; si no hay ninguna, quedan marcadas
  `sin revisión independiente` en la `resolucion` y el dueño lo ve
  antes de firmar.
- Conflicto de mezcla: como hoy (la base no se mueve, la propuesta
  queda en `conflicto` con la lista de archivos) y la sala lo
  anuncia; la unificadora propone la salida y el dueño decide si hay
  choque de criterio.

## 7 bis. Cómo se cachan los errores: tres fuentes, y el fallo cae en la sala

Pregunta central del dueño (2026-11-16): cuando algo falla en su PC,
¿cómo se enteran las Muses y cómo agarran el fallo para corregirlo?
La captura **ya existe** — son tres fuentes, todas texto — ; lo nuevo
de este diseño es el aterrizaje: **todo fallo cae en la sala con su
extracto de diagnóstico**, listo para que la otra cuenta lo agarre.

### Las tres fuentes (piezas ya construidas)

1. **La salida del proceso.** Toda tarea que el runner ejecuta
   devuelve código de salida y stdout/stderr. Si la compilación o la
   prueba falla, ese detalle es la materia prima del diagnóstico: no
   hay que adivinar qué pasó, el proceso lo dijo. La prueba de
   consumo la miden `recursos.py` y `supervision.py` (Fase 4):
   latidos, duración máxima, y matar solo árboles propios si algo se
   cuelga o se pasa de su tope — con el aviso previo y la aprobación
   que el modo presente exige para pruebas físicas, como ya quedó
   implementado.
2. **Los registros del sistema.** Linux deja escrito el fallo aunque
   haya pasado antes: el journal de systemd y los registros de
   apt/dpkg. Ante «revisen por qué falló la actualización», la Muse
   corre por el runner comandos de diagnóstico **de solo lectura** y
   lee la causa exacta en la salida.
3. **El arreglo con root.** Reparar (terminar de configurar paquetes,
   reinstalar lo roto) entra por el intermediario de la Fase 6:
   lista blanca cerrada, aprobación del dueño, sin contraseña. Lo
   que la lista tiene hoy es `apt-actualizar` y `apt-instalar` (y
   los servicios de su lista); los comandos típicos de reparación de
   una actualización rota (`dpkg --configure -a`,
   `apt-get install -f`) **todavía no están en la lista**: agregar
   una acción `apt-reparar` al registro cerrado —con la doble
   validación app↔ayudante de siempre— queda nombrado aquí como
   extensión concreta para cuando se implemente esta pieza, no como
   algo que ya exista.

### El aterrizaje en la sala (lo nuevo)

- Cada fallo de una tarea de un encargo genera un mensaje `sistema`
  de subtipo **`fallo`** con: el encargo y la fase, la cuenta que la
  llevaba, el código de salida y un **extracto acotado** de la salida
  (las últimas líneas relevantes, ya redactado por el único punto de
  escritura de §3: ningún secreto entra en la sala). El resultado
  completo queda en el sitio de siempre (runner-results); la sala
  lleva el extracto y la referencia.
- El fallo queda **asignable**: la planificadora puede convertirlo
  en una fase nueva del mismo encargo («esto lo mira la otra») o la
  otra cuenta puede **reclamarlo** en la sala con el mismo mecanismo
  de §4 — y al agarrarlo recibe, por `consulta` o por la propia
  tarea, el extracto y el resultado completo. Nadie rebusca en
  carpetas: el fallo llega a la mesa con su detalle.
- Si la cuenta que falló sigue en línea, el circuito corto es el de
  siempre: la salida vuelve a su carril y ella misma corrige sobre
  la marcha (el ciclo compilar→fallar→corregir del §3 bis de MQTT
  cuando el canal es MQTT). La sala es el registro común y la vía
  para pasar el fallo de mano, no un rodeo obligatorio.

### Los dos ejemplos del dueño, caminados

**El traductor imagen→texto, entre las dos.** El dueño lo pide en la
sala → se crea el repositorio y se comparte → reparto conversado
(§4): cada una escribe su parte **en su rama** → la unificadora
(§7) descarga y une → **lo prueba en el PC midiendo cuánto consume**
(`recursos.py`/`supervision.py`, con las reglas de presencia de la
Fase 4) → si la prueba falla, el `fallo` cae en la sala con el
extracto (qué proceso, qué salida, cuánto consumía cuando cayó) →
la otra cuenta lo agarra, corrige en su rama y la unión se rehace.
El dueño ve toda la película en la sala sin abrir una terminal.

**La actualización de Linux que falla.** El dueño manda «revisen por
qué falló» → una cuenta corre el diagnóstico de solo lectura
(journal y registros de apt/dpkg) por el runner → la causa queda en
la sala, en texto («tal paquete quedó a medias por tal motivo») →
si el arreglo necesita root, se pide por el intermediario de la
Fase 6 con la aprobación del dueño (con la extensión `apt-reparar`
cuando exista en la lista; hoy, lo que la lista ya cubre) → el
resultado del arreglo también cae en la sala. Arreglar «directamente»
significa esto: diagnóstico y reparación sin que el dueño toque la
terminal, pero **nunca sin su aprobación** para lo que lleva root.

## 8. Datos que cambian

- `cuentas.py`: la cuenta gana tres campos **opcionales** —
  `motor` (str o None), `fuertes` (lista de str) y `roles`
  (`{"planifica": bool, "unifica": bool}`, solo preferencia por
  defecto; la verdad por encargo es `reparto.planificadora` y
  `reparto.epoca`, §4.1). Un `accounts.json` de la v1 carga igual: lo
  que falta se lee como «sin motor propio, sin fuertes, sin roles» y
  la principal de compatibilidad conserva planifica+unifica por
  defecto. Sin migración destructiva.
- Carpeta compartida: `sala.jsonl` (nuevo, solo vista y registro) y
  el bloque `reparto` dentro del encargo existente en
  `encargos.json` (la autoridad: propuesta, respuestas, resolución
  con su foto de puntuaciones, época y estados).
- Nada de esto toca `cola.db`, el tablero ni los canales.

## 9. Límites honestos

- **Hoy hay dos carriles.** Una tercera cuenta (Groda) puede existir
  en el registro sin carril: ve la sala y puede ser consultada, pero
  no ejecuta fases ni puede ser planificadora/unificadora hasta que
  exista un tercer carril. Los roles se configuran entre cuentas con
  carril.
- El reparto conversado **tarda más** que el automático (hay una
  conversación por medio): es el precio de que el dueño lo vea y de
  que las cuentas elijan. «Empezar ya» lo salta cuando hay prisa.
- La puntuación de §4.2 reparte con los datos que hay (fuertes
  declarados, peso con techo verificable, % del tablero): queda
  escrita en la sala con sus números, y la fórmula ya no se puede
  ganar declarando 100 (B7), pero un fuerte mal declarado sigue
  torciendo el reparto — la transparencia es la defensa, no un juez
  escondido.
- Los motores por API (DeepSeek, Kimi) dependen de sus servicios y
  sus claves: sin clave válida en la bóveda, el motor falla como
  cualquier motor sin credencial hoy; y sin runner agéntico nombrado
  son motores de texto (§5), no ejecutan fases.

## 10. Implementación propuesta (si el dueño lo aprueba)

- **E1 — La sala como mesa común**: `sala.jsonl` con su único punto
  de escritura y su redacción (B8), la autoridad en `encargos.json`
  (B1), la página «Sala» en modo lectura y notificaciones con el
  destino «sala» sin duplicar (I5). **Sin lanzamiento de encargos
  todavía** (I6): la puerta se abre cuando existen sus defensas.
- **E2 — El reparto conversado**: encargos desde la sala con la
  firma HMAC del dueño (B3), la lista cerrada de tareas (B4), el CAS
  de época (B2), el protocolo de §4 con su fórmula normalizada (B7,
  I1, I2, I7) y los roles configurables.
- **E3 — Motor y fuertes por cuenta**: campos en `cuentas.py`,
  fichas de DeepSeek y Kimi en `engines.json` (de texto, §5), clave
  de motor por cuenta y prioridad de fuertes en el selector de
  skills (con la validación de I3).
- **E4 — Unificación por la principal**: rama de unión, veredictos
  cruzados sin autorrevisión y la aprobación del dueño atada al sha
  de unión (B6), con el informe en la sala.

## 11. bis — Revisión de Opus 5.5 (2026-11-16): correcciones aplicadas

Revisión completa guardada en el historial del proyecto. Resumen de
lo aplicado (todo está en el cuerpo, en la sección citada):

- **B1** Dos fuentes de verdad → autoridad única en `encargos.json`
  con bloqueo y revisión optimista; la sala es vista posterior e
  idempotente, escrita bajo el mismo bloqueo; lector tolerante (§3).
- **B2** Doble planificadora / doble arranque → rol y `epoca` fijados
  por encargo en el archivo compartido; resolución y arranque por
  CAS `(revision, epoca)` con marcador previo a `relevo.asignar`;
  «empezar ya» compite por el mismo CAS (§4.1, §4.2, §4.3).
- **B3** Mensaje del dueño duplicable y falsificable → solo la UI
  receptora crea el encargo, con marcador previo; efectos solo con
  firma HMAC del dueño, fail-closed; `autor` lo pone el programa;
  los motores no escriben en la carpeta compartida (§3).
- **B4** Bucle de tareas desde la sala → lista cerrada de tipos que
  generan tarea, con presupuesto por raíz e ids idempotentes (§4.2).
- **B5** Una API de chat no ejecuta fases → `capacidades: ["texto"]`
  fail-closed y runner agéntico nombrado como condición para
  ejecutar (§5).
- **B6** La unión crea un sha sin revisar y con autorrevisión →
  rama de unión propia, aprobación HMAC atada al sha de unión (se
  quema si cambia), revisión cruzada o marca `sin revisión
  independiente` (§7).
- **B7** Fórmula con escalas mezcladas ganable declarando 100 →
  términos normalizados con coeficientes publicados, desempate
  determinista y peso efectivo con techo verificable (§4.2).
- **B8** Secretos en la sala → único punto de escritura con
  redacción por patrones y por coincidencia exacta con la bóveda;
  rechazo con sustitución si persiste la coincidencia (§3).
- **I1** Filtro de candidatas (carril + presencia) antes de puntuar
  (§4.2). **I2** La asignación acordada solo fija `asignada_a`;
  cierre por `relevo` y su buzón, ids derivados (§4.2). **I3**
  Fuertes: rechazar al guardar, advertir al cargar, 0 al repartir
  (§6). **I4** Orden por secuencia por escritor, no por hora (§3).
  **I5** Un aviso, una escritura: la sala es el registro canónico
  (§3). **I6** E1 sin lanzamiento de encargos; la puerta se abre en
  E2 con sus defensas (§10). **I7** `tokens_libre` definido como el
  `pct_efectivo` del tablero para (motor actual, cuenta), con foto
  en la resolución y sin repuntuación por cambio de motor (§4.2).
- **Menores**: la `resolucion` nombra los rechazos pisados (§4.2);
  `roles` es solo preferencia y §8 lo dice (§4.1, §8); rotación de
  `sala.jsonl` sin perder estado (§3).
