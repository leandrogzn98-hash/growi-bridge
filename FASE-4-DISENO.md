# Fase 4 — Harness multiagente, relevo por teléfono, recursos por % y modos de presencia

Diseño previo a la implementación, para revisión (Opus 5.5 vía MWAPI) y como
contrato de aceptación de la fase. Sigue el patrón de las Fases 1 a 3:
módulos puros con lógica testeable + cableado fino en el monolito. Rama:
`fase-4-harness-relevo`.

Piezas nuevas: `relevo.py` (recepción, división, entrega y cierre de
encargos), `supervision.py` (vigilancia de las N cuentas, duración máxima,
cierre de encargos), `recursos.py` (detección de hardware, % por modo,
traducción a límites y medición), `presencia.py` (señales, máquina de
modos y override) y `avisos.py` (avisos básicos con destinos enchufables).
Los cinco son archivos LF nuevos. `harness.py` y `permission-layer.py`
ganan la cuenta como parámetro (compatible hacia atrás) y el monolito solo
gana cableado fino, conservando su CRLF.

Esta fase cierra además las tres integraciones diferidas de las fases
anteriores: el modo dual contra la cola real (Fase 1), la cuenta de cada
tarea en la capa de permisos desde harness y runner (Fase 1) y quién fija
`GROWI_CUENTA_ID` (Fase 2).

## 1. Principios

1. **El encargo nunca se pierde por no saber dividirlo.** Si la
   planificación falla (harness caído, plan inválido, sin smolagents), el
   encargo se convierte en UNA subtarea con el texto íntegro para la
   cuenta que lo recibió. Dividir es una optimización; perder el encargo
   del dueño, jamás.
2. **La identidad la pone el código, nunca el payload.** La raíz de
   correlación, la cuenta de origen y la cuenta asignada a cada subtarea
   las genera el proceso que recibe/crea, desde su cuenta de carril
   (misma regla I7 de la Fase 2 para el origen de las consultas). Un
   `.task.json` que declara otra cosa se revalida al entregar y al
   recoger, y lo que no cuadra se cierra sin correr.
3. **Marcador antes que movimiento, otra vez.** El encargo se registra en
   `encargos.json` antes de entregar la primera subtarea; cada subtarea
   entregada queda anotada antes de escribir su archivo; el protocolo
   dual anota en `dual_en_vuelo` antes de considerar una tarea enviada al
   servidor. Cada paso es idempotente y el barrido de supervisión
   reconcilia lo que un corte dejó a medias (patrón de las Fases 1 a 3).
4. **Fallar hacia no molestar.** Ante la duda, el modo es *presente*
   (menos recursos, cero ventanas) y una tarea dudosa se clasifica como
   prueba física (pregunta antes de actuar). El coste de dudar es
   trabajar más despacio o preguntar de más; nunca interrumpir al dueño
   ni ejecutar dos veces.
5. **El % es relativo siempre.** Ningún límite de recursos lleva una
   cifra absoluta de una máquina concreta: todo es porcentaje de lo
   detectado en ESTA PC al arrancar. Lo que no se puede limitar de
   verdad desde Python se dice (§7.3) y se gobierna por admisión y
   medición, no se finge un tope.
6. **Los avisos no bloquean y el canal no decide.** `avisos.py` guarda
   primero en su registro local y despacha después: un destino caído
   jamás pierde un aviso ni frena una tarea. El transporte concreto
   (WhatsApp u otro) es una decisión del dueño para la Fase 5: aquí solo
   se fija el contrato del adaptador (§10).
7. **Una sola hora para todos.** Todos los procesos viven en la misma
   PC: las marcas que se comparan entre procesos salen de los archivos
   compartidos (sus `*_ts` y su `mtime`, un único reloj: el del sistema
   de archivos). Las duraciones dentro de un proceso se miden con reloj
   monótono. Ningún agente usa «su» hora para juzgar la frescura de otro.

## 2. Identidad de correlación: la raíz del encargo

La cola ya tiene las columnas `raiz` y `tarea_padre` (Fase 2) y las
tareas ya las transportan; lo que faltaba es quién genera la raíz de un
encargo y cómo se hereda. Queda así:

- **Formato:** `enc-<yyyymmdd>-<8 hex de uuid4>` (pasa `_safe_id` del
  monolito). La genera el código del proceso que RECIBE el encargo, en
  el momento de registrarlo, bajo el lock de `encargos.json` con
  comprobación de no existencia (la unicidad entre carriles la da el
  registro compartido, no la suerte del uuid).
- **El payload no manda:** si la tarea que llega por el puente trae
  `raiz`, se ignora y se anota en el historial de la fila («raíz del
  payload descartada»). Lo mismo para `cuenta`: la receptora es la
  cuenta del carril que recoge el encargo.
- **Herencia:** toda subtarea del encargo, toda consulta que una
  subtarea cree, toda ronda de corrección y toda tarea de revisión
  derivada hereda `raiz` intacta y pone `tarea_padre` = id de su
  creadora directa. La raíz NUNCA cambia dentro de la cadena; es el
  invariante que `relevo.entregar` revalida (una subtarea cuya raíz no
  sea la del encargo registrado se rechaza).
- **Ids de subtarea:** `<raiz>-s<n>` (n desde 1, en orden de plan). El
  id de la tarea-encargo original se conserva como `encargos[raiz]
  .tarea_encargo`.
- **Dónde aparece la raíz:** dict de cada tarea, columnas de `cola.db`,
  `encargos.json`, cada aviso (§10) y la auditoría: `registrar()` no
  gana parámetros nuevos — el cableado compone el resumen visible como
  `[<raiz>] <texto>` cuando la acción pertenece a un encargo, igual que
  el harness ya prefija `[<accion>] <resumen>` en sus registros. La
  correlación en auditoría es (cuenta, raíz en el resumen, id de tarea).

## 3. El relevo (`relevo.py`)

### 3.1 Entrada: la tarea `encargo`

Un encargo es una tarea normal con `"tipo": "encargo"` que entra por los
canales de siempre (el puente, con su `canal`: `app`, `whatsapp`, …):

```json
{
  "id": "t-20261116-xxxx",
  "tipo": "encargo",
  "prompt": "hagan X trabajo: parte 1..., parte 2...",
  "canal": "whatsapp",
  "subtareas": null
}
```

- `subtareas` opcional: si el canal ya trae la división hecha (lista con
  el esquema del §3.3), se valida y se usa; si es null, planifica el
  harness (§3.2).
- La recoge el runner del carril donde entró, con la puerta de siempre:
  si la cuenta receptora está restringida o en cuarentena, el encargo
  ESPERA (no se planifica con una cuenta sin tokens: la puerta ya lo
  retiene). Un encargo NO lo ejecuta `process_one` como tarea de motor:
  el bucle lo deriva al manejador de relevo (§12.2).

### 3.2 Planificación: quién divide

1. **Con `subtareas` en el payload:** validación pura del §3.3 y a
   repartir. (El payload propone la división, pero la ASIGNACIÓN de
   cuentas la hace siempre `relevo.py`: un payload que trae `cuenta` en
   una subtarea la ve ignorada, principio 2.)
2. **Texto libre:** se lanza el harness en modo planificador (§4.4) como
   subproceso, con la cuenta receptora en `GROWI_CUENTA_ID`, la raíz en
   `GROWI_RAIZ` y el timeout del encargo (`timeout_min`, por defecto 10
   en encargos). Su respuesta final debe ser SOLO el JSON del plan
   (esquema del §3.3). `relevo.validar_plan` extrae el primer objeto
   JSON del texto y lo valida entero; cualquier desviación = plan
   inválido.
3. **Plan de reserva (principio 1):** harness no disponible, error,
   timeout o plan inválido tras UN reintento → una única subtarea con el
   prompt íntegro del encargo, asignada a la receptora, y el motivo
   anotado en `encargos.json` (`plan: "reserva"`). El aviso
   `division_hecha` lo dice («sin división: lo hace entero la cuenta X»).

### 3.3 Esquema y validación del plan

```json
{
  "subtareas": [
    {"prompt": "...", "motor": "claude", "archivos": ["src/salto.py"],
     "git": "requerido", "timeout_min": 30, "depende_de": [],
     "prueba_fisica": null}
  ]
}
```

Validación pura en `relevo.validar_plan(datos, registro, engines)`:

- Entre 1 y `MAX_SUBTAREAS = 12` subtareas.
- `prompt` no vacío y dentro del límite del puente; `motor`, si viene,
  existe en `engines.json`; `timeout_min` entre 1 y la duración máxima
  del §5.3; `archivos` con el saneado de siempre.
- `depende_de`: índices válidos de la misma lista y grafo acíclico (una
  subtarea no puede depender de sí misma ni en cadena circular).
- `prueba_fisica`: null o el bloque del §9.2.
- Presupuesto del encargo: el número de subtareas ES el compromiso
  inicial (cada ejecución de subtarea consume su cuota por (motor,
  cuenta) con el conteo existente del runner); no se crea un segundo
  libro de gasto: el tope duro es `MAX_SUBTAREAS` y el de consultas por
  raíz de la Fase 2 sigue aplicando a las consultas que nazcan dentro.

### 3.4 Asignación: quién hace cada subtarea

Determinista, con la primitiva de la Fase 2:

- Se procesan las subtareas en orden de plan. Para cada una se llama a
  `tablero.elegir_cuenta(vista, tareas_activas, registro)` con un
  contador de activas SIMULADO que parte de las reales y se incrementa
  con cada asignación de esta división (la segunda subtarea ya «ve» a
  la primera: el reparto equilibra dentro del propio encargo).
- La vista es la del momento de dividir (`pct_puerta`, estados): una
  cuenta restringida o en cuarentena no recibe nada, como manda la
  Fase 2. Si una subtarea trae `motor` y la elegida tiene ese (motor,
  cuenta) sin margen según el tablero, se reintenta la elección
  excluyéndola para esa subtarea.
- Si `elegir_cuenta` devuelve None (nadie está activa), la subtarea
  queda `pendiente_entrega` en el registro con el motivo; el barrido
  del §5 la reintenta en cada latido. El encargo queda abierto y, si la
  espera supera 30 min, sale el aviso `bloqueo_dueno`.
