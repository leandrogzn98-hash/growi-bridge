# Fase 2 — Tablero compartido, porcentajes, cuota por cuenta y consulta entre Muses

Diseño previo a la implementación, para revisión (Opus 5.5 vía MWAPI) y como
contrato de aceptación de la fase. Sigue el patrón de la Fase 1: módulos puros
con lógica testeable (`tablero.py`, `consulta.py`) + cableado fino en el
monolito. Rama: `fase-2-tablero-consulta`.

## 1. Principios

1. **El % nunca se inventa.** Cada porcentaje del tablero lleva su fuente:
   `declarado` (lo reportó la propia Muse o el dueño), `estimado` (calculado
   del uso local por cuenta) o `sin_dato` (pct = None). La UI y el reparto
   tratan `sin_dato` como desconocido, no como 100 ni como 0.
2. **El tablero es un archivo compartido, no un servicio.** `tablero.json`
   vive en la carpeta compartida por usuario del programa (`_token_dir()`:
   la misma que guarda el token del plano de control), NO en el `APP_DIR`
   de cada copia: los dos carriles son dos copias del programa y un tablero
   por copia no sería un tablero compartido. Mismo patrón de la Fase 1:
   lock entre procesos, `revision` y escritura atómica (tmp + `os.replace`).
   Los dos carriles y la UI lo leen y escriben; ningún proceso es dueño.
   El libro de consultas (`consultas-uso.json`) vive en la misma carpeta.
   (`accounts.json` se queda en `APP_DIR` como lo dejó la Fase 1: cada
   copia conoce su cuenta de carril desde su registro local.)
3. **El reparto es determinista.** Misma entrada → misma elección, siempre.
   Sin azar: si dos Muses empatan, desempata el nº de tareas activas y luego
   el id de cuenta en orden alfabético.
4. **La cuarentena no pierde tareas.** Una cuenta restringida o en cuarentena
   simplemente no recoge tareas NUEVAS: los archivos quedan en su
   `runner-tasks/` y la cola los sigue mostrando. Nada se borra ni se mueve
   en esta fase (el traspaso llega en la Fase 3).
5. **La consulta tiene topes duros.** Saltos y presupuesto se validan al
   crearla y al continuarla; superarlos es un error explícito, no un aviso.

## 2. El tablero (`tablero.py`)

### 2.1 Formato de `tablero.json`

```json
{
  "version": 1,
  "revision": 0,
  "config": {
    "umbral_cuarentena": 10,
    "margen_salida": 5,
    "frescura_declarado_s": 1800
  },
  "cuentas": {
    "principal": {
      "tarea": "arreglar el salto del personaje",
      "avance": 40,
      "pct_declarado": 62,
      "pct_declarado_ts": 1763...,
      "motor_principal": "claude",
      "estado": "activa",
      "latido_ts": 1763...,
      "actualizado_ts": 1763...
    }
  }
}
```

- `tarea`: texto libre de la tarea en curso (o null). `avance`: 0–100 o null.
- `pct_declarado`: 0–100 o null; con su timestamp. Lo escribe la propia Muse
  (vía la página Cuentas del dueño en esta fase; el canal automático llega con
  el harness de la Fase 4) o el dueño.
- `motor_principal`: motor con el que se estima el % cuando no hay declarado
  fresco (por defecto `claude`).
- `estado`: último estado calculado de la máquina de cuarentena (§4), guardado
  para que la salida con margen sea posible sin recalcular historia.
- El % efectivo NO se guarda: se calcula al leer (§3), porque depende de la
  hora actual y del uso registrado en la cuota.

### 2.2 API

- `cargar(base_dir)` → dict del tablero. Archivo ausente o corrupto →
  tablero vacío con la config por defecto; nunca lanza. (Si el archivo existe
  pero es inválido, el llamador del monolito registra un aviso, igual que en
  la Fase 1 con `accounts.json`.)
- `publicar(base_dir, cuenta, tarea=..., avance=..., pct_declarado=...,
  motor_principal=..., reloj=None)` → actualiza SOLO los campos dados de esa
  cuenta, bajo lock y con control de revisión (relee dentro del lock; la
  escritura es read-modify-write completa del archivo, como `cuentas.py`).
  Actualiza `latido_ts` y `actualizado_ts`. Valida: cuenta con el patrón de
  id de la Fase 1, avance y pct en 0–100.
