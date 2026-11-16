# Fase 3 — Trabajo en GitHub con aislamiento, respaldo triple y traspaso por cuarentena

Diseño previo a la implementación, para revisión (Opus 5.5 vía MWAPI) y como
contrato de aceptación de la fase. Sigue el patrón de las Fases 1 y 2:
módulos puros con lógica testeable + cableado fino en el monolito. Rama:
`fase-3-github-worktrees`.

Piezas nuevas: `git_trabajo.py` (worktrees, ramas, propuestas de mezcla),
`alquileres.py` (leases por proyecto y por archivo), `secretos.py` (escáner
y hook pre-push), `respaldo.py` (respaldo triple y restauración) y
`traspaso.py` (traspaso por cuarentena exactamente-una-vez). Los cinco son
archivos LF nuevos; el monolito solo gana cableado fino y conserva su CRLF.

## 1. Principios

1. **Cada Muse en su espacio, sin pisarse.** Dos cuentas Muse nunca
   comparten directorio de trabajo: cada tarea con repo trabaja en un
   worktree propio sobre una rama propia. La rama es el punto de encuentro
   (propuesta, revisión, mezcla), nunca el directorio.
2. **Lo compartido vive en la carpeta compartida.** Como en la Fase 2,
   todo estado que coordina a los dos carriles vive en `_token_dir()` (la
   carpeta por usuario), NO en el `APP_DIR` de cada copia: `cola.db` es
   por carril y por tanto NO puede guardar los alquileres ni los
   marcadores de traspaso (cada copia vería solo los suyos). Los archivos
   nuevos (`alquileres.json`, `propuestas.json`, `traspasos.json`,
   `proyectos.json`) siguen el patrón ya probado: lock de archivo entre
   procesos + mutex en proceso, `revision`, read-modify-write bajo el lock
   y escritura atómica (tmp + `os.replace`). Ningún proceso es dueño.
3. **Fail-closed en lo que sale o se mezcla; el runner nunca muere por
   esto.** Subir a GitHub y mezclar a la rama principal son acciones hacia
   fuera: ante cualquier duda (escáner que falla, alquiler perdido,
   aprobación ausente) NO se hacen. En cambio, un fallo de estas piezas
   jamás tumba el runner: la tarea queda en cola con el motivo, como ya
   hace la puerta del tablero.
4. **Ningún secreto sale por los caminos de Growi.** Toda subida que
   hace Growi pasa el escaneo del §6, y las Muses ejecutan con un
   entorno git saneado, sin credenciales de escritura (§6.2): su único
   camino de subida es `git_trabajo.subir`. El hook (§6.3) protege
   además al dueño cuando sube a mano desde su terminal; no se promete
   que detenga a una Muse con acceso libre a la red (ver §6.3 y la
   corrección B13 del §11 bis). Los respaldos excluyen la bóveda por
   construcción: el manifiesto solo admite una lista blanca de archivos
   de estado (§7).
5. **Marcador antes que movimiento (exactamente-una-vez).** Igual que la
   reserva de gasto de la Fase 2 (B5) y el `por_confirmar` de la Fase 1:
   toda operación que mueve trabajo entre cuentas escribe primero su
   intención persistente y luego actúa; cada paso es idempotente y un
   barrido de reconciliación al arrancar resuelve lo que un corte dejó a
   medias. Nada se ejecuta dos veces ni se pierde en silencio.
6. **Todo queda en la auditoría por cuenta.** Propuestas, revisiones,
   aprobaciones, mezclas, robos de alquiler por caducidad, traspasos y
   respaldos se registran con `permission-layer.registrar(...,
   cuenta=<la que actúa>)`, cada una en su `audit-log-<cuenta>.json` con
   su cadena y su ancla (Fase 1). La mezcla, además, exige confirmación
   humana por el circuito HMAC ya existente: sin aprobación del dueño no
   hay mezcla, aunque las dos Muses estén de acuerdo.
7. **Compatibilidad hacia atrás.** Una tarea sin repo se ejecuta como hoy.
   Una tarea con repo pero sin marcar `git: "requerido"` degrada a
   ejecutarse en su `cwd` de siempre si git no está o el directorio no es
   un repo (con aviso en el log y en el resultado). Solo
   `git: "requerido"` convierte eso en fallo cerrado.

## 2. Proyectos y registro (`proyectos.json`)

Un «proyecto» es un repositorio Git local. El registro vive en la carpeta
compartida (`_token_dir()/proyectos.json`), gestionado por
`git_trabajo.py`, con lock y revisión como los demás:

```json
{
  "version": 1,
  "revision": 0,
  "proyectos": {
    "<repo_id>": {
      "ruta": "C:\\Users\\forte\\Proyectos\\MiJuego",
      "nombre": "MiJuego",
      "rama_base": "main",
      "mezcladora": null,
      "contenedores": "proyecto",
      "creado": "2026-11-16T..."
    }
  }
}
```

- `repo_id`: primeros 16 hex del SHA-256 de la ruta canónica del repo
  (`Path(ruta).resolve()` normalizado, minúsculas en Windows). Estable
  aunque se registre dos veces; registrar la misma ruta es idempotente.
- `rama_base`: la rama principal del proyecto (por defecto, la que
  reporte `git symbolic-ref refs/remotes/origin/HEAD` o `main` si no hay
  remoto). Es la rama a la que se mezcla; nunca se trabaja directo en
  ella desde un worktree de tarea.
- `mezcladora`: cuenta designada para ejecutar las mezclas aprobadas.
  `null` = la revisora de cada propuesta (decisión del §5). Se puede
  fijar por proyecto desde la UI.
- `contenedores`: decisión del §9 (`"proyecto"` por defecto,
  `"por_cuenta"` como opt-in). En esta fase solo se registra; la
  implementación es de la Fase 6.
- El proyecto se registra automáticamente la primera vez que una tarea
  con repo lo usa, o a mano desde la página Cuentas (§10). Registrar no
  modifica el repo: solo anota su ruta.

## 3. Worktrees y ramas (`git_trabajo.py`)

### 3.1 Convenciones

- **Rama por (cuenta, tarea):** `muse/<cuenta>/<tarea>`, donde `<tarea>`
  es el id de la tarea saneado (los ids ya pasan `_safe_id` en el
  monolito; el módulo reaplica el saneado: minúsculas, `[a-z0-9-]{1,48}`,
  sin `..` ni `/`). Una tarea = una rama; los reintentos de la misma
  tarea reusan su rama (es la misma unidad de trabajo).
- **Worktree por (cuenta, tarea):** directorio HERMANO del repo, nunca
  dentro de su árbol de trabajo, con un nivel por cuenta (sin
  separadores ambiguos en el nombre):

  ```
  <padre-del-repo>/<nombre-repo>.worktrees/<cuenta>/<tarea>/
  ```

  Fuera del repo: jamás aparece en un `git status` del proyecto, no hay
  que tocar el `.gitignore` de nadie y borrarlo no toca el código. Los
  metadatos quedan donde git los pone siempre (`.git/worktrees/…`). Si
  el padre no es escribible o está dentro de otro repo, se usa la
  ubicación alternativa `_token_dir()/worktrees/<repo_id>/<cuenta>/<tarea>/`
  (corrección I13 del §11 bis).
- **Worktree de mezcla:** `<nombre-repo>.worktrees/_mezcla-<cuenta>/`,
  reutilizable, siempre en HEAD separado sobre `origin/<rama_base>` y
  limpio (ver §5; por qué no sobre la rama misma: corrección B7).

### 3.2 API (git se invoca por un ejecutor inyectable)

El módulo no llama a `subprocess` directamente en su lógica: recibe un
`correr_git(args, cwd) -> (rc, stdout, stderr)` (por defecto, el real con
timeout de 60 s y sin shell). Las pruebas unitarias inyectan un git falso
que registra la conversación; las físicas usan git de verdad.

- `es_repo(ruta)` → bool (`rev-parse --is-inside-work-tree`).
- `repo_id_de(ruta)` → id del §2 (resuelve la raíz con
  `rev-parse --show-toplevel`: si el `cwd` de la tarea es una subcarpeta
  del repo, el proyecto es la raíz).
- `registrar_proyecto(ruta, ...)` → entrada del registro (idempotente).
- `preparar_worktree(repo, cuenta, tarea, rama_base, rama=None)` → ruta
  del worktree. La rama es `muse/<cuenta>/<tarea>` por convención,
  pero si viene `rama` explícita (del bloque `traspaso` o de una
  propuesta: la continuidad manda sobre la convención, corrección B6
  del §11 bis) se usa esa. Casos:
  - La rama no existe → `git worktree add -b muse/<cuenta>/<tarea>
    <ruta> <rama_base>`.
  - La rama existe y ya tiene worktree en la ruta esperada → se reusa
    tal cual (reintento de la misma tarea: el estado sucio anterior ES
    el punto de reanudación; se anota en el log si está sucio).
  - La rama existe sin worktree → `git worktree add <ruta> <rama>`
    (reanudar trabajo ya empezado, p. ej. tras un traspaso, §8).
  - La rama está ocupada por un worktree en OTRA ruta → error explícito
    `ErrorGit` (alguien la está usando: probablemente un traspaso a
    medias; lo resuelve el barrido del §8, no la fuerza bruta).
- `estado_worktree(ruta)` → `{sucio: bool, archivos: [..], rama: str}`.
- `liberar_worktree(repo, cuenta, tarea, forzar=False)` → quita el
  worktree del registro de git (`git worktree remove`). Con cambios sin
  confirmar y sin `forzar` → error explícito, nunca se pierde trabajo en
  silencio. La rama NO se borra aquí: la rama es el historial de la
  propuesta.
