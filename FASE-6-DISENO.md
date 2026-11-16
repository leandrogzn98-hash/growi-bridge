# Fase 6 — Seguridad avanzada en Linux: intermediario de root y contenedores por proyecto

Diseño previo a la implementación, para revisión (Opus 5.5 vía MWAPI) y
como contrato de aceptación de la fase. Sigue el patrón de las Fases 1
a 5: módulos puros con lógica testeable + cableado fino en el monolito.
Rama: `fase-6-seguridad`. Es la última fase del plan.

Piezas nuevas: `privilegios.py` (el lado de la app: detección de vías,
lectura del catálogo, petición de acciones de sistema, vale de
confirmación e invocación), `contenedores.py` (detección del runtime,
ciclo de vida y envoltura de ejecución), la carpeta `intermediario/`
(el despachador `growi-rootbroker.py` — biblioteca estándar pura, se
instala como root fuera de la carpeta de la app —, su instalador para
el dueño y el catálogo de ejemplo) y campos nuevos en `proyectos.json`.
Todos los `.py` nuevos son LF; el monolito solo gana cableado fino,
conservando su CRLF.

La fase tiene dos mitades independientes que comparten filosofía
(fail-closed, confirmación humana por el circuito que ya existe,
auditoría por cuenta y degradación honesta):

1. **Intermediario de root.** Ninguna Muse conoce ni usa la clave de
   root — ni la del usuario con sudo — jamás. Lo privilegiado pasa por
   un despachador mínimo instalado como root que solo sabe ejecutar
   las acciones de una **lista blanca cerrada** (comandos concretos con
   argumentos acotados), cada una con su nivel de riesgo y su
   confirmación humana previa por el circuito existente
   (`permission-layer.py` + aprobaciones del monolito), y deja asiento
   en dos auditorías: la de la cuenta que lo pidió y la suya propia.
2. **Contenedores por proyecto.** Un contenedor por proyecto con los
   dos worktrees dentro (decisión registrada en la Fase 3, §9 de su
   diseño), como caja de arena **opcional y por proyecto** para
   ejecutar los motores. Las credenciales de git no entran nunca: la
   subida sigue siendo la puerta `subir` de la Fase 3, desde fuera.

Lo que esta fase NO hace: tocar Windows (el intermediario es Linux; en
Windows las acciones de sistema quedan «no disponibles» y se declara),
dar a ningún agente una shell privilegiada o un comando libre, ni
permitir editar la lista blanca desde la app (solo el dueño, con su
editor y su sudo, fuera de la app).

===

## 1. Principios

1. **El agente nunca toca la palanca.** Una acción privilegiada nace
   como declaración estructurada en una tarea (`sistema: [...]`, §3.2),
   la clasifica código, la confirma una persona y la ejecuta el
   despachador. No existe ningún camino «el motor ejecuta sudo»: el
   entorno del motor no gana ningún privilegio nuevo en esta fase.
2. **Lista blanca cerrada, argv exactos, nada de shell.** El
   despachador ejecuta con `execve` (vía `subprocess` con lista,
   `shell=False`) plantillas de argv cuyos huecos se rellenan con
   parámetros validados contra dominios cerrados (enumeraciones,
   prefijos de ruta, rangos). Un parámetro es siempre **un elemento
   entero** de argv: nunca se concatena dentro de un elemento ni se
   interpreta. Lo que no está en el catálogo no existe.
3. **La lista blanca vive fuera del alcance de la app.** El catálogo
   autoritativo es `/etc/growi-bridge/acciones.json`, propiedad de
   root, legible por todos (0644) y escribible solo por root. La app
   lo lee para mostrar y clasificar; ni la app ni un agente pueden
   ampliarlo. Ampliarlo es un acto del dueño en su terminal.
4. **La confirmación es la de siempre.** No se crea ningún circuito
   nuevo: las tareas `sistema` pasan por la puerta de aprobaciones del
   monolito según su nivel (tabla de `riesgos.json`), y la decisión
   humana se materializa en un registro del circuito de
   `permission-layer.py` (firma HMAC, origen humano), atado a la
   acción, a sus parámetros exactos y al catálogo vigente por hash.
   Ese registro es la **solicitud**; el vale que el despachador
   ejecuta es otra cosa: lo **sella el propio despachador** como root
   y vive solo en su dominio (`/var/lib/growi-bridge/vales/`,
   §3.5), porque la revisión de esta fase (§12, B1) demostró que un
   vale guardado en el dominio del usuario no es un control.
5. **El despachador no importa código del usuario.** Es un único
   archivo de biblioteca estándar, instalado en
   `/usr/local/libexec/growi-rootbroker.py`, propiedad de root. Si
   importara módulos de la carpeta de la app, quien escriba ahí
   tendría root: por eso reimplementa en 100 líneas lo poco que
   necesita (leer el catálogo, validar, verificar el vale, ejecutar,
   auditar) y no importa nada del proyecto.
6. **Fail-closed y degradación honesta.** Sin intermediario instalado,
   las acciones privilegiadas **no están disponibles** y las tareas
   que las piden esperan con ese motivo (no se ejecutan «sin» el paso
   privilegiado ni se salta el paso en silencio). Sin runtime de
   contenedores, un proyecto que lo exige no corre fuera «porque no
   haya» contenedor (§5.7). Todo lo no disponible se dice, en la UI y
   en el resultado de la tarea.
7. **Doble auditoría contrastable.** La app asienta la petición y el
   resultado en el audit-log de la cuenta (Fase 1). El despachador
   asienta lo que ejecutó de verdad en su propio log encadenado,
   propiedad de root. Si difieren, manda el del despachador y la
   diferencia es en sí misma una señal de alarma.
8. **Frontera declarada, sin maquillaje.** Como la bóveda de la
   Fase 1, esto es una frontera frente al **agente** (un proceso
   acotado por la capa de permisos: sin tools de firma, sin lectura
   arbitraria de archivos, sin forma de invocar
   `resolver_confirmacion`). La primera versión de este diseño decía
   que la fase «no empeora» esa frontera; la revisión (§12, B1) lo
   corrigió: en cuanto una confirmación firmada con
   `permission-secret.key` abre acciones de root, esa clave pasa a
   ser **material root-equivalente** y hay que tratarla como tal. Por
   eso el diseño final no ejecuta contra registros del dominio del
   usuario: el despachador verifica la solicitud firmada una sola
   vez, al **sellar**, y lo que ejecuta después es su propio vale,
   acuñado y consumido en el dominio de root (§3.5). Un proceso
   arbitrario del mismo usuario que leyera la clave podría fabricar
   una solicitud y pedir el sello por la vía sudo: sigue fuera del
   modelo de amenaza del proyecto (es el límite declarado desde la
   Fase 1), pero ya no puede reescribir, resucitar ni reutilizar un
   vale sellado, ni alargar su ventana. Y las acciones R3 exigen
   además un acto del dueño en su terminal (§3.5), fuera del alcance
   de cualquier proceso. Lo que la fase cierra de verdad: que el
   **motor** (el LLM y sus herramientas) no tenga ningún camino a
   root.

## 2. Mapa general

```
 TAREA (tipo "sistema" o con paso declarado)
   │  el runner la clasifica (riesgos.json + nivel del catálogo)
   ▼
 PUERTA DE APROBACIONES del monolito  ── el dueño aprueba en la app
   │  (R1/R2 por su canal permitido; R3 solo en la app)   │
   │                                                       ▼
   │                          permission-layer: SOLICITUD firmada
   │                          (tool "rootbroker", acción
   │                           sistema:<id>:<huella completa>)
   ▼  al recoger la tarea, el runner pide el SELLO:
 sudo -n /usr/local/libexec/growi-rootbroker.py --sellar
   │  el despachador (root) verifica la solicitud HMAC una vez y
   │  acuña SU vale en /var/lib/growi-bridge/vales/ (clave propia,
   │  nonce, tarea y aprobación ligados, ventana por nivel)
   ▼  y acto seguido, con el nonce del vale:
 privilegios.ejecutar(acción, params, cuenta, vale)
   │  petición JSON por stdin a:
   ▼
 sudo -n /usr/local/libexec/growi-rootbroker.py ejecutar
   │  (o pkexec al envoltorio de la acción, según su lanzador: §3.4;
   │   con euid 0 no hay lanzador: vía «root-local», §3.4)
   ▼
 DESPACHADOR (root): valida catálogo → dominios → llamante
   (SUDO_UID/PKEXEC_UID contra su config, o euid 0 en root-local) →
   vale PROPIO fresco y sin consumir (R3: + autorización del dueño
   en su terminal) → lo consume → asienta intención → ejecuta el
   argv exacto bajo systemd-run con timeout → asienta resultado →
   responde JSON por stdout
```

Y para los motores, cuando el proyecto lo pide:

```
 _f3_preparar (Fase 3) prepara worktree ──► prep gana «contenedor»
   │                                          (nombre, runtime, espejo)
   ▼
 el lanzamiento del motor se envuelve:  podman exec -w <worktree> …
   │  (el motor edita/compila/prueba dentro; sin credenciales,
   │   sin HOME, sin la carpeta de la app)
   ▼
 al cerrar la tarea: la subida sigue siendo git_trabajo.subir(),
   desde el anfitrión, con su escaneo de secretos (Fase 3)
```

## 3. El intermediario de root

### 3.1 Qué proceso es y con qué privilegios corre

El despachador **no es un demonio residente**: es un programa que se
invoca una vez por acción y muere al terminar. Esto es deliberado:

- Sin superficie permanente: no escucha en ningún puerto ni socket;
  entre acciones no hay nada privilegiado corriendo.
- El privilegio dura lo que dura la acción (segundos), no la sesión.
- El modelo de invocación es el clásico «sudo a un ayudante propiedad
  de root»: `sudo` (o `pkexec`) eleva **ese binario concreto**, y el
  binario es la lista blanca hecha código.

Ficha del despachador:

| Aspecto | Decisión |
|---|---|
| Archivo | `/usr/local/libexec/growi-rootbroker.py`, dueño root, 0755 |
| Lenguaje | Python 3, **solo biblioteca estándar**, sin imports del proyecto |
| Configuración propia | `/etc/growi-bridge/intermediario.json` (root, **0600**): rutas del registro de confirmaciones y de la clave HMAC, uid del dueño autorizado, ventanas de frescura por nivel, rutas de su log, de sus vales y de su clave de vales. Las rutas que fija hacia su propio dominio (`/var/lib/growi-bridge/…`) no pueden apuntar a nada escribible por el uid del dueño: si apuntan, `no_configurado` |
| Catálogo | `/etc/growi-bridge/acciones.json` (root, 0644): §3.3 |
| Sus vales | `/var/lib/growi-bridge/vales/` (root, 0700; ficheros 0600), con clave propia `/var/lib/growi-bridge/vale.key` (root, 0400): §3.5 |
| Autorizaciones R3 | `/var/lib/growi-bridge/autorizaciones/` (root, 0700): las crea el subcomando `autorizar`, que el dueño ejecuta en su terminal (§3.5) |
| Su log | `/var/log/growi-bridge/rootbroker.jsonl` (root, 0600, append-only, cadena de hashes propia con ancla: §3.7) |
| Subcomandos | sin subcomando = ejecutar (petición por stdin); `--sellar` (acuña el vale desde la solicitud firmada), `autorizar` (acto del dueño para R3), `sonda` (presencia sin ejecutar), `--validar-catalogo`, `--verificar-log` |
| Entrada | JSON por **stdin** (nunca un archivo en ruta del usuario, nunca argumentos de línea de comandos con datos) |
| Salida | JSON por stdout: `{ok, rc, salida, duracion_s, motivo}`; la salida del comando va truncada (§3.6) |
| Entorno al ejecutar | Mínimo y fijo: `PATH` de sistema, `LANG=C.UTF-8`, sin variables del llamante (sudo ya hace `env_reset`; el despachador además construye el entorno desde cero) |
| cwd al ejecutar | `/` |
| stdin del comando | `DEVNULL`, salvo acciones que lo declaren (ninguna del catálogo inicial) |

La configuración del despachador vive en `/etc` y **no** en la
petición: qué registro de confirmaciones se acepta y qué clave lo
firma lo decide el dueño al instalar, no quien llama. Si
`intermediario.json` falta o no valida, el despachador no ejecuta
nada y responde `no_configurado`.

El despachador **no lee ninguna variable de entorno para
configurarse** (§12, B14): ni rutas, ni catálogo, ni ventanas. Las
rutas de `/etc` y `/var` están fijas en el código del binario
instalado. Su única entrada del entorno son `SUDO_UID`/`SUDO_USER`
(los pone sudo) o `PKEXEC_UID` (lo pone pkexec), que usa para
verificar al llamante (§3.4); en la vía «root-local» (§3.4) verifica
el euid directamente. La lógica interna sí acepta las rutas como
parámetros — así la prueban las unitarias con directorios temporales
—, pero el punto de entrada instalado las pasa fijas y ningún
entorno puede cambiarlas: una prueba física lo verifica
(`GROWI_BROKER_ETC=… sonda` no cambia nada, §9.2).

### 3.2 Cómo nace una petición: la tarea `sistema`

Una acción privilegiada solo puede nacer declarada en una tarea, de
dos formas:

- **Tarea dedicada**: `{"tipo": "sistema", "sistema": [...]}` — no
  lleva motor; el runner ejecuta las acciones en orden y se detiene
  en el primer fallo. Es la forma normal: «reinicia el servicio del
  juego», «monta el disco de respaldo y luego…» (el resto del encargo
  va en tareas hermanas del mismo encargo de la Fase 4, con su raíz
  de correlación).
- **Sin forma libre**: no hay campo «comando» ni «shell» en ninguna
  parte del esquema. Una tarea que traiga claves desconocidas en
  `sistema` se rechaza entera en la validación, como hacen las demás
  validaciones del proyecto. Las tareas `sistema` no preparan repo:
  no toman alquileres ni worktrees de la Fase 3, así que su espera
  (sin intermediario, vale caducado, lo que sea) no retiene ningún
  recurso de otra fase.

