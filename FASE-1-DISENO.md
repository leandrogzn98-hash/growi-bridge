# Fase 1 — Diseño: registro de cuentas y bóveda por cuenta

Estado: implementado y probado (2026-11-16). Diseño revisado por Claude
Opus 5.5 vía MWAPI; sus correcciones (B3–B5, I1–I11 y menores) están
aplicadas e integradas en este documento. Nota de honestidad: el inicio de
la revisión (bloqueantes B1 y B2) se perdió por un corte de salida; los dos
huecos más probables que cubrían —la compatibilidad silenciosa ante un
registro corrupto y la migración simultánea de dos procesos— quedaron
cubiertos igualmente (aviso en log y lock de registro, ver §2 y §3).

## 1. Principios

- Compatibilidad primero: sin `accounts.json`, la app se comporta EXACTAMENTE
  como hoy. El modo servidor existente no cambia por fuera (mismo header
  `X-Shared-Secret`, mismo 401).
- El secreto vive SOLO en la bóveda (almacén del sistema vía
  `_sec_get/_sec_set`). Nunca en `accounts.json`, nunca en logs, nunca en
  la UI (el campo de secreto se escribe pero jamás se muestra).
- Cada cambio es reversible borrando `accounts.json` (procedimiento en §8).

## 2. Registro de cuentas — `accounts.json` (módulo `cuentas.py`)

Esquema v1:

```json
{
  "version": 1,
  "revision": 3,
  "migrado_secret_txt": true,
  "borradas": [{"id": "vieja", "ts": "2026-11-16T00:00:00-04:00"}],
  "cuentas": [{
    "id": "principal", "nombre": "Muse principal",
    "asistente": "growi", "carril": "a", "conexion": "servidor",
    "habilitada": true, "creada": "2026-11-16T13:58:14-04:00",
    "permisos": {"modo": "hereda", "clases_extra_denegadas": []}
  }]
}
```

Reglas e invariantes (validadas en `cuentas.validar`):

- `id`: 2–32 caracteres `[a-z0-9-]`, empieza y termina en letra o dígito
  (fullmatch). Único. **No reutilizable**: un id en `borradas` (lápida) no
  puede volver — heredaría el secreto y la auditoría de la cuenta anterior.
- `carril`: `a`, `b` o `null`; como máximo una cuenta HABILITADA por carril.
- `conexion`: `servidor` | `local` | `ambas`.
- La cuenta `principal` no se puede deshabilitar (sostiene la
  compatibilidad). Una cuenta deshabilitada de un carril NO es «sin
  cuenta»: su puente rechaza las peticiones (gateway_token devuelve vacío
  con aviso en log).