- `limpieza(repo)` → borra worktrees de tareas terminadas cuya propuesta
  esté `mezclada` o `rechazada` y hayan pasado 7 días (configurable en
  `proyectos.json`: `limpieza_dias`), y las ramas ya mezcladas con el
  mismo criterio. Lo invoca el latido del supervisor una vez al día; cada
  borrado va a la auditoría de la cuenta dueña de la rama. Un worktree
  sucio jamás se limpia automáticamente.

### 3.3 Cómo entra una tarea

El dict de la tarea gana campos opcionales (el monolito los pasa tal
cual; las tareas de siempre no los traen y no cambia nada para ellas):

```json
{
  "cwd": "C:\\Users\\forte\\Proyectos\\MiJuego",
  "git": "requerido",
  "archivos": ["src/salto.py", "src/niveles/nivel2.json"]
}
```

- `cwd` dentro de un repo (o el propio repo) + cuenta de carril →
  el runner, antes de ejecutar, llama a `preparar_worktree` y el `cwd`
  efectivo de la ejecución pasa a ser el worktree. La tarea original no
  se muta en disco: el worktree se anota en la fila de cola
  (`historial`) y en el `.result.json` (`worktree`, `rama`).
- `git` ausente o distinto de `"requerido"` + problema (no hay git, no
  es repo, git falla) → se ejecuta en el `cwd` original con aviso
  (principio 7). Con `"requerido"` → la tarea se cierra como fallida
  con ese motivo, sin ejecutar nada.
- Los `archivos` declarados alimentan los alquileres del §4 (en el
  carril B ya son obligatorios por la guardia existente: allí el
  alquiler por archivo sale gratis).

## 4. Alquileres (`alquileres.py`)

### 4.1 Por qué no en cola.db

`cola.db` es por carril (cada copia del programa tiene la suya en su
`APP_DIR`): una tabla ahí no coordina nada entre los dos procesos. Los
alquileres coordinan a las dos cuentas, así que viven donde vive el
tablero: `alquileres.json` en `_token_dir()`, mismo patrón de lock,
revisión y escritura atómica. La relación con la cola es por referencia:
cada alquiler guarda el id de la tarea, y el monolito consulta la fila
de su cola cuando necesita el resto. Sin cambio de esquema en `cola.db`
(`user_version` se queda en 1).

### 4.2 Formato

```json
{
  "version": 1,
  "revision": 0,
  "alquileres": {
    "<repo_id>|src/salto.py": {
      "tipo": "archivo",
      "repo": "<repo_id>",
      "ruta": "src/salto.py",
      "cuenta": "principal",
      "tarea": "arreglar-salto",
      "desde_ts": 1763...,
      "latido_ts": 1763...,
      "expira_ts": 1763...
    },
    "<repo_id>|*": { "tipo": "proyecto", "...": "..." }
  }
}
```

- Clave: `<repo_id>|<ruta relativa normalizada>` (separadores `/`,
  sin `..`: una ruta que sale del repo se rechaza al pedir el alquiler).
  `"*"` = alquiler de proyecto entero.
- TTL por defecto **300 s** (constante `TTL_DEF_S`, configurable por
  llamada). El runner renueva TODOS los alquileres de su cuenta en cada
  latido (el hilo de pulso de 60 s que ya existe, que no se bloquea con
  `process_one`), no solo los que están a punto de caducar: el margen
  real son varios latidos perdidos, no uno (corrección I1 del §11 bis).
  Una Muse colgada 5 minutos pierde sus alquileres; una pausa breve
  no. Si entre dos latidos propios el reloj saltó más que el TTL
  (suspensión del equipo), el proceso renueva los suyos ANTES de que
  cualquier purga le robe — o le deje robar — alquileres a otro.

### 4.3 API y reglas

- `tomar(base_dir, repo, rutas, cuenta, tarea, ttl_s=TTL_DEF_S)` →
  atómico bajo el lock: primero purga los caducados, luego comprueba
  conflictos y solo entonces escribe TODOS (todo o nada: una tarea no se
  queda con media lista). Conflictos:
  - la misma ruta (o el `*` del repo) la tiene otra cuenta con alquiler
    vivo → conflicto;
  - pedir un archivo cuando otra cuenta tiene el `*` → conflicto;
  - pedir el `*` cuando otra cuenta tiene cualquier archivo → conflicto;
  - la misma cuenta y la misma tarea → renueva (es suyo);
  - la misma cuenta pero OTRA tarea → también conflicto (dos tareas de
    la misma Muse tampoco se pisan: el alquiler es por tarea, no por
    cuenta).
  Devuelve `{"ok": True, "expira_ts": ...}` o
  `{"ok": False, "conflictos": [{ruta, cuenta, tarea, expira_ts}, ...]}`.
- `renovar(base_dir, cuenta, tarea)` → actualiza `latido_ts` y
  `expira_ts` de los alquileres de esa (cuenta, tarea). Si alguno ya no
  es suyo (caducó y lo tomó otra) devuelve `False` y la lista perdida:
  el runner marca la tarea como «perdió el alquiler» y NO la deja
  confirmar ni subir (§6.2); el trabajo local queda en el worktree
  para decisión del dueño, no se borra.
- `soltar(base_dir, cuenta, tarea)` → libera los suyos (al terminar la
  tarea, tras subir o al cerrarla). Soltar lo de otro es imposible por
  la API (cuenta y tarea deben coincidir).
- `vigentes(base_dir, repo=None)` → vista con los alquileres vivos
  (purga perezosa al leer: los caducados no se muestran, se borran en
  la siguiente escritura).
- **Robo por caducidad:** cuando `tomar` ocupa una ruta cuyo alquiler
  estaba caducado, el hecho se devuelve en el resultado
  (`"robados": [{ruta, cuenta_anterior, tarea_anterior}]`) para que el
  monolito lo registre en la auditoría de la cuenta que toma. La cuenta
  desposeída se entera en su siguiente `renovar` (devuelve `False`).
- **Qué hace el runner si no consigue alquiler:** la tarea NO se
  ejecuta y NO gira en bucle: se queda en cola con
  `proximo_intento = expira_ts del conflicto + 5 s` (mecanismo que la
  cola ya tiene) y el motivo «esperando alquiler de <ruta> (cuenta
  <otra>)». Determinista y sin sondeo agresivo.

## 5. Autoridad de mezcla

### 5.1 Actores y flujo

Roles por propuesta: **proponente** (la cuenta que hizo el trabajo en su
rama), **revisora** (la otra cuenta Muse; si hay más de dos cuentas,
`elegir_cuenta` de la Fase 2 entre las activas que no sean la
proponente), **mezcladora** (la designada del proyecto; por defecto la
revisora: ya tiene el contexto y nadie se mezcla su propio trabajo) y
**dueño** (aprueba; su aprobación es condición necesaria siempre).

Flujo (cada transición se escribe en `propuestas.json`, en la carpeta
compartida, con el patrón de siempre, y en la auditoría de quien actúa):

1. `propuesta` — la proponente sube su rama (§6: con escaneo superado)
   y registra la propuesta: `{id, repo, rama, cuenta, tarea, base,
   creada_ts, estado, sha_base}`. El id sale del hash de
   `(repo_id, rama)` — una propuesta por (repo, rama), sin inferir
   nada del nombre de la rama (corrección B6) — y la cuenta dueña
   actual queda guardada en la propia propuesta.
2. `en_revision` — se crea una tarea de tipo **`revision`** para la
   revisora (mismo mecanismo de entrega entre carriles que la consulta
   de la Fase 2): su `prompt` trae la rama, la base y la instrucción de
   revisar el diff; es de solo lectura y NO toma alquileres (ni de
   archivo ni de proyecto: §10.1 la excluye de la toma por defecto).
   Si necesita árbol, usa un worktree en HEAD separado sobre el sha a
   revisar (`git worktree add --detach <ruta> <sha>`): la rama
   propuesta sigue ocupada por el worktree de la proponente y git no
   la deja abrir dos veces (corrección B7). Al emitir el veredicto, la
   propuesta guarda `sha_revisado` (la punta de la rama en ese
   momento) y el veredicto firma ESE sha, no la rama en abstracto
   (corrección B8). Su resultado trae `veredicto`: `ok`, `cambios`
   (con comentarios) o `rechazo` (con motivo).
3. Con `veredicto: cambios` → la propuesta vuelve a la proponente
   (estado `cambios_pedidos`): la misma tarea o una hija corrige en la
   MISMA rama y se vuelve al paso 1 (la propuesta se actualiza, no se
   duplica: una propuesta por (repo, rama)).
4. Con `veredicto: ok` → estado `esperando_dueno`. La mezcla pide
   confirmación humana por el circuito de `permission-layer.py`
   (confirmación HMAC, solo el dueño, con caducidad: el mismo mecanismo
   que las acciones sensibles), y el payload firmado incluye
   `repo|rama|sha_revisado`: la aprobación es de UN commit concreto,
   no de una rama que puede seguir moviéndose (corrección B8). Sin
   confirmación válida y vigente NO hay paso 5, aunque las dos cuentas
   estén de acuerdo. Cualquier push posterior a la rama (detectado por
   el latido comparando `origin/<rama>` con `sha_revisado`) devuelve
   la propuesta a `en_revision` e invalida veredicto y aprobación.