- La asignación queda escrita en `encargos.json` ANTES de entregar
  (principio 3): si el proceso muere a mitad de división, el barrido
  entrega lo asignado-no-entregado sin reasignar (la división no se
  rehace: sería otra división, no la misma). Única excepción
  (corrección I13 del §14 bis): si la cuenta elegida entra en
  cuarentena o se deshabilita DESPUÉS de asignada pero ANTES de que se
  le haya entregado nada de esta raíz, el barrido reasigna sus
  subtareas aún no entregadas (seguro por definición: nada se ejecutó
  todavía). A partir de la primera entrega a esa cuenta, la asignación
  se congela y el remedio es del dueño desde la página Cuentas.

### 3.5 Entrega

`relevo.entregar(subtarea, encargo, destino)` construye el `.task.json`
completo y lo entrega en el `runner-tasks/` del carril destino con el
orden observable de la corrección B8 del §14 bis (nunca «anotada como
entregada pero sin archivo»): primero escribe
`<id>.task.json.tmp` en el destino (un hecho observable y por tanto
recuperable), después anota `entregada` en `encargos.json`, y por
último hace el `os.replace` al nombre final. El barrido reconcilia el
hueco: una subtarea `entregada` sin archivo final ni resultado tras 3
pasadas vuelve a `pendiente_entrega` (seguro: el id es estable y el
destino deduplica por id al registrar en su cola):

- Campos: `id` del §2, `raiz`, `tarea_padre` = id de la tarea-encargo,
  `cuenta` = asignada (la pone relevo, no se negocia), `lane` = carril
  de la asignada, `canal` heredado del encargo, `motor`, `timeout_min`,
  y el `prompt` con cabecera de contexto (precedente: la cabecera de
  continuación del traspaso, Fase 3 I8):
  `[Encargo <raiz> · parte <n> de <N> · encargo del dueño: «<resumen>»]`
  seguida del prompt propio de la subtarea.
- **Carril B sin contexto git:** se aplica la misma regla que ya usa la
  consulta de la Fase 2 para pasar la guardia del carril B: `cwd` = base
  del carril destino y `archivos` derivados a su carpeta de encargos.
  Con contexto git manda la preparación `f3` de la Fase 3 (el worktree
  cuenta como carpeta propia).
- **Directorio destino inexistente** (ese carril no está instalado): la
  subtarea queda `pendiente_entrega` con motivo explícito; nada de
  crear rutas en silencio donde nadie mira (regla de
  `consulta.entregar`).
- **Revalidación al recoger (carril destino):** la puerta del runner
  gana una regla (§12.2): una tarea con `cuenta` distinta de la cuenta
  de este carril se cierra sin correr (extiende a todas las tareas la
  regla que la Fase 2 aplicó a las consultas). Las tareas sin `cuenta`
  (las de siempre) no se tocan. El cierre no es un aviso suelto
  (corrección B2 del §14 bis): el carril que cierra escribe el
  resultado con `motivo_cierre` también en el buzón compartido de
  relevo (§3.7), y el barrido lo lee como subtarea `fallida` a todos
  los efectos (incluida la cadena de dependencias). Y una sola regla
  para la fila: el runner apunta en SU fila de cola la cuenta de SU
  carril, siempre; la `cuenta` del payload se descarta antes de
  `cola_registrar`, así que esta puerta jamás puede cerrar el propio
  encargo del dueño (§3.1) por una discrepancia de payload.

### 3.6 Registro del encargo (`encargos.json`)

En la carpeta compartida, patrón de siempre (lock + mutex, `revision`,
tmp + `os.replace`):

```json
{
  "version": 1,
  "revision": 0,
  "encargos": {
    "enc-20261116-a1b2c3d4": {
      "tarea_encargo": "t-20261116-xxxx",
      "receptora": "principal",
      "canal": "whatsapp",
      "creado_ts": 1763...,
      "prompt_resumen": "hagan X trabajo…",
      "plan": "harness" | "payload" | "reserva",
      "estado": "abierto",
      "subtareas": {
        "enc-20261116-a1b2c3d4-s1": {
          "cuenta": "principal", "carril": "a",
          "estado": "entregada",
          "depende_de": [],
          "asignada_ts": 1763..., "entregada_ts": 1763...,
          "terminada_ts": null, "resultado": null
        }
      },
      "dividido_ts": 1763..., "cerrado_ts": null
    }
  }
}
```

Estados del encargo: `abierto` (registrado, dividiendo o entregando) →
`trabajando` (todo entregado o en espera de dependencias) → terminales
`terminado` (todas ok), `terminado_con_fallos` (alguna falló, con el
detalle por subtarea) o `bloqueado` (espera al dueño: sin cuentas
activas, dependencias imposibles, dual sin resolver del §6.1). Estados
de subtarea: `asignada` → `pendiente_entrega` | `entregada` →
`terminada` | `fallida` (desde entregada, al ver su resultado).

**Plazo del encargo (corrección I7 del §14 bis):** el registro guarda
`plazo_ts = creado_ts + PLAZO_ENCARGO_S` (defecto 6 h). Vencido el
plazo con el encargo aún abierto, el barrido lo lleva a
`terminado_con_fallos` con el detalle de lo hecho hasta ahí y aviso
`bloqueo_dueno` — sin matar la subtarea que esté en curso (esa termina
o la corta su propio timeout; su resultado tardío se anota pero ya no
reabre el encargo). Sin plazo, 12 subtareas × 120 min serían 24 h de
encargo abierto: el conjunto también necesita un tope, no solo cada
pieza.

### 3.7 Cierre del encargo

Lo hace el barrido de supervisión (§5.2), no el runner que ejecutó la
última subtarea (ese proceso puede ser cualquiera de los dos carriles):

- En cada latido, para cada encargo no terminal: lee el estado de sus
  subtareas del **buzón de relevo compartido**,
  `_token_dir()/relevo-resultados/<raiz>/<id-subtarea>.result.json`
  (corrección B1 del §14 bis: los `runner-results/` de cada carril NO
  son legibles desde el otro carril por construcción, así que no son
  la fuente del cierre). Cada carril, al terminar una subtarea de un
  encargo —ejecutada, cerrada por la puerta o fallida—, escribe su
  resultado TAMBIÉN en ese buzón compartido (además de su buzón de
  siempre, que no cambia). El buzón compartido es la única autoridad
  para el cierre; la fila de cola del carril destino es su fuente
  operativa interna y no se lee desde el otro proceso.
- Entrega las subtareas cuyos `depende_de` ya terminaron en ok (si una
  dependencia falló, la dependiente se cierra como `fallida` con motivo
  «su dependencia <id> falló», sin ejecutarse: ejecutar la parte 2 sin
  la 1 no es el encargo del dueño).
- Al pasar a terminal: escribe `<raiz>.resumen.json` en los
  `runner-results/` del carril ORIGEN (el que recibió el encargo), con
  el resultado por subtarea — el canal que trajo el encargo encuentra
  el cierre donde encuentra cualquier resultado —, emite el aviso
  `encargo_terminado` y registra en auditoría con la cuenta receptora.
  **Atomicidad del cierre (corrección I10 del §14 bis):** el
  `cerrado_ts` se escribe en el MISMO gesto con lock que cambia el
  estado a terminal, y solo el proceso que efectivamente hizo ese
  cambio escribe el resumen y emite el aviso (el otro barrido, al
  releer, ya lo ve terminal y no repite nada): un cierre, un resumen,
  un aviso.

## 4. Harness multiagente (`harness.py`)

El harness actual es un proceso por invocación con estado único
(`harness-state.json`), router por palabras clave y cadenas de motores.
Pasa a N cuentas con cuatro cambios cerrados; su bucle pensar/actuar y
sus herramientas no se tocan.

### 4.1 Estado por ejecución

- La ruta del estado sale del entorno: `GROWI_HARNESS_ESTADO` la fija
  quien lanza el proceso (`<APP_DIR>/harness-state-<raiz>.json` en el
  relevo; `harness-state-<tarea>.json` en lanzamientos sueltos). Sin la
  variable, la ruta de siempre (compatibilidad con el uso manual).
- El estado gana `cuenta`, `raiz`, `tarea_id` y marcas por paso:
  `pasos: [{n, ts, motor, ok}]` (se conservan los últimos 50). Son las
  marcas de tiempo verificables que la supervisión (§5) usa para
  distinguir «trabajando» de «colgado»: un estado cuyo último paso es
  viejo con el proceso vivo es un cuelgue, no una impresión.

### 4.2 La cuenta del harness: quién la fija y cómo se valida

- `GROWI_CUENTA_ID` lo fija SOLO código del programa: el monolito al
  lanzar un harness desde el runner (con `_cuenta_de_este_carril()`) y
  `relevo.py` al lanzar el planificador (con la receptora del encargo).
  Nunca se lee del dict de la tarea ni de un payload.
- El harness la valida al arrancar contra el `accounts.json` de SU
  copia: la cuenta existe, está habilitada y su `carril` coincide con
  el carril de este proceso (`GROWI_BRIDGE_LANE` o el de settings).
  Inválida → no ejecuta nada, escribe el estado en error y sale con
  código 4 (el de fail-closed de permisos). Sin la variable →
  comportamiento histórico (cuenta None, cuota agregada): el uso manual
  de siempre sigue funcionando, pero el runner del sistema multi-cuenta
  siempre la fija (si no puede, es un bug y se registra como tal).

### 4.3 Permisos con cuenta (integración diferida de la Fase 1)

- `permission-layer.py`: `CapaPermisos.__init__` gana `cuenta=None`;
  `verificar_permiso` pasa esa cuenta a `clasificar_tarea(texto,
  cuenta)` (que ya la acepta desde la Fase 1) y `ejecutar_con_permiso`
  y `registrar_bloqueo` la pasan a `registrar(..., cuenta=...)` (que ya
  la acepta). Con `cuenta=None` todo se comporta exactamente como hoy.
- `harness.py`: construye su capa con la cuenta validada del §4.2 y su
  `clasificar()` interno pasa la cuenta al clasificar (hoy llama a
  `clasificar_tarea` sin cuenta: las clases extra denegadas por cuenta
  no se aplicaban en el harness).
- El runner (§6.2) hace lo propio en el monolito.

### 4.4 Modo planificador

- `harness.py --planificar` (con `--sesion`, `GROWI_CUENTA_ID` y
  `GROWI_RAIZ` en el entorno): mismo bucle, prompt de sistema de
  planificación cuya única salida válida es el `final_answer` con el
  JSON del plan del §3.3, `MAX_STEPS_PLAN = 6`. El planificador no
  ejecuta herramientas de escritura: sus motores van con las cadenas de
  siempre pero la capa de permisos le deniega las clases de escritura
  (planificar es leer y pensar; la división la valida `relevo.py` y la
  ejecución es de los runners). **Exención declarada (corrección I12
  del §14 bis):** la escritura del propio estado del harness
  (`harness-state-*.json`) NO pasa por la capa de permisos — es la
  contabilidad del arnés, no trabajo sobre el proyecto, y denegarla
  mataría al planificador en su primer paso —; la exención cubre solo
  ese archivo y la LECTURA de archivos del proyecto que el
  planificador necesite para dividir con criterio. Todo lo demás,
  denegado como queda dicho.