Cada elemento de `sistema` es `{"accion": "<id del catálogo>",
"params": {...}}` con los parámetros por nombre. Ejemplo:

```json
{"tipo": "sistema",
 "prompt": "Reinicia el servidor del juego para aplicar el cambio",
 "sistema": [{"accion": "reiniciar-servicio",
              "params": {"servicio": "servidor-juego"}}]}
```

El `prompt` sigue existiendo (lo lee el dueño al aprobar y queda en
la auditoría), pero **no manda**: lo que se ejecuta sale solo del
catálogo y los parámetros validados. Si el prompt dice otra cosa que
los parámetros, el dueño lo ve al confirmar (la confirmación muestra
la descripción construida desde el catálogo y los parámetros, §3.5,
no el prompt).

Clasificación y niveles: el runner trata `sistema` como un tipo de
acción declarada más de `riesgos.json` (las acciones declaradas son
«lo más fiable» según la propia tabla), con dos reglas propias:

- El nivel de la tarea es el **mayor** de los niveles de sus acciones
  según el catálogo (el catálogo manda sobre la tabla genérica: una
  acción marcada R3 en el catálogo es R3 aunque la tabla dijera
  menos; y al revés no: la tabla puede subir, nunca bajar el nivel
  del catálogo — se toma el máximo de ambos).
- Si alguna acción no existe en el catálogo, la tarea se
  **rechaza en la validación** con el motivo `accion_desconocida:
  <id>` (la app relee el catálogo antes de validar). La primera
  versión de este diseño la dejaba «en espera de decisión»; la
  revisión (§12, B4) lo corrigió: sin entrada en el catálogo no hay
  nivel, sin nivel no hay clasificación ni puerta, y
  `decidir_aprobacion` no tendría nada que decidir — la tarea
  colgaría para siempre (fail-hang, no fail-closed). Por la misma
  regla se rechazan en validación una lista `sistema` vacía y un
  elemento sin `accion`.

### 3.3 El catálogo de acciones (`acciones.json`)

Esquema v1:

```json
{
  "version": 1,
  "acciones": [
    {
      "id": "reiniciar-servicio",
      "descripcion": "Reiniciar el servicio «{servicio}»",
      "argv": ["/usr/bin/systemctl", "restart", "{servicio}"],
      "params": {
        "servicio": {"tipo": "enum",
                     "valores": ["servidor-juego"]}
      },
      "nivel": "R2",
      "lanzador": "sudoers",
      "timeout_s": 120
    }
  ]
}
```

Reglas del esquema (las valida el instalador al escribir, la app al
leer y el despachador en cada arranque: un catálogo que no valida
**inhabilita todo**, no abre nada):