5. `mezclada` — la mezcladora trabaja en el worktree de mezcla en
   **HEAD separado** sobre la base remota actualizada
   (`git worktree add --detach <ruta> origin/<rama_base>` tras
   `fetch`): la `rama_base` local del dueño casi siempre está ocupada
   por su propio árbol y git no permite la misma rama en dos
   worktrees (corrección B7). Allí comprueba que `origin/<rama>`
   sigue en `sha_revisado` y mezcla ESE sha: avance rápido si la base
   es su ancestro; si no, `git merge --no-ff <sha>` con mensaje que
   cita la propuesta y la tarea. Sube con
   `git push origin HEAD:refs/heads/<rama_base>` (con el escaneo del
   §6 sobre el sha resultante), sin `--force` jamás, y marca la
   propuesta `mezclada` con el hash resultante. Si el push se rechaza
   por no ser avance rápido (alguien subió entretanto), vuelve a
   `fetch` y repite el paso una vez; si al repetir hay conflicto, es
   el paso 6. El `main` local del dueño no se toca nunca. **Sin
   remoto:** solo se avanza `rama_base` con `update-ref` si no está
   ocupada en ningún worktree; si lo está, la propuesta queda en
   `mezcla_manual_pendiente` y la mezcla la hace el dueño a mano.
6. **Conflicto:** si el merge da conflicto → `git merge --abort`
   INMEDIATO, estado `conflicto` con la lista de archivos en conflicto,
   y la pelota vuelve a la proponente (ella resuelve en su rama
   mezclando la base o rehaciendo sus cambios; nunca lo resuelve la
   mezcladora, nunca se usa `--force`, nunca se elige «ours/theirs» en
   silencio). La mezcladora no toca el contenido: su trabajo es
   mecánico y queda abortado sin efectos.
7. `rechazada` — por veredicto de rechazo o por el dueño en el paso 4.
   La rama queda (historial); la limpieza del §3.2 la retirará a su
   tiempo.

Casos borde cerrados:

- **El dueño mezcla a mano fuera de Growi:** al detectar que
  `rama_base` avanzó y la rama ya es ancestro, la propuesta pasa a
  `superada` (no es un error; se anota y se cierra). Las mezclas con
  squash o rebase hechas en GitHub no dejan la rama como ancestro: se
  detectan comparando el ÁRBOL de la rama con el de la base tras el
  avance (árboles iguales = el contenido ya entró); si tampoco así se
  detecta, la cierra el dueño desde la UI. Una propuesta con
  `sha_revisado == sha_base` (rama sin commits propios) se rechaza al
  nacer: no hay nada que proponer (corrección I7).
- **Dos propuestas del mismo repo:** se revisan en paralelo, pero las
  mezclas se serializan con una clave de alquiler aparte,
  `<repo_id>|@mezcla`, que solo choca consigo misma (corrección B9):
  la mezcla no toca el worktree de nadie y no debe esperar a que la
  otra Muse termine su tarea, solo a que no haya OTRA mezcla en
  curso. La segunda mezcla recalcula sobre la base ya movida y puede
  acabar en `conflicto` legítimo.
- **Revisora en cuarentena:** la propuesta espera en `propuesta` (no se
  auto-aprueba jamás por ausencia de revisora). El dueño puede asignar
  otra revisora desde la UI o revisar él mismo y registrar el veredicto
  manualmente.
- Nota sobre la revisión sin alquileres: revisar es leer el diff
  (`git diff base...rama`), no editar; por eso la revisora no toma
  alquileres de archivo. Si la revisión quisiera ejecutar el proyecto,
  eso ya es una tarea normal con su worktree y sus alquileres.

### 5.2 Auditoría

Cada transición llama a `registrar(tool="git", prompt=<resumen>,
resultado=<estado nuevo>, accion=<...>, cuenta=<la que actúa>)`:
propone la proponente, el veredicto lo firma la revisora, la aprobación
es del dueño (la confirmación HMAC queda registrada por el propio
circuito de confirmaciones) y la mezcla la registra la mezcladora con
el hash del commit resultante. `verificar_ancla()` sigue detectando
cualquier manipulación posterior de estos registros.

## 6. Subida sin secretos (`secretos.py` + hook)

Doble capa independiente: si una falla o se salta, la otra sigue
cerrando la puerta. Ambas usan el mismo módulo `secretos.py`.

### 6.1 Qué se detecta

**Por contenido** (tabla de patrones del módulo; es un superconjunto de
la tabla `_SECRETO_RES` que el monolito ya usa para las skills — esa
tabla no se toca; la del módulo la incluye y la amplía):

- claves `sk-…` / `sk-ant-…` / `sk-proj-…`, tokens de GitHub
  (`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`), de Slack
  (`xox…`), de Google (`AIza…`), de Tripo (`tsk_`) — las ya existentes;
- claves AWS (`AKIA[0-9A-Z]{16}`), claves privadas (`-----BEGIN …
  PRIVATE KEY-----`), JWT con pinta de credencial (`eyJ…` de 3
  segmentos y ≥ 40 caracteres en asignación), y asignaciones genéricas
  en `.env`/config: `NOMBRE_CLAVE = valor` con nombre que contenga
  `SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|APIKEY|PRIVATE_KEY` y valor de
  ≥ 12 caracteres que no sea un marcador obvio (`...`, `xxx`, `changeme`,
  `${...}`, `<...>`).

**Por nombre de archivo** (lista de bloqueo: no suben NUNCA, contengan
lo que contengan; la comparación es sobre el nombre base en
minúsculas, para que `.ENV` o `Secret.txt` no se cuelen en Windows):
`secret.txt`, `.env` y `.env.*` (salvo `.env.example`/`.env.sample`
si pasan el escaneo de contenido), `credenciales.dpapi.json`,
`audit-log*.json`, `audit-indice*.json`, `*.pem`, `*.key`, `id_rsa*`,
`id_ed25519*`, `*.dpapi.json`, `consultas-uso.json`, `tablero.json`,
`alquileres.json`, `traspasos.json`, `propuestas.json`,
`accounts.json`, `cola.db` y sus `cola.db-wal`/`cola.db-shm`,
`settings.json`, `manifiesto.json`, y cualquier ruta con un componente
`respaldo/`, `respaldo-estado/` o `.growi/` — es decir: ningún archivo
de estado o de credenciales de Growi entra en un repo, aunque alguien
lo copie dentro por error (lista ampliada en la corrección I12).

**Alcance del escaneo: objetos, no diffs** (corrección B11). El
conjunto a escanear es exactamente el que el push va a enviar: los
objetos alcanzables desde el sha a subir que no están en NINGUNA
referencia del remoto (`git rev-list --objects <sha> --not
--remotes=<remoto>`; corrección B10: así una rama nueva no reescanea
todo el historial del proyecto, solo lo que el remoto no tiene). De
cada blob nuevo se lee el contenido ENTERO con `git cat-file --batch`
y se le aplican los patrones, decodificando UTF-8 y, si hay BOM,
UTF-16. Escanear diffs queda prohibido como mecanismo: un
`.gitattributes` con `-diff`/`binary` (que escribe el propio repo),
los commits de mezcla que `log -p` no muestra, los archivos UTF-16 o
un textconv dejarían pasar secretos sin hacer ruido. Reglas duras:

- La lista de nombres se aplica a TODAS las rutas de los árboles
  nuevos, no solo a las modificadas.
- Un blob que supera el tamaño máximo escaneable (16 MB) o que no se
  puede decodificar produce un hallazgo de tipo `no_escaneable`:
  bloquea igual (fail-closed) y solo lo perdona la lista de
  permitidos por huella DEL BLOB (§6.4).
- Si el repo usa Git LFS, la subida se bloquea hasta que el dueño lo
  decida expresamente: los objetos LFS viajan como punteros y su
  contenido real no pasa por este escaneo.

### 6.2 Capa A — chequeo en el código antes de subir

Toda subida que hace Growi pasa por `git_trabajo.subir(repo, rama,
cuenta, tarea)`:

0. **El entorno de las Muses no tiene credenciales de escritura**
   (corrección B13): el runner lanza las tareas con
   `credential.helper=` vacío (vía `GIT_CONFIG_COUNT`/
   `GIT_CONFIG_KEY_0`), `GIT_TERMINAL_PROMPT=0`, sin `SSH_AUTH_SOCK` y
   sin `GH_TOKEN`. La Muse puede hacer todo el git local que quiera,
   pero no puede autenticar un push propio. `subir` inyecta la
   credencial desde la bóveda SOLO para su propio proceso de push.
1. Verifica que la cuenta sigue teniendo sus alquileres (si la tarea
   perdió un alquiler, no sube: §4.3).
2. Fija el sha exacto a subir (`HEAD` de la rama en ese instante) y
   llama a `secretos.escanear_objetos(repo, sha, remoto)` → lista de
   hallazgos `{commit, archivo, linea, tipo, evidencia_redactada}`
   (la evidencia va SIEMPRE redactada, como en el escáner de skills:
   el secreto no aparece ni en logs ni en la auditoría).
3. Con ≥ 1 hallazgo → **no hay push**: la propuesta/tarea queda con el
   motivo y los hallazgos (redactados) en el resultado y en la
   auditoría de la cuenta. Sin excepciones silenciosas.
4. Sin hallazgos → sube EXACTAMENTE el sha escaneado:
   `git push <remoto> <sha>:refs/heads/<rama>`. Si la Muse confirma
   algo más después del escaneo, eso será otro push con su propio
   escaneo: no hay ventana entre escanear y subir (corrección B10).
   Si el propio escáner falla (excepción, git caído a mitad) →
   tampoco hay push: fail-closed.

### 6.3 Capa B — hook `pre-push` en el repo