- Si smolagents no está importable o el proceso sale con error, el
  lanzador lo detecta por código de salida y `relevo.py` aplica el plan
  de reserva del §3.2. El planificador es prescindible por diseño.

## 5. Supervisión: ninguna Muse sin vigilancia (`supervision.py`)

### 5.1 Qué vigila y con qué fuentes

La supervisión vive en los procesos de los carriles (no hay un tercer
proceso con lógica: el vigilante del §11 es tonto a propósito) y corre
en cada latido del tablero, como `_f4_latido` tras `_f3_latido`, con las
excepciones tragadas y anotadas (el runner nunca depende de ella).
`supervision.py` es la lógica pura; el monolito inyecta lectores y
efectores. Fuentes, todas con marcas comparables (principio 7):

- `tablero.json`: latido y tarea declarada de cada cuenta.
- `runner-status.json` de cada carril: `last_poll` y `pid` (¿el proceso
  vive y late?).
- `runner-live.json` de cada carril: paso actual de la tarea en curso.
- `harness-state-*.json`: último paso de cada ejecución de harness.
- `cola.db` de cada carril: filas `en_curso` con su `actualizado_ts`.
- `encargos.json` y `dual_en_vuelo` (§6.1): lo que espera cierre.

**Inventario y degradación (corrección I3 del §14 bis):** cada fuente
se usa con su campo concreto, verificado contra el código al
implementar (el «inicio real de la ejecución» es el `inicio_ts` que el
runner anota en el historial al recoger la tarea, no el
`actualizado_ts` que el latido refresca; `last_poll` es el latido del
bucle, que el hilo de pulso mantiene durante un `process_one` largo).
Y la regla que manda sobre todas: **si una fuente falta o no se puede
leer, el barrido NO declara cuelgue ni mata nada por esa fuente** —
«no se sabe» no autoriza un kill; aquí el fail-open es el correcto
porque el daño de un falso positivo (matar trabajo sano) es
irreversible, y el de un falso negativo (detectar tarde) ya lo cubre
el timeout de la propia tarea.

### 5.2 El barrido

En cada pasada, `supervision.barrer(...)`:

1. **Latidos por cuenta:** cuenta con tarea en curso cuyo carril no
   late (`last_poll` viejo > 180 s) y cuyo pid no existe → cuenta
   caída: aviso `cuenta_sin_latido` (nivel acción, una vez por
   episodio). No se recupera nada aquí: la recuperación es del propio
   carril al rearrancar (`cola_recuperar` + barridos de las Fases 2 y
   3, con el vigilante del §11 relanzándolo). La supervisión detecta y
   avisa; no resucita ni duplica.
2. **Duración máxima (§5.3):** tarea `en_curso` que supera su límite →
   se trata como el timeout existente (matar el árbol vía el efector
   del monolito y cerrar/reintentar según la política de la cola). La
   fila manda: primero se marca, después se reencola; nunca al revés.
   Dos candados (corrección B9 del §14 bis): cada carril mata SOLO los
   árboles que él lanzó (la duración del carril B la aplica B; A se
   limita a marcar y avisar si B no responde), y el efector verifica
   identidad antes de matar: el historial guarda `pid` +
   `create_time` (psutil) del proceso raíz y ambos deben coincidir
   con el proceso vivo; si no coinciden, NO se mata y se anota «pid
   reciclado, no se mata» (un pid reutilizado puede ser una app del
   dueño).
3. **Cuelgues de harness:** ejecución cuyo estado no avanza en
   `CUELGUE_HARNESS_S = 600` s con su proceso vivo → se marca
   `atascada` en el historial de su fila y se mata su árbol (con la
   misma verificación de identidad del punto anterior y solo si el
   árbol es de este carril); la tarea sigue la política de reintentos
   de la cola (con `cortes` + 1) o cierra fallida al agotarlos, con
   aviso.
4. **Encargos:** entregas diferidas cuyas dependencias terminaron,
   reintento de `pendiente_entrega`, y cierre de encargos (§3.7).
5. **Dual:** si el vigía está en `reconciliando`, corre la
   reconciliación del §6.1 con los resolver/ejecutar inyectados.
6. **Marca de pasada:** escribe `supervision_ts` en `presencia.json`
   (§8) — es el latido que el vigilante del §11 comprueba para saber
   que la supervisión misma corre.

### 5.3 Duración máxima por tarea (deuda I1 de la Fase 3)

- Ya existe `timeout_min` por tarea (defecto 30, tope 120 en la
  validación del puente) y `process_one` mata el árbol al agotarlo. Lo
  que faltaba era el tope del SISTEMA para lo que el timeout por tarea
  no cubre: alquileres renovados eternamente y ejecuciones de harness
  sin reloj de pared.
- `DURACION_MAX_MIN = 120` (constante de `supervision.py`, alineada con
  `MAX_TIMEOUT_MIN`): ninguna tarea, venga con el `timeout_min` que
  venga, pasa de ahí en una sola ejecución. El barrido la aplica a las
  filas `en_curso` (su `actualizado_ts` no basta: se usa el inicio real
  de la ejecución que el runner anota en el historial al recogerla).
- Consecuencia en alquileres: al morir la ejecución por duración
  máxima, sus alquileres dejan de renovarse (el latido de la Fase 3
  solo renueva tareas vivas de su proceso) y caducan a los 300 s: el
  tope de duración ES el tope de tenencia de alquileres que la Fase 3
  dejó anotado.
- El harness hereda el mismo reloj: el lanzador le pasa
  `GROWI_TIEMPO_MAX_S` = el menor entre el `timeout_min` de su tarea y
  la duración máxima; el bucle lo comprueba en cada paso y cierra con
  error de timeout (el estado queda en `error`, no en «working»
  eterno).

## 6. Integraciones diferidas que se cierran

### 6.1 Modo dual ↔ cola real (diferido de la Fase 1)

El vigía de la Fase 1 decide (servidor/local/reconciliando con
histéresis) pero su `por_confirmar` vive solo en memoria y nadie lo
cruza con la cola. Se cierra así:

**Persistencia.** Tabla nueva en la `cola.db` de cada carril (la cuenta
dual es la de ese carril: la tabla por carril es correcta aquí, a
diferencia de los alquileres de la Fase 3):

```sql
CREATE TABLE IF NOT EXISTS dual_en_vuelo (
  tarea TEXT PRIMARY KEY, cuenta TEXT NOT NULL,
  estado TEXT NOT NULL,  -- por_confirmar | resuelta_dueno
  enviada_ts REAL, resuelta_ts REAL,
  intentos INTEGER NOT NULL DEFAULT 0)
```

Se crea en `cola_init()` con `CREATE TABLE IF NOT EXISTS` (sin tocar
la tabla `tareas` ni su versionado). Al arrancar, el monolito
reconstruye el dict en memoria del vigía desde las filas
`por_confirmar` (la tabla manda; el dict de `dual.py` es su caché) y
cada transición posterior escribe la tabla en el mismo gesto.

**Qué significa «ir al servidor».** El modo servidor de Growi ya existe:
la sesión remota de la cuenta recoge las tareas por el puente y
devuelve sus resultados por el buzón de resultados, como ha trabajado
el programa desde antes de este plan. La Fase 4 no crea un transporte:
le pone encima el protocolo de exactamente-una-vez de la Fase 1.

**Flujo.**

- Vigía en `servidor`: el runner NO ejecuta localmente las tareas
  nuevas de la cuenta dual. **El punto de interceptación es el puente**
  (corrección B3 del §14 bis): cuando la cuenta destino es dual, el
  puente NO entrega la tarea a la sesión remota directamente; la tarea
  entra en la cola del carril y es el runner quien, en un solo gesto y
  en este orden, (1) inserta la fila `por_confirmar` en
  `dual_en_vuelo`, (2) deja la fila de cola como `enviada_servidor` y
  (3) la hace visible para la sesión remota, cuya recogida exige que
  el marcador exista (sin fila en `dual_en_vuelo`, la sesión remota no
  la ve: marcador primero, envío después, sin ventana). Cuando su
  resultado aparece en el buzón, el barrido la confirma
  (`confirmar_hecha_en_servidor` + fila de cola terminada con ese
  resultado, sin ejecutar nada localmente).
- Vigía en `local`: las tareas nunca enviadas se ejecutan en local como
  siempre (no necesitan fila en `dual_en_vuelo`: no hay ambigüedad).
  Las `por_confirmar` NO se ejecutan: la puerta dual (§12.2) las
  retiene en cualquier estado del vigía hasta que la reconciliación
  las resuelva.
- Vigía en `reconciliando`: `VigiaDual.reconciliar(resolver,
  ejecutar_local)` con los inyectados de verdad:
  - `resolver(tarea)` = ¿existe ya un resultado del servidor para ella
    en el buzón? Con margen de gracia: si no existe pero la tarea se
    envió hace menos de `GRACIA_RECONCILIACION_S = 120` s, se espera a
    la siguiente pasada (el resultado puede estar llegando).
  - `True` → hecha en servidor: se adopta el resultado y se cierra la
    fila sin ejecutar.
  - `False` (sin resultado tras la gracia) → `ejecutar_local`: se
    borra la fila de `dual_en_vuelo`, la puerta la deja pasar UNA vez
    con la anotación `dual_resuelta_local` en el historial, y corre en
    local.
  - **Indeterminado** (buzón ilegible, error de lectura): NO se decide.
    La tarea sigue `por_confirmar`, `intentos` + 1. A los 3 intentos o
    30 min en ese estado pasa a `resuelta_dueno`: aviso `bloqueo_dueno`
    y el dueño decide desde la página Cuentas («se hizo en el
    servidor» cierra la fila sin ejecutar; «ejecutarla aquí» la libera
    para el runner). Con duda, jamás se auto-ejecuta: exactamente-una-
    vez manda sobre la prisa.
- Cuenta sin `conexion: "ambas"`: nada de esto existe para ella (ni
  tabla, ni puerta): cero cambio de comportamiento.

### 6.2 La cuenta en permisos desde el runner (diferido de la Fase 1)