- `declarar_pct(base_dir, cuenta, pct, reloj=None)` → atajo de `publicar`
  para el % declarado.
- `vista(base_dir, estimador, ahora=None)` → lista de entradas completas por
  cuenta: lo publicado + `pct_efectivo`, `pct_fuente` y `estado` calculados.
  `estimador(cuenta, motor)` es un callback que devuelve el % libre estimado
  (0–100) o None; el monolito lo implementa con la cuota por (motor, cuenta)
  del §5. Inyectarlo mantiene el módulo puro y testeable sin tocar disco de
  cuotas en las pruebas.
- `elegir_cuenta(vista, tareas_activas, registro)` → id de la cuenta que debe
  recibir la próxima tarea, o None. Candidatas: cuentas del registro
  habilitadas, con carril asignado y con estado `activa` en la vista.
  Orden determinista: mayor `pct_efectivo` primero (las `sin_dato` van
  detrás de cualquier % conocido, como grupo, ordenadas entre sí por los
  mismos desempates), luego menos tareas activas (dict `tareas_activas`
  cuenta → nº), luego id ascendente. Es la primitiva que el relevo de la
  Fase 4 usará para repartir; en esta fase queda probada y expuesta, y la
  puerta del runner (§7.2) usa la misma vista para decidir si ESTE carril
  recoge trabajo nuevo.

## 3. El % efectivo

Para cada cuenta, al leer:

1. Si hay `pct_declarado` y su antigüedad ≤ `frescura_declarado_s` →
   `pct_efectivo = pct_declarado`, fuente `declarado`.
2. Si no, se pide al estimador: si devuelve un número →
   `pct_efectivo = estimado`, fuente `estimado`.
3. Si tampoco → `pct_efectivo = None`, fuente `sin_dato`.

Un declarado viejo no se borra: queda en el archivo como último reporte,
pero deja de mandar cuando caduca. La estimación sale de la cuota:
`100 − porcentaje_usado(motor_principal, cuenta)` del `quota-tracker.py`
ampliado en el §5; si ese motor no tiene límite, no hay estimación posible
(None honesto, no 100 inventado).

## 4. Máquina de estados de cuarentena

Estados: `activa`, `restringida`, `cuarentena`. Función pura
`transicion(estado_prev, pct_efectivo, config)`:

- pct es None (`sin_dato`) → se conserva el estado previo (sin dato no se
  castiga ni se libera a nadie).
- pct ≤ 0 → `cuarentena` desde cualquier estado.
- Desde `activa`: pct < `umbral_cuarentena` → `restringida`.
- Desde `restringida`: pct ≥ `umbral_cuarentena + margen_salida` → `activa`;
  si no, sigue `restringida` (el margen evita el parpadeo cuando el % ronda
  el umbral).
- Desde `cuarentena`: pct ≥ `umbral_cuarentena + margen_salida` → `activa`
  (pasando el margen de una vez; no hay salida directa a un estado
  intermedio porque `restringida` con % alto no significa nada), si pct está
  entre 1 y el umbral → `restringida`, si sigue ≤ 0 → `cuarentena`.

Efecto: `restringida` y `cuarentena` no recogen tareas nuevas (§7). La
diferencia es de señalización y de Fase 3: `cuarentena` marca a la cuenta
como agotada (candidata a traspaso cuando exista); `restringida` es solo
precaución.

## 5. Cuota por (motor, cuenta) — `quota-tracker.py`

- `registrar_uso(motor, cantidad=1, tipo="llamada", cuenta=None)` y
  `obtener_estado(motor, cuenta=None)`, `obtener_todos(cuenta=None)`,
  `para_estado(cuenta=None)`.
- Sin `cuenta`, comportamiento y formato EXACTOS de hoy (compatibilidad con
  `harness.py` y con los `quota-uso.json` existentes).
- Con `cuenta` (validada con el patrón de id), la clave de uso en
  `quota-uso.json` es `"<motor>@<cuenta>"`. La config (límites) sigue siendo
  por motor: en esta fase las dos cuentas comparten el límite configurado del
  motor pero cada una lleva SU contador; el % de cada una se calcula contra
  ese límite. (Límites por cuenta: fuera de alcance; se anota como deuda.)
- El estado devuelto con cuenta incluye `"cuenta": <id>`.
- CLI: `--registrar <motor> <cantidad> [--cuenta <id>]` y la salida de estado
  acepta `--cuenta <id>`.