Para las subidas que NO hace Growi (el dueño desde una terminal en
ese repo): al registrar el proyecto, Growi instala el hook
`pre-push` **donde git lo va a buscar de verdad**:
`git rev-parse --git-path hooks/pre-push`, que respeta
`core.hooksPath` y el directorio común compartido por los worktrees
(corrección B13). El hook es un script fino que invoca el escáner
pasándole por stdin las líneas `<rama local> <sha local> <rama
remota> <sha remoto>` que git entrega, ignora las líneas de borrado
(sha local en ceros) y sale con código ≠ 0 si hay hallazgos (git
aborta el push). Alcance honesto de esta capa: protege al dueño de SUS
errores en su terminal. A la Muse no la detiene un hook (podría usar
`--no-verify` o borrarlo): a ella la detiene la capa A, que es la
única con credenciales (§6.2 paso 0).

- El hook lleva una marca (`# growi-bridge: pre-push v1`) y su
  instalación es idempotente. Llama a una **copia estable** del
  escáner en `_token_dir()/secretos.py` (refrescada al arrancar si su
  hash difiere del de la app) con la ruta absoluta del intérprete
  (`sys.executable`, entre comillas y con barras `/`): mover o
  actualizar una de las dos copias de la app no rompe el hook, y en
  Windows el `sh` de Git no depende de que `python` esté en el PATH
  (corrección I4). El hook de git-lfs, si está, se detecta y se trata
  como el caso `conflicto` de abajo (y el LFS ya bloquea por §6.1).
- **Si ya existe un `pre-push` ajeno, o `core.hooksPath` apunta a una
  carpeta ajena (husky y similares):** Growi NO lo sobrescribe ni lo
  encadena en silencio: el proyecto queda marcado
  `hook: "conflicto"` en `proyectos.json`, la capa B no se instala y la
  UI lo dice con claridad. La capa A sigue protegiendo las subidas de
  Growi. (Decisión cerrada: nunca pisar el hook de otro.)
- El hook es fail-closed ante sus propios errores: si el intérprete no
  está o el módulo falla, sale ≠ 0 y el push no ocurre (con mensaje que
  explica cómo desactivarlo a mano si el dueño lo decide: borrar el
  archivo del hook es un acto manual y visible, no un ajuste oculto).

### 6.4 Falsos positivos y lista de permitidos

Un fixture de prueba con una clave falsa (como el `sk-ant-falso123` de
la autoprueba del propio Growi) no debe bloquear un proyecto para
siempre, pero la salida tampoco puede ser «apagar el escáner» ni un
archivo editable por la propia Muse:

- Los permitidos viven FUERA del repo, en
  `_token_dir()/permitidos-<repo_id>.json` (corrección B12: si
  vivieran en el árbol de trabajo, la Muse podría fabricarse el
  permiso y confirmarlo en el mismo push). Cada entrada:
  `{ruta, huella, tipo, creada_ts, firma}`, donde `huella` es el
  sha256 de la línea exacta con el hallazgo (o del blob entero para
  los `no_escaneable`) y `firma` es el HMAC del dueño sobre
  `repo|ruta|huella|tipo`, producido por el mismo circuito de
  confirmaciones de `permission-layer.py`. El escáner ignora un
  hallazgo solo si existe una entrada con firma VÁLIDA que lo cubre;
  una entrada sin firma o con firma inválida se ignora y el hallazgo
  bloquea (y el intento queda en la auditoría).
- Añadir una entrada es acción del dueño: comando
  `python secretos.py --permitir <repo> <archivo> <linea>`, que pide
  la confirmación humana como cualquier acción sensible, queda
  registrado en su auditoría y la entrada cita el tipo de hallazgo,
  nunca el secreto.
- La lista de bloqueo por NOMBRE (§6.1) no admite permitidos: un
  `secret.txt` no sube aunque el dueño lo liste; para eso está
  renombrarlo fuera del repo. Fail-closed también aquí.

## 7. Respaldo triple (`respaldo.py`)

### 7.1 Qué es «el estado»

Lista blanca cerrada (el manifiesto solo admite estos nombres; cualquier
otro archivo en las carpetas origen se ignora, y la bóveda y los
secretos quedan fuera por construcción):

- De la carpeta compartida (`_token_dir()`): `tablero.json`,
  `consultas-uso.json`, `alquileres.json`, `propuestas.json`,
  `traspasos.json`, `proyectos.json`.
- De cada carril (`_dir_carril(carril)`): `accounts.json` (registro sin
  secretos: los secretos viven en la bóveda, no en el registro),
  `cola.db`, `audit-log.json`, `audit-log-<cuenta>.json` por cuenta,
  `audit-indice.json`, `settings.json`.
- El código NO va en este respaldo: el código es la pata de GitHub.
- **Cómo se copia cada cosa** (corrección B14 e I10): los JSON se leen
  a través del `cargar` de su módulo dueño (con su lock tomado un
  instante), nunca copiando el archivo vivo a ciegas mientras el otro
  carril lo reescribe; y `cola.db` NO se copia como archivo: la
  instantánea se hace con la API de respaldo de SQLite
  (`sqlite3.Connection.backup()`), que produce una base coherente
  aunque el carril esté escribiendo y con el WAL aplicado, y se le
  pasa `PRAGMA integrity_check` antes de admitirla en el manifiesto.
  El hash del manifiesto prueba que la copia es íntegra; el
  `integrity_check` prueba que además es una base válida.
- Antes de crear la instantánea, cada archivo de la lista blanca se
  valida (JSON parseable, base coherente) y se pasa por
  `secretos.escanear`: que `settings.json` «no tiene secretos» es un
  supuesto, no un hecho verificado (I10). Un archivo inválido o con un
  secreto aborta la instantánea con nota en la auditoría: no se
  respalda corrupción ni se multiplica un secreto por tres carpetas.

### 7.2 Las tres patas

1. **PC (vivo + instantáneas):** los archivos vivos son la primera
   copia. Además, `respaldo.py` mantiene instantáneas en
   `_token_dir()/respaldo/<ts>/` con `manifiesto.json`
   (`{ts, archivos: {ruta_relativa: {sha256, bytes}}}`), rotación de
   las últimas **10**, creadas y rotadas bajo un lock propio de
   respaldo (dos procesos no crean ni rotan a la vez), MÁS una
   instantánea diaria fuera de esa rotación
   (`respaldo/diario/<fecha>/`, se guardan 7): con un disparador
   horario, 10 instantáneas rotan en pocas horas y una corrupción que
   se detecta tarde se quedaría sin ninguna copia buena (I10).
   **Alcance honesto (I11):** esta pata y la 3 viven en el mismo
   disco que el estado vivo: el respaldo triple protege contra un
   carril corrupto, un borrado accidental y una mala actualización,
   NO contra la muerte del disco. Para eso, `respaldo.py` ofrece
   `exportar(ruta)` — copia verificada de la última instantánea a la
   ruta que elija el dueño (otro volumen, USB, carpeta de red) — por
   CLI en esta fase; su automatización queda fuera de alcance (§12).
2. **GitHub (código):** los repos de proyecto subidos con el flujo del
   §5/§6. Ningún archivo de estado va a GitHub: el hook del §6 bloquea
   por nombre precisamente esos archivos (las patas no se mezclan).
3. **Espacio de cada Muse:** cada proceso copia la última instantánea
   a SU espacio: `_dir_carril(<su carril>, "respaldo-estado")`, con la
   misma estructura y manifiesto. «Su espacio» = la carpeta de su copia
   del programa (la del carril A para la cuenta del carril A, etc.):
   si un carril se corrompe entero, el otro conserva una copia del
   estado íntegra y verificable por hash.

### 7.3 Disparadores y reglas

- Instantánea nueva: al terminar una mezcla, al completarse un
  traspaso, al registrar un proyecto, y una vez por hora desde el
  latido del supervisor si algo cambió (comparación por hash: sin
  cambios, no hay instantánea nueva ni copias).
- Tras crear la instantánea, cada proceso presente actualiza la copia
  de su espacio; un proceso que arranca con su copia desactualizada la
  refresca ANTES de aceptar tareas (mismo orden que la migración de la
  Fase 1: primero el estado, luego el trabajo).
- Toda escritura es a carpeta temporal + renombrado (una instantánea a
  medias nunca parece válida: sin `manifiesto.json` completo, no
  existe a efectos de restauración).
- Cada instantánea y cada copia quedan en la auditoría de la cuenta del
  proceso que la hizo.

### 7.4 Restauración y simulacro

- `respaldo.verificar(carpeta)` → comprueba el manifiesto contra los
  hashes reales; devuelve la lista de archivos dañados o ausentes.
- `respaldo.restaurar(carpeta_origen, dir_destino)` → restaura en un
  directorio DESTINO distinto del vivo (nunca pisa el estado en
  caliente sin pasar por el procedimiento): copia, verifica hashes y
  deja un `RESTAURADO.md` con el qué y el cuándo. La restauración
  SANEА antes de entregar (I10): todo marcador de `traspasos.json` no
  terminal pasa a `requiere_dueno` en la copia restaurada (un marcador
  viejo resucitado no puede reofrecer tareas ya resueltas), y el
  `RESTAURADO.md` anota que los `audit-log` restaurados pueden quedar
  por detrás del ancla `audit-indice.json` (la verificación de ancla
  lo señalará; esa discrepancia es en sí misma el registro del
  incidente). Pasar a producción desde ahí es un acto manual del
  dueño con la app cerrada (procedimiento documentado en el propio
  `RESTAURADO.md`).
- **Simulacro (parte de la aceptación de la fase):** con las dos copias
  de la app del entorno de pruebas: se hace una instantánea, se
  «destruye» el estado del carril B (se apartan sus archivos), se
  restaura desde la copia del espacio de la cuenta A y desde la
  instantánea de la PC, y se arranca el carril B restaurado comprobando
  que reconoce cuentas, cola y tablero. Tiempos declarados como
  objetivo del simulacro: instantánea completa < 30 s y restauración
  verificada < 5 min para el tamaño de estado actual (se mide y se
  anota el real en el cierre de la fase; si crece, se revisa el
  objetivo, no se maquilla).