- Toda llamada del monolito a `permission-layer.registrar(...)` por el
  ciclo de vida de una tarea pasa `cuenta=` la cuenta DE LA FILA de la
  cola (la que `cola_registrar` ya resolvió: la del payload validado o
  la de este carril), nunca el payload crudo. Las de las Fases 2 y 3
  (consulta, mezcla, traspaso) ya lo hacían; se extiende a bloqueos del
  guardrail y cierres sin correr.
- Cuando el monolito clasifica el prompt de una tarea al validarla,
  pasa la cuenta de este carril a `clasificar_tarea` (las clases extra
  denegadas de ESA cuenta por fin aplican también en el runner, no solo
  en el harness del §4.3).

### 6.3 `GROWI_CUENTA_ID` (diferido de la Fase 2)

Cerrado en el §4.2: lo fija el monolito/`relevo.py`, lo valida el
harness contra el registro, y el runner lo fija también para cualquier
subproceso de motor que consuma cuota por cuenta (el entorno de la
tarea se compone en un solo sitio de `process_one`, desde la fila de la
cola).

## 7. Recursos de la PC por porcentaje (`recursos.py`)

### 7.1 Detección de hardware

`recursos.detectar()` → dict con lo que la máquina tenga, sin inventar
(None honesto donde no se pueda saber):

- **CPU:** núcleos físicos y lógicos y nombre (`psutil.cpu_count` y
  `/proc/cpuinfo` en Linux; en Windows, el registro como ya hace
  `detect_pc_specs()` del monolito, que queda como respaldo).
- **RAM:** total (`psutil.virtual_memory().total`).
- **GPU/VRAM:** `nvidia-smi` (nombre, VRAM total), con la misma
  consulta que la `_gpu_query()` existente; sin NVIDIA → `gpu: None`
  (las GPU de otros fabricantes quedan fuera: se dice, no se estima).
- **Disco:** total y libre del volumen donde viven los worktrees
  (`psutil.disk_usage`).

El resultado se guarda en `recursos.json` (carpeta compartida, patrón
de siempre) con `detectado_ts` y una firma (núcleos + RAM total + VRAM
total + identificador del volumen de los worktrees): al arrancar se
redetecta solo si la firma cambió o el archivo no existe — cambiar la
gráfica no exige reinstalar nada. Si la firma cambia con la app viva,
los límites nuevos aplican a las tareas SIGUIENTES: los scopes y jobs
ya creados no se reescriben a mitad de ejecución (corrección I5 del
§14 bis; el estado dice qué se aplicó a lo que corre, no lo que se
aplicaría ahora). Sin `psutil`, degradación declarada:
`os.cpu_count()`, `shutil.disk_usage` y lo que `nvidia-smi` dé; el
resto a None y el % de ese recurso no se gobierna (solo se mide lo
medible).

### 7.2 Asignación del dueño

En el mismo `recursos.json`, sección `asignacion` que solo escribe la
UI de Opciones:

```json
"asignacion": {
  "ausente":  {"cpu": 100, "ram": 100, "gpu": 100},
  "presente": {"cpu": 50,  "ram": 50,  "gpu": 50}
}
```

- El % es del TOTAL de la máquina y del CONJUNTO del programa (las dos
  cuentas comparten un presupuesto: es la PC la que se reparte). Con
  dos tareas en curso, el gobernador divide el presupuesto vigente
  entre las tareas vivas (a partes iguales; el reparto fino por cuenta
  es deuda anotada, no de esta fase).
- Valores 1–100 validados al guardar; cualquier otra cosa se rechaza
  con el motivo (patrón `guardar_config` del tablero).

### 7.3 Traducción del % a límites reales (con honestidad)

`recursos.limites(specs, asignacion_modo, n_tareas)` → estructura pura
y testeable con lo que hay que aplicar por tarea. Por recurso:

- **CPU, Linux:** con systemd de usuario disponible Y VERIFICADO,
  cada motor/harness se lanza envuelto en `systemd-run --user
  --scope` con `CPUQuota = cpu% × núcleos_lógicos` (el 100 % de
  systemd es UN núcleo: la conversión es parte de la función pura)
  repartido entre tareas. La verificación es una sonda real al
  arrancar (`systemd-run --user --scope -p CPUQuota=50% -- /bin/true`
  capturando código y stderr: sin bus de sesión o sin el controlador
  delegado, la sonda falla) y su resultado queda en
  `recursos-estado.json` como mecanismo efectivo (corrección B10 del
  §14 bis): sin sonda en verde NO se envuelve nada a ciegas — un fallo
  de scope no puede matar el lanzamiento del motor — y se cae a la
  rama sin systemd. Sin systemd: `nice` (10 en presente, 0 en ausente,
  sobre los árboles propios) y, si la medición (§7.4) supera el %
  durante 3 muestras seguidas, duty-cycle por SIGSTOP/SIGCONT en
  ventanas de 100 ms SOLO sobre las hojas de motor (los procesos que
  ejecutan la tarea), jamás sobre el runner, el hilo de pulso ni
  ningún proceso con descriptores sobre la carpeta compartida
  (corrección B11 del §14 bis: parar al runner con un lock tomado
  convertiría el gobierno de CPU en un interbloqueo de los dos
  carriles); si las hojas no se pueden distinguir con fiabilidad, no
  hay duty-cycle: queda nice + admisión, declarado en el estado.
- **CPU, Windows:** prioridad de proceso (BELOW_NORMAL en presente,
  NORMAL en ausente) y Job Object por `ctypes` con control de tasa de
  CPU (`CpuRate = cpu% × 100`, en centésimas de punto porcentual del
  total). Si la creación del job falla, queda solo la prioridad y se
  declara en el estado: «CPU gobernada por prioridad».
- **RAM, Linux:** con systemd, `MemoryMax = RAM_total × ram%`
  (repartido). Sin systemd NO hay tope duro alcanzable desde Python:
  se gobierna por medición — si el RSS del conjunto supera el %
  durante 3 muestras, no arrancan tareas nuevas (la puerta consulta al
  gobernador) y sale aviso; matar una tarea por RAM sigue el camino
  del timeout (con motivo y registro), nunca es un kill silencioso.
- **RAM, Windows:** Job Object con límite de memoria por proceso
  (`ctypes`), con la misma caída honesta a medición si el job falla.
- **GPU (ambas plataformas):** no existe un tope por proceso accesible
  desde Python (`nvidia-smi` mide, no limita; MPS queda fuera). El %
  de GPU gobierna por ADMISIÓN: una tarea de motor local/modelos solo
  arranca si su VRAM estimada (el catálogo ya calcula `vram_need_mib`)
  cabe en el margen: VRAM comprometida + necesidad ≤ gpu% × VRAM
  total; y por medición por proceso (`--query-compute-apps`) para el
  estado. Se documenta como admisión, no como cap. **Sin estimación**
  (motor de API, modelo desconocido, `nvidia-smi` ausente —
  corrección I14 del §14 bis): la admisión no pasa «por defecto»: se
  aplica un suelo declarado del 25 % de la VRAM libre como necesidad
  supuesta, o la tarea espera a modo ausente si ni eso cabe; y el
  estado dice «GPU no gobernada» para esa tarea en vez de dar por
  gobernado lo que no se pudo medir.
- **Disco:** el % es de espacio ocupado por el trabajo de Growi
  (worktrees + resultados + respaldos): medición por barrido de esas
  carpetas y aviso al superar el % del volumen; en presente, `ionice`
  de clase idle para los árboles propios en Linux (en Windows la
  prioridad baja ya arrastra la E/S).
- **Mínimos de cordura:** si `pct × total` deja a un árbol por debajo
  de un suelo operativo (256 MB de RAM, 5 % de un núcleo), manda el
  suelo y queda anotado en el estado («suelo aplicado»): en una PC
  modesta el % no puede estrangular al propio programa.

### 7.4 Medición y gobernador

- El gobernador vive en el hilo de pulso del monolito; la lógica de
  decisión (qué toca hacer con estas mediciones y este presupuesto) es
  pura en `recursos.py` y recibe las mediciones inyectadas.
- Cada 5 s: por cada tarea en curso, su árbol de procesos (el runner
  registra el pid raíz al lanzar; `psutil` suma CPU normalizada a % de
  máquina, RSS y, si aplica, VRAM por proceso). Agregado por cuenta y
  total del programa.
- Escribe `recursos-estado.json` en la **carpeta compartida**, con una
  sección por carril (`carriles: {"a": {...}, "b": {...}}`): cada
  proceso escribe SOLO la suya bajo el lock del archivo (corrección
  B5 del §14 bis: el presupuesto es del conjunto del programa, así
  que el reparto se calcula sobre la SUMA de las tareas vivas de
  ambos carriles; un estado por carril en su APP_DIR haría que cada
  gobernador creyera suyo todo el presupuesto y el % del dueño se
  cumpliera al doble). La pestaña Recursos lee ese archivo
  (presupuesto vigente según el modo, medido por tarea y por cuenta,
  y qué mecanismo gobierna cada recurso). El tablero no lleva esto:
  ya lleva tarea y % de tokens.
- La puerta de admisión: antes de `process_one`, el runner pregunta
  `recursos.hay_margen(estado, motor, modo)` — sin margen de RAM/GPU,
  la tarea espera con motivo en la fila (no es un fallo: es el % del
  dueño mandando). La admisión NUNCA escribe `proximo_intento`
  (corrección B6 del §14 bis: ese campo tiene dueño — la aprobación
  aplazada del §9.3 — y un segundo escritor lo machacaría): la
  retención de admisión vive en un campo aparte de la fila
  (`bloqueo_admision_ts`, hasta cuándo no reintentar) que la puerta
  consulta antes de recoger, sin tocar el reloj de la tarea; si algún
  día hay que escribir `proximo_intento`, será
  `max(existente, ahora + 60)`, jamás una rebaja.

### 7.5 El mismo % en cualquier PC

Los límites salen SOLO de `specs × %`: la misma configuración en el
Xeon del dueño (28 hilos, 32 GB, 8 GB de VRAM) y en una PC modesta
produce límites proporcionales sin tocar una cifra. Para probarlo sin
otra máquina, `recursos.detectar` acepta specs inyectadas y el entorno
de pruebas puede fijar `GROWI_RECURSOS_SPECS=<ruta json>` SOLO con
`GROWI_PRUEBAS=1` en el entorno (una costura de prueba, no una opción
de usuario: sin la variable de pruebas se ignora en silencio).