- `harness.py`: si el entorno trae `GROWI_CUENTA_ID`, sus
  `registrar_uso`/`para_estado` pasan esa cuenta; sin la variable, igual que
  hoy. (Que el monolito fije la variable al lanzar el harness por tarea se
  cablea si el punto de lanzamiento es único y barato; si no, queda anotado
  para la Fase 4, donde el harness se rehace multiagente.)

## 6. La consulta (`consulta.py`)

Una consulta es un `.task.json` normal con `"tipo": "consulta"`, que el
carril destino ejecuta con su motor de siempre; la pregunta va en `prompt`.

### 6.1 Forma

```json
{
  "id": "consulta-<raiz>-<n>",
  "tipo": "consulta",
  "lane": "b",
  "motor": "claude",
  "prompt": "¿pregunta concreta?",
  "tarea_padre": "<id de la tarea que pregunta>",
  "raiz": "<id raíz>",
  "consulta": {
    "origen": "principal",
    "destino": "segunda",
    "saltos": 1,
    "presupuesto": 10,
    "gastado": 0
  }
}
```

### 6.2 Reglas (validadas en `crear_consulta`, puras)

- `origen != destino`; ambas cuentas existen y están habilitadas (el módulo
  recibe el registro de cuentas ya cargado; no lee disco por su cuenta).
- `saltos` ≥ 1 y ≤ `MAX_SALTOS = 2`. Una consulta nacida de otra consulta
  suma un salto; al llegar a 2 ya no puede tener hijas.
- `presupuesto`: unidades de cuota que la consulta puede gastar en el motor
  del destino; > 0 y ≤ `TOPE_PRESUPUESTO = 20` (constantes del módulo,
  configurables por parámetro).
- `pregunta` no vacía; `tarea_padre` obligatoria (toda consulta cuelga de
  una tarea: es «por caso», como pidió el dueño, no charla libre).
- El estado del destino en el tablero no es `restringida` ni `cuarentena`:
  consultar a una Muse sin tokens es gastar los propios en nada. Si lo es,
  `crear_consulta` devuelve error con el motivo y NO escribe archivo.

### 6.3 Entrega y gasto

- `entregar(task, dir_tareas_destino)` escribe el `.task.json` de forma
  atómica (tmp + `os.replace`) en el `runner-tasks/` del carril destino. Si
  el directorio no existe → error explícito (nada de crearlo en silencio en
  una ruta equivocada: el monolito pasa la ruta ya resuelta de su mapa de
  carriles; si el carril destino no está instalado, la consulta no sale).
- `registrar_gasto(task, tracker, cantidad=1)` suma el gasto a la cuota de
  (motor, cuenta destino) y al campo `gastado` de la consulta; si
  `gastado + cantidad > presupuesto`, no registra y devuelve False: el
  ejecutor debe parar. El cableado del gasto por llamada lo hace el runner
  al recoger y al terminar la consulta (1 unidad por ejecución en esta
  fase; el conteo fino por tokens llega con el harness).
- La respuesta vuelve como el `.result.json` normal del carril destino; el
  carril origen la recoge de su propio buzón de resultados cuando el destino
  la deposita allí (mismo mecanismo de entrega, dirección inversa, hecho por
  el runner del destino al cerrar una tarea de tipo consulta: copia el
  resultado a los `runner-results/` del carril de la cuenta origen). Si el
  carril origen no está instalado, el resultado se queda en el destino y se
  registra el aviso: no se pierde, queda localizable por `tarea_padre`.

## 7. Cableado en el monolito (fino)

1. **cola.db con `cuenta` y `tipo`:** `cola_init()` comprueba
   `PRAGMA table_info(tareas)` y añade las columnas que falten con
   `ALTER TABLE`; fija `PRAGMA user_version = 1` como primer versionado del
   esquema (el inventario de la Fase 0 lo echaba en falta).
   `cola_registrar` guarda `tipo=data.get("tipo")` y
   `cuenta=data.get("cuenta")` o, si falta, la cuenta de este carril.
2. **Puerta del runner:** en `runner_loop`, antes de `process_one`, si el
   candidato no es tarea de ronda y la cuenta de este carril está
   `restringida` o `cuarentena` según el tablero, se salta en esta vuelta
   (el archivo se queda; se registra una vez por cambio de estado, sin
   spamear el log). Las tareas ya en curso terminan.