## 8. Traspaso por cuarentena (`traspaso.py`)

La Fase 2 dejó la cuarentena sin traspaso: la cuenta agotada no recoge
tareas nuevas, pero su tarea EN CURSO quedaba donde estaba. Esta fase lo
activa: al entrar una cuenta en `cuarentena`, su tarea en curso pasa a
otra cuenta Muse **exactamente una vez**, con su contexto (su rama y su
worktree de código incluidos).

### 8.1 Disparo y destino

- Disparo **por nivel, no por transición** (corrección B4): en cada
  latido se comprueba «¿hay una cuenta en `cuarentena` con tarea en
  curso y sin marcador vivo?». Detectar solo el flanco de la
  transición perdería el traspaso si el latido que la vio morir o el
  proceso se cayó justo ahí; el nivel se reevalúa solo en cada vuelta.
  El barrido de arranque del proceso origen (antes de aceptar tareas)
  hace la misma comprobación.
- **El protocolo lo ejecuta SOLO el proceso de la cuenta origen**
  (corrección B4): es el único que tiene el dict de la tarea, su
  `cola.db` y su proceso hijo. El otro carril NO puede «ejecutarlo él»
  leyendo el tablero: el tablero no conoce la tarea en curso ni el
  dict vive en estado compartido. Si el proceso origen está muerto,
  no hay ejecución viva que traspasar: al rearrancar, SU barrido crea
  o continúa el marcador antes de recuperar su cola (y los hijos
  huérfanos de la ejecución anterior se matan en ese mismo arranque,
  como ya hace la recuperación de tareas a medias). Para que dos
  ejecuciones del protocolo no se solapen jamás, el marcador lleva un
  **alquiler de ejecutor** (`ejecutor`, `ejecutor_latido_ts`) tomado
  bajo el lock al empezar y renovado por paso: solo se roba si está
  caducado (> 120 s sin latido), y el robo queda en la auditoría.
- Destino: `tablero.elegir_cuenta` entre las cuentas `activa` (la misma
  primitiva determinista de la Fase 2). Si no hay destino disponible, el
  marcador nace en estado `sin_destino` y se reintenta en cada latido
  (la tarea sigue en la cuenta origen, ya detenida según el paso 1b:
  no se pierde ni se duplica por esperar).

### 8.2 El marcador (`traspasos.json`, carpeta compartida)

```json
{
  "version": 1,
  "revision": 0,
  "traspasos": {
    "traspaso-<tarea>-<n>": {
      "tarea": "<id>",
      "origen": "principal",
      "destino": "segunda",
      "estado": "ofrecido",
      "creado_ts": 1763...,
      "expira_ts": 1763...,
      "ejecutor": "principal",
      "ejecutor_latido_ts": 1763...,
      "origen_detenido_ts": 1763...,
      "reclamante": null,
      "repo": "<repo_id o null>",
      "rama": "muse/principal/<tarea>",
      "commit_rescate": "<hash o null>",
      "motivo": "cuarentena"
    }
  }
}
```

Estados: `sin_destino` → `ofrecido` → `entregado` → `aceptado` →
`confirmado` (fin bueno); salidas laterales: `devuelto` (el destino no
confirmó a tiempo y la tarea vuelve al origen) y `requiere_dueno`
(algo no cuadra y nadie actúa sin el dueño). TTL del traspaso: **600 s**
de `ofrecido` a `aceptado`; pasado sin aceptación, se devuelve. El
estado `confirmado` tiene su propio TTL de supervisión (corrección
B3): si el destino deja de latir en el tablero más de **600 s** con el
marcador en `confirmado` y la tarea sin cerrar, el marcador pasa a
`requiere_dueno` (nadie la reejecuta ni la devuelve solo: el destino
pudo haber aplicado efectos). `reclamante` guarda
`{cuenta, carril, instancia}` de quien aceptó: es lo que distingue
«reanúdame» de «duplicado» en la puerta (paso 4).

### 8.3 Protocolo (marcador primero, pasos idempotentes)

Lo ejecuta el proceso de la cuenta origen (o su propio barrido al
rearrancar), con el alquiler de ejecutor del marcador tomado (§8.1).

1. **Crear el marcador** en estado `ofrecido` bajo el lock compartido,
   ANTES de tocar ningún archivo. Si ya hay un marcador vivo para esa
   tarea, no se crea otro (idempotencia por tarea).
1b. **Detener al origen** (corrección B1; sin este paso el resto es
   papel mojado): entrar en cuarentena NO detiene por sí solo la
   ejecución en curso, y rescatar el worktree bajo una Muse que sigue
   escribiendo captura un estado a medias — en Windows ni siquiera se
   puede retirar el worktree con el proceso hijo dentro. Solo puede
   hacerlo el proceso origen: cancela la ejecución (mata el árbol de
   procesos de la tarea con el `_matar_arbol` de la Fase 0 y espera su
   salida), marca su fila de cola como `traspasando` y escribe
   `origen_detenido_ts` en el marcador. El paso 2 EXIGE ese campo. Si
   la parada no se confirma en 120 s, el marcador pasa a
   `requiere_dueno` y no se toca nada más. Y mientras una fila esté en
   `traspasando`, si su `process_one` termina tarde, su resultado se
   DESCARTA: la tarea ya no es de ese carril.
2. **Rescate del worktree** (solo si la tarea tiene repo; exige
   `origen_detenido_ts`): si el worktree del origen está sucio, commit
   de rescate en su rama con identidad fija
   (`-c user.name="Growi Bridge" -c user.email=growi@localhost`,
   `--no-verify` para no ejecutar los hooks del repo, mensaje
   `wip: rescate por traspaso <id>`), escaneando los blobs staged tras
   el `add` — un rescate con un secreto dentro NO se confirma: el
   marcador pasa a `requiere_dueno`. Si el worktree tiene una mezcla o
   un rebase a medias (`MERGE_HEAD`, `rebase-*`), tampoco se rescata:
   `requiere_dueno` (corrección I5). Los archivos ignorados presentes
   en el worktree (un `.env` local, artefactos) NO viajan con el
   commit: sus nombres se listan en el marcador
   (`ignorados_no_viajan`) para que el dueño lo sepa. Después,
   `git worktree remove` del worktree del origen (la rama queda libre:
   git no permite la misma rama en dos worktrees; antes de diagnosticar
   «ocupada» se corre `git worktree prune`, por si el directorio se
   borró a mano). Si el worktree ya no existe o la rama no está
   ocupada, el paso es un no-op verificado. El hash del commit de
   rescate queda en el marcador.
3. **Entregar la tarea** en el `runner-tasks/` del carril destino
   (escritura atómica, como `consulta.entregar`). El archivo y la fila
   del destino se llaman como el MARCADOR, no como la tarea
   (corrección I9): el dict entregado lleva `"id": <id del marcador>`
   y el bloque
   `"traspaso": {"de": <origen>, "marcador": <id>, "tarea": <id original>,
   "rama": <rama>}`; la correlación se conserva por `traspaso.tarea` y
   por la `raiz`, que no cambia. Así, un reofrecimiento `n+1` nunca
   choca con la fila ya cerrada de `n`, ni dos cuentas del mismo
   carril chocan en la misma `cola.db`. El `prompt` gana una cabecera
   de continuación (corrección I8): «continúas la tarea <id> de la
   cuenta <origen>; su trabajo va por el commit <rescate>; no repitas
   lo ya hecho». La sesión de la Muse origen NO viaja: lo que viaja
   es la rama, el commit de rescate y esta cabecera. Por eso, **una
   tarea sin repo solo se traspasa si trae `"idempotente": true`**;
   sin esa marca, reejecutarla desde cero podría repetir efectos ya
   aplicados fuera de git y el marcador pasa a `requiere_dueno`. El
   destino creará SU worktree sobre la MISMA rama con
   `preparar_worktree(..., rama=<la del bloque>)`: la rama es la
   continuidad del trabajo; el directorio es nuevo. El marcador pasa
   a `entregado`.
4. **Reclamación en el destino (claim):** la puerta del runner del
   destino, al ver una tarea con bloque `traspaso`, comprueba el
   marcador bajo el lock ANTES de ejecutarla:
   - Si está `entregado` y no ha expirado → claim: en una misma pasada
     y con orden de locks fijo (primero `traspasos`, después
     `alquileres`, para que ningún otro camino pueda interbloquearse)
     pasa el marcador a `aceptado` guardando `reclamante` Y reasigna
     los alquileres de la tarea de la cuenta origen a la destino
     (corrección B5: los alquileres van por (cuenta, tarea) y, sin
     reasignarlos, el destino chocaría con los del origen para
     siempre, porque el latido del origen los seguiría renovando; por
     la misma razón, el latido del origen deja de renovar tareas con
     marcador no terminal). Si la tarea era una consulta con reserva
     de gasto de la Fase 2, el claim cierra la reserva del origen en
     el libro y reserva en el destino. El claim es reintentable: si
     algo falla a mitad, el marcador queda como estaba y la puerta lo
     reintenta en la siguiente vuelta.
   - Si está `aceptado`/`confirmado` y el `reclamante` es ESTA cuenta
     en ESTE carril → no es un duplicado: es la reanudación tras una
     caída propia, y rige la semántica normal de recuperación de su
     cola (corrección B3). Solo se cierra como duplicado, con un
     `.result.json` que lo dice y SIN ejecutar, si el reclamante es
     OTRO, o si el marcador está `devuelto`/`requiere_dueno` (ya no
     vale; y `requiere_dueno` bloquea también la reanudación propia
     hasta que el dueño decida).
   Este es el `por_confirmar` de la Fase 1 aplicado al traspaso: la
   tarea está en el aire hasta que el destino la reclama, y solo
   puede reclamarse una vez.