## 8. Modos de presencia (`presencia.py`)

### 8.1 Señales (con sus falsos positivos declarados)

Adaptadores por plataforma que devuelven datos crudos; la evaluación es
pura sobre esos datos:

- **`idle_s`** (segundos sin teclado/ratón): Windows,
  `GetLastInputInfo` por `ctypes`. Linux X11: `XScreenSaverQueryInfo`
  está en **`libXss.so.1`** (no en libX11: corrección I2 del §14 bis),
  comprobando antes `XScreenSaverQueryExtension` y reservando la
  estructura `XScreenSaverInfo` por `ctypes` (o `xprintidle` si está).
  **Wayland: no hay API estándar accesible** — el `IdleHint` de logind
  no es un sustituto (suele ser `false` permanente salvo configuración
  de `IdleAction`): se lee si está pero se trata como señal débil más,
  y su ausencia deja la señal desconocida. Falso positivo clásico: ver
  una película da idle enorme sin estar ausente → el idle SOLO nunca
  decide (ver §8.2).
- **`pantalla_completa`**: Windows, `SHQueryUserNotificationState`
  (D3D a pantalla completa o modo presentación). Linux X11: ventana
  activa con `_NET_WM_STATE_FULLSCREEN`. Wayland: desconocido.
- **`sesion_bloqueada`**: Windows, escritorio de entrada no abrible;
  Linux, `LockedHint` de logind.
- **`proceso_absorbente`**: algún proceso de la lista configurable
  (juegos y reproductores: steam, vlc, mpv, kodi, …) en ejecución.
  Señal débil: tener VLC abierto no es estar viendo nada; solo suma
  combinada (§8.2).
- **`gpu_ajena_cargada`**: uso de GPU > 80 % sostenido por procesos que
  no son de Growi. Débil (un render del dueño también la dispara, y
  eso ES estar presente trabajando: suma a presente, nunca a ausente).

### 8.2 La máquina de modos

`presencia.evaluar(senales, config)` → `presente` | `ausente`:

- **Presente** si: hay pantalla completa, o la sesión está desbloqueada
  y hay proceso absorbente con fullscreen o con idle < 3600 s, o
  idle < `idle_presente_s` (120 s), o gpu ajena cargada con idle
  < 3600 s.
- **Ausente** SOLO si todo esto a la vez: idle > `idle_ausencia_s`
  (900 s), sin pantalla completa, sin proceso absorbente, y (sesión
  bloqueada o idle > 3600 s). **Excepción (corrección I1 del §14
  bis):** `sesion_bloqueada = true` sin ninguna señal positiva de
  presencia basta para ausente (con la misma histéresis), sin exigir
  el idle: en Wayland no hay API de idle pero `LockedHint` sí existe,
  y una sesión bloqueada es evidencia más fuerte que la inactividad —
  sin esta excepción, el presupuesto «ausente» sería inalcanzable en
  Wayland y la PC bloqueada toda la noche trabajaría siempre al % de
  presente.
- **Cualquier otro caso → presente** (señales desconocidas, Wayland sin
  datos, error de un adaptador): principio 4.
- **Histéresis:** entrar en ausente exige 3 evaluaciones seguidas en
  ausente (una cada 30 s, desde el latido); volver a presente es
  inmediato con una sola. Nadie quiere que la PC «parpadee» de modo
  mientras juega.
- El estado vive en `presencia.json` (compartido): `modo` efectivo,
  `desde_ts`, la última evaluación con las señales que la decidieron
  (para que la UI diga POR QUÉ está en ese modo) y `supervision_ts`
  del §5.2.

### 8.3 Override manual

- `presencia.json` gana `override: null | "presente" | "ausente"` con
  `override_ts` y `override_hasta_ts` opcional. **El override manda
  siempre** mientras viva: la máquina ni se evalúa para el modo
  efectivo (sí se sigue registrando lo que habría dicho, para que el
  dueño vea si el automático coincide).
- Lo pone y lo quita el dueño desde Opciones (o forzando el modo desde
  la bandeja). Sin `hasta`, dura hasta que el dueño lo quite; con
  `hasta`, al caducar vuelve el automático y se anota.
- Todo cambio de modo (automático, override, caducidad) se registra en
  el log y en el historial corto de `presencia.json`. No va a la
  auditoría por cuenta: no es una acción de ninguna cuenta Muse.

### 8.4 Qué cambia con el modo (exactamente)

**En presente:**

- Presupuesto de recursos «presente» (§7.2).
- **Cero ventanas sorpresa, por construcción:** (i) `toast()` no
  muestra nada: el aviso va al contador silencioso de la bandeja y al
  registro de avisos; (ii) las notificaciones de la bandeja quedan
  desactivadas; (iii) ningún hilo de fondo puede levantar la ventana:
  toda llamada que muestra o enfoca ventana pasa por el punto único
  `_f4_ventana_ok()` del monolito, que en presente devuelve False
  salvo que la acción nazca de un gesto del dueño (clic en bandeja,
  atajo, clic en la propia ventana); (iv) los subprocesos ya nacen sin
  ventana (bandera existente en Windows; en Linux sin terminal por
  construcción); (v) las pruebas físicas no arrancan (§9).
- El relevo y las tareas siguen trabajando: son archivos y procesos
  sin ventana, segundo plano de verdad.

**En ausente:**

- Presupuesto «ausente» (hasta el 100 % si el dueño lo dejó así).
- Toasts y avisos por el destino local, normales.
- Las tareas pueden abrir las ventanas de SU trabajo (probar el juego
  es una prueba física, §9): Growi sigue sin levantar SU ventana por
  iniciativa propia.

## 9. Pruebas físicas con aviso previo

### 9.1 Qué es una prueba física

Trabajo que toca la máquina de verdad y no puede hacerse en silencio:
medir el consumo y el rendimiento de todo el equipo (CPU, RAM, GPU,
disco), ejecutar el proyecto para verificar errores, abrir ventanas del
programa probado. En modo presente no arranca sola, nunca.

### 9.2 Clasificación

- **Declarada (la vía normal):** la tarea nace con
  `"tipo": "prueba_fisica"` y su bloque:
  ```json
  "prueba": {"clase": "medicion" | "ejecutar_proyecto" | "abrir_programa",
             "detalle": "qué va a hacer, en palabras del dueño",
             "duracion_est_min": 15,
             "impacto": "qué notará el dueño si está delante"}
  ```
  La pone quien crea la tarea (la Muse que la propone o el dueño).
- **Red de seguridad:** al registrar una tarea SIN la marca, un
  clasificador por patrones del monolito (mismo espíritu que el de
  riesgos: «medir el rendimiento de todo», «benchmark», «consumo del
  equipo», «abrir el juego para probar»…) la marca como prueba física
  con clase deducida y `duracion_est_min` por defecto de 15, anotado
  en el historial de la fila. Fallar hacia preguntar (principio 4):
  una falsa alarma solo cuesta una pregunta; una prueba sin avisar
  cuesta la confianza.

### 9.3 En modo presente: el circuito de aprobación con aplazamiento

La prueba recogida en presente NO se ejecuta: va a `WAITING` con un
pedido del circuito de aprobaciones existente (`aprobaciones` +
`decidir_aprobacion`), con estas particularidades:

- **El permiso es de un solo uso y se consume al recoger** (corrección
  B7 del §14 bis): la puerta, antes de mandar a espera, consulta la
  tabla `aprobaciones` por esta tarea — si ya hay una fila `aprobada`
  vigente para ella (de una vuelta anterior), la prueba NO vuelve a
  pedir permiso: se recoge y, en el mismo gesto y antes de
  `process_one`, la aprobación se marca consumida (no vale para un
  segundo arranque). Sin este consumo, aprobar en presente sería un
  bucle: la tarea vuelve a la cola, la puerta la ve «prueba física en
  presente» otra vez y el pedido reaparece para siempre.

- El pedido lleva nivel `R2` (existe en la tabla de riesgos y tiene su
  vencimiento) y el motivo compuesto: «PRUEBA FÍSICA — <detalle>.
  Duración estimada: <n> min. Impacto: <impacto>». El archivo
  `.pedido.json` gana el bloque `prueba` íntegro para que cualquier
  canal lo muestre tal cual.
- Aviso `prueba_fisica_pendiente` (nivel acción) por `avisos.py` al
  crear el pedido: bandeja (silencioso en presente) + registro +
  canales que la Fase 5 conecte.
- **Decisiones del dueño** (la única entrada sigue siendo
  `decidir_aprobacion`):
  - `aprobar` = «de una vez»: como hoy, la tarea vuelve a la cola y
    arranca en la siguiente vuelta.
  - `aplazar` con `minutos` (1–1440) = «espera X tiempo»: **es una
    aprobación programada, no otra pregunta.** La fila de aprobación
    queda `aprobada` con resultado «aprobada, aplazada <n> min:
    arranca a las <hora>»; el archivo vuelve a la cola y su fila gana
    `proximo_intento = ahora + n×60` — la maquinaria existente
    (`cola_en_espera`) lo retiene y el runner lo recoge cuando vence,
    ni un segundo antes. No se vuelve a preguntar.
  - `rechazar`: como hoy, no se hace nada y queda el resultado.
  - **Sin respuesta** al vencer el pedido: como hoy, pasa a
    `necesita_decision` SIN ejecutarse. En presente, el silencio nunca
    es un sí.
- Si el modo cambia mientras la prueba espera su hora (aprobada y
  aplazada), la hora manda: la aprobación ya existe. Si cambia a
  presente con la prueba EN CURSO, la prueba termina (no se mata un
  benchmark a medias por un cambio de modo) y queda anotado.

### 9.4 En modo ausente

La puerta la deja pasar sin aprobación (el plan: dentro del encargo,
avisando). Antes de ejecutarla sale el aviso `prueba_fisica_inicio`
(qué, duración estimada) y su resultado incorpora la foto de recursos
del periodo (de `recursos-estado.json`) cuando la clase es `medicion`:
el dueño se entera al terminar, con los números.

## 10. Avisos básicos (`avisos.py`)

### 10.1 Qué se avisa

Tipos de esta fase (los básicos que el plan adelanta de la Fase 5):
`encargo_recibido`, `division_hecha`, `subtarea_fallida`,
`encargo_terminado`, `bloqueo_dueno`, `prueba_fisica_pendiente`,
`prueba_fisica_inicio`, `cuenta_cuarentena`, `cuenta_sin_latido`,
`dual_sin_resolver`. Cada aviso:

```json
{"id": "av-<uuid8>", "ts": 1763..., "tipo": "encargo_recibido",
 "nivel": "info" | "accion", "cuenta": "principal" | null,
 "raiz": "enc-..." | null, "tarea": "..." | null, "texto": "..."}
```

`nivel: "accion"` = necesita al dueño (una aprobación, un dual sin
resolver, una cuenta caída). El resto es información.

### 10.2 La interfaz: guardar primero, despachar después

- `avisos.emitir(base_dir, tipo, texto, cuenta=None, raiz=None,
  tarea=None, nivel="info")`:
  1. Añade la línea a `avisos.jsonl` (carpeta compartida, append con
     lock de archivo; rotación a 5 MB dejando `.1`). Este registro ES
     el destino mínimo garantizado: consultable desde la UI y por el
     dueño sin ningún canal externo.
  2. Despacha a los destinos activos. Un destino que falla se anota en
     el log y NO reintenta ni bloquea: el aviso ya está guardado.
- **Destinos** (contrato): cualquier objeto con `nombre` y
  `enviar(aviso) -> bool`. Registro por nombre en el módulo y
  activación en `avisos-config.json` (compartido):
  - `registro`: el propio `.jsonl` (siempre activo, no se puede
    apagar).
  - `local`: callback inyectado por el monolito (toast en ausente; en
    presente solo suma al contador silencioso: decidir si molesta es
    de presencia, no del aviso).
  - `canal`: adaptador de canal externo — **en esta fase solo existe
    `CanalNulo`** (disponible() = False, lo anota y no envía): el
    contrato queda fijado (`enviar(aviso)`, `disponible()`,
    `registrar_canal(nombre, fabrica)`) y el transporte concreto
    (WhatsApp no oficial, API oficial o Telegram) lo decide el dueño
    en la Fase 5. Este diseño NO toma esa decisión ni depende de ella:
    los avisos de nivel `accion` son exactamente los que esa fase
    enrutará a aprobaciones por canal.
- **Sin spam:** deduplicación por (tipo, cuenta, raíz, tarea) en
  ventana de 10 min para los avisos que un barrido puede repetir (sin
  latido, sin resolver) — la `cuenta` va en la clave (corrección I8
  del §14 bis: sin ella, dos cuentas caídas en la misma ventana
  colapsaban en un solo aviso y el dueño arreglaba una) —, y los
  cierres agregan contadores en vez de gotear (un `encargo_terminado`
  resume sus subtareas; no hay un aviso por cada subtarea que salió
  bien — `subtarea_fallida` sí sale, una por fallo).

## 11. El vigilante (supervisor muerto)

El modelo de fallos del plan pide que si el supervisor muere, un
vigilante simple lo relance. Diseño:

- `vigilante.py` nuevo, **stdlib pura y sin importar el proyecto** (si
  el proyecto está roto, el vigilante tiene que seguir vivo): cada
  60 s, por cada carril instalado (a y, si existe su copia, b):
  - Lee su `runner-status.json`: si el `pid` no existe y `last_poll`
    tiene más de 180 s → relanza la app de ese carril con su comando
    de arranque de siempre. Tope: 3 relanzamientos por carril y hora
    (contadores en `vigilante-estado.json`, carpeta compartida);
    superado el tope, deja de insistir y escribe UN aviso
    `bloqueo_dueno` en `avisos.jsonl`. El formato del §10.1 es un
    contrato de datos, pero la ESCRITURA no es «directa» (corrección
    I9 del §14 bis): el vigilante lleva duplicado un helper mínimo en
    stdlib pura que hace el mismo append bajo el mismo lock de
    archivo que `avisos.py`, y la rotación la decide solo quien gana
    ese lock comprobando el tamaño — dos escritores sin coordinar
    perderían líneas o romperían la rotación.
  - Si el proceso vive pero `last_poll` supera 300 s, o
    `supervision_ts` (en `presencia.json`) es viejo con la app viva →
    posible cuelgue: aviso `bloqueo_dueno` y NADA más. Matar un
    proceso vivo no es decisión de un vigilante tonto: es del dueño o
    de los timeouts internos (§5).
- Al vigilante lo arranca el sistema operativo (servicio de usuario de
  systemd con `Restart=on-failure` en Linux; tarea programada
  repetitiva en Windows), siguiendo el patrón de instaladores que ya
  usa `supervisor/`. Instancia única con el lock de siempre: la tarea
  repetitiva puede dispararlo diez veces, corre uno.
- Cadena de custodia completa: app → la vigila el vigilante → al
  vigilante lo repone el SO. No hay un tercer nivel: dos vigilantes
  tontos que se vigilan entre sí serían el problema, no la solución.

## 12. Cableado en el monolito (fino) y UI

1. **`cola_init()`:** `CREATE TABLE IF NOT EXISTS dual_en_vuelo`
   (§6.1). Y una migración SEMÁNTICA declarada (corrección B4 del §14
   bis): los estados de fila `enviada_servidor` y `resuelta_dueno`
   entran en la lista explícita de estados que `cola_recuperar()` NO
   reencola al arrancar y que el selector de `process_one` excluye por
   construcción — sin esto, el arranque tras una caída reencolaría en
   local lo que la sesión remota puede estar ejecutando, y la doble
   ejecución llegaría por la puerta de la recuperación, no por la del
   trabajo. Se cubre con la prueba de reinicio del §14.
2. **`runner_loop`:** tras `_puerta_tablero` y antes de
   `_f3_preparar`: (a) puerta dual — tarea de cuenta dual en
   `dual_en_vuelo` como `por_confirmar` → «esperar» siempre; cuenta
   dual con vigía en `servidor` y tarea nueva → se marca
   `enviada_servidor` (fila en `dual_en_vuelo` primero) y no se
   ejecuta; (b) `tipo == "encargo"` → manejador de relevo
   (`_f4_procesar_encargo`: registrar, planificar, asignar, entregar,
   resultado-resumen de la división) en vez de `process_one`;
   (c) `tipo == "prueba_fisica"` (o marcada por el clasificador) en
   modo presente → `_f4_prueba_a_espera` (§9.3); en ausente → aviso de
   inicio y `process_one` normal.
3. **`_tablero_latido`:** tras `_f3_latido`, `_f4_latido`: tick del
   gobernador y `supervision.barrer(...)` con los lectores/efectores
   del monolito. Mismo patrón de fallo: excepción tragada con log, el
   runner sigue. **La presencia NO cuelga de este latido** (corrección
   I4 del §14 bis): su histéresis pide evaluaciones cada 30 s y el
   latido es de 60 s — con el latido, entrar en ausente tardaría el
   doble de lo prometido —, así que la evaluación de presencia corre
   en su propio temporizador de 30 s (un hilo más del patrón del hilo
   de pulso), y `_f4_latido` solo lee el modo ya calculado.
4. **`process_one`:** el entorno de la tarea se compone en un solo
   sitio con `GROWI_CUENTA_ID` (de la fila), `GROWI_RAIZ` y
   `GROWI_TIEMPO_MAX_S`; al lanzar, registra el pid raíz en el mapa del
   gobernador; los registros de auditoría del ciclo de vida pasan la
   cuenta de la fila (§6.2). El entorno se compone por LISTA BLANCA de
   claves (corrección I11 del §14 bis): jamás por copia del dict de la
   tarea — y las costuras de prueba de esta fase (`GROWI_PRUEBAS`,
   `GROWI_RECURSOS_SPECS`, el forzado de la sonda dual) se leen SOLO
   si `GROWI_PRUEBAS=1` está en el entorno del PROCESO PADRE (la app),
   nunca en el del hijo: una tarea no puede activarlas desde su
   payload.
5. **`decidir_aprobacion`:** gana la decisión `aplazar` con `minutos`
   (§9.3), válida para cualquier pedido (nace por las pruebas físicas
   pero el circuito es el de todos). Es un cambio de CONTRATO del
   circuito (corrección I6 del §14 bis), no una línea: toca la
   validación de decisiones, el formato del `.pedido.json` (bloque
   `prueba`), la UI de aprobaciones y la consulta de pedidos vencidos
   (una fila `aprobada` aplazada no es una pendiente vencida: el
   barrido de vencimientos la excluye por estado, y su
   `proximo_intento` en la fila de cola es lo único que la despierta).
6. **UI:**
   - Opciones → sección «Multi-Muse»: % de recursos por modo (§7.2),
     modo de presencia (automático / forzado) con el modo actual y las
     señales que lo deciden, y la lista de avisos recientes (de
     `avisos.jsonl`).
   - Pestaña Recursos: presupuesto vigente vs medido, por tarea y por
     cuenta, y el mecanismo que gobierna cada recurso.
   - Página Cuentas: encargos abiertos con su división y estado por
     subtarea (de `encargos.json`), y los `por_confirmar` del dual con
     los dos botones del dueño del §6.1.
7. **Instaladores:** el vigilante (§11) se añade a los instaladores
   existentes (systemd de usuario / tarea programada), patrón
   `supervisor/`.

## 13. Modelo de fallos

| Fallo | Comportamiento diseñado |
|---|---|
| Proveedor/motor caído | La cadena de motores del harness y la salud de motores del monolito ya degradan; la subtarea afectada reintenta con su política de cola y las demás subtareas del encargo siguen (el fallo de una parte no tumba el encargo: cierra `terminado_con_fallos` con el detalle) |
| Supervisor (barrido) muerto con la app viva | `supervision_ts` viejo → el vigilante avisa (§11); el runner sigue trabajando sin barrido (degradado, no detenido) |
| App de un carril muerta | El vigilante la relanza con tope (§11); al arrancar, `cola_recuperar` y los barridos de las Fases 2–4 dejan todo en exactamente-un-ejecutor |
| Vigilante muerto | Lo repone el temporizador del SO; instancia única por lock |
| Llavero bloqueado / bóveda ilegible | La lectura de secretos degrada como en la Fase 1 (aviso y vía de respaldo); una tarea que necesita el secreto espera con `proximo_intento` y motivo, y sale `bloqueo_dueno` si persiste: jamás se ejecuta «a ciegas» ni se cae el runner |
| Relojes desfasados entre procesos | No hay dos relojes que comparar: misma PC, marcas de los archivos compartidos y su `mtime` (principio 7); las duraciones internas, con reloj monótono |
| Red caída con cuenta dual | §6.1 entero: lo enviado queda `por_confirmar`, lo nuevo corre en local, al volver se reconcilia preguntando por el resultado; con duda, decide el dueño |
| Planificador caído o plan inválido | Plan de reserva (§3.2): el encargo lo hace entero la receptora |
| Carril destino no instalado | Subtarea `pendiente_entrega` con motivo; el encargo queda abierto y avisa a los 30 min |
| Sin systemd / sin Job Object | Degradación declarada de §7.3 (nice/prioridad + medición), visible en `recursos-estado.json`, nunca un tope fingido |
| Wayland sin señales de presencia | Modo presente permanente (principio 4) + override manual del dueño |
| `avisos.jsonl` gigante o destino de avisos caído | Rotación a 5 MB; el despacho nunca bloquea ni pierde el registro (§10.2) |
| Dos barridos a la vez (los dos carriles) | Los archivos compartidos se escriben bajo sus locks de siempre; el barrido es idempotente y el cierre de un encargo lo gana quien primero lo deja terminal bajo el lock de `encargos.json` |