3. **Latido del tablero:** el runner publica su entrada en cada
   `runner_heartbeat()`: tarea en curso (de `_cola_corriendo`/cola) y, al
   empezar/terminar `process_one`, `tarea` y `avance`. El % declarado no lo
   toca el runner: es de la Muse.
4. **Estimador:** `_tablero_estimador(cuenta, motor)` usa un `QuotaTracker`
   con `obtener_estado(motor, cuenta=cuenta)`: si hay `porcentaje`, el %
   libre estimado es `100 − porcentaje`; si no, None.
5. **UI (página Cuentas):** bajo la lista de cuentas, la vista del tablero:
   por cuenta, tarea actual, avance, % efectivo con su fuente
   («declarado»/«estimado»/«sin dato») y estado con color. Botón
   «Declarar %» para la cuenta seleccionada (campo 0–100) y campo de umbral
   de cuarentena que guarda en la config del tablero. Todo lectura/escritura
   pasa por `tablero.py`; la página no toca el JSON a mano.

## 8. Aceptación de la fase

Pruebas unitarias:
- `test_tablero.py`: publicar/leer con dos cuentas sin pisarse; archivo
  corrupto → tablero vacío; publicaciones concurrentes (hilos y dos
  procesos) sin perder actualizaciones; % efectivo: declarado fresco manda,
  declarado caducado cae a estimado, sin ninguno → `sin_dato`; máquina de
  estados: todas las transiciones del §4 incluido el margen de salida y el
  `sin_dato` que conserva estado; `elegir_cuenta` determinista (mayor %,
  desempates por tareas activas y por id; excluye restringidas/cuarentena y
  cuentas sin carril; None si no hay nadie).
- `test_consulta.py`: topes (saltos 3 rechazado, presupuesto 0 y > tope
  rechazados, origen = destino rechazado, sin tarea_padre rechazado);
  destino en cuarentena → error sin archivo; entrega atómica en un dir
  temporal; dir inexistente → error; gasto que supera el presupuesto no se
  registra.
- `test_quota.py`: con cuenta, dos cuentas del mismo motor llevan contadores
  separados y el % se calcula por cuenta; sin cuenta, el archivo de uso y
  las salidas son idénticos a los de hoy (compatibilidad); reset de periodo
  por cuenta.

Pruebas físicas (entorno de pruebas Linux, app real):
- Arranque real: el tablero se crea, el latido publica la entrada de la
  cuenta del carril y la página Cuentas muestra el % estimado/sin dato sin
  romper nada con una sola cuenta (compatibilidad).
- Declarar 5 % desde la UI → la entrada queda `restringida` y el runner deja
  de recoger una tarea nueva de prueba (el archivo se queda en
  `runner-tasks/`, log con el motivo); declarar 80 % → vuelve a `activa` y
  la tarea se ejecuta.
- Consulta real entre dos procesos: un script hace de carril B usando los
  módulos contra el mismo `base_dir` (así trabajaría el segundo proceso) y
  la app (carril A) crea la consulta; se verifica el archivo en el destino,
  el gasto registrado y el rechazo de una tercera generación (saltos).
- Fallos inyectados: `tablero.json` corrupto con la app en marcha (sigue,
  avisa, el tablero se reconstruye al publicar); matar la app a mitad de una
  publicación (el archivo nunca queda a medias: o la versión anterior o la
  nueva); `quota-uso.json` con formato antiguo (compatibilidad intacta).

## 8 bis. Correcciones de la revisión de Opus 5.5 (aplicadas)

Revisión recibida el 2026-11-16 (5 bloqueantes, 8 importantes; el inicio de
B1 llegó cortado por la salida, pero su corrección venía completa y se
aplicó). Decisiones resultantes, que mandan sobre el texto anterior donde
choquen:

- **B1 — El estado se recalcula en un solo sitio.** `tablero.recalcular()`
  corre bajo el lock, es idempotente y es la única vía que cambia `estado`
  (más el recálculo local de `publicar` cuando entra un % declarado nuevo).
  Guarda `estado` y `estado_ts`. El estimador se llama FUERA del lock y su
  resultado entra como argumento. `vista()` ya no transiciona al leer:
  muestra el estado guardado. Entrada nueva nace en `activa` explícito.