5. **Confirmación y cierre en el origen:** al aceptar, el destino
   anota el marcador como `confirmado` (decisión: al ACEPTAR, porque
   desde ese instante la responsabilidad es del destino; el TTL de
   supervisión de `confirmado` está en §8.2). El origen, en su latido,
   ve el marcador `confirmado` y marca su fila de cola como
   `traspasada` (estado nuevo, terminal a efectos de recuperación:
   `cola_recuperar` al arrancar SALTA toda tarea con marcador NO
   terminal — `sin_destino`, `ofrecido`, `entregado`, `aceptado`,
   `confirmado` y también `requiere_dueno`: nadie reejecuta lo que un
   marcador retiene, corrección B2). Si el marcador expira sin
   aceptación (`devuelto`), el origen solo recupera y reejecuta la
   tarea en local **si ya salió de cuarentena**; si sigue en
   cuarentena, la tarea queda retenida SIN crear un marcador `n+1` en
   bucle (el ciclo ofrecer→devolver cada 600 s sería ruido eterno):
   solo se reofrece cuando aparece un destino DISTINTO del que dejó
   caducar el anterior, o cuando el dueño lo ordena. Ejecutada en un
   sitio o en otro, nunca en los dos, como manda el protocolo de la
   Fase 1.
6. Todo el ciclo queda en la auditoría de ambas cuentas (ofrecimiento
   y parada en la del origen, aceptación y confirmación en la del
   destino, devolución en la del origen).

### 8.4 Cortes de luz: tabla de reconciliación

El barrido al arrancar (y en cada latido) cruza marcador ↔ realidad:

| Corte tras… | Realidad al volver | Resolución del barrido |
|---|---|---|
| 1 (marcador `ofrecido`) | sin entrega, origen quizá aún ejecutando | se reanuda en el paso 1b (parada) y luego el 2 |
| 1b (origen detenido) | `origen_detenido_ts` escrito, sin rescate | se reanuda en el paso 2 |
| 2 (rescate hecho) | rama libre, sin entrega | se reanuda en el paso 3 |
| 3 (entrega hecha) | archivo en destino, marcador `entregado` | nada: el destino reclamará |
| 4 (claim hecho, destino rearranca) | marcador `aceptado`, `reclamante` = el propio destino | el destino REANUDA su tarea (no es duplicado); el origen no la recupera jamás |
| destino muere tras aceptar y no vuelve | marcador `confirmado`, sin latido del destino > 600 s | el marcador pasa a `requiere_dueno` (NO se devuelve solo: el destino pudo haber aplicado efectos no visibles; el dueño decide) |
| origen rearranca con marcador `sin_destino` | la tarea sigue en su cola | `cola_recuperar` la salta (marcador no terminal); el paso a `ofrecido` exige `origen_detenido_ts` |
| marcador corrupto o tarea sin marcador pero con bloque `traspaso` | — | la puerta del destino la cierra como no válida (fail-closed) y se registra |

La fila delicada es la quinta: aceptar y morir. Devolverla
automáticamente arriesgaría una doble ejecución con efectos ya
aplicados; por eso ese único caso pide al dueño. Es la misma
filosofía que el `por_confirmar` de la Fase 1: ante la duda entre
duplicar o esperar, se espera y se pregunta.

## 9. Decisión registrada: contenedores por proyecto

**Decisión: UN contenedor por proyecto, con los dos worktrees dentro.**
La implementación llega en la Fase 6; aquí queda la decisión y su
porqué, como pide el plan:

- Lo que hay que compartir entre las dos Muses de un proyecto es el
  almacén de objetos de git y las ramas: la revisora lee el diff de la
  proponente al instante y la mezcladora mezcla sin copiar repos entre
  contenedores. Con dos contenedores, ese almacén compartido exigiría
  de todos modos un volumen común montado en ambos: la frontera real
  de aislamiento no estaría donde parece.
- El aislamiento que importa en esta arquitectura es otro y se logra
  sin multiplicar contenedores: directorio de trabajo separado
  (worktree por tarea, §3), credenciales por cuenta que nunca entran en
  el entorno del proyecto (bóveda de la Fase 1) y permisos por cuenta
  (Fase 1). Nada de eso mejora por partir el contenedor en dos.
- Los recursos se asignan en porcentaje del equipo (decisión del
  dueño, Fase 4): un contenedor por proyecto hace el porcentaje
  directamente aplicable al proyecto; dos contenedores obligarían a
  repartir y reconciliar cuotas por cuenta dentro del mismo proyecto.
- Coste en equipos modestos: un contenedor por proyecto es la mitad de
  procesos base que dos; el producto debe correr en una PC normal.
- **Excepción prevista:** un proyecto con código no confiable puede
  pedir `"contenedores": "por_cuenta"` en `proyectos.json` (§2): dos
  contenedores con el volumen de git compartido en solo lectura para
  la revisora. Queda como opt-in de la Fase 6, no como defecto.

## 10. Cableado en el monolito (fino) y UI

1. **Runner — worktree y alquileres:** en `runner_loop`, tras la
   puerta del tablero y antes de `process_one`: si la tarea trae repo
   (o su `cwd` está en uno), `preparar_worktree` y fijar el `cwd`
   efectivo — que es el worktree MÁS la subruta del `cwd` original
   dentro del repo (corrección I3: las rutas de `archivos` son
   relativas a la RAÍZ del repo, y las claves de alquiler se
   normalizan a minúsculas en repos con `core.ignorecase=true`, cuyo
   valor se guarda en `proyectos.json` al registrar);
   `alquileres.tomar` con los `archivos` declarados (o `*` de proyecto
   si no declara). **Excepciones a la toma por defecto:** las tareas
   de tipo `revision` y la operación de mezcla no toman alquiler de
   proyecto (la mezcla usa su clave `@mezcla`, §5.1). Sin alquiler →
   dejar en cola con `proximo_intento` según §4.3, y además el latido
   reintenta la toma cada 60 s (si la otra cuenta suelta antes de que
   expire su TTL, quien espera no paga la espera entera, corrección
   I2). Al cerrar la tarea: `soltar` y anotar `worktree`/`rama` en el
   resultado. Los alquileres evitan ediciones SIMULTÁNEAS del mismo
   archivo; no prometen mezclas sin conflicto (dos ramas pueden tocar
   el mismo archivo en tiempos distintos y el conflicto lo gestiona
   el §5, I2).
2. **Latido:** el `runner_heartbeat` existente añade: renovar los
   alquileres de la cuenta, detectar la transición a `cuarentena` para
   disparar el traspaso (§8.1), barrido de traspasos y de propuestas
   `superada`s, y el disparador horario de respaldo (§7.3). Todo con el
   patrón de la Fase 2: excepciones tragadas con log, el runner nunca
   depende de esto para vivir (salvo lo fail-closed del §6, que solo
   bloquea la acción concreta).
3. **Puerta — claim de traspaso:** `_puerta_tablero` gana la rama del
   §8.3 paso 4 para tareas con bloque `traspaso`, antes de dejarlas
   pasar y DESPUÉS de la comprobación de cuarentena (una tarea
   traspasada a una cuenta que acaba de entrar en cuarentena no se
   reclama: el marcador expira y se devuelve, o el barrido la
   reofrece a otra cuenta activa creando un marcador nuevo con `n+1`).
4. **Subidas y mezclas:** ningún `git push`/`git merge` del monolito va
   directo: todo pasa por `git_trabajo.subir` y por el flujo del §5.
   La aprobación del dueño reutiliza el circuito de confirmaciones de
   `permission-layer.py` (la mezcla se clasifica como acción sensible
   en `clasificar_tarea` con cuenta, como las demás).
5. **UI (página Cuentas):** sección «Proyectos y respaldo» bajo el
   tablero: por proyecto, ruta, rama base, mezcladora y estado del
   hook; propuestas pendientes con su estado; última instantánea de
   respaldo y estado de la copia en cada espacio, con botones «Hacer
   respaldo ahora» y «Verificar respaldo». Todo pasa por los módulos;
   la página no toca los JSON a mano (mismo criterio que la Fase 2).
6. **Arranque:** tras la migración de la Fase 1 y antes de aceptar
   tareas: refrescar la copia de respaldo del propio espacio si está
   desactualizada (§7.3) y correr el barrido de traspasos (§8.4). El
   registro de proyectos y la instalación del hook ocurren al primer
   uso de un repo, no al arrancar.

## 11. Aceptación de la fase

Pruebas unitarias (módulos puros, git falso inyectado donde aplique):

- `test_git_trabajo.py`: convención de ramas y rutas de worktree
  (hermano del repo, nunca dentro); crear/reusar/reanudar worktree;
  rama ocupada por otro worktree → error; liberación con cambios sin
  confirmar → error sin `forzar`; `repo_id` estable e idempotente;
  limpieza que respeta worktrees sucios y propuestas vivas.
- `test_alquileres.py`: tomar/renovar/soltar; conflicto archivo↔archivo,
  archivo↔proyecto y misma cuenta distinta tarea; todo-o-nada (una
  ruta en conflicto ⇒ ninguna se toma); caducidad y robo por caducidad
  con su aviso; renovar lo perdido devuelve `False`; rutas con `..`
  rechazadas; dos procesos reales tomando a la vez sin doble concesión.
- `test_secretos.py`: cada patrón del §6.1 detectado en un rango de
  varios commits (incluido un secreto en un commit intermedio, no solo
  en HEAD); lista de bloqueo por nombre sin excepción; permitidos por
  (ruta, huella) que solo perdonan SU línea; evidencia siempre
  redactada (el secreto literal no aparece en ningún hallazgo);
  `.env.example` limpio pasa, `.env.example` con clave real no.