- `asistente`: nombre simple de perfil (sin `/`, `\` ni `..`).
- `permisos.clases_extra_denegadas`: solo nombres con formato de clase; los
  permisos por cuenta SOLO restan (el clasificador las cruza con las clases
  reales, así que una clase inexistente no permite nada nuevo).
- `revision`: control optimista. `guardar` exige que la revisión coincida
  con la del disco y la incrementa; todo el ciclo leer-modificar-escribir
  va bajo un lock de archivo entre procesos (`accounts.json.lock`, O_EXCL,
  con ruptura de huérfanos a los 15 s). Dos carriles y la UI no se pisan.
- Carga: si el archivo falta → compatibilidad silenciosa (arranque limpio).
  Si EXISTE pero no valida → compatibilidad CON aviso en log (no es lo
  mismo un registro roto que uno ausente).

Recarga en caliente (qué pasa al editar la cuenta de un proceso vivo):

| Campo       | Cuándo se aplica                                             |
|-------------|--------------------------------------------------------------|
| `carril`    | Requiere reinicio: el carril del proceso lo fija su arranque (env `GROWI_BRIDGE_LANE` o settings) y no cambia en caliente. |
| `habilitada` y secreto | En caliente: el registro se relee por (mtime, tamaño) y al cambiar la revisión se olvida la caché en memoria de los secretos `muse:*`. |
| `asistente` | Entre tareas: `asis_activo()` lo resuelve en cada uso. Además, el selector de asistente de la UI escribe TAMBIÉN el `asistente` de la cuenta del carril (si no, cambiarlo no haría nada). |

Asistente por carril: `asis_activo()` prefiere el `asistente` de la cuenta
asignada al carril; `settings.asistente_activo` queda como valor por
defecto. (El carril B sigue sin perfiles por su diseño previo,
ESTADO-CARRIL-B; su cuenta registra el campo igualmente.)

## 3. Bóveda por cuenta

- Nombre de credencial por cuenta: `muse:<id>` sobre el almacén existente
  (`_sec_get/_sec_set`, servicio `growi-bridge`). Aislamiento LÓGICO por
  nombre dentro del mismo usuario del sistema — documentado como tal: no
  es una frontera frente a otro proceso del mismo usuario.
- `cred_via()` en POSIX: usa keyring si hay un backend REAL (Secret
  Service, KWallet, Keychain) y pasa una prueba de escribir-leer-borrar.
  Son degradados y caen al archivo: `fail.Keyring`, `null.Keyring`,
  `ChainerBackend` sin backends y los backends de texto plano de
  `keyrings.alt`.
- Archivo de respaldo POSIX: se crea con 0600 desde el nacimiento (sin
  ventana de carrera), se refuerza a 0600 en cada escritura y al leerlo se
  avisa en log si sus permisos son más laxos. La página Cuentas muestra el
  aviso de degradación también en pantalla, no solo en el log.
- Cada proceso carga solo el secreto de SU cuenta (gateway_token resuelve
  la del carril; la UI solo comprueba existencia al listar).
- Autenticación: el puente valida SOLO contra el secreto de la cuenta de
  su carril, con `hmac.compare_digest` (como ya hacía). Si la cuenta está
  deshabilitada, no hay token válido. Sin ruta de código que lea un secreto
  «global»: `load_secret()` queda solo como lector histórico para la
  migración y para `browser-server.py`.

### Migración de `secret.txt` (arranque, solo carril A siembra)

Bajo el lock del registro (dos procesos no migran a la vez):

1. Si `accounts.json` ya existe y valida → no hacer nada (idempotente).
2. Valor = EXACTAMENTE lo que devuelve `load_secret()` hoy (que ya hace
   strip; si el archivo falta, lo crea — comportamiento previo de la app).
3. Si la bóveda no tiene `muse:principal` o difiere → `_sec_set`; se
   verifica releyendo; si no coincide → abortar SIN crear el registro (la
   app sigue con secret.txt como hasta ahora).
4. Crear el registro con la cuenta `principal` (carril del proceso,
   asistente activo) y `migrado_secret_txt: true`.
5. `secret.txt` NO se toca.

**Decisión B4 (dos lectores, una verdad):** `browser-server.py` sigue
leyendo `secret.txt`. Por tanto, rotar el secreto de `principal` en la UI
escribe la bóveda Y actualiza `secret.txt` atómicamente a la par. Rotar
cualquier otra cuenta solo toca la bóveda.

`gateway_token()`: con registro, primero devuelve el secreto de la cuenta
del carril desde la bóveda (origen «bóveda (cuenta X)»); el archivo de
token clásico queda como respaldo del mismo valor, y al guardar un token
nuevo también se escribe en la bóveda.

## 4. Auditoría y permisos por cuenta (`permission-layer.py`)

- `registrar(..., cuenta=None)`: la cuenta por defecto conserva
  `audit-log.json`; cada otra cuenta escribe en `audit-log-<cuenta>.json`
  con SU propia cadena de hashes (un archivo y una cadena por cuenta: dos
  procesos sobre un solo JSON ya es una carrera, y entrelazar cadenas no
  gana nada). Las entradas llevan `v: 2` y `cuenta`. Las entradas v1
  antiguas verifican igual: el hash se recalcula sobre los campos
  almacenados de cada entrada (probado con cadena mixta v1+v2).
- **Ancla**: `audit-indice.json` guarda por archivo la cabeza y el número
  de entradas, actualizado en cada escritura. `verificar_ancla(cuenta)`
  detecta el borrado o truncado COMPLETO de un log, que la cadena sola no
  ve. La rotación deriva el nombre del propio archivo (antes quemaba
  «audit-log» y habría pisado el nombre entre cuentas).
- `clasificar_tarea(texto, cuenta=None)`: sin cuenta, idéntico a hoy. Con
  cuenta en modo `restringido`, sus `clases_extra_denegadas` bloquean con
  motivo explícito. `auditoria_disponible(cuenta=None)` por archivo.
- El cableado del harness con la cuenta de cada tarea llega en la Fase 4;
  aquí queda fijado el esquema (eso pedía el plan).

## 5. Modo dual (módulo `dual.py`)

Alcance corregido tras la revisión: el peligro real no es duplicar filas
de cola, es duplicar EJECUCIONES. Protocolo:

- **Latido con histéresis**: sonda cada 15 s; 3 fallos seguidos →
  `local`; 2 éxitos seguidos → `reconciliando`; reconciliación completa →
  `servidor`; un fallo en reconciliación → `local`. Un latido fallido no
  es una tarea fallida.
- **Por confirmar**: una tarea que ya salió al servidor NO se ejecuta en
  local durante el corte. Al reconciliar se pregunta al servidor:
  ejecutada → se marca hecha SIN ejecutarla; no ejecutada → se ejecuta en
  local exactamente una vez.
- La prueba de corte es automática (`test_dual.py`) y cuenta EJECUCIONES
  en ambos lados con un servidor falso con interruptor: el invariante es
  ejecuciones totales por tarea == 1, incluida la tarea en vuelo cuya
  confirmación se perdió.
- En el monolito: `_iniciar_vigia_dual()` arranca el vigía si la cuenta
  del carril es «ambas», expone `state["dual"]` y registra los cambios.
  La integración con la cola real (marcar en vuelo al enviar y reconciliar
  contra el servidor de verdad) llega con el harness de la Fase 4; el
  vigía y el protocolo ya son los definitivos.

## 6. UI — página «Cuentas»

Lista de cuentas (nombre, carril, conexión, estado, si hay secreto en la
bóveda), formulario de alta/edición (el id no se edita: es la clave de la
bóveda), campo de secreto siempre vacío y solo de escritura, guardado vía
`cuentas.guardar` (con su revisión: si otro proceso guardó antes, la UI lo
dice y no pisa). No existe NINGÚN endpoint HTTP que escriba en la bóveda:
la página vive dentro de la app de escritorio, con la misma confianza que
Ajustes → Claves.

## 7. Aceptación de la fase (todo verificado el 2026-11-16)

- 28 pruebas unitarias en verde: `test_cuentas.py` (16),
  `test_permission_layer.py` (9), `test_dual.py` (3).
- Migración real en el entorno de prueba: arranque 1 migra y el puente
  autentica con el valor de secret.txt leído de la bóveda; arranque 2 no
  remigra (idempotente).
- Aislamiento: `_sec_get("muse:segunda")` no devuelve jamás el de
  `principal` y viceversa (prueba unitaria + comprobación en la app real).
- Registrar la 2ª cuenta desde la UI no toca la 1ª (creada y secreto
  intactos) y su puente sigue autenticando.
- Centinela (I6): los secretos de prueba no aparecen en claro en ningún
  log ni en accounts.json; solo en la bóveda (en esta VM, el archivo de
  respaldo en base64 — es el almacén degradado, ver §3).
- Corte de red: invariante de ejecución única probado con contadores.
- Cuenta deshabilitada en un carril → su puente no autentica.

## 8. Reversión (procedimiento)

1. Cerrar la app.
2. Borrar `accounts.json` (y `accounts.json.lock` si quedara).
3. La app vuelve al comportamiento anterior: `secret.txt` y el token
   clásico mandan como antes de la fase. Nada más que deshacer: la
   migración no modificó `secret.txt`.
4. Opcional (limpieza): borrar de la bóveda las entradas `muse:*` y, en
   POSIX con archivo de respaldo, las claves `muse:*` de
   `credenciales.dpapi.json`; y los `audit-log-<cuenta>.json` junto a
   `audit-indice.json` si se quiere volver a un solo log.