- **B2 — Cuota con doble escritura.** `registrar_uso` con cuenta escribe la
  clave `motor@cuenta` Y la agregada `motor` (los lectores de siempre,
  incluido el harness sin cuenta, siguen viendo el total: sin esto la clave
  vieja se congelaba y el límite quedaba fail-open). Nunca se deriva el
  agregado sumando claves en lectura (duplicaría el histórico). El archivo
  gana una marca `"_v": 1`. El uso sin atribuir (escritores legacy sin
  cuenta) existe: el % estimado por cuenta es una cota inferior y la UI lo
  etiqueta «estimado por uso local», nunca «tokens restantes».
- **B3 — Presupuesto por raíz y tope de hijas.** Libro mayor
  `consultas-uso.json` junto al tablero: gasto acumulado por `raiz`
  (tope `TOPE_RAIZ = 40`) e hijas por `tarea_padre` (tope
  `MAX_HIJAS = 3`), comprobados al crear y al reservar.
- **B4 — Saltos, raíz y presupuesto se derivan del padre.** El llamante no
  los declara: si el padre es una consulta, saltos = padre + 1 y el
  presupuesto del hijo ≤ restante de la raíz; si es una tarea normal,
  saltos = 1 y raíz = el padre.
- **B5 — Reserva antes de ejecutar y caducidad.** `reservar_gasto` anota y
  persiste ANTES de correr la consulta (tracker + libro + el dict que el
  runner reescribe en el archivo); al recoger se relee el `gastado` del
  archivo, no se resetea. Toda consulta nace con `expira_ts` (TTL 1 h): si
  caduca esperando (p. ej. destino restringido), el runner la cierra como
  fallida con resultado, para que el origen no espere para siempre.
- **I1 — Mutex en proceso + lock de archivo** en `tablero.py` (la UI y el
  latido son hilos del mismo proceso). Orden de locks documentado: nunca se
  llama a la cuota con el lock del tablero tomado.
- **I2 — Fuente `declarado_caducado`**: un declarado viejo sin estimación se
  distingue de `sin_dato`; la UI lo muestra como tal y ofrece «Liberar»
  (fuerza `activa`, queda en el log).
- **I3 — La puerta usa el mínimo.** `vista` expone `pct_puerta` =
  min(declarado fresco, estimado) cuando hay ambos; la máquina de estados
  trabaja con `pct_puerta`. La UI muestra declarado y estimado juntos y
  marca divergencias > 25 puntos. Además el declarado caduca por evento:
  sigue fresco mientras la cuenta tenga latido fresco y tarea en curso.
- **I4 — % normalizado a entero** en `pct_efectivo`; intervalos de la
  máquina cerrados con `<=`/`<` explícitos (sin hueco (0, 1)).
- **I5 — Migración de cola.db a prueba de carreras:** cada `ALTER` va con
  captura de `OperationalError` (columna duplicada = ya estaba) y una
  bandera `_COLA_TIENE_CUENTA`: si la migración falla, `cola_registrar`
  encola como siempre sin las columnas nuevas y el arranque lo grita en el
  log (no degrada en silencio ni tumba el arranque).
- **I6 — Sin cambio de esquema:** verificado en código, `accounts.json` de
  la Fase 1 YA trae `carril` por cuenta (`cuentas.cuenta_de_carril`).
- **I7 — `entregar` revalida** la tarea completa (un dict forjado a mano no
  se cuela) y el runner destino revalida al recoger (topes, caducidad,
  reserva). El `origen` de una consulta lo pone el código del proceso que
  la crea desde su cuenta de carril, nunca un dato del payload de una
  tarea. El id ya usa sufijo uuid4.
- **Puerta fail-open:** si el tablero no se puede leer, el runner recoge
  como siempre y avisa; un JSON roto no detiene la producción. El latido
  del tablero se publica solo si algo cambió o cada 30 s, con timeout
  corto y excepción tragada con log: el runner nunca depende del tablero
  para seguir vivo.

## 9. Fuera de alcance (explícito)

- Traspaso de tareas entre cuentas (Fase 3, con el aislamiento de GitHub).
- Límites de cuota distintos por cuenta (deuda anotada en el §5).
- Que la Muse declare su % automáticamente desde su motor (Fase 4,
  harness); en esta fase la declaración es manual desde la UI.
- Mostrar el tablero fuera de la página Cuentas (la app de Android de la
  Fase 5 lo consumirá de `harness-state.json` o del propio tablero).