- `test_traspaso.py`: protocolo completo con directorios temporales;
  marcador antes que archivo (si la entrega falla, el marcador queda
  `ofrecido` y el barrido lo reanuda); la parada del origen (paso 1b)
  es previa al rescate y un resultado tardío del origen se descarta;
  claim único (el segundo archivo idéntico se cierra como duplicado
  sin ejecutar); claim del PROPIO reclamante tras una caída = reanudar,
  no duplicado; el claim reasigna los alquileres de la tarea;
  expiración → `devuelto` y el origen puede ejecutar SOLO si salió de
  cuarentena (si sigue, no hay bucle de reofrecimientos); aceptación
  del destino ⇒ el origen nunca recupera la tarea;
  `cola_recuperar` salta también `sin_destino` y `requiere_dueno`;
  rescate con worktree sucio crea el commit `wip` y libera la rama;
  rescate con secreto o con mezcla a medias → `requiere_dueno` sin
  commit; tarea sin repo y sin `idempotente: true` → `requiere_dueno`.
- `test_respaldo.py`: instantánea con manifiesto y hashes; rotación a
  10 + diaria protegida; verificación que detecta un archivo alterado
  y uno ausente; `cola.db` copiada con la API de respaldo MIENTRAS un
  hilo escribe en la original (la copia pasa `integrity_check`);
  instantánea abortada si un JSON de estado está corrupto o contiene
  un secreto plantado; restaurar en destino aparte y verificar, con
  los marcadores no terminales saneados a `requiere_dueno`; la lista
  blanca ignora un archivo extraño plantado en la carpeta origen y
  JAMÁS incluye un archivo de bóveda plantado con nombre parecido.
- `test_git_trabajo.py` gana además: mezcla con la `rama_base` ocupada
  por el árbol principal del dueño (HEAD separado, sin tocar su
  `main`); mezcla del sha aprobado aunque la rama se haya movido
  después (la propuesta vuelve a `en_revision` y NO se mezcla lo no
  revisado); propuesta vacía (`sha == sha_base`) rechazada;
  `preparar_worktree` con `rama` explícita reusa la rama del origen en
  un traspaso.
- `test_secretos.py` gana además: secreto en un blob marcado `binary`
  en `.gitattributes` y en un archivo UTF-16 (detectados por el
  escaneo de objetos); secreto SOLO en un commit de mezcla
  (detectado); permitido con firma HMAC inválida o fabricado dentro
  del repo (bloquea igual); `.ENV` y `Secret.txt` bloqueados por
  nombre en cualquier combinación de mayúsculas.

Pruebas físicas (entorno de pruebas Linux, dos copias de la app):

- Repo de juguete local (un «juego» mínimo con `main` y remoto local
  tipo bare): la tarea de la cuenta A crea su worktree
  `principal--<tarea>` y su rama `muse/principal/<tarea>`, trabaja y
  sube; la cuenta B revisa el diff como tarea `revision`; el dueño
  aprueba en la app; la mezcladora mezcla a `main` y el remoto lo
  refleja. Todo el ciclo visible en las auditorías de ambas cuentas.
- Alquiler real entre dos procesos: B pide el mismo archivo que A
  tiene en curso → B espera con motivo en su cola; A termina → B
  arranca sin intervención.
- **Simulacro de restauración del §7.4**, con tiempos medidos y
  anotados en el cierre de la fase.
- Traspaso real: con una tarea larga en curso en A, se declara 0 % →
  cuarentena → la tarea aparece en el carril B con su rama y su
  worktree, B la termina, y A no la reejecuta al rearrancar.

Fallos inyectados:

- **Secreto en un commit:** se confirma una clave de juguete en el
  worktree y se intenta subir por la capa A (bloqueado, hallazgo
  redactado) y por `git push` directo en terminal (el hook lo
  bloquea). Se repite con el secreto en un commit intermedio del
  rango, en un archivo marcado `binary`, en UTF-16 y dentro de un
  commit de mezcla. Y el intento de la propia Muse de subir por su
  cuenta (`git push` desde su sesión) falla por falta de credenciales
  en su entorno, sin llegar a red.
- **Alquiler de una Muse muerta:** A toma un alquiler y se mata su
  proceso (`kill -9`); B no puede tomarlo hasta que caduca (180 s) y
  entonces lo toma con el robo registrado en auditoría; al rearrancar
  A, su `renovar` devuelve `False` y su tarea no puede subir.
- **Corte a mitad de traspaso:** `kill -9` al proceso que ejecuta el
  traspaso tras cada paso del §8.3 (se fuerza con un retardo de
  prueba entre pasos); al rearrancar, el barrido deja el sistema en
  exactamente un ejecutor: la tarea se ejecuta una vez en total,
  verificado por un contador que la propia tarea de juguete
  incrementa en su resultado.
- **Conflicto de mezcla:** A y B tocan la misma línea desde la misma
  base en ramas distintas; la primera mezcla entra; la segunda
  propuesta acaba en `conflicto` con su lista de archivos, la base no
  se mueve y nadie resuelve en silencio.
- **Sin git / hook ajeno:** PATH sin git → la tarea normal degrada con
  aviso y la `git: "requerido"` falla cerrada; repo con un `pre-push`
  ajeno → el proyecto queda `hook: "conflicto"`, el hook ajeno
  intacto, y la capa A sigue bloqueando el secreto.

## 11 bis. Correcciones de la revisión de Opus 5.5 (aplicadas)

Revisión recibida el 2026-11-16 (14 bloqueantes, 13 importantes).
Decisiones resultantes, que mandan sobre el texto anterior donde
choquen; el cuerpo del diseño ya está ajustado en los puntos que se
citan.

- **B1 — El traspaso detiene primero al origen.** Paso 1b nuevo en
  §8.3: el proceso origen cancela la ejecución (mata el árbol, espera
  la salida), marca su fila `traspasando`, escribe
  `origen_detenido_ts` y solo entonces se rescata el worktree. Sin
  confirmación de parada en 120 s → `requiere_dueno`. Un resultado
  tardío de una fila `traspasando` se descarta.
- **B2 — `cola_recuperar` salta TODO marcador no terminal**, incluidos
  `sin_destino` y `requiere_dueno`. Pasar a `ofrecido` exige
  `origen_detenido_ts`. `devuelto` solo libera la tarea si el origen
  salió de cuarentena; si sigue, queda retenida sin bucle de
  reofrecimientos hasta que haya un destino distinto (§8.3 paso 5).
- **B3 — El claim distingue reanudar de duplicar.** El marcador guarda
  `reclamante {cuenta, carril, instancia}`: si quien se encuentra la
  tarea es el propio reclamante, la reanuda con la semántica normal
  de su cola; duplicado solo si el reclamante es otro. `confirmado`
  gana un TTL de supervisión propio (600 s sin latido del destino →
  `requiere_dueno`), y `requiere_dueno` bloquea también la
  reanudación propia (§8.2, §8.3 paso 4, §8.4).
- **B4 — El protocolo lo ejecuta solo el origen.** El otro carril no
  puede: ni tiene el dict de la tarea ni su cola, y el tablero no
  conoce la tarea en curso. Disparo por nivel en cada latido (no por
  transición) y barrido de arranque del origen antes de recuperar su
  cola. El marcador lleva alquiler de ejecutor con latido, robable
  solo si caduca (§8.1).
- **B5 — El claim reasigna los alquileres.** En la misma pasada del
  claim, con orden de locks fijo (traspasos → alquileres), los
  alquileres de la tarea pasan de la cuenta origen a la destino; el
  latido del origen deja de renovar tareas con marcador no terminal.
  Sin esto, el destino esperaba un alquiler que el origen renovaba
  para siempre (§8.3 paso 4).
- **B6 — La rama no se deriva siempre de (cuenta, tarea).**
  `preparar_worktree` acepta `rama` explícita (traspaso, propuesta,
  hija que corrige): la continuidad manda sobre la convención. El id
  de propuesta es el hash de `(repo_id, rama)` y la cuenta dueña se
  guarda en `propuestas.json`, nunca se infiere del nombre (§3.2,
  §5.1).
- **B7 — La mezcla no usa la `rama_base` local.** Worktree de mezcla
  en HEAD separado sobre `origin/<rama_base>`; push con
  `HEAD:refs/heads/<rama_base>`; el `main` del dueño no se toca. Sin
  remoto, `update-ref` solo si la base no está ocupada en ningún
  worktree; si lo está, `mezcla_manual_pendiente`. La revisora usa
  `--detach <sha>` si necesita árbol (§5.1 paso 5).
- **B8 — La aprobación se firma sobre un sha.** La propuesta guarda
  `sha_base` y `sha_revisado`; el veredicto firma ese sha y el
  payload HMAC del dueño es `repo|rama|sha`. La mezcla mezcla el sha,
  tras comprobar que `origin/<rama>` no se movió; cualquier push
  posterior a la revisión devuelve la propuesta a `en_revision` e
  invalida la aprobación (§5.1 pasos 2, 4 y 5).
- **B9 — Mezcla y revisión no usan el alquiler de proyecto.** Clave
  aparte `<repo_id>|@mezcla` que solo choca consigo misma; el §10.1
  excluye `tipo: revision` y la mezcla de la toma por defecto.
  Desaparece el «alquiler de rama en modo compartido», que no existía
  en la API del §4.