## 14. Aceptación de la fase

Pruebas unitarias (módulos puros, inyecciones como en las fases
anteriores):

- `test_relevo.py`: validación del plan (0 y 13 subtareas rechazadas,
  motor desconocido, dependencia circular, timeout fuera de rango);
  asignación determinista con la vista simulada (equilibrio dentro de
  la división por el contador simulado; cuenta en cuarentena no recibe;
  nadie activa → `pendiente_entrega`); herencia de raíz e ids; entrega
  atómica en dir temporal y dir inexistente → pendiente con motivo;
  plan de reserva ante plan inválido; una subtarea con `cuenta` en el
  payload la ve ignorada y reasignada por el código.
- `test_supervision.py`: cuenta caída detectada por latido+pid;
  duración máxima aplicada a una fila vieja (con reloj inyectado);
  cuelgue de harness por estado sin avance; cierre de encargo con
  todas ok / con una fallida / con dependencia fallida (la dependiente
  no se entrega); entrega diferida al cumplirse la dependencia;
  `supervision_ts` escrito en cada pasada.
- `test_recursos.py`: detección con specs inyectadas (Xeon 28 hilos /
  32 GB / 8 GB VRAM y PC modesta 4 hilos / 8 GB / 2 GB): los límites
  salen proporcionales y SIN ninguna cifra absoluta compartida;
  conversión CPUQuota (× núcleos), MemoryMax, CpuRate de Job Object;
  suelos de cordura aplicados y anotados; `hay_margen` de GPU por
  admisión; asignación inválida rechazada.
- `test_presencia.py`: la tabla de verdad de `evaluar` (película:
  fullscreen + idle enorme → presente; idle largo sin nada → ausente
  solo con las 3 confirmaciones de histéresis; señal desconocida →
  presente; proceso absorbente sin fullscreen e idle medio →
  presente); override que manda sobre la máquina y su caducidad;
  vuelta a presente inmediata.
- `test_avisos.py`: emitir guarda en el `.jsonl` aunque todos los
  destinos fallen; destino que lanza no bloquea ni pierde el aviso;
  deduplicación en ventana; rotación; `CanalNulo` no envía y lo dice.
- `test_harness_multi.py`: cuenta inválida o de otro carril → exit 4
  sin ejecutar; estado por ejecución con pasos y marcas; clasificar y
  registrar reciben la cuenta (las clases extra denegadas de la cuenta
  bloquean en el harness); sin `GROWI_CUENTA_ID`, comportamiento
  histórico.
- `test_dual_cola.py`: marcador antes que envío (si el «envío» falla,
  la fila queda y la tarea no se ejecutó); en local, una
  `por_confirmar` nunca se ejecuta; reconciliación con resultado →
  cerrada sin ejecutar; sin resultado tras la gracia → se ejecuta UNA
  vez en local; indeterminado x3 → `resuelta_dueno` sin ejecutarse;
  reinicio del proceso a mitad: la tabla reconstruye el estado y nadie
  se duplica.
- `test_pruebas_fisicas.py` (lógica del monolito extraída a funciones
  puras donde se pueda): clasificador que marca la no marcada;
  `aplazar 30` deja `proximo_intento = ahora + 1800` y la fila de
  aprobación `aprobada` con su resultado; sin respuesta → vence a
  `necesita_decision` sin ejecutarse.

Pruebas físicas (entorno de dos carriles, app real), mapeadas a la
aceptación del plan:

- **Relevo completo (aceptación del plan):** encargo por el canal de
  entrada a la cuenta A con dos partes claras → se registra, se divide
  entre A y B según el tablero (con B declarando menos %, B recibe la
  parte menor o ninguna si está restringida), ambas ejecutan, el
  resumen `<raiz>.resumen.json` aparece en el buzón de A y la
  auditoría de ambas cuentas muestra el rastro con la misma raíz. Sin
  intervención del dueño tras enviar el encargo.
- **(a) Ausente a pleno:** modo forzado ausente con cpu 100 %: una
  tarea pesada de CPU sostenida usa hasta el máximo configurado
  (medido en `recursos-estado.json`: el agregado del programa se
  acerca al presupuesto sin pasarlo de forma sostenida).
- **(b) Presente con «juego»:** modo forzado presente con cpu 50 % y
  una ventana a pantalla completa en el escritorio de pruebas durante
  10 min con trabajo en curso: cero ventanas nuevas del programa
  (conteo de ventanas antes/después y ningún `toast` visible: los
  avisos quedan en el contador) y consumo dentro del % compartido.
  *La versión literal del plan (una hora con un juego real) queda como
  prueba del dueño en su PC, igual que el checklist de la Fase 0: el
  entorno de Lu no tiene un juego ni una hora de escritorio real.*
- **(c) PC modesta simulada:** con `GROWI_PRUEBAS=1` y specs simuladas
  (4 hilos, 8 GB, 2 GB de VRAM), los límites calculados y aplicados
  son los proporcionales (la mitad de CPU que en (a) con el mismo %,
  MemoryMax de 4 GB al 50 %, admisión de GPU con 2 GB): ningún ajuste
  manual entre una corrida y otra, solo cambian las specs.
- **(d) Prueba física aplazada:** en presente, una prueba física de
  juguete NO arranca sola; el dueño (desde la app de pruebas) responde
  «espera 2 minutos» (versión corta de los 30 del plan; la unitaria
  cubre los 30 con reloj falso) → no hay ejecución antes de los 2 min
  (ni proceso ni resultado) y SÍ a partir de los 2 min sin volver a
  preguntar. Y sin respuesta: vence y no se ejecuta.
- **Dual con encargo real (modelo de fallos):** cuenta en «ambas» con
  la sonda forzada a fallar por la costura de prueba (la sonda del
  monolito honra un archivo de forzado SOLO con `GROWI_PRUEBAS=1`):
  con un encargo en curso se «cae la red» → el vigía pasa a local, lo
  no enviado sigue en local, lo enviado queda `por_confirmar` y no se
  duplica; «vuelve la red» → reconciliación con el resultado que el
  lado servidor dejó en el buzón: cada tarea se ejecutó exactamente
  una vez, verificado con el contador que la tarea de juguete
  incrementa en su resultado (patrón de la Fase 3).

Fallos inyectados:

- Matar el proceso del carril B a mitad de un encargo dividido: el
  vigilante lo relanza (dentro de su tope), su subtarea se recupera
  una sola vez y el encargo cierra con el detalle real.
- Matar el planificador a mitad de planificar: plan de reserva y el
  encargo sigue.
- `encargos.json` corrupto: se trata como los demás registros
  compartidos (vacío con aviso, los encargos en vuelo se reconcilian
  desde las filas de cola y los resultados, nadie se duplica porque
  las subtareas ya entregadas llevan su raíz).
- Bóveda bloqueada simulada (el almacén devuelve error): la tarea que
  necesita el secreto espera con motivo y el runner sigue con las
  demás.
- Gobernador sin systemd (PATH sin `systemd-run`): la traducción cae a
  nice + medición y `recursos-estado.json` lo declara.

## 14 bis. Correcciones de la revisión de Opus 5.5 (aplicadas)

Revisión recibida el 2026-11-16 (11 bloqueantes, 14 importantes).
Decisiones resultantes, que mandan sobre el texto anterior donde
choquen; el cuerpo del diseño ya está ajustado en los puntos que se
citan.

- **B1 — El cierre del encargo lee un buzón compartido de relevo, no
  los `runner-results/` del otro carril.** Esos buzones son de cada
  instalación y no son legibles cruzados por construcción (la Fase 3
  ya lo aprendió con el traspaso). Cada carril escribe el resultado de
  las subtareas de encargo TAMBIÉN en
  `_token_dir()/relevo-resultados/<raiz>/<subtarea>.result.json`, y
  ese buzón compartido es la única autoridad del cierre; la fila de
  cola del destino es interna de su proceso (§3.7).
- **B2 — Una sola regla para la cuenta de la fila, y el cierre por
  puerta alimenta el encargo.** El runner apunta en su fila la cuenta
  de SU carril siempre, y la del payload se descarta antes de
  `cola_registrar` (sin esto, la puerta nueva podría cerrar el propio
  encargo del dueño). El cierre por «cuenta distinta» escribe su
  resultado con `motivo_cierre` en el buzón compartido, y el barrido
  lo cuenta como subtarea fallida con su cadena de dependencias
  (§3.5).
- **B3 — El punto de interceptación dual es el puente, y el envío va
  tras el marcador.** Con cuenta dual, el puente no entrega a la
  sesión remota: la tarea entra en cola y el runner inserta
  `por_confirmar`, marca `enviada_servidor` y solo entonces la hace
  visible para la sesión remota, cuya recogida exige que el marcador
  exista. Sin esto, el «marcador antes que movimiento» protegía
  contra una duplicación que ya había ocurrido aguas arriba (§6.1).
- **B4 — `enviada_servidor` y `resuelta_dueno` son estados que la
  recuperación no toca.** Entran en la lista explícita de exclusiones
  de `cola_recuperar()` y del selector de `process_one`, declarado
  como migración semántica en el §12.1 y cubierto con prueba de
  reinicio: reencolar al arrancar lo que el servidor puede estar
  ejecutando sería la doble ejecución más frecuente de todas.
- **B5 — El estado de recursos es compartido y por secciones.** El
  presupuesto es del conjunto del programa: `recursos-estado.json`
  vive en la carpeta compartida con una sección por carril que cada
  proceso escribe bajo lock, y el reparto se calcula sobre la suma de
  tareas vivas de ambos. Con un estado por carril, cada gobernador se
  quedaría el presupuesto entero y el % del dueño se cumpliría al
  doble (§7.4).