- `id`: `[a-z0-9-]{2,48}`, único. Es el nombre que las tareas usan.
- `argv`: lista no vacía de cadenas. La plantilla se **parsea una
  vez** y cada elemento es exactamente una de dos cosas (§12, B5):
  un **literal** sin `{`, sin `}` y sin caracteres de shell
  (`` *?$`\"'\\|&;<>() `` ni caracteres de control), o **un único
  hueco** `{nombre}` declarado en `params`. Nada de huecos pegados
  a texto ni a otro hueco (`"--config={ruta}"` y `"{a}{b}"` no
  valen): si un comando necesita un flag con valor, se usan dos
  elementos (`"--config", "{ruta}"`). El primer elemento,
  `argv[0]`, es siempre un literal: ruta absoluta a un ejecutable
  propiedad de root y no escribible por otros (el despachador lo
  comprueba con `stat` al validar el catálogo; un `argv[0]`
  parametrizable apuntaría a `/bin/sh` y se acabó la lista blanca).
- `params`: cada hueco de `argv` tiene exactamente una entrada, y
  cada entrada tiene un `tipo` con su dominio:
  - `enum`: `valores` (lista cerrada de cadenas, 1–64, cada una
    `[A-Za-z0-9._-]{1,64}`). Es el tipo preferido: servicios,
    paquetes y nombres salen de aquí.
  - `ruta`: `prefijos` (lista de rutas absolutas canónicas): el
    valor, canonicalizado con `realpath`, debe caer dentro de un
    prefijo y no contener `..` tras canonicalizar. Los valores con
    caracteres de control se rechazan (un salto de línea en una ruta
    acabaría dentro de la descripción que lee el dueño). Para
    desmontar.
  - `dispositivo`: para el origen de un montaje (§12, I2):
    `realpath` sobre `/dev/disk/by-label/<etiqueta>` escapaba del
    prefijo por diseño (resuelve a `/dev/sdN`), así que este tipo
    valida la **etiqueta** (`[A-Za-z0-9._-]{1,32}`) sin resolver, el
    despachador construye la ruta `by-label` él mismo y además
    exige que el destino resuelto case con
    `^/dev/(sd|hd|vd|nvme[0-9]n[0-9]|mmcblk[0-9])[a-z0-9]*$`.
  - `entero`: `min`/`max`, con forma canónica (§12, I1): el valor
    llega como cadena `^[0-9]{1,9}$` (nada de `+1`, `007`, espacios
    ni dígitos Unicode, que `int()` aceptaría y harían que lo
    ejecutado no fuera lo hasheado) y se usa `str(int(v))` tanto
    para el hash del vale como para argv. Para puertos de escucha
    internos o tamaños, si algún día hace falta.
  - `nombre`: regex completa fijada en el propio tipo
    (`^[a-z0-9][a-z0-9-]{0,62}$`): nombres de unidad, de contenedor
    o de lo que no merezca un enum porque lo crea el propio sistema
    (p. ej. unidades temporales). Se usa con cuentagotas: el enum
    siempre es preferible.
- `nivel`: `R1` | `R2` | `R3` — el vocabulario de `riesgos.json`.
  Fija la puerta de aprobación y la ventana de frescura del vale
  (§3.5). No hay acciones R0: si no necesita root, no pasa por aquí.
- `lanzador`: `sudoers` | `polkit` (§3.4). Por defecto, `sudoers`.
  La primera versión admitía `ambos`; la revisión (§12, I4) lo
  quitó: no fijaba orden ni qué pasa si el primero falla, y una
  acción con dos vías es una acción cuya vía real nadie puede
  declarar.
- **Invariante de contenido** (§12, B7): los dominios acotan argv,
  no lo que el comando *consume*. Ninguna acción puede interpretar
  contenido del usuario como código o configuración (intérpretes,
  hooks, `cp`/`chown -R` sobre rutas del usuario, paquetes
  construidos por el llamante…), y ningún parámetro `ruta` puede
  apuntar bajo árboles escribibles por el usuario (su HOME, la
  carpeta de la app, los worktrees) salvo los puntos de montaje
  declarados, en los que el despachador rechaza si **algún
  componente del camino es un symlink** (la única indirección
  permitida es la del tipo `dispositivo`, validada aparte).
  `instalar-paquete` no viola el invariante — los scripts de un
  paquete firmado de la distro corren como root por definición de
  apt — pero consta en su fila: por eso su dominio es un enum
  cerrado y su nivel R2.
- `timeout_s`: 1–600. El despachador mata el árbol al vencer (§3.6).
- `descripcion`: la frase que el dueño lee al confirmar, con los
  huecos ya rellenados. Se construye en la app desde el catálogo y
  los parámetros validados — nunca desde el prompt de la tarea — y
  escapando cualquier carácter de control que un valor pudiera
  traer (§12, I2): la descripción es texto que una persona lee para
  decidir, no un canal para colarle escapes ANSI.

**Catálogo inicial** (el que instala el instalador, con los dominios
de ejemplo que el dueño ajusta a su máquina editando el archivo como
root; los valores de ejemplo son inofensivos a propósito):

| id | argv | dominio | nivel | porqué |
|---|---|---|---|---|
| `reiniciar-servicio` | `systemctl restart {servicio}` | enum de servicios suyos (ej.: su servidor de juego) | R2 | el caso típico: la Muse desplegó y hay que reiniciar el servicio |
| `instalar-paquete` | `apt-get install -y {paquete}` | enum de paquetes (ej.: `ffmpeg`, `imagemagick`) | R2 | dependencias concretas que un proyecto necesita (los scripts del paquete corren como root: es apt, y por eso el enum es cerrado) |
| `montar` | `mount {dispositivo} {punto}` | `dispositivo` de tipo `dispositivo` (etiqueta) y `punto` ruta con prefijos `/mnt/`, `/media/` | R2 | montar el disco de respaldo antes de copiar |
| `desmontar` | `umount {punto}` | rutas con prefijos (`/mnt/`, `/media/`) | R2 | la pareja de la anterior |
| `reiniciar-equipo` | `systemctl reboot` | sin parámetros | R3 | su PC es también su servidor casero: reiniciarlo desde fuera es el caso extremo, solo en app y con vale muy fresco |
| `apagar-equipo` | `systemctl poweroff` | sin parámetros | R3 | igual que la anterior |

Y lo que **no** entra, dicho en el propio diseño para que conste:
`apt-get upgrade` o `update` genéricos (efectos no acotados),
`systemctl` con la unidad libre (eso es una shell con pasos extra),
cualquier acción cuyo argv incluya un intérprete (`sh`, `bash`,
`python`, `env`…) como ejecutable o como parámetro, y montar con
opciones libres (`-o` con datos del llamante convierte `mount` en
una puerta giratoria). Si el dueño quiere una de esas, la hace él en
su terminal: el intermediario no está para eso.

### 3.4 Los lanzadores: sudoers preferente, polkit como alternativa

El despachador es el mismo binario en las dos vías; lo que cambia es
quién lo eleva y cómo comprueba el despachador que la elevación es
la prevista.

**Vía sudoers (preferente).** El instalador escribe
`/etc/sudoers.d/growi-bridge` (0440, validado con `visudo -cf` antes
de darlo por bueno) con una sola regla:

```
<usuario> ALL=(root) NOPASSWD: /usr/local/libexec/growi-rootbroker.py
```

La regla fija el **binario exacto** y nada más: la granularidad por
acción vive en el despachador y su catálogo (ambos propiedad de
root), que es donde puede expresarse con dominios de verdad. sudoers
no puede expresar «uno de estos cinco paquetes» sin comodines, y un
comodín en sudoers sobre argumentos es una puerta conocida
(`apt-get install *` permitiría flags extra). Por eso el diseño
elige conscientemente: sudoers acota el *programa*, el despachador
acota los *argumentos*, y las dos capas son propiedad de root. La
app invoca `sudo -n -- /usr/local/libexec/growi-rootbroker.py` con
la petición por stdin; `-n` garantiza que sudo nunca pedirá una
contraseña por la app (si la regla falta, falla al instante: eso es
la sonda, §6.3).

El despachador, al arrancar, verifica su llamante: exige que
`SUDO_UID` exista y coincida con el uid del dueño fijado en
`intermediario.json`, y que su proceso se esté ejecutando como
root. Sin `SUDO_UID` (ni `PKEXEC_UID` en la otra vía) no hay
ejecución: alguien lo lanzó «a mano» como root y eso no es el
circuito (el dueño no necesita al despachador para nada: tiene su
terminal).

Y el factor humano de esta vía, declarado sin maquillaje (§12,
B2): `NOPASSWD` significa que cualquier proceso del uid del dueño
puede *invocar* al despachador sin nadie delante. Lo que lo separa
de «root para cualquier proceso» es el vale: sin un vale sellado
(§3.5), la invocación no ejecuta nada. El factor humano de las
acciones R1/R2 por esta vía es el circuito de aprobaciones — la
decisión del dueño en la app o su canal permitido, tras la cual la
máquina ejecuta sin él delante —, exactamente el mismo modelo que
el resto de Growi (una aprobación R2 por tipo dura 24 h y las
tareas corren desatendidas). Lo que esta vía **no** vale es para
R3: una acción R3 nunca se ejecuta solo con sudoers+vale; exige
además el acto del dueño en su terminal o la vía polkit con
`auth_admin` (§3.5).

**Vía root-local.** Si la propia app corre con euid 0 — la VM de
Lu, un contenedor del propio Growi, una instalación deliberada
como root — sudo no aporta nada: `sudo -n` tiene éxito sin regla
alguna y `SUDO_UID` sería 0. En ese caso la vía es `root-local`
(§12, B12): el runner invoca al despachador directamente, sin
sudo, y el despachador exige euid 0 y que `intermediario.json`
declare `uid_dueno: 0`. La sonda sudoers solo se da por válida si
la respuesta trae `uid_origen != 0` (si trae 0, lo que hay es
root-local, no una regla). La vía queda anotada en cada resultado:
nadie debe creer que hay una regla de sudoers donde lo que hay es
«la app ya era root».

**Vía polkit.** Para las acciones cuyo `lanzador` sea `polkit` (o
cuando el dueño prefiera que ciertas acciones pidan su contraseña
estando delante), el instalador deja además
`/usr/share/polkit-1/actions/org.growi.bridge.policy` con **una
acción por id del catálogo** (`org.growi.bridge.<id>`). La
anotación de polkit se asocia al programa que pkexec ejecuta, así
que para tener una acción polkit **por acción del catálogo** el
instalador genera un envoltorio por acción
(`/usr/local/libexec/growi-broker-<id>`, root, 0755) y cada
`.policy` apunta a su envoltorio con
`org.freedesktop.policykit.exec.path`. La invocación es directa:
la app ejecuta `pkexec /usr/local/libexec/growi-broker-<id>` con
la petición por stdin (§12, B6: la primera versión metía un
ayudante genérico que lanzaba pkexec contra el despachador, y
entonces `--accion-fija` lo elegía el llamante y no polkit — una
contradicción). El envoltorio lleva el id **literal dentro**,
ignora cualquier argumento del llamante (no acepta ninguno) y hace
`exec` del despachador con `--accion-fija <id>`; el despachador
con `--accion-fija` solo acepta peticiones de esa acción y exige
`PKEXEC_UID` = uid del dueño. polkit se
configura en el `.policy` con `auth_admin` (el dueño teclea SU
contraseña en el diálogo del sistema, delante de la PC) para las de
nivel R3 y `auth_admin_keep` para R2, según fije el dueño al
instalar; el diseño no esconde el coste: **la vía polkit exige
presencia física en el momento de ejecutar**, así que no sirve para
el relevo desde el teléfono — sirve como endurecimiento local para
las acciones que el dueño marque «solo estando yo delante». En ese
caso la confirmación en la app sigue existiendo (la puerta de
aprobaciones manda), y polkit es la segunda llave, no un sustituto.
Si no hay agente de autenticación ni sesión gráfica, pkexec falla y
la acción queda no disponible por esa vía: declarado, no reintentado
en silencio.

**Sin ninguna vía**: no hay tercera opción automática. En particular
la app **nunca** ejecuta `sudo` a secas esperando que el dueño haya
dejado `NOPASSWD: ALL` ni nada parecido: si la sonda no responde,
no hay intermediario (§6.3).

### 3.5 La confirmación: puerta de aprobaciones + vale firmado

Dos piezas existentes, articuladas sin crear un circuito nuevo:

1. **La puerta** (la de siempre): la tarea `sistema` se clasifica
   con su nivel (§3.2) y pasa por la puerta de aprobaciones del
   monolito como cualquier tarea con acciones declaradas: R1 según
   la política del dueño (puede no preguntar si su ajuste lo dice
   para ese tipo), R2 por acción exacta, R3 **solo en la app**
   (un pedido R3 por canal remoto se deniega al instante, como ya
   hace el circuito). Sin aprobación vigente, el runner ni siquiera
   construye la petición.
2. **La solicitud firmada** (lo que la puerta deja): cuando una
   aprobación de una tarea `sistema` queda aprobada — por la app, la
   consola o un canal permitido, siempre a través de
   `decidir_aprobacion`, que es la única entrada de decisiones — el
   monolito crea en `permission-layer.py` un registro de confirmación
   ya aprobado por cada acción de la tarea, con:
   - `tool = "rootbroker"`,
   - `accion = "sistema:<id>:<huella>"`, donde `<huella>` son los
     primeros 16 hex del SHA-256 de un JSON canónico (claves
     ordenadas, separadores `(",", ":")`, UTF-8) que cubre **la
     huella del archivo de catálogo, el id, el nivel, el argv ya
     resuelto y los parámetros validados**. La primera versión
     hasheaba solo los parámetros; la revisión (§12, B3) demostró
     el TOCTOU: la app clasifica con su lectura del catálogo y el
     despachador ejecutaría con la suya, y una edición intermedia
     del dueño cambiaría el argv o el nivel bajo una aprobación ya
     dada. Con la huella completa, cualquier divergencia se detecta
     (§3.5, paso de sellado) y nada se ejecuta.
   - `sesion` = la sesión del runner que procesa la tarea,
   - firmado con la HMAC de siempre (`_firma` de
     `permission-layer.py`), con un campo extra `via` que anota por
     dónde se aprobó (`app`, `consola`, el canal…). `via` es
     **informativo**: queda fuera del payload que firma `_firma` en
     el código actual, así que ninguna regla de seguridad descansa
     sobre él (§12, I7) — la política de canales la impone
     `decidir_aprobacion`, que es quien crea la solicitud, y la de
     R3 la impone el acto en terminal del paso 4.

   Para esto `permission-layer.py` gana UNA función nueva,
   `registrar_vale_sistema(sesion, accion_id, huella, via)`, que es
   código del monolito/de la capa — **no una tool del agente**: el
   harness no la ve, ningún motor puede llamarla, y solo se invoca
   desde el camino que sigue a una decisión humana ya registrada en
   el circuito de aprobaciones. `resolver_confirmacion` sigue siendo
   la única vía para las confirmaciones que nacen en el harness, y
   su regla (origen `app-humano`/`consola-humano`) no se toca. La
   solicitud no sustituye a la puerta: es el recibo firmado que la
   puerta deja. Y — esto es lo que cambió la revisión — **la
   solicitud no es el vale**: vive en el dominio del usuario, y un
   token de ejecución de root no puede vivir ahí (§12, B1).

3. **El sello** (el vale de verdad, en el dominio de root): al
   recoger la tarea ya aprobada, el runner invoca al despachador
   con `--sellar` (por la vía de la acción) pasándole por stdin el
   id de la solicitud, el `tarea_id` y el `approval_id`. El
   despachador, ya como root:
   1. verifica el llamante (§3.4) y que la acción existe;
   2. lee el `confirmaciones.json` fijado por su configuración y
      exige el registro exacto (`tool="rootbroker"`, la `accion`
      con la huella completa), en estado `aprobada`, con la **firma
      HMAC válida** (la clave es `permission-secret.key`, cuya ruta
      fija su configuración: la lee root, nunca viaja en la
      petición) y dentro de la vigencia de la capa (8 h);
   3. **recalcula la huella con su propio catálogo**: si la huella
      de la solicitud no coincide con la que sale de su catálogo y
      los parámetros de la petición, responde `catalogo_divergente`
      y no sella nada (§8) — así una edición del catálogo entre la
      aprobación y la ejecución invalida lo aprobado en vez de
      ejecutarlo cambiado;
   4. acuña el vale: un fichero
      `/var/lib/growi-bridge/vales/<nonce>.json` (0600) firmado con
      **su propia clave** (`vale.key`, 0400, que no sale de root)
      con `{accion, huella, argv_resuelto, tarea_id, approval_id,
      uid_dueno, sellado_wall, sellado_mono, boot_id,
      ventana_s}`. La ventana por nivel — R1: 60 min, R2: 15 min,
      R3: 5 min; el dueño puede acortarlas en `intermediario.json`,
      nunca alargarlas más allá de los topes 120/30/10 — **cuenta
      desde el sello** (§12, I5): como el sello se pide al recoger
      la tarea, la ventana cubre el paso de ejecutar, no la espera
      en la cola ni un `aplazar` del dueño, que era la colisión de
      la primera versión.
   5. devuelve el `nonce`. La solicitud de `permission-layer` queda
      como estaba (es el registro auditable de la decisión); el
      vale es un token aparte, efímero y de root.

4. **La autorización R3**: para acciones R3, el vale no basta. El
   despachador exige además una autorización en su dominio creada
   por el subcomando `autorizar`, que el dueño ejecuta **en su
   terminal**: `sudo /usr/local/libexec/growi-rootbroker.py
   autorizar <huella>` (sudo interactivo, con su contraseña, sin
   `-n`: es un acto deliberado delante de la máquina). El
   subcomando anota `/var/lib/growi-bridge/autorizaciones/<huella>`
   con la hora; vale 5 minutos y se consume con el vale. La vía
   polkit con `auth_admin` sustituye a este acto (pkexec ya pidió
   la contraseña delante de la PC). Así R3 tiene dos factores
   reales: la aprobación en la app y un acto local que ningún
   proceso del uid puede fabricar.

El despachador verifica al **ejecutar**, en este orden (de barato a
caro, todo fail-closed):

1. La petición está bien formada y la acción existe en el catálogo.
2. Los parámetros validan contra el dominio y el argv resuelto
   coincide con el del vale.
3. El llamante es el previsto (`SUDO_UID`/`PKEXEC_UID` = el uid del
   dueño, §3.4; o euid 0 en root-local).
4. El vale existe en su directorio, su MAC (clave propia) verifica,
   liga esta acción, esta huella, esta tarea y esta aprobación, y
   el llamante es el uid del vale.
5. **Frescura con doble reloj** (§12, I20): el transcurrido se
   calcula por reloj de pared y por `CLOCK_MONOTONIC`+`boot_id`
   guardados al sellar, y manda el **mayor**; un salto de pared
   hacia atrás no resucita vales. Si venció, no se ejecuta: la
   tarea vuelve a `esperando_aprobacion` con el motivo
   `vale_caducado` y hace falta una aprobación nueva (que sellará
   un vale nuevo). No hay reapertura silenciosa ni reintentos del
   paso privilegiado: cada aprobación sella exactamente un vale por
   acción.
6. Si la acción es R3, la autorización del paso 4 existe, es
   fresca y liga la misma huella.
7. Toma el lock global del despachador (`flock` sobre
   `/run/growi-rootbroker.lock`, espera máxima 10 s): si otro
   despacho está en curso, responde `ocupado` y la tarea vuelve a
   espera **con el vale intacto** (§12, I17).
8. **Consumo en la invocación**: ya con el lock, el vale se mueve
   atómicamente a `vales/consumidos/` (rename dentro del mismo
   directorio de root) **antes** de ejecutar. Un `rc != 0` del
   comando consume igual (§12, I17): el vale ampara un intento, no
   un éxito. Una segunda ejecución con el mismo nonce no encuentra
   el vale: rechazada. Como el nonce es por aprobación, dos
   aprobaciones legítimas de la misma acción con los mismos
   parámetros sellan dos vales distintos y ambos funcionan — el
   un-solo-uso ata la aprobación, no la huella, que era el defecto
   simétrico de la primera versión. Acto seguido asienta la
   **intención** en su log (§3.7: si no puede asentar, no ejecuta)
   y ejecuta (§3.6).

### 3.6 Ejecución: timeouts, salida y señales

- El comando se ejecuta bajo una **unidad transitoria de
  systemd**: `systemd-run --quiet --property=RuntimeMaxSec=<timeout_s>
  --property=KillMode=control-group -- <argv>` con stdin `DEVNULL`,
  entorno mínimo fijo y cwd `/` (§12, I8: un `killpg` sobre el grupo
  de procesos deja vivos a los hijos que hacen `setsid` o se
  demonizan; el cgroup no). El instalador sondea `systemd-run` de
  verdad al instalar (el precedente es `sonda_systemd()` de la
  Fase 4); en un sistema sin systemd el despachador cae a
  `start_new_session=True` + matar el grupo y lo **declara** en el
  resultado (`ejecutor: "grupo"`, más débil, frente a
  `ejecutor: "cgroup"`).
- La salida (stdout+stderr por separado) se devuelve truncada a
  64 KB por flujo, con la marca `…[truncada]`; el código de salida
  se devuelve tal cual. Un `rc != 0` no es un error del
  intermediario: es el resultado de la acción, y la tarea lo recibe
  como tal (fallida con el motivo del comando, como cualquier tarea
  cuyo motor falla).
- El despachador tiene su propio tope global: ninguna acción puede
  declarar más de 600 s, y el despachador muere por su cuenta a los
  660 s (un `alarm` interno) para no quedarse colgado como root.
- Un timeout sobre `instalar-paquete` merece una línea propia:
  matar a apt a mitad puede dejar el sistema de paquetes a mitad de
  transacción (el lock de dpkg se libera al morir el proceso, pero
  el paquete puede quedar por configurar). El resultado de ese
  timeout incluye el aviso «revisa el estado de paquetes antes de
  reintentar» y la tarea no se reintenta sola: reinstalar es otra
  aprobación.
- Nada de lo que el comando imprima puede contener la clave HMAC ni
  el contenido del registro de confirmaciones: el despachador nunca
  los pasa al entorno ni a los argumentos (la verificación ocurre en
  su memoria).

### 3.7 Auditoría del despachador

`/var/log/growi-bridge/rootbroker.jsonl`: una línea JSON por evento
(`peticion_recibida` con el resultado de cada validación,
`intencion` antes de ejecutar, `ejecutada`, `rechazada` con el
motivo, `vale_sellado`, `vale_consumido`, `autorizada_r3`), con
`prev_hash`/`hash` encadenados con el mismo esquema que
`permission-layer.py` (SHA-256 sobre el JSON canónico) y estos
campos: hora (de pared y monotónica, §3.5), `sudo_user`, acción,
huella (los parámetros van en claro: son datos del dueño y el log
es 0600 de root; lo que nunca va es ningún secreto), rc y duración.

Tres reglas que la revisión exigió (§12, I6):

- **Concurrencia**: el despachador no es un demonio y dos
  invocaciones podrían bifurcar la cadena; por eso leer-la-cola y
  añadir va bajo el mismo `flock` global de §3.5, y la rotación
  **no** la hace `logrotate` (rompería la cadena entre la lectura y
  el append): la hace el propio despachador, bajo el flock, al
  pasar de 10 MB — renombra a `.1` y abre el fichero nuevo con una
  primera línea que anota la cabeza y el conteo del anterior. El
  ancla vive en `/var/lib/growi-bridge/rootbroker-ancla.json`
  (root), actualizada en cada rotación, y `--verificar-log`
  verifica la cadena interna y la contrasta con el ancla.
- **Si no se puede auditar, no se ejecuta** (la regla de la Fase 1,
  también de este lado): si el asiento de `intencion` falla (disco
  lleno, permisos), el despachador responde `auditoria_no_disponible`
  y no ejecuta nada. La app hace lo simétrico: asienta su intención
  en el log de la cuenta **antes** de invocar al despachador.

La app, por su parte, asienta en el audit-log **de la cuenta** que
pidió la acción (Fase 1): la petición (`accion="sistema:<id>"`,
resultado `ok`/`bloqueado` con el motivo del despachador) — con lo
que la cadena de la cuenta y la del despachador se pueden cruzar por
hora y huella. La aceptación del plan («la cadena de auditoría se
verifica íntegra tras un reinicio») se cumple verificando las dos:
la de la app con su `--verificar-log` de siempre y la del
despachador con el suyo, tras reiniciar la app y tras reiniciar la
PC (el log del despachador no depende de la app para nada).

### 3.8 Degradación: qué pasa sin intermediario

`privilegios.disponible()` (§6.3) devuelve la vía y el catálogo
visible, o «ninguna». Con «ninguna»:

- La UI muestra «Intermediario de root: no instalado» con el botón
  «Ver cómo se instala» (abre las instrucciones y la ruta del
  instalador: **la app no lo instala ni pide contraseñas jamás**).
- Una tarea `sistema` no se ejecuta ni se marca fallida: queda en
  espera de decisión con el motivo «intermediario no instalado», y
  si el dueño lo instala después, la misma tarea puede seguir su
  curso (la aprobación y el vale se gestionan entonces).
- La misma espera, con su motivo propio (§8), cubre los demás
  «ahora no» del circuito: `catalogo_divergente` (el catálogo
  cambió tras la aprobación), `vale_caducado` (toca reaprobar),
  `ocupado` (otro despacho en curso) y `reloj` (salto de reloj
  detectado). En ninguno se gasta la aprobación salvo en
  `vale_caducado`, que por definición la consume.
- Ninguna otra cosa del programa cambia: sin acciones de sistema,
  esta mitad de la fase es invisible.

### 3.9 Último recurso: sin clave en la bóveda (solo especificado)

La primera versión de esta sección especificaba guardar la
contraseña del usuario en la bóveda (`sistema:sudo`) para que un
despachador residente la usara con `sudo -S`. La revisión (§12, B8)
demostró que era **inviable y engañoso a la vez**: un servicio que
ya corre como root no eleva nada con sudo (sudo no le pide
contraseña), y la contraseña guardada sería legible por cualquier
proceso del mismo uid vía `_sec_get` — que la Fase 1 declaró que no
es una frontera —, así que el «último recurso» no resolvía el caso
que decía resolver y sí creaba un secreto con poder total durmiendo
en el almacén. **La variante de la clave queda tachada**: en este
diseño no hay ninguna contraseña en la bóveda para el intermediario,
nunca.

Lo que queda especificado, **no implementado**, como último recurso
para una máquina donde ni sudoers ni polkit sirvan:

- Un **servicio de sistema** instalado por el dueño (unit de
  systemd, socket-activado, root) que ejecuta el mismo despachador
  y el mismo catálogo, recibiendo las peticiones por un socket Unix
  en `/run/growi-bridge/broker.sock` (directorio 0750 root:grupo
  del dueño). El llamante se verifica por `SO_PEERCRED` (uid del
  extremo, lo pone el kernel: no es un campo del JSON ni una
  variable de entorno), y el sello y el vale son los de §3.5 sin
  cambios — el servicio no necesita ninguna contraseña porque ya
  es root, que era el punto que la variante tachada no entendía.
- Por qué sigue siendo el último recurso: introduce el único
  proceso privilegiado **residente** del diseño (superficie
  permanente, hay que mantenerlo y vigilarlo), cuando las vías de
  §3.4 no guardan ningún secreto ni dejan nada corriendo.
- Mientras el dueño no lo pida, esta variante no existe en el
  código: ni el servicio ni el socket. La alternativa mientras
  tanto es la de siempre: el dueño ejecuta a mano en su terminal el
  comando que la tarea necesitaba (la tarea deja el motivo exacto
  en su resultado).

## 4. (Reservado)

*Sección intencionadamente breve: la numeración sigue con los
contenedores en el §5, como en el resto del documento.*

## 5. Contenedores por proyecto

### 5.1 Qué se decidió ya y qué decide este diseño

La Fase 3 (su §9) registró la decisión: **un contenedor por
proyecto, con los dos worktrees dentro**, y `"contenedores":
"por_cuenta"` en `proyectos.json` como opt-in para código no
confiable. Este diseño la implementa sin reabrirla, y decide lo
demás: runtime, montajes, red, ciclo de vida e integración con la
preparación de la Fase 3.

### 5.2 Runtime: Podman preferente, Docker si es lo que hay

`contenedores.detectar_runtime()` sondea en este orden:

1. **Podman** (`podman` en el PATH + `podman info` responde en
   ≤ 5 s): preferente porque es rootless y sin demonio — el
   contenedor corre como el propio usuario, que es exactamente la
   frontera que queremos (dentro parece root; fuera es el dueño).
2. **Docker** (`docker` + `docker info`): si el demonio responde y
   el usuario puede usarlo (grupo `docker` o rootless). Se declara
   el matiz conocido: acceso al socket de Docker equivale en la
   práctica a root en el anfitrión; por eso el diseño lo acepta
   como runtime pero la UI lo dice al mostrar la vía («Docker: el
   socket da acceso de root al anfitrión; Podman rootless no»).
3. Ninguno → no disponible, y la fase degrada (§5.7).

La sonda es real (ejecuta `info`), como la sonda de `systemd-run`
de `recursos.py` en la Fase 4: estar en el PATH no basta. El
resultado se cachea por proceso y se re-sondea si una operación
falla con «runtime caído».

Un matiz que la revisión obligó a declarar (§12, I9): la premisa
«rootless» solo vale si la app corre como un usuario normal. Si el
euid es 0 (la VM de Lu, una instalación como root), Podman no corre
rootless — corre como root, y «dentro parece root, fuera es el
dueño» se convierte en root sobre root: el contenedor sigue
aislando sistema de archivos, procesos y red, pero **no** hay
frontera de usuario. `detectar_runtime()` lo detecta y lo devuelve
(`rootful: true`), la UI lo muestra junto a la vía, y la aceptación
de §9 lo trata como lo que es: en la PC del dueño (usuario normal)
la promesa rootless es la real; en la VM solo se verifica la
mecánica.

### 5.3 Campos nuevos en `proyectos.json`

Sobre el esquema de la Fase 3 (que ya trae `contenedores:
"proyecto"|"por_cuenta"`), esta fase añade:

```json
"contenedor_modo": "no",
"contenedor_imagen": null,
"contenedor_red": "saliente",
"contenedor": null
```

- `contenedor_modo`: `"no"` (defecto: el proyecto corre como en la
  Fase 3, el contenedor ni se menciona), `"opcional"` (se usa si
  hay runtime; si no hay, la tarea corre fuera **con aviso** en su
  resultado y en el log) o `"requerido"` (sin contenedor no hay
  tarea: §5.7). El defecto `"no"` es el opt-in que pide el encargo:
  nada cambia para los proyectos que no lo activen.
- `contenedor_comando`: el comando que mantiene vivo el contenedor
  si no es `sleep infinity` (§5.6). Estaba citado en el ciclo de
  vida y no en el esquema; la revisión (§12, I14) lo trajo aquí.
- `contenedor_imagen`: la imagen a usar (p. ej.
  `docker.io/library/python:3.12-slim` o la imagen propia del
  proyecto con sus dependencias). **Sin imagen declarada no hay
  contenedor**: el diseño no inventa una imagen por el dueño,
  porque la imagen ES el entorno de su proyecto (su juego pedirá
  Godot, otro proyecto pedirá Node). La UI la pide al activar el
  modo. La primera creación hace el `pull` (puede tardar: se hace
  en la preparación, **antes de tomar los alquileres** y por
  digest, con su propio timeout generoso de 600 s y queda
  asentado; si el pull falla, es un fallo de preparación, no de
  la tarea: §5.8).
- `contenedor_red`: `"saliente"` (la red normal del usuario; los
  motores necesitan hablar con sus APIs) o `"ninguna"`
  (`--network none`). El defecto depende del modo de contenedores
  de la Fase 3 (§12, I15): en `proyecto`, `"saliente"`; en
  `por_cuenta` — la caja para código no confiable —, `"ninguna"`,
  y consta lo que eso implica: con red ninguna, los motores de
  nube no operan dentro (ni APIs ni, por §5.8, credenciales), así
  que `por_cuenta` sirve para motores locales y trabajo sin red.
  Una salida por lista blanca de dominios (proxy) queda como
  trabajo futuro nombrado, no prometido. No hay opción de puertos
  publicados: **nunca** se pasa `-p`/`--publish`; el contenedor no
  escucha nada hacia fuera.
- `contenedor_pasar_credenciales`: `false` siempre por defecto.
  Solo en modo `proyecto` y puesto a `true` a mano por el dueño
  deja pasar las variables de credencial del motor (§5.8). En
  `por_cuenta` el campo no existe como opción: es `false` y no se
  puede cambiar.
- `contenedor`: el estado vivo que escribe `contenedores.py` (no
  lo edita el dueño): `{runtime, nombre, huella, creado,
  estado}` o `null`.

### 5.4 Montajes: los worktrees y el `.git`, nada más del HOME

El contenedor ve exactamente dos cosas del anfitrión, montadas en
**sus mismas rutas absolutas** (montaje espejo, para que los
punteros `.git` de los worktrees — que contienen la ruta absoluta
del almacén principal — resuelvan dentro sin traducción):

| Montaje | Modo | Porqué |
|---|---|---|
| `<repo>.worktrees/` | lectura-escritura | los worktrees de las dos cuentas (modo `proyecto`) o solo `<repo>.worktrees/<cuenta>/` (modo `por_cuenta`). Dentro vive también `.growi-home/`, el `HOME` que se fija dentro del contenedor (§5.8) |
| `<repo>/.git/` | lectura-escritura en modo `proyecto`; **solo lectura** en `por_cuenta` | sin el almacén, git no funciona en un worktree; la diferencia de modo es deliberada y se explica abajo |

Y **no** se monta: el directorio raíz del repo (el checkout de
trabajo del dueño no existe para el contenedor: solo ve el almacén
y los worktrees), el HOME, `~/.ssh`, la carpeta de la app (con la
bóveda, `permission-secret.key` y los audit-logs), la carpeta
compartida de Growi (tablero, cuentas) ni ningún otro proyecto.

El contenedor se crea además con el endurecimiento por defecto de
esta fase: `--cap-drop=ALL`, `--security-opt no-new-privileges`,
`--pids-limit 1024` y `--tmpfs /tmp` (los motores necesitan un
`/tmp` escribible, pero efímero y suyo).

Dos consecuencias, dichas en claro como manda el proyecto:

- **Las credenciales de git no entran.** El entorno del motor ya va
  sin credenciales desde la Fase 3 (`aplicar_entorno_sin_credenciales`
  en `git_trabajo.py` y el entorno del monolito), y dentro del
  contenedor no hay `~/.ssh` ni almacén de credenciales que leer.
  Antes de crear el contenedor se comprueba que `<repo>/.git/config`
  no contenga credenciales embebidas en la URL del remoto (un
  `https://token@github.com/…`): si las hay, **no se crea** y la UI
  dice por qué y cómo limpiarlo (la URL con token es un secreto
  durmiendo en un archivo que el contenedor leería). La subida
  sigue haciéndose desde el anfitrión con `git_trabajo.subir()` y
  su escaneo de secretos, con el entorno de push que solo existe en
  ese momento.
- **El `.git` en lectura-escritura es un arma de doble filo, y se
  trata como tal** (§12, B9). Con el almacén montado rw, el código
  de dentro puede reescribir `.git/config` (`core.hooksPath`, la
  URL del remoto, `core.sshCommand`…) y el **anfitrión** ejecutaría
  eso después en la mezcla o en `subir()` — justo cuando existe el
  entorno de push: token exfiltrado y código arbitrario en el
  anfitrión. Por eso el modo `proyecto` (código del propio dueño,
  que de todos modos corre en su máquina al probarlo) solo se
  ofrece con un endurecimiento obligatorio en `git_trabajo.py`:
  **toda** invocación git del anfitrión sobre un repo con
  contenedor (y, por higiene, en general) pasa
  `-c core.hooksPath=/dev/null -c core.fsmonitor=false
  -c core.sshCommand= -c credential.helper=` y
  `protocol.ext.allow=never` por línea de comandos (que manda
  sobre el archivo de config), y `subir()`/`mezclar()` verifican
  además que la URL del remoto coincide con la **huella de URL**
  registrada al dar de alta el proyecto, antes de tocar la red. En
  modo `por_cuenta` no hay esta discusión: el `.git` va en solo
  lectura, dentro no se comitea nada, y el commit del worktree lo
  hace el anfitrión al cerrar la tarea (§5.8).
- **La frontera es la declarada en la Fase 3, con dos precisiones
  nuevas** (§12, I10): el almacén de objetos es **compartido** —
  cada cuenta puede leer los commits de la otra, porque son
  worktrees del mismo repo; son las dos cuentas del mismo dueño y
  la UI lo dice al activar el modo, en vez de prometer un
  aislamiento que no existe — y en `por_cuenta`, con el `.git` en
  solo lectura, el índice y el HEAD de cada worktree viven también
  en el almacén (`<repo>/.git/worktrees/<id>/`), así que dentro
  git es de lectura (`status`, `diff`, `log` con
  `GIT_OPTIONAL_LOCKS=0`) y puede trabajar sobre un índice no
  refrescado: se declara, y los commits de ese flujo los hace el
  anfitrión al cerrar. Quien comprometa el contenedor no puede
  subir nada (sin credenciales y con la puerta de subida fuera),
  no ve otros proyectos ni el sistema de archivos del dueño, y
  los alquileres, la mezcla y las propuestas siguen gobernados
  desde el anfitrión.

El usuario dentro del contenedor es el del dueño
(`--user <uid>:<gid>` en Docker; en Podman rootless el mapeo por
defecto ya hace que los archivos creados sean del dueño), para que
los archivos del worktree sigan siendo suyos y git no proteste por
la propiedad. El directorio de trabajo de cada ejecución es el
worktree de la tarea (su ruta espejo).

### 5.5 Recursos: el % de la Fase 4 manda también aquí

Al crear el contenedor se le fijan los límites del proyecto con el
presupuesto vigente: `contenedores.py` reutiliza
`recursos.limites()` con la asignación del modo de presencia actual
y el número de tareas del proyecto, y traduce a `--cpus` y
`--memory` (Podman y Docker comparten esas banderas). Los límites
forman parte de la huella de configuración (§5.6): si el modo de
presencia cambia con el contenedor vivo, el barrido de supervisión
(Fase 4) compara y aplica `podman/docker update` cuando difieren —
y si el runtime no acepta el update en vivo, el cambio de límites
queda como diferencia de huella para la próxima recreación, no
como sorpresa silenciosa.
Con contenedor activo **no** se envuelve además con `systemd-run`:
los límites se aplican una sola vez, en el contenedor, y
`recursos-estado.json` lo declara (mecanismo «contenedor» en vez de
«systemd-run») para no prometer dos topes distintos.

### 5.6 Ciclo de vida

- **Crear**: perezosamente, en la preparación de la primera tarea
  del proyecto que lo necesite (§5.8), o a mano desde la UI
  («Crear contenedor» en el editor del proyecto). Nombre
  determinista: `growi-<repo_id>` en modo proyecto,
  `growi-<repo_id>-<cuenta>` en modo `por_cuenta`. Etiquetas
  `growi.proyecto=<repo_id>` y `growi.modo=...` para poder
  encontrarlo sin depender del estado guardado.
- **Huella de configuración**: SHA-256 de (runtime, imagen por
  digest, montajes con su origen y su modo, red, usuario, comando
  de espera **y los límites de recursos vigentes**), guardada en
  `proyectos.json` y en la etiqueta `growi.huella` del contenedor
  (§12, I11). El comando que mantiene vivo el contenedor es
  `sleep infinity` por defecto; a la creación se **sondea**: si el
  contenedor muere al instante con ese comando, se prueba
  `tail -f /dev/null`, y si ninguno vale, la creación falla con el
  motivo «la imagen no tiene comando de espera válido: declara
  `contenedor_comando`» (hay imágenes mínimas sin ninguno de los
  dos; §12, I14).
- **Reutilizar**: solo si un `inspect` confirma que el contenedor
  con ese nombre lleva las etiquetas del proyecto **y**
  `growi.huella` = la huella calculada (un nombre determinista sin
  verificar permitiría adoptar un contenedor ajeno o desfasado).
  Si está parado, se arranca. Si la huella difiere (el dueño
  cambió la imagen, la red o los límites), **recrear es destruir y
  crear**: pasa por la misma confirmación R2 que destruir, con el
  texto normalizado de la confirmación nombrando el contenedor y
  las dos huellas (vieja y nueva) — un «recrear» sin confirmación
  aprobando «lo que sea» era un agujero (§12, I12) — y solo cuando
  el proyecto no tiene tareas en curso (los alquileres lo saben);
  con tareas dentro, se pospone y queda anotado.
- **Cuarentena**: si una tarea muere por timeout dentro del
  contenedor, el contenedor queda **en cuarentena**: matar el
  `exec` no garantiza matar el proceso de dentro (§12, B10), así
  que no se reutiliza; se destruye y se recrea con la **misma**
  huella antes de la siguiente tarea del proyecto (esta recreación
  no es un cambio de configuración: no pide confirmación, pero se
  audita y se avisa). Si dentro había otra tarea de la otra cuenta
  (modo `proyecto`), su `exec` muere con el contenedor: esa tarea
  falla con el motivo `contenedor_cuarentena` y puede reintentarse
  — su worktree está intacto en el anfitrión.
- **Destruir**: a mano desde la UI, con confirmación (es una acción
  destructiva: pasa por el circuito de confirmaciones como
  cualquier borrado, con nombre y huella en el texto), o al
  desregistrar el proyecto. Nunca automáticamente por inactividad
  en esta fase: un contenedor parado no cuesta casi nada y
  destruir por sorpresa rompería la reutilización. Destruir no
  toca los worktrees ni el `.git` (son montajes, no volúmenes del
  contenedor). Crear, recrear, cuarentena y destruir dejan asiento
  en la auditoría encadenada de la cuenta que actúa (la mezcladora
  del proyecto si actúa el sistema).
- **Si el contenedor muere a mitad de tarea**: el `exec` devuelve
  error, la tarea falla con el motivo «el contenedor se detuvo
  durante la ejecución» y el estado en `proyectos.json` se marca
  para recrear en la siguiente preparación. No hay reintento
  silencioso fuera del contenedor (§5.7).

### 5.7 Sin runtime o sin contenedor: la degradación por modo

| Modo del proyecto | Sin runtime / creación imposible | Contenedor muere a mitad |
|---|---|---|
| `no` | ni se intenta | — |
| `opcional` | la tarea corre fuera, con aviso en su resultado y en el log («sin contenedor: no hay runtime disponible») | la tarea falla; la siguiente preparación reintenta crear y, si sigue sin poder, corre fuera con el mismo aviso |
| `requerido` | la tarea **no corre**: queda en espera con el motivo, como con un alquiler ocupado, y el latido reintenta la creación (aviso al dueño si pasan 30 min, por el canal de avisos de la Fase 4) | la tarea falla con el motivo; nunca se reejecuta fuera |

La asimetría es deliberada: `requerido` existe para código que el
dueño no quiere ejecutar en su sistema ni una vez; degradarlo en
silencio sería exactamente el fallo que el modo promete evitar.

### 5.8 Integración con la preparación de la Fase 3

El gancho es el de siempre y no cambia el flujo cuando el modo es
`no`:

1. En `_f3_preparar` (monolito), el orden importa (§12, I13): si
   el proyecto tiene `contenedor_modo != "no"`, primero
   `contenedores.asegurar(base, proyecto, prep)` — que incluye el
   `pull` de la imagen, por digest, **deduplicado entre carriles**
   con un lock y un estado «pull en curso» en la carpeta compartida
   (la otra carril espera el estado, no relanza su propio pull) —
   y **después** `preparar_worktree` y los alquileres: un pull de
   600 s con los alquileres tomados bloquearía el proyecto entero
   para la otra cuenta. `asegurar` devuelve el contenedor listo
   (creado, arrancado o reutilizado) o un motivo de espera/fallo
   según §5.7; en modo `requerido`, la espera del latido espera al
   estado del pull, no reintenta pulls. La `prep` gana
   `prep["contenedor"] = {runtime, nombre}` y el `cwd_efectivo`
   sigue siendo el worktree (la ruta espejo es la misma dentro y
   fuera: por eso el resto del runner no nota la diferencia).
2. En el lanzamiento del motor (el `Popen` que hoy usa
   `_engine_env`): si la `prep` trae contenedor, el argv del motor
   se envuelve con `contenedores.argv_exec(runtime, nombre,
   cwd_efectivo, env_motor, argv)`, que produce
   `[runtime, "exec", "-w", <cwd>, "-e", K=V, …, nombre, *argv]`.
   El entorno que entra **no** es «el que el motor recibiría
   fuera» (§12, B11): `contenedores.py` aplica su propia lista —
   pasan las variables inocuas (`LANG`, `TERM`, las `GROWI_*` sin
   secretos) y se fijan `PATH` y `HOME` **de la imagen**
   (`HOME=<repo>.worktrees/.growi-home`, una ruta montada y
   escribible; el `PATH`/`HOME` del anfitrión no existen dentro) —
   y las variables con forma de credencial (`*KEY*`, `*TOKEN*`,
   `*SECRET*`, `*PASSWORD*` y las que `engines.json` marque como
   credencial) **no pasan**, salvo en modo `proyecto` con
   `contenedor_pasar_credenciales: true` (§5.3). Se añaden
   `GROWI_EN_CONTENEDOR=1` y, en modo `por_cuenta`,
   `GIT_OPTIONAL_LOCKS=0`. Consecuencia declarada: un motor cuyo
   acceso sea por **login en archivos** (la CLI de claude con su
   OAuth en `~/.claude`, que no se monta) no puede autenticarse
   dentro en esta versión; `engines.json` lo marca
   (`login_archivo: true`) y la preparación de un proyecto con
   contenedor y ese motor falla con ese motivo en vez de lanzar un
   motor que no puede trabajar. El proxy que inyectaría la clave
   sin exponerla queda como trabajo futuro nombrado. El timeout y
   la captura de salida siguen siendo los del runner; la muerte,
   no: si hay timeout, el contenedor entra en cuarentena (§5.6) —
   matar el `exec` no basta y el diseño ya no finge que sí.
3. Al cerrar la tarea (`_f3_tras_process_one`): se anota
   `contenedor` (nombre y runtime) en el resultado, junto al
   worktree y la rama que ya se anotan. En modo `por_cuenta`, el
   anfitrión hace aquí el commit del worktree (dentro no se pudo:
   el `.git` es de solo lectura, §5.4) con el mensaje de la tarea,
   antes de soltar los alquileres. Los alquileres se sueltan como
   siempre; el contenedor queda vivo para la siguiente tarea
   (salvo cuarentena).

El harness (subagentes de la Fase 4) hereda el mismo tratamiento:
sus procesos nacen del mismo lanzamiento de motor, así que entran
en el contenedor del proyecto de su tarea sin código nuevo.

## 6. Instalación y detección

### 6.1 Lo que el dueño hace una vez (intermediario)

El instalador es `intermediario/instalar-intermediario.sh` y lo
ejecuta **el dueño, en su terminal**, nunca la app. Su contrato:

1. Imprime, antes de tocar nada, el contenido **completo** de cada
   archivo que va a escribir, con su ruta: el despachador, la
   configuración, el catálogo de ejemplo (con los dominios de
   ejemplo marcados como tales), la regla de sudoers y, si elige la
   vía polkit, el `.policy` y los envoltorios.
2. Pide confirmación tecleada (`SI`) tras mostrarlo todo.
3. Eleva **una vez** con `sudo` en esa terminal (la contraseña la
   teclea el dueño ante sudo, en su terminal: la app no está ni
   delante ni detrás de este paso) y escribe los archivos con los
   dueños y permisos de §3.1/§3.3. El orden es el que la revisión
   exigió (§12, B13), porque «escribir sudoers y validar después»
   puede dejar sudo roto en la máquina del dueño: cada archivo se
   escribe primero en un **temporal**, se valida ahí (`visudo -cf`
   sobre el temporal de sudoers; el catálogo, con el propio
   despachador `--validar-catalogo`) y solo entonces se **mueve**
   a su sitio. El instalador lleva un **diario de pasos** en
   `/var/lib/growi-bridge/instalador.jsonl` y un `trap` de
   ERR/EXIT que, si muere a mitad, revierte en orden inverso lo
   ya movido. Es idempotente (re-ejecutarlo deja el mismo
   contenido) y toma un lock para no correr dos veces a la vez.
4. Deja la sonda probada **desde la cuenta del dueño**: si el
   instalador corre como root (corre con sudo), prueba con
   `runuser -u "$SUDO_USER" -- sudo -n …/growi-rootbroker.py
   sonda` — probar «desde la cuenta del dueño» siendo ya root no
   probaría nada (§12, B12) — y muestra su salida: la instalación
   no se da por buena si la sonda no responde con
   `uid_origen != 0` (o si la vía declarada es root-local, con su
   sonda propia).
5. `--desinstalar` simétrico y completo: quita la regla de
   sudoers, el despachador, la configuración, el catálogo, **el
   `.policy` y los envoltorios polkit** y el diario (el log del
   despachador y los vales consumidos se conservan salvo
   `--desinstalar --con-logs`).

La app detecta la instalación (§6.3), pero **instalar, desinstalar
y editar el catálogo son actos del dueño en su terminal**, fuera
de la app, para siempre. La UI como mucho muestra el texto de
ayuda y la ruta del instalador.

### 6.2 Lo que el dueño hace una vez (contenedores)

Nada como root desde Growi: el runtime lo instala el dueño con el
gestor de paquetes de su distribución si no lo tiene (la UI lo
dice con esas palabras y detecta el resultado). Podman rootless no
necesita más; Docker necesita que su usuario pueda hablar con el
demonio, y eso también lo deja hecho el dueño fuera de la app.

### 6.3 Detección en la app: qué vía hay, de verdad

`privilegios.disponible()` devuelve
`{via: "sudoers"|"polkit"|"root-local"|"ninguna",
acciones: [ids…], huella_catalogo, motivo, detalle}` y
`contenedores.detectar_runtime()` el suyo. Reglas:

- **Catálogo**: se lee de `/etc/growi-bridge/acciones.json` si
  existe y valida (la app valida con el mismo esquema; si el
  archivo del dueño está roto, la app lo dice y trata el catálogo
  como vacío — nunca «interpreta» un catálogo dudoso). Se relee
  por (mtime, tamaño), como el registro de cuentas de la Fase 1,
  y su huella (SHA-256 del archivo) viaja en la sonda y en el
  barrido (§7): un cambio de catálogo no pasa desapercibido.
- **Vía sudoers**: sonda real al arrancar (y bajo demanda desde la
  UI): `sudo -n /usr/local/libexec/growi-rootbroker.py sonda`
  debe responder el JSON de sonda con la versión, la huella del
  catálogo **del despachador** y el `uid_origen`; si la huella
  difiere de la del catálogo leído por la app, la UI lo anota
  («el catálogo cambió: relee») y ninguna tarea se clasifica
  contra un catálogo que el despachador no tiene (la huella
  completa del vale lo garantiza en el sello, §3.5). Si
  `uid_origen` es 0, no hay vía sudoers: hay root-local (§3.4).
  La sonda se cachea 60 s **solo para la UI**: `ejecutar` no usa
  la caché — invoca y, si el despachador no responde, la tarea
  espera sin gastar la aprobación (§12, I19).
- **Motivos enumerados** (§12, I18): `ninguna` nunca va sola. El
  `motivo` es uno de `sin_sudo`, `sin_despachador`, `sin_regla`
  (la sonda devolvió error), `sin_catalogo`, `catalogo_invalido`,
  `sin_python`, `plataforma_no_soportada` o `no_instalado`, y el
  `detalle` trae el comando exacto que falló y su código: la UI
  dice qué arreglar, no solo que algo falta.
- **Vía polkit**: se detecta por presencia (pkexec en el PATH, el
  `.policy` instalado, al menos un envoltorio), **sin sonda en
  segundo plano**: sondear por pkexec abriría un diálogo de
  contraseña, y una ventana sorpresa viola el modo presente de la
  Fase 4. La vía polkit se marca «presente, sin verificar» hasta
  que el dueño ejecuta delante de la pantalla una acción que la
  use; su resultado verifica o desmiente.
- **Sin trampas**: la app nunca prueba `sudo -n true`, ni busca
  reglas anchas, ni usa un sudo que funcione «por otro motivo»
  (que el dueño tenga NOPASSWD para otra cosa no habilita nada:
  la sonda es al binario exacto del despachador).

## 7. Cableado en el monolito (fino) y UI

1. **Runner**: la clasificación de tareas aprende el tipo
   declarado `sistema` (§3.2); el procesamiento de una tarea
   `sistema` es un camino corto en el runner (sin motor): puerta de
   aprobaciones → al recoger, por cada acción, sellar su vale y
   `privilegios.ejecutar(...)` → resultado con el detalle por
   acción. Una tarea con varias acciones usa **un vale por
   acción** y se detiene en el primer fallo; las acciones ya
   ejecutadas **no se deshacen** (no hay transacción posible sobre
   el sistema: el resultado lo dice, acción por acción). Si el
   intermediario no está disponible, la tarea queda en espera de
   decisión (§3.8) antes de gastar ninguna aprobación.
2. **`privilegios.py`**: `disponible()`, `catalogo()`,
   `describir(accion, params)` (la frase de la confirmación),
   `huella(accion, params, huella_catalogo)` (la canonicalización
   completa de §3.5, compartida en especificación con el
   despachador), `sellar(...)` y `ejecutar(base, cuenta, raiz,
   accion, params, vale)` — construye la petición, la pasa por
   stdin al lanzador, parsea la respuesta y asienta en la
   auditoría de la cuenta (su intención, antes de invocar: §3.7).
   Todo con el ejecutor inyectable para las pruebas, como el resto
   de módulos del proyecto.
3. **`permission-layer.py`**: gana `registrar_vale_sistema(...)`
   (§3.5) y nada más; su CLI gana `--vales` para listar las
   solicitudes vivas (sesión, acción, huella, caducidad) — el
   dueño puede ver qué está autorizado ahora mismo; los vales
   sellados y consumidos se ven en el log del despachador, que es
   su dominio.
4. **UI**: en la página Cuentas, junto a «Proyectos y respaldo»
   (Fase 3), dos bloques:
   - **Privilegios (Linux)**: vía detectada, sonda, la tabla del
     catálogo (id, descripción, nivel, lanzador) tal como la ve el
     despachador, y el texto de ayuda de instalación. Sin botones
     que instalen ni campos que editen el catálogo.
   - **Contenedores por proyecto**: en el editor de cada proyecto,
     los campos `contenedor_modo`, `contenedor_imagen` y
     `contenedor_red`, el estado del contenedor y los botones
     «Crear» y «Destruir» (destruir, con su confirmación). El
     runtime detectado se muestra con su matiz (§5.2).
5. **Vigilancia**: el barrido de supervisión (Fase 4) gana tres
   chequeos baratos: la sonda del intermediario cada 10 min (si
   ayer había vía y hoy no, aviso «el intermediario dejó de
   responder»), la **huella del catálogo** en esa misma sonda (si
   cambia sin que el dueño lo anuncie, aviso «el catálogo de
   acciones cambió»: es su archivo y su acto, pero el cambio
   queda visto y asentado) y la reconciliación de límites de
   contenedores al cambiar el modo de presencia (§5.5).

## 8. Modelo de fallos

| Fallo | Comportamiento |
|---|---|
| Catálogo de `/etc` corrupto o con una acción inválida | El despachador no ejecuta **nada** (ni las acciones buenas) y responde `catalogo_invalido`; la app lo muestra. Un catálogo roto nunca abre media puerta |
| Petición con acción desconocida o parámetro fuera de dominio | Rechazo antes de mirar el vale, con el motivo exacto, asentado en los dos logs (el intento queda registrado: es la prueba en rojo del plan) |
| Parámetros manipulados (`../`, `;`, `$(...)`, espacios, NUL) | Los dominios los rechazan (enum/regex/prefijo canonicalizado) o el valor viaja como **un** elemento de argv literal sin shell que lo interprete: `systemctl restart "x; rm -rf /"` es un nombre de unidad inválido, no un comando |
| Vale ausente, de otra acción, con otra huella, caducado o ya consumido | Rechazo con su motivo; la tarea vuelve a espera de decisión («confirma de nuevo») sin ejecutar nada |
| El catálogo cambió entre la aprobación y el sello | `catalogo_divergente`: el despachador no sella ni ejecuta; la tarea espera con el motivo y el dueño decide si reaprobar contra el catálogo nuevo (§3.5) |
| El dueño aprueba pero la tarea espera en la cola o se aplaza | Nada caduca: la ventana corre desde el **sello**, que se pide al recoger (§3.5). Lo que sí puede caducar es un vale ya sellado si la ejecución se atasca tras sellar: `vale_caducado`, no se renueva solo, toca reaprobar |
| Otro despacho en curso al ir a ejecutar | Lock con espera de 10 s → `ocupado`: la tarea vuelve a espera con el vale intacto |
| Salto de reloj (NTP o manual) hacia atrás | La frescura manda por el mayor de los dos relojes (pared y monotónico con `boot_id`, §3.5): un salto no resucita vales; el salto queda asentado en el log del despachador |
| El log del despachador no se puede escribir (disco lleno, permisos) | `auditoria_no_disponible`: no se ejecuta nada (la regla «sin auditoría no hay acción» vale también de este lado, §3.7) |
| Despachador borrado o regla de sudoers retirada a mitad de fase | La sonda lo detecta; las tareas `sistema` esperan con el motivo (§3.8); nada privilegiado se ejecuta por otra vía |
| El comando de la acción se cuelga | Timeout del catálogo: se mata el árbol, `rc` de timeout, asentado; el despachador muere a los 660 s en el peor caso |
| Runtime de contenedores caído entre tareas | La sonda de la siguiente preparación lo ve: modo `opcional` degrada con aviso, modo `requerido` espera (§5.7) |
| Contenedor comprometido intenta leer el HOME o la bóveda | No están montados: el intento ve un sistema de archivos vacío en esas rutas; queda como evidencia en la salida de la tarea |
| `.git/config` con token en la URL | La creación del contenedor se niega hasta limpiarlo (§5.4) |
| Dos carriles piden la misma acción a la vez | Cada petición sella su propio vale (de un solo uso, ligado a su aprobación) y su asiento; el despachador serializa por su lock en `/run/growi-rootbroker.lock` — dos ejecuciones idénticas exigen dos aprobaciones |
| Una tarea muere por timeout dentro del contenedor | El contenedor entra en **cuarentena** (§5.6): no se reutiliza; se destruye y recrea con la misma huella antes de la siguiente tarea. Si dentro iba otra tarea de la otra cuenta, falla con `contenedor_cuarentena` y puede reintentarse |
| El `pull` de una imagen tarda o lo está haciendo la otra carril | El pull va antes de los alquileres y deduplicado (§5.8): la tarea espera el estado «pull en curso», no lanza otro ni bloquea el proyecto |
| La PC se reinicia con vales vivos | Un vale sellado antes del reinicio lleva otro `boot_id`: se rechaza como no válido (la frescura monotónica no es comparable entre arranques) y toca reaprobar; la cadena de auditoría de ambos lados se verifica (§3.7); los contenedores se redescubren por nombre/etiqueta, no por memoria |

## 9. Aceptación de la fase

Pruebas unitarias (módulos puros, ejecutores falsos inyectados,
reloj falso donde toque):

- `test_privilegios.py` (el lado de la app): lectura del catálogo
  (válido, ausente, roto → vacío con motivo); clasificación de la
  tarea `sistema` (nivel = máximo entre catálogo y tabla; acción
  desconocida → **rechazo en validación** con `accion_desconocida`;
  lista `sistema` vacía o elemento sin `accion` → rechazo); la
  huella completa (estable ante reordenación de claves de los
  parámetros; distinta al cambiar un valor, el argv resuelto o la
  huella del catálogo); descripción para el dueño construida desde
  el catálogo con los controles escapados; respuesta del
  despachador parseada (ok, rc≠0, JSON roto → motivo, timeout del
  lanzador); `disponible()` con motivos enumerados (§6.3).
- `test_rootbroker.py` (el despachador, con un ejecutor falso y
  directorios temporales **inyectados como parámetros** de la
  lógica — nunca por entorno, §3.1 — que hacen de `/etc`, de
  `/var/lib` y de la carpeta de la app): la validación del catálogo
  (plantilla con shell metido → catálogo inválido entero; hueco sin
  dominio; dominio sin hueco; **huecos pegados `{a}{b}`** y
  **hueco en `argv[0]`** → inválido); la validación de parámetros
  (enum cerrado, ruta que se escapa del prefijo con `..` y con un
  enlace simbólico en un componente, **entero no canónico**
  (`+1`, `007`, dígitos Unicode) rechazado, nombre con espacios o
  `;`, `dispositivo` con etiqueta inválida o destino resuelto
  fuera del patrón de dispositivos); el **sello** (solicitud con
  firma buena/mala, solicitud caducada, **catálogo divergente → no
  sella**); el **vale de root** (MAC buena/mala, acción, huella,
  tarea o aprobación distintas, caducado por nivel con reloj
  inyectable, `boot_id` distinto → rechazado, **segundo uso →
  rechazado**, R3 sin autorización del dueño → rechazado, llamante
  distinto del uid fijado → rechazado, sin `SUDO_UID` → rechazado,
  vía root-local solo con euid 0 y `uid_dueno: 0`); la ejecución
  con el ejecutor falso (el argv final es exactamente la plantilla
  con los parámetros como elementos, lanzado por la unidad
  transitoria con su `RuntimeMaxSec`; el entorno es el mínimo; un
  parámetro con `$(rm -rf /)` llega como un literal o no llega,
  nunca interpretado); salida truncada a 64 KB; su cadena de log
  verifica tras escribir N entradas bajo concurrencia simulada y
  detecta una línea manipulada; si el log no se puede escribir, no
  se ejecuta.
- `test_contenedores.py` (con ejecutor falso): detección (podman
  que responde, podman que está pero no responde → docker, ninguno
  → no disponible, euid 0 → `rootful: true` declarado);
  construcción del argv de creación (montajes espejo exactos y
  solo esos dos, `--user`, red según política y modo, banderas de
  endurecimiento `--cap-drop=ALL`/`no-new-privileges`/
  `--pids-limit`/`--tmpfs`, **sin** `--publish` jamás, límites
  desde `recursos.limites`); modo `por_cuenta` (dos nombres,
  montaje por cuenta, `.git` en solo lectura,
  `GIT_OPTIONAL_LOCKS=0` en el exec, commit del anfitrión al
  cerrar); la huella (cambia al cambiar la imagen, la red o los
  límites; no cambia por el estado); reutilizar exige `inspect`
  con las etiquetas y la huella; recreación por cambio de
  configuración pospuesta con tareas en curso y con su
  confirmación; **cuarentena tras un timeout** (no se reutiliza:
  se destruye y recrea con la misma huella); el orden de la
  preparación (el pull se registra **antes** que la toma de
  alquileres en el ejecutor falso compartido); el filtro del
  entorno del exec (una variable canario de credencial en el
  entorno del motor **no** aparece en el argv ni en el entorno
  construido; con `proyecto` + opt-in del dueño, sí); la negativa
  a crear con token en la URL del remoto.
- Regresión: todas las pruebas de las fases 0–5 siguen en verde;
  el monolito compila con su CRLF intacto; un secreto canario
  pasado por todos los caminos nuevos (petición, vale, argv del
  contenedor) no aparece en ningún log (grep final, como el
  centinela de la Fase 1).

Pruebas físicas en el entorno de Lu (esta VM), con lo que la VM
tiene de verdad — verificado el 2026-11-16: corre como **root**
(uid 0), hay `sudo` y `systemd` 255 con `systemd-run`, **no** hay
`pkexec` ni `polkitd` operativos, y **no** hay ni Podman ni Docker
instalados:

1. **El circuito completo del intermediario, con privilegio
   simulado de forma honesta**: se instala el despachador en la VM
   (somos root: la instalación es real, con sus archivos en `/etc`
   y `/usr/local/libexec`) con un catálogo de prueba que trae una
   acción inocua pero que solo root puede hacer (crear un
   directorio bajo `/var/lib/growi-prueba/`). La vía que se ejerce
   en la VM es **root-local** (§3.4): la app corre como root y la
   sonda sudoers no se da por válida (su `uid_origen` sería 0), y
   el resultado lo dice. Desde la app real: una tarea `sistema`
   con esa acción pasa la puerta, el dueño (la consola de pruebas)
   aprueba, el despachador sella el vale en su dominio, ejecuta y
   el directorio aparece; los dos logs lo asientan y las dos
   cadenas verifican.
2. **Prueba en rojo** (la aceptación del plan): la misma tarea con
   la acción cambiada a una inexistente, con un parámetro fuera
   del enum, con un parámetro `../`, y reutilizando el vale de la
   prueba 1: las cuatro se rechazan con su motivo y **no se
   ejecuta nada** (el directorio de la acción manipulada no
   aparece). Y la quinta, el vale caducado, **sin tocar el
   despachador instalado** (§12, I16): se sella un vale con el
   reloj falso de la costura de pruebas del entorno
   (`GROWI_PRUEBAS=1`, del lado de la app, como las costuras de la
   Fase 4) de modo que al ejecutar ya nació vencido → el
   despachador rechaza por `vale_caducado`. Ninguna constante del
   binario instalado es configurable para pruebas.
3. **Intermediario caído, tres causas** (§12, I18): se renombra el
   despachador instalado (`sin_despachador`), se retira el
   catálogo (`sin_catalogo`) y se rompe su JSON
   (`catalogo_invalido`): la sonda pasa a «ninguna» con el motivo
   enumerado correcto en cada caso, una tarea `sistema` nueva
   queda en espera y nada se ejecuta; y con el despachador caído
   más de 60 s (la caché de la UI ya vencida), `ejecutar` tampoco
   gasta la aprobación. Se restaura todo.
4. **Detección honesta de lo que no hay**: la app en la VM muestra
   la vía polkit como no disponible (no hay pkexec) y los
   contenedores como no disponibles (no hay runtime), sin errores
   ni reintentos en bucle.
5. **El despachador sin atajos**: con una segunda instalación de
   prueba cuyo `intermediario.json` fija un `uid_dueno` distinto
   de 0, la invocación directa como root (sin lanzador, sin
   `SUDO_UID` válido) rechaza ejecutar: no hay «modo manual». Y
   con `GROWI_BROKER_ETC` apuntando a un catálogo falso en el
   entorno, la sonda responde con el catálogo real: el binario
   instalado no lee entorno (§12, B14).

Y lo que **solo se puede probar en la PC del dueño**, declarado
desde ya como lista preparada (como el checklist de la Fase 0):

- La regla de sudoers con su usuario real (en la VM somos root y
  sudo no demuestra nada: la sonda y la ejecución con un usuario
  sin privilegios es la prueba de verdad), incluida la negativa:
  su usuario no puede ejecutar el despachador con argumentos
  libres fuera del circuito… (puede invocarlo, pero sin vale no
  ejecuta: eso también se comprueba allí).
- La vía polkit con su sesión gráfica (diálogo de contraseña,
  acción R3 con `auth_admin`, sin agente → no disponible).
- Los contenedores con Podman o Docker reales: crear el de un
  proyecto de juguete, ejecutar una tarea dentro (el motor edita
  en el worktree; desde fuera se comprueba que el HOME no es
  visible dentro con un `ls` de la tarea y que el `pwd` del `exec`
  coincide con el `cwd_efectivo` espejo del anfitrión), la subida
  posterior por la puerta de la Fase 3, y la **medición del
  coste** que pide el plan: tiempo de creación, latencia de un
  `exec` frente a la ejecución directa de un comando equivalente,
  y memoria base del contenedor en reposo, anotados en el
  resultado de la prueba.
- Un intento de escape de juguete desde dentro: leer
  `~/.ssh` y la carpeta de la app (no montadas: no existen dentro)
  y escribir fuera del worktree (no hay ruta montada).

Límites honestos que se declaran desde ya: en la VM de Lu el
intermediario se prueba con el privilegio «prestado» de ser root
en una VM desechable — el circuito (validación, vale, auditoría,
rechazos) se prueba entero, pero la frontera sudoers con un
usuario normal solo existe en la PC del dueño; y los contenedores
quedan probados en unitario y en su detección, con la física real
preparada para su PC.

## 10. Fuera de alcance (explícito)

- Windows y macOS: el intermediario es de Linux y los contenedores
  se diseñan contra Podman/Docker en Linux. En Windows, las tareas
  `sistema` quedan «no disponibles» con su motivo.
- Editar el catálogo, instalar o desinstalar el intermediario
  desde la app. Nunca. La app solo detecta y muestra.
- Acciones interactivas (que pidan entrada durante la ejecución),
  acciones con salida en vivo, y cualquier forma de terminal
  privilegiada o «sudo libre» para agentes o para el dueño desde
  la app.
- La variante de servicio root con socket y `SO_PEERCRED`
  (§3.9): especificada, no implementada. La variante anterior —
  la contraseña del usuario en la bóveda — quedó **tachada** por
  la revisión (§12, B8): no se implementará ni aunque se pida en
  esos términos; lo que se puede pedir es el servicio con socket.
- Contenedores para tareas sin proyecto (consultas, encargos sin
  repo): el contenedor es por proyecto y entra por la preparación
  de la Fase 3; lo demás corre como siempre.
- Red entrante en los contenedores, puertos publicados,
  contenedores privilegiados (`--privileged` está prohibido en la
  construcción del argv: la función que lo construye no tiene
  forma de emitirlo) y dispositivos del anfitrión (`--device`)
  salvo que una fase futura lo diseñe para un caso concreto.
- Cambiar `resolver_confirmacion`, la tabla de riesgos o los
  vencimientos: el intermediario se adapta a los circuitos, nunca
  al revés (misma regla que la Fase 5 con las aprobaciones).

## 11. Reversión

- Intermediario: `instalar-intermediario.sh --desinstalar` (del
  dueño, en su terminal). La app vuelve a «no instalado» sola, por
  la sonda. Las tareas `sistema` que quedaran en espera siguen en
  espera con su motivo; ninguna se ejecuta por la reversión.
- Contenedores: poner `contenedor_modo: "no"` en el proyecto (o
  destruir el contenedor desde la UI) devuelve el proyecto al
  flujo exacto de la Fase 3. Los campos nuevos de `proyectos.json`
  son ignorados por el código anterior.
- Vales y solicitudes: borrar `confirmaciones.json` invalida las
  solicitudes pendientes como en cualquier otra reversión de la
  capa de permisos; los vales ya sellados viven en el dominio de
  root, caducan solos por su ventana (≤ 60 min) y, sin
  despachador instalado, no los puede consumir nadie.

## 12. Diseño tal como se implementó (2026-11-16) y por qué difiere del cuerpo

Registro honesto de lo que pasó con este documento. El cuerpo (§1–§11)
describe la primera arquitectura: un despachador residente como root
(`growi-rootbroker.py` en `/usr/local/libexec`), catálogo en `/etc` y
vales firmados con HMAC. La revisión de Opus 5.5 se hizo en cuatro
pasadas por secciones (guardadas en el historial del proyecto) y sus
bloqueantes tumbaron esa arquitectura:

- El vale vive en el dominio del atacante: la clave HMAC y
  `confirmaciones.json` son del mismo uid que los motores, así que
  una HMAC que el solicitante puede calcular no autentica nada, y
  convertir ese material en llave de root empeora la frontera.
- `NOPASSWD` acota el programa, no al humano: cualquier proceso del
  uid ejecutaría el despachador sin nadie delante, contra el
  principio de confirmación humana previa.
- TOCTOU de catálogo entre lo que la app clasifica y lo que root
  ejecuta; «acción desconocida» en espera de decisión sería un
  fail-hang, no un fail-closed; las plantillas de argv dejaban huecos
  (hueco en `argv[0]`, huecos pegados, caracteres no prohibidos).

La consolidación de la revisión llegó tarde y está en el §13 de
este mismo documento: documenta los hallazgos contra la primera
arquitectura y unas correcciones que apuntaban a un despachador
que sella vales como root. Esa tampoco es la arquitectura final:
la implementación tomó una ruta más simple que responde a los
mismos bloqueantes sin ningún componente residente como root (no
hay vale que forjar porque no hay vales; el ayudante no tiene
privilegios; el factor humano es el circuito de aprobaciones más
la orden de un solo uso). Cuando el §13 y este §12 difieran, **el
§12 manda**: es lo que el código hace.

### 12.1 La arquitectura implementada

- **`raiz.py`** — el registro cerrado de acciones vive EN CÓDIGO (no
  en un archivo editable): `systemctl status|start|stop|restart`
  solo sobre la lista de unidades del dueño (regex estricta +
  pertenencia a la lista), `apt-get update`, `apt-get install -y`
  con nombre de paquete validado por la regex de Debian. Sin shell,
  sin plantillas: cada argv se construye desde el registro. Una
  acción desconocida se RECHAZA en validación con motivo
  `accion_desconocida` (nunca queda colgada). La huella canónica de
  los parámetros liga lo aprobado con lo ejecutado.
- **`growi-ayudante.py`** — ejecutable SIN privilegios al que una
  regla sudoers autoriza por argv exacto (lo instala el dueño con
  `instalar-raiz.py`, §12.3). Espejo independiente del registro:
  revalida todo por su cuenta, exige `SUDO_UID`/`PKEXEC_UID` (ni
  siquiera root invocándolo a mano lo hace correr), impone su propio
  ritmo desde su log encadenado por hashes y ejecuta con
  `shell=False`, entorno mínimo y timeout con muerte del grupo.
- **La orden de un solo uso** — tras la aprobación humana en el
  circuito existente, el runner deja una orden breve y de un solo
  uso en `raiz-ordenes/`; el ayudante la exige y la consume
  (`O_EXCL`). Sin orden viva no ejecuta nada, venga la petición de
  donde venga. La orden NO es una credencial criptográfica: vive en
  el dominio del usuario y su valor es de consumo y auditoría (liga
  cada ejecución a UNA aprobación concreta y la quema), no de
  autenticación entre procesos del mismo uid — ese límite se declara,
  no se disimula: el control real es el circuito de aprobación con
  orígenes humanos de la capa de permisos.
- **Sin clave de root en ningún sitio**: no hay daemon residente, no
  hay secreto que guardar; la elevación la concede la regla sudoers
  que el dueño instala, y solo para el ayudante y sus argv exactos.
- **Contenedores**: implementados tal como dice el §5 (uno por
  proyecto con los dos worktrees, Podman sin root preferente,
  credenciales de git fuera, red por política, opt-in por proyecto).
- **Detección y degradación**: la vía se detecta y se declara
  (sudoers verificado por sonda / pkexec presente sin verificar /
  ninguna); sin vía, las acciones privilegiadas simplemente no están
  disponibles y la app lo dice.

### 12.2 Pruebas de esta arquitectura

64 pruebas nuevas (409 en total con las anteriores): argv
manipulados y metacaracteres rechazados, clases no registradas,
huella coincidente entre app y ayudante, ritmos, el generador que no
compone nada con nombres inválidos, el ayudante que rechaza sin
elevación, sin orden, con orden caducada o reutilizada, y el cruce
real app↔ayudante sin mocks entre ellos. Las pruebas físicas con una
regla sudoers de un usuario real y con un contenedor real quedan
para la PC del dueño (en la VM de desarrollo se corre como root, lo
que no demuestra la vía, y no hay Podman ni Docker instalados).

## 13. Revisión de Opus 5.5 y correcciones aplicadas (§ bis)

La revisión se pidió a `claude-opus-5-5` vía MWAPI con un anexo de
hechos verificados del código (el circuito de `permission-layer.py`,
las aprobaciones del monolito, `_f3_preparar`, `git_trabajo.py` y el
entorno real de la VM). El gateway cortó las peticiones largas una y
otra vez (desconexiones de stream a mitad de generación), así que la
revisión se hizo en **cuatro pasadas por secciones** — A: §1–§3.3;
B: §3.4–§3.9; C: §5; D: §6–§11 — con salidas acotadas; las cuatro
salidas completas quedan guardadas en el historial del proyecto
(`~/workspace/revision-fase6/opus-{A,B,C,D}.txt`). La numeración de
esta sección es continua; cada hallazgo cita su pasada. Todas las
correcciones están aplicadas en el cuerpo, en la sección que se
indica.

### Bloqueantes

- **B1 (A-B1, B-B1, B-I2, A-I4). El vale vivía en el dominio del
  atacante.** `permission-secret.key` y `confirmaciones.json` son
  del mismo uid que los motores: una HMAC que el solicitante puede
  calcular no autentica nada, y al abrir acciones de root esa clave
  se convierte en material root-equivalente — «no empeora la
  frontera» era falso. Sin nonce ni liga a tarea, además, el vale
  era reutilizable durante toda su ventana. **Corrección
  aplicada**: el registro de `permission-layer` pasa a ser la
  *solicitud*; el vale lo **sella el despachador como root**
  (`--sellar`), con clave propia, nonce por aprobación, liga a
  tarea y aprobación, y consumo atómico en su dominio (§1.4, §1.8,
  §3.5).
- **B2 (B-B2, parte de A-B1). `NOPASSWD` acota el programa, no al
  humano.** Cualquier proceso del uid invocaría el despachador sin
  nadie delante, contra «cada acción con confirmación humana
  previa». **Corrección aplicada**: el factor humano se declara
  como lo que es — el circuito de aprobaciones, como en el resto
  de Growi — y **R3 nunca se ejecuta solo con sudoers+vale**:
  exige el acto `autorizar` del dueño en su terminal o la vía
  polkit con `auth_admin` (§3.4, §3.5).
- **B3 (A-B3, D-B5). TOCTOU y divergencia de catálogo.** La app
  clasifica con su lectura y root ejecutaría con la suya; una
  edición intermedia cambiaba el argv o el nivel bajo una
  aprobación ya dada, y la divergencia solo «se anotaba».
  **Corrección aplicada**: la huella cubre huella del catálogo +
  id + nivel + argv resuelto + parámetros; el despachador la
  recalcula al sellar y, si difiere, `catalogo_divergente` sin
  ejecutar (§3.3, §3.5, §8).
- **B4 (A-B4). Acción desconocida = fail-hang.** En espera de
  decisión no hay nivel ni puerta que la decida: la tarea colgaría
  para siempre. **Corrección aplicada**: rechazo en validación
  con `accion_desconocida`, y también para `sistema` vacío o sin
  `accion` (§3.2).
- **B5 (A-B5). Plantillas de argv con huecos.** Nada prohibía
  `{a}{b}`, un hueco en `argv[0]` (un `ruta` ahí apuntaría a
  `/bin/sh`) ni `{`/`}` en los literales. **Corrección aplicada**:
  plantilla parseada una vez; cada elemento es un literal limpio
  o exactamente un hueco declarado; `argv[0]` literal, absoluto,
  de root y no escribible por otros (§3.3).
- **B6 (B-B3). Polkit contradictorio.** El diseño mezclaba un
  ayudante que lanzaba pkexec contra el despachador (una sola
  identidad de acción, y `--accion-fija` elegido por el llamante)
  con los envoltorios por acción. **Corrección aplicada**: la app
  invoca `pkexec /usr/local/libexec/growi-broker-<id>`
  directamente; el envoltorio lleva el id literal, ignora
  argumentos y hace `exec` del despachador (§3.4).
- **B7 (B-B4). Los dominios acotan argv, no el contenido.** Una
  acción que opere sobre rutas escribibles por el usuario es
  ejecución de código como root por contenido o por symlink.
  **Corrección aplicada**: invariante de catálogo (nada interpreta
  contenido del usuario como código/config; rutas fuera de árboles
  del usuario; rechazo si un componente del camino es symlink)
  (§3.3).
- **B8 (B-B5). El §3.9 era inviable.** Un servicio root lanzando
  `sudo -S` no eleva nada, y la contraseña en la bóveda la lee
  cualquier proceso del uid con `_sec_get`. **Corrección
  aplicada**: la variante de la clave queda **tachada**; el último
  recurso especificado es un servicio root con socket Unix y
  `SO_PEERCRED`, sin ningún secreto (§3.9, §10).
- **B9 (C-B1). El `.git` rw anula la frontera por la puerta de
  atrás.** Desde dentro se reescribe `core.hooksPath` o la URL
  del remoto y el anfitrión lo ejecuta en la mezcla o en
  `subir()`, con el entorno de push presente. **Corrección
  aplicada**: en `por_cuenta`, `.git` en solo lectura y commits
  del anfitrión; en `proyecto`, rw solo con el endurecimiento
  obligatorio en `git_trabajo.py` (config neutralizada por `-c` en
  toda invocación y huella de la URL del remoto verificada antes
  de empujar) (§5.4).
- **B10 (C-B4). Matar el `exec` no mata el proceso de dentro.**
  El runner soltaría alquileres y lanzaría otra tarea sobre el
  mismo worktree con el proceso anterior aún escribiendo.
  **Corrección aplicada**: cuarentena — tras un timeout el
  contenedor no se reutiliza; se destruye y recrea con la misma
  huella, auditado y avisado; la otra tarea que compartía
  contenedor falla con `contenedor_cuarentena` y puede
  reintentarse (§5.6, §5.8, §8).
- **B11 (C-B5). Las credenciales del motor entrarían al
  contenedor.** Filtrar «lo que el motor ya recibiría» incluye la
  clave del modelo, y el `PATH`/`HOME` del anfitrión no existen
  dentro. **Corrección aplicada**: lista de entorno propia de
  `contenedores.py` (las credenciales no pasan salvo opt-in
  explícito en modo `proyecto`; en `por_cuenta`, nunca), `HOME`
  dentro del montaje, y declarado que los motores con login por
  archivo no se autentican dentro en esta versión (§5.3, §5.8).
- **B12 (D-B1). Con euid 0, la sonda miente en los dos sentidos.**
  `sudo -n` como root no consulta sudoers (falso positivo de vía)
  y el despachador rechazaría por `SUDO_UID` (falso negativo); y
  el instalador no puede probar «desde la cuenta del dueño»
  siendo ya root. **Corrección aplicada**: vía `root-local` con
  euid 0, sonda sudoers válida solo con `uid_origen != 0`, e
  instalador que prueba con `runuser -u "$SUDO_USER"` (§3.4,
  §6.1, §9.2).
- **B13 (D-B3). El instalador podía dejar sudo roto.** Escribir
  `/etc/sudoers.d` y validar después, sin diario ni orden de
  deshacer; y `--desinstalar` no quitaba lo de polkit.
  **Corrección aplicada**: temporal + validación + mover, diario
  de pasos con `trap` que revierte en orden inverso, idempotencia
  con lock, y desinstalación completa (§6.1).
- **B14 (D-B4). La inyección de rutas para pruebas sería una
  puerta trasera.** Si el binario instalado leyera su raíz de una
  variable de entorno, la lista blanca dejaría de existir.
  **Corrección aplicada**: el despachador instalado no lee
  entorno para configurarse; las rutas se inyectan como parámetros
  solo en la lógica que prueban las unitarias, y una prueba física
  verifica que `GROWI_BROKER_ETC=…` no cambia nada (§3.1, §9.1,
  §9.2).

### Importantes

- **I1 (A-I1).** `entero` sin forma canónica: `int()` acepta
  `+1`, `007` y dígitos Unicode; lo ejecutado podía no ser lo
  hasheado. Forma `^[0-9]{1,9}$` y `str(int(v))` para hash y argv
  (§3.3).
- **I2 (A-I2).** `ruta`+`realpath` rompía el catálogo inicial
  (`/dev/disk/by-label/X` resuelve fuera del prefijo: `montar` no
  validaría nunca) y admitía controles que acaban en la
  descripción del dueño. Tipo `dispositivo` nuevo, rechazo de
  controles y escapado en descripciones (§3.3).
- **I3 (A-I3).** No se decía quién emite la prueba con origen
  humano. Queda escrito sin ambigüedad: la emite la puerta al
  decidir (la solicitud), y el despachador solo ejecuta vales
  sellados por él (§3.5).
- **I4 (A-I5).** `lanzador: "ambos"` sin orden ni política de
  fallo, y polkit inviable en el entorno verificado. Fuera del
  esquema v1: una acción, una vía (§3.3).
- **I5 (B-I1).** La ventana contaba desde la aprobación y chocaba
  con la cola, `aplazar` y la suspensión, sin estado de reapertura
  definido. La ventana cuenta **desde el sello**, el sello se pide
  al recoger, y `vale_caducado` vuelve a `esperando_aprobacion`
  exigiendo aprobación nueva (§3.5).
- **I6 (B-I3, D-I1).** El log del despachador bifurcaba con dos
  invocaciones y `logrotate` lo rompía; y faltaba el bloqueo si
  no se puede auditar. `flock` para leer-y-añadir, rotación
  propia con ancla en `/var/lib`, asiento de intención antes de
  ejecutar en los dos lados y bloqueo si falla (§3.7).
- **I7 (B-I4).** `via` queda fuera del payload que firma `_firma`:
  era falsificable y R3 no puede descansar sobre él. `via` es
  informativo; la política de canales vive en
  `decidir_aprobacion` y la de R3 en el acto en terminal (§3.5).
- **I8 (B-I5).** El timeout con `alarm`+`killpg` deja vivos a los
  hijos que hacen `setsid`. Ejecución bajo unidad transitoria de
  systemd con `KillMode=control-group`, sondeada al instalar;
  fallback declarado más débil (§3.6).
- **I9 (C-B3).** La premisa rootless es falsa con euid 0. La
  detección lo devuelve (`rootful: true`), la UI lo declara y la
  aceptación lo trata como mecánica, no como frontera (§5.2).
- **I10 (C-B2).** El almacén compartido deja leer los commits de
  la otra cuenta y el índice ro puede ir desfasado. Declarado en
  §5.4 y en la UI en vez de prometido al revés; la alternativa
  (clones por cuenta) se rechazó porque rompe el modelo de
  worktrees de la Fase 3 para aislar a dos cuentas del mismo
  dueño entre sí, que no es la amenaza.
- **I11 (C-I1).** La huella ignoraba límites y orígenes, y
  reutilizar por nombre permitía adoptar un contenedor ajeno.
  Huella con límites y montajes, y reutilización solo tras
  `inspect` con etiquetas y huella coincidentes (§5.5, §5.6).
- **I12 (C-I2).** Recrear destruía sin la confirmación que
  destruir sí exige. Recrear por cambio de configuración pasa por
  la misma confirmación R2, con nombre y ambas huellas en el
  texto normalizado (§5.6).
- **I13 (C-I3).** El `pull` de 600 s con los alquileres tomados
  bloqueaba el proyecto y en `requerido` se reintentaba cada
  latido. Pull antes de los alquileres, por digest y deduplicado
  entre carriles (§5.3, §5.8).
- **I14 (C-I4).** `contenedor_comando` no estaba en el esquema y
  hay imágenes sin `sleep`. Campo añadido y sonda de comando de
  espera a la creación con su motivo exacto (§5.3, §5.6).
- **I15 (C-I5).** Red `saliente` por defecto en `por_cuenta`
  contradecía la caja de arena. Defecto por modo: `proyecto` →
  `saliente`, `por_cuenta` → `ninguna`, con lo que eso implica
  declarado (§5.3).
- **I16 (D-B2).** La prueba del vale caducado («ventana de 5 s»)
  contradecía §10 y las ventanas fijas. Caducidad con reloj
  inyectable en unitarias y, en físico, con un sello de reloj
  falso desde la costura de pruebas de la app — nunca una
  constante del despachador instalado (§9.1, §9.2).
- **I17 (D-I2).** No se decía si un `rc != 0` consume el vale ni
  qué pasa con el lock ocupado 660 s. Consumo en la invocación
  (un intento, no un éxito) y lock con espera de 10 s → `ocupado`
  con el vale intacto (§3.5, §8).
- **I18 (D-I3).** `via: "ninguna"` mezclaba causas y la UI no
  podía decir qué arreglar. Motivos enumerados con el comando
  exacto que falló, y la prueba física cubre tres causas (§6.3,
  §9.2).
- **I19 (D-I4).** La caché de la sonda (60 s) no puede autorizar
  ejecuciones. Caché solo para la UI; `ejecutar` invoca y, si no
  hay respuesta, la tarea espera sin gastar la aprobación (§6.3).
- **I20 (D-I5).** Un salto de reloj resucitaría vales y dejaría
  asientos incoherentes. Frescura por el mayor de reloj de pared
  y monotónico con `boot_id` (un reinicio invalida los vales
  sellados antes), y salto asentado (§3.5, §8).

### Menores (los «resto» de las cuatro pasadas)

Vales por acción y sin deshacer en tareas multi-acción (§7.1); el
timeout de `instalar-paquete` avisa del estado de dpkg (§3.6); los
scripts de paquete como root, declarados en la fila del catálogo
(§3.3); las tareas `sistema` no toman alquileres ni worktrees
(§3.2); `intermediario.json` a 0600 y sus rutas de dominio root
validadas (§3.1); asientos de crear/recrear/cuarentena/destruir en
la auditoría de la cuenta y banderas de endurecimiento del
contenedor (§5.4, §5.6); el `pwd` espejo se verifica en la prueba
física de contenedores (§9.2); `plataforma_no_soportada` como
motivo (§6.3); instalador idempotente con lock (§6.1); y el
barrido vigila la huella del catálogo (§7.5).

### Lo que la revisión no cambió

El despachador no residente invocado por acción, la petición JSON
por stdin, el entorno construido desde cero, el catálogo fuera del
alcance de la app, la doble auditoría, que sudoers fije el binario
exacto con la granularidad en el catálogo de root, montar solo los
worktrees y el `.git` en sus rutas absolutas (los punteros
resuelven sin traducción), la sonda real de runtime, el nombre
determinista de contenedor con etiquetas, la asimetría de
degradación de §5.7, que la app nunca instale nada como root, la
detección polkit por presencia sin diálogos sorpresa y la simetría
de la reversión.

### Nota de divergencia con §12

El §12 de este documento registra que la implementación se hizo
sobre una arquitectura corregida distinta de la del cuerpo
(`raiz.py` con el registro en código, `growi-ayudante.py` sin
privilegios autorizado por sudoers con argv exactos, y una *orden*
de un solo uso en el dominio del usuario, declarada no
criptográfica). Esta sección y los ajustes del cuerpo llegaron
después de ese registro: el cuerpo (§1–§11) ya incorpora las
correcciones de la revisión, pero su arquitectura — despachador
root en `/usr/local/libexec`, catálogo en `/etc`, vale sellado en
el dominio de root — **no es la implementada**. Las dos resuelven
varios bloqueantes por caminos distintos: B1, aquí con el sello
root y allí con la orden consumible y su límite declarado; B5,
aquí con plantillas parseadas y allí sin plantillas (argv
construidos desde el registro en código); B4, igual en ambas
(rechazo con `accion_desconocida`); los contenedores (§5) sí
coinciden. Cuál de las dos arquitecturas manda — y si el cuerpo o
el código es el que debe moverse — es una decisión del dueño y del
agente principal, no de esta revisión; queda registrada aquí para
que nadie lea el cuerpo como descripción del código actual.

### 12.3 Pruebas físicas (2026-11-16) y dos defectos más

Con la app real y la regla instalada de verdad en la máquina de
pruebas (regla compuesta desde el registro, `visudo` OK, ayudante
instalado en `/usr/local/libexec`): la sonda verifica la vía
«sudoers»; antes de instalar el ayudante, la detección dijo con
honestidad «instalación incompleta», que es su trabajo. Una acción
R1 (`servicio-estado`) aprobada por el canal recorrió todo el
circuito: permiso consumido al recoger, orden creada y consumida,
el ayudante ejecutó el argv exacto y el resultado (código 4: la
máquina de pruebas no corre systemd) quedó asentado dos veces, en
la auditoría de la cuenta y en el log encadenado del ayudante, con
la misma huella. La acción desconocida se rechazó sin colgarse y el
parámetro manipulado (`ssh; touch …`) se rechazó sin ejecutar nada.
`instalar-raiz.py` sin TTY se niega (rc 2). Sin Podman ni Docker en
la máquina, la detección de contenedores dice «ninguna».

Dos defectos cazados en estas pruebas:

1. **La puerta dual se tragaba las tareas `sistema`.** Con la cuenta
   en modo «ambas» y el vigía en «servidor», la tarea se enviaba a
   la sesión remota y quedaba `por_confirmar` para siempre: las
   acciones de root son de ESTA máquina. Corrección: `sistema` se
   suma a `consulta` y `encargo` en las exenciones de
   `_f4_dual_aplica` (se procesan en local siempre).
2. **La base del ayudante sale del hogar del uid, no del entorno.**
   El ayudante deriva su carpeta de datos del `pw_dir` del
   `SUDO_UID` a propósito (sudo recorta el entorno; una base que
   viniera del llamante sería movible por él). Consecuencia: con un
   `XDG_DATA_HOME` no estándar, la app y el ayudante mirarían
   carpetas distintas y la unidad parecería «fuera de la lista». En
   una instalación estándar (XDG por defecto) coinciden; queda
   declarado aquí como límite conocido.