- **B10 — El conjunto escaneado es el que el remoto no tiene.**
  `git rev-list <sha> --not --remotes=<remoto>` en las dos capas (una
  rama nueva ya no reescanea todo el historial), y la capa A sube el
  sha exacto escaneado (`push <remoto> <sha>:refs/heads/<rama>`): sin
  ventana entre escanear y subir. El hook ignora las líneas de
  borrado (§6.1, §6.2).
- **B11 — Se escanean objetos, no diffs.** Blobs nuevos enteros vía
  `cat-file --batch`, con decodificación UTF-8/UTF-16; la lista de
  nombres cubre todas las rutas de los árboles nuevos; blob no
  escaneable (tamaño o codificación) = hallazgo fail-closed
  perdonable solo por huella del blob; repo con LFS = bloqueado
  hasta decisión del dueño (§6.1).
- **B12 — Los permitidos no viven en el repo.** Pasan a
  `_token_dir()/permitidos-<repo_id>.json`, cada entrada con firma
  HMAC del dueño (`repo|ruta|huella|tipo`) por el circuito de
  confirmaciones. Entrada sin firma válida = no existe (§6.4).
- **B13 — La capa que detiene a la Muse es la A, y el principio 4
  lo dice así.** Las tareas ejecutan con el entorno git saneado (sin
  `credential.helper`, sin agente SSH, sin `GH_TOKEN`,
  `GIT_TERMINAL_PROMPT=0`) y `subir` inyecta la credencial desde la
  bóveda solo para su push. El hook se instala donde git lo busca
  (`git rev-parse --git-path hooks/pre-push`, respetando
  `core.hooksPath`: si apunta a algo ajeno, `hook: "conflicto"`) y
  protege al dueño en su terminal, no a la Muse (§1 principio 4,
  §6.2 paso 0, §6.3).
- **B14 — `cola.db` se respalda con la API de SQLite.**
  `sqlite3.Connection.backup()` + `PRAGMA integrity_check` antes de
  entrar en el manifiesto; copiar el archivo en caliente (y sin el
  WAL) producía respaldos rotos con hash «válido» (§7.1).
- **I1 — TTL de alquileres a 300 s y renovación en cada latido** del
  hilo de pulso (que no se bloquea con `process_one`), con guarda de
  salto de reloj: tras una suspensión, renovar lo propio antes de
  purgar lo ajeno. Se anota como deuda una duración máxima por tarea
  (llega con el harness de la Fase 4) (§4.2).
- **I2 — Los alquileres evitan ediciones simultáneas, no conflictos
  de mezcla** (queda dicho en §10.1). Quien espera un alquiler lo
  reintenta en cada latido: soltar adelanta a los que esperan sin
  esperar a que expire el TTL del difunto.
- **I3 — Rutas y `cwd` normalizados:** `archivos` relativos a la raíz
  del repo; `cwd` efectivo = worktree + subruta original; claves de
  alquiler en minúsculas si el repo es `core.ignorecase=true` (§10.1).
- **I4 — Hook robusto en Windows:** ruta absoluta de `sys.executable`
  entre comillas y con barras `/`, y escáner desplegado en una ruta
  estable de `_token_dir()`; el hook de git-lfs se detecta y cae en
  el caso `conflicto` conocido (§6.3).
- **I5 — Rescate endurecido:** identidad git fija y `--no-verify`;
  mezcla o rebase a medias → `requiere_dueno`; escaneo de los blobs
  staged tras el `add`; los archivos ignorados del worktree se listan
  en el marcador como lo que no viaja (§8.3 paso 2).
- **I6 — Robustez de git en el ejecutor:** timeouts por operación
  (120 s local, 300 s de red), `GIT_TERMINAL_PROMPT=0` siempre, matar
  el árbol al agotar el timeout, `git worktree prune` antes de
  diagnosticar una rama «ocupada» y comparación de rutas normalizadas
  (§3.2 y §8.3 paso 2; el detalle vive en `git_trabajo.py`).
- **I7 — `superada` también por árbol:** además del ancestro, se
  compara el árbol de la rama con el de la base tras su avance
  (cubre squash/rebase de GitHub); propuesta con `sha == sha_base`
  rechazada al nacer (§5.1).
- **I8 — El traspaso conserva contexto declarado, no la sesión:** el
  prompt entregado lleva cabecera de continuación con el commit de
  rescate; las tareas sin repo solo se traspasan con
  `"idempotente": true` (si no, `requiere_dueno`); al reclamar, la
  reserva de consulta del origen se cierra y se reserva en el
  destino (§8.3 pasos 3 y 4).
- **I9 — El destino nombra por el marcador:** archivo y fila del
  destino con el id del marcador; el id original viaja en
  `traspaso.tarea` y la `raiz` no cambia. Sin colisiones entre
  reofrecimientos ni entre cuentas del mismo carril (§8.3 paso 3).
- **I10 — Instantáneas sin corrupción y restauración saneada:** JSON
  leídos bajo el lock de su módulo dueño; lock propio para crear y
  rotar; validación y escaneo de secretos de cada archivo ANTES de
  crear la instantánea (una corrupta aborta, no se respalda);
  instantánea diaria fuera de la rotación de 10; al restaurar, los
  marcadores no terminales pasan a `requiere_dueno` y la posible
  truncación de auditoría frente al ancla queda anotada en
  `RESTAURADO.md` (§7.1, §7.2, §7.4).
- **I11 — El respaldo triple no sobrevive a la muerte del disco, y
  se dice.** Dos de las tres patas comparten disco con el estado
  vivo; se añade `respaldo.exportar(ruta)` por CLI como pata
  opcional fuera del disco (§7.2).
- **I12 — Lista de bloqueo por nombre ampliada y sin mayúsculas:**
  comparación por nombre base en minúsculas; entran `cola.db` y sus
  `-wal`/`-shm`, `settings.json`, `audit-indice*`, `manifiesto.json`
  y los componentes `respaldo/`, `respaldo-estado/`, `.growi/` (§6.1).
- **I13 — Worktrees sin ambigüedad y con plan B:** un nivel por
  cuenta (`<cuenta>/<tarea>/`, sin separadores en el nombre); si el
  directorio hermano no sirve (raíz de unidad, padre no escribible o
  dentro de otro repo), `_token_dir()/worktrees/<repo_id>/…`; al
  registrar un repo se le pone `core.longpaths=true` en Windows y se
  comprueba que no exista una rama `muse/<cuenta>` suelta que
  bloquearía las referencias `muse/<cuenta>/<tarea>` (error
  explícito al dueño, que solo él puede renombrar) (§3.1, §2).

## 12. Fuera de alcance (explícito)

- Contenedores en ejecución (Fase 6; aquí solo la decisión del §9).
- Relevo por teléfono, reparto automático de tareas nuevas entre
  cuentas y declaración automática del % (Fase 4, harness): el
  traspaso de esta fase cubre SOLO la tarea en curso al entrar en
  cuarentena; las tareas en cola de la cuenta agotada siguen esperando
  en su carril (su puerta ya las retiene) hasta que la Fase 4 las
  reparta.
- Límites de cuota por cuenta (deuda de la Fase 2, sigue anotada).
- Botón de «permitir secreto» en la UI (§6.4 nace por CLI en esta
  fase).
- Mezcla automática sin aprobación del dueño: no existirá; la
  aprobación humana es parte del diseño, no una opción.

## 11 ter. Correcciones de las pruebas físicas (2026-11-16)

Dos defectos reales que solo aparecieron con las dos copias de la app
corriendo a la vez; ambos corregidos en el monolito y verificados de
nuevo en el entorno:

1. **La guardia del carril B rechazaba las tareas de proyecto.** La
   guardia preexistente exige `cwd` y `archivos` dentro del APP_DIR del
   carril B, y `validate_task` la aplica sobre la tarea cruda ANTES del
   cambio de `cwd` al worktree: toda tarea git de la cuenta del carril
   B sobre un proyecto externo moría rechazada aunque la Fase 3 hubiera
   preparado su worktree y sus alquileres. Corrección: `_lane_guard` y
   `validate_task` aceptan el contexto `f3` (la preparación de ESTA
   tarea en el runner); con preparación, el worktree cuenta como
   carpeta propia del carril (los relativos se resuelven contra él y el
   `cwd` válido es el efectivo). Sin `f3` (puente y demás caminos) la
   regla es la de siempre. Las tareas de `revision` cuyo `cwd` ya es un
   worktree preparado registran también su preparación (sin alquileres)
   para pasar la misma guardia. La lista de prohibidos no cambia.
2. **El latido renovaba los alquileres de tareas muertas.** `_f3_latido`
   renovaba TODOS los alquileres vigentes de la cuenta, incluidos los
   de tareas que ese proceso no estaba ejecutando: el alquiler de una
   tarea muerta con la app viva no caducaba nunca y la otra cuenta
   esperaba para siempre. Corrección: solo se renuevan los alquileres
   de las tareas en ejecución en ese proceso (la actual y las
   preparadas en `_F3_PREP`). Verificado: caducado el alquiler, la otra
   cuenta lo toma y el robo queda en su auditoría (`alquiler_robado`).

El resto de la aceptación del §11 se verificó en el entorno de dos
carriles: worktree y rama por cuenta, espera por alquiler con motivo en
la cola y arranque al liberarse, secreto bloqueado por la capa A y por
el hook (evidencia redactada) y subida limpia correcta, ciclo de mezcla
completo (propuesta → veredicto sobre el sha → aprobación del dueño por
el circuito HMAC → mezcla de la designada; el remoto avanza y el `main`
local del dueño no se toca), conflicto de mezcla con la base inmóvil,
respaldo con instantánea en 0,23 s y restauración verificada en 0,04 s,
traspaso con commit de rescate `wip:`, reclamación única (duplicado
para otra cuenta, reanudar para la propia) y hook ajeno en conflicto
sin pisar.