- **B6 — La admisión no escribe `proximo_intento`.** Ese campo es el
  reloj de la aprobación aplazada (§9.3); la retención de admisión
  vive en `bloqueo_admision_ts`, un campo aparte que la puerta
  consulta sin tocar el reloj de la tarea. Si algún día hay que
  escribirlo: `max(existente, ahora + 60)`, nunca una rebaja (§7.4).
- **B7 — El permiso de prueba física es de un solo uso y se consume
  al recoger.** La puerta consulta `aprobaciones` por la tarea: si ya
  hay una aprobación vigente, no vuelve a pedirla (sería un bucle
  infinito de pedidos en modo presente), y la aprobación se marca
  consumida en el mismo gesto, antes de `process_one` (§9.3).
- **B8 — La entrega es observable antes de anotarse, y el hueco se
  reconcilia.** Orden: escribir `<id>.task.json.tmp` en el destino,
  anotar `entregada`, `os.replace` al nombre final. Una `entregada`
  sin archivo ni resultado tras 3 pasadas vuelve a
  `pendiente_entrega`; el destino deduplica por id al registrar
  (§3.5).
- **B9 — Nadie mata por pid sin verificar identidad, y cada carril
  mata solo lo suyo.** El historial guarda `pid` + `create_time`; el
  efector exige que ambos coincidan con el proceso vivo, y si no,
  anota «pid reciclado, no se mata». La duración máxima y los
  cuelgues del carril B los ejecuta B; A marca y avisa (§5.2).
- **B10 — systemd se verifica con una sonda real antes de envolver
  nada.** `systemd-run --user --scope -p CPUQuota=50% -- /bin/true` al
  arrancar, con su resultado como mecanismo efectivo en el estado.
  Sin bus de sesión o sin controlador delegado, la sonda falla y se
  cae a nice/prioridad + medición: envolver a ciegas convertiría un
  problema de infraestructura en motores que no arrancan (§7.3).
- **B11 — El duty-cycle solo toca hojas de motor.** Nunca al runner,
  al hilo de pulso ni a procesos con descriptores sobre la carpeta
  compartida: parar a quien tiene un lock tomado interbloquea a los
  dos carriles y haría caducar alquileres de trabajo vivo. Si las
  hojas no se distinguen con fiabilidad, no hay duty-cycle (§7.3).
- **I1 — Sesión bloqueada basta para ausente.** Sin exigir el idle
  (que en Wayland no existe como API): `LockedHint` sí está, y es
  evidencia más fuerte que la inactividad. Sin esto, el presupuesto
  de ausente sería inalcanzable en Wayland (§8.2).
- **I2 — El idle de X11 vive en `libXss.so.1`.** Con
  `XScreenSaverQueryExtension` comprobada y la estructura
  `XScreenSaverInfo` por `ctypes`; el `IdleHint` de logind se trata
  como señal débil (suele ser `false` permanente), no como sustituto
  (§8.1).
- **I3 — Inventario de fuentes con degradación fail-open.** Cada
  fuente de supervisión se usa con su campo concreto verificado, y
  si falta o no se puede leer, el barrido no declara cuelgue ni mata
  nada por ella: el falso positivo (matar trabajo sano) es
  irreversible; el falso negativo lo cubre el timeout de la tarea
  (§5.1).
- **I4 — La presencia tiene su propio temporizador de 30 s.** La
  histéresis de 3 evaluaciones no puede colgar del latido de 60 s sin
  duplicar el tiempo de entrada en ausente (§12.3).
- **I5 — La redetección no reescribe lo que ya corre.** La firma
  gana el identificador del volumen de worktrees, y unos specs nuevos
  aplican a las tareas siguientes; los scopes/jobs vivos conservan lo
  aplicado, y el estado lo dice (§7.1).
- **I6 — `aplazar` es un cambio de contrato del circuito de
  aprobaciones.** Validación de decisiones, `.pedido.json`, UI y
  consulta de vencidos se tocan a la vez; la fila `aprobada` aplazada
  queda fuera del barrido de vencimientos por estado (§12.5).
- **I7 — El encargo tiene plazo global.** `plazo_ts` (defecto 6 h):
  vencido, el encargo cierra `terminado_con_fallos` con lo hecho,
  sin matar la subtarea en curso (§3.6).
- **I8 — La deduplicación de avisos incluye la cuenta.** (tipo,
  cuenta, raíz, tarea): sin ella, dos cuentas caídas colapsaban en un
  solo aviso (§10.2).
- **I9 — El vigilante escribe avisos con el mismo lock, no «directo».**
  Helper mínimo duplicado en stdlib pura con el append bajo el lock
  de `avisos.py`, y la rotación la decide quien gana el lock (§11).
- **I10 — El cierre de un encargo es atómico con su decisión.**
  `cerrado_ts` se escribe en el mismo gesto con lock que deja el
  encargo terminal, y solo quien hizo ese cambio escribe el resumen y
  emite el aviso: un cierre, un resumen, un aviso (§3.7).
- **I11 — Las costuras de prueba se leen del entorno del padre, y el
  entorno de la tarea es por lista blanca.** Nada de copiar el dict
  de la tarea al entorno del hijo: una tarea no puede activar
  `GROWI_PRUEBAS` ni forzar la sonda dual desde su payload (§12.4).
- **I12 — El estado del harness es contabilidad del arnés, exenta de
  la capa de permisos.** La exención cubre solo
  `harness-state-*.json` y la lectura del proyecto que el planificador
  necesite; denegar la escritura del estado mataría al planificador
  en su primer paso (§4.4).
- **I13 — Reasignación permitida solo antes de la primera entrega a
  esa cuenta.** Si la elegida cae en cuarentena tras asignar pero
  antes de recibir nada de esta raíz, el barrido reasigna lo no
  entregado; tras la primera entrega, se congela y decide el dueño
  (§3.4).
- **I14 — GPU sin estimación no pasa por defecto.** Suelo declarado
  del 25 % de la VRAM libre como necesidad supuesta, o espera a modo
  ausente; y el estado dice «GPU no gobernada» para esa tarea (§7.3).

## 15. Fuera de alcance (explícito)

- El transporte de los avisos y aprobaciones por WhatsApp/Telegram y
  la app Android (Fase 5): aquí solo el contrato del adaptador y el
  `CanalNulo`.
- Contenedores por proyecto (Fase 6) y el intermediario de root (Fase
  6).
- Topes duros de GPU por proceso (no existen desde Python: §7.3) y el
  protocolo de idle de Wayland (sin API estándar: §8.1).
- Límites de cuota distintos por cuenta (deuda desde la Fase 2) y
  reparto fino de recursos POR cuenta (el presupuesto es del programa:
  §7.2).
- División de encargos entre más de un nivel (una subtarea no puede
  ser un encargo: el relevo no es recursivo).
- Que el supervisor externo con LLM (`supervisor/`) actúe: sigue
  siendo de solo lectura; la supervisión de esta fase es la del
  monolito.

## 14 ter. Correcciones de las pruebas físicas (2026-11-16)

Las pruebas físicas con dos carriles reales cazaron cuatro defectos de
integración que las unitarias no podían ver (en todas, la lógica pura
era correcta y fallaba el cableado):

1. **Motores del plan declarado.** El cableado del encargo construía el
   conjunto de motores como `set(load_engines()[0].keys())`: las claves
   del documento `engines.json` entero (`motores`, `router`, …), no los
   ids de motor. Todo plan declarado con motor caía a planificador y de
   ahí a reserva. Corregido: se leen las claves de la sección `motores`.
2. **Reparto dentro de la división.** `elegir_cuenta` ordena por %
   antes que por tareas activas, así que con 80 % frente a 70 % TODAS
   las subtareas iban a la misma cuenta y la otra no trabajaba nunca
   mientras hubiera una brecha, por pequeña que fuera. `relevo.asignar`
   ahora mantiene una vista simulada y descuenta de la cuenta elegida
   una parte igual del encargo (100/n) por subtarea asignada: el
   reparto equilibra dentro del encargo y una cuenta solo se lo queda
   todo si su ventaja supera al propio encargo. La primitiva de la
   Fase 2 no cambia.
3. **cwd derivado del carril B.** La subtarea entregada a B sin
   contexto git deriva cwd = carpeta del carril y archivos en
   `encargos/` (o `consultas/`), pero la regla preexistente de carpetas
   permitidas rechazaba ese cwd y la subtarea moría al instante.
   `validate_task` acepta ahora esa forma derivada exacta (carril B,
   cwd = su carpeta, todos los archivos dentro de `encargos/` o
   `consultas/`): es la carpeta de trabajo interna que el propio
   programa deriva al entregar, con el mismo criterio que la excepción
   de worktrees de la Fase 3. La consulta de la Fase 2 sufría el mismo
   rechazo y queda curada por la misma vía.
4. **El vigilante leía el estado donde no está.** La app escribe
   `runner-status.json` en `share/outbox/` y el vigilante lo buscaba en
   la raíz del carril: sin estado legible no actuaba nunca.
   `_leer_status` busca ahora en `share/outbox/` y, como respaldo, en
   la raíz.

Verificado en físico tras las correcciones: encargo dividido de verdad
(s1 a principal, s2 a segunda, ambas ejecutadas en su carril, buzón
compartido y resumen de cierre devuelto a la receptora); con la sonda
forzada a fallar, ambos vigías pasaron a local y la tarea
`por_confirmar` no se ejecutó en local; al retirar el forzado, el
vigía pasó a reconciliando; la prueba física en presente creó su
pedido R2 y, sin respuesta, venció sin ejecutarse; el override de
presencia mandó sobre las señales y la vuelta a presente fue
inmediata al quitarlo; el vigilante relanzó el carril B matado a los
180 s de poll muerto, dentro de su tope; y con las specs modestas
inyectadas por la costura, la app las adoptó y los límites al 50 %
salieron proporcionales (Xeon: CPUQuota 1400, 16 GB por tarea, 4 GB
de VRAM; modesta: 200, 4 GB, 1 GB) sin tocar ningún ajuste.

Límites honestos que quedan como prueba del dueño en su PC, igual que
el checklist de la Fase 0: la hora con un juego real a pantalla
completa en modo presente (el entorno no tiene gestor de ventanas ni
señal de pantalla completa: el veredicto queda «presente» por la vía
segura) y la medición de saturación de CPU con un motor real en
marcha (en el entorno no hay ningún motor disponible; el gobernador
declara sus mecanismos en `recursos-estado.json`: nice + medición).
