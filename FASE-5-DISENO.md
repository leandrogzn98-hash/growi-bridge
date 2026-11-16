# Fase 5 — Canales completos: el dueño manda y aprueba desde fuera

Diseño previo a la implementación, para revisión (Opus 5.5 vía MWAPI) y como
contrato de aceptación de la fase. Sigue el patrón de las Fases 1 a 4:
módulos puros con lógica testeable + cableado fino en el monolito. Rama:
`fase-5-canales`.

Piezas nuevas: `canales.py` (la capa común: emparejamiento, entrada,
parseo de decisiones, salida, ritmo y auditoría del canal),
`canal_telegram.py`, `canal_whatsapp_oficial.py` y `canal_whatsapp.py`
(los tres adaptadores de transporte, tras la interfaz que la Fase 4 fijó
en `avisos.py`) y `canal-whatsapp/` (el acompañante Node del transporte
no oficial, con su instalador). Todos los `.py` nuevos son LF; el
monolito solo gana cableado fino, conservando su CRLF.

La Fase 4 dejó los avisos básicos funcionando en local (registro
`avisos.jsonl` + toast/contador) y el contrato del canal externo con un
`CanalNulo` que no envía nada. Esta fase conecta el transporte real: el
dueño escribe desde su teléfono, el mensaje se convierte en un encargo
de la Fase 4 con su `canal`, las Muses le responden por el mismo canal,
y las aprobaciones R1/R2 se deciden respondiendo al pedido. **Qué
transporte se usa lo decide el dueño** (se le pregunta en paralelo a
este diseño): este documento deja la capa común completa y, por
transporte, solo el adaptador — la decisión no cambia ni una línea de
la capa común.

Lo que esta fase NO hace: construir la app Android (queda especificada
en el §13 como prototipo opcional, primer recorte del plan) y tocar el
circuito de aprobaciones (se reutiliza tal cual: §6).

## 1. Principios

1. **El canal crea tareas, no shells.** Un mensaje del dueño nunca es un
   comando: se convierte en una tarea (`tipo: "encargo"`) que pasa por
   `validate_task`, la clasificación de riesgos y el circuito de
   aprobaciones exactamente igual que si hubiera nacido en la app. El
   chat es una ventanilla de entrada más, con las mismas puertas.
2. **Sin emparejamiento no hay canal.** Antes de emparejar, el canal no
   procesa nada de nadie. Después, solo procesa al remitente emparejado
   (la identidad que el transporte certifica: un `chat_id`, un JID, un
   `wa_id`). Todo lo demás es silencio hacia fuera y una línea de
   auditoría hacia dentro.
3. **El circuito de aprobaciones no se toca.** `decidir_aprobacion` ya
   es «la única entrada para aprobar o rechazar un pedido (app o, más
   adelante, un canal remoto)»: acepta el parámetro `canal`, comprueba
   el vencimiento antes que nada, apunta las tardías y las descarta, y
   deniega R3 al instante si el canal no es `app`. El canal solo
   transporta la pregunta y trae la respuesta; no interpreta permisos,
   no guarda pases, no decide nada por su cuenta. La confirmación de
   confirmaciones de `permission-layer.py` (`resolver_confirmacion`,
   solo `app-humano`/`consola-humano`) es otro circuito (el de las
   herramientas del harness) y el canal **no lo toca**.
4. **R3 no viaja como decidible, nunca.** Un pedido R3 ni siquiera se
   ofrece con código: el archivo `.pedido.json` ya nace con
   `se_puede_por_whatsapp = False` y `texto_pedido` ya dice «esto solo
   se aprueba en la app». Por el canal puede llegar, como mucho, la
   *notificación* de que un R3 espera en la app (§7.3). Y si el dueño
   intenta decidirlo igualmente por chat, la capa común **ni siquiera
   lo pasa al circuito** (corrección B6 del §17 bis): responde «solo
   en la app», lo anota y el pedido queda intacto, porque
   `decidir_aprobacion` con un canal remoto no solo deniega un R3:
   lo *cierra*. Que el circuito también lo denegaría es la segunda
   muralla, y se prueba en unitarias llamándolo directamente; la
   primera es que el canal no lo toca.
5. **Guardar primero, también a la entrada.** Todo lo que entra se
   anota en `canal-registro.jsonl` antes de crear ninguna tarea, y la
   recepción no se confirma al transporte (no se avanza el offset de
   Telegram, no se mueve el cursor del acompañante, se responde 500 al
   webhook) hasta haber anotado: si el registro falla, el mensaje no
   se procesa y el transporte lo reentrega. Es el espejo del «guardar
   primero, despachar después» de `avisos.py`.
6. **Un solo dueño, un solo destino.** El adaptador no sabe enviar a
   nadie que no sea la identidad emparejada: no acepta un parámetro de
   destino libre. Las Muses no pueden escribir a terceros por este
   canal ni aunque una tarea lo pida; para eso está la clasificación
   de riesgos de siempre (enviar mensajes a otros es una acción R2+
   que no pasa por este adaptador).
7. **El transporte es sustituible y prescindible.** Si el canal cae,
   el sistema sigue completo en local: los avisos quedan en el
   registro, los pedidos esperan y vencen en la app como siempre. Lo
   único que se cierra con el canal caído es la *decisión remota*
   (comportamiento cerrado que pide el plan): sin canal no hay
   aprobación remota, y eso nunca se «compensa» relajando nada.
8. **Los secretos, en la bóveda y en el último momento.** Tokens y
   claves viven en la bóveda de las Fases 1/4 (`_sec_get`/`_sec_set`
   con nombres `canal:<transporte>`), se piden con un getter inyectado
   en el momento de usarlos y no aparecen en `canales.json`, ni en
   logs, ni en la línea de comandos de ningún proceso, ni en el
   registro del canal.
9. **La hora es la del PC.** Los vencimientos, ritmos y caducidades se
   calculan con el reloj del PC al recibir el mensaje (principio 7 de
   la Fase 4). La hora que traiga el transporte solo sirve para
   ordenar y para detectar mensajes viejos, nunca para decidir.

## 2. Arquitectura: capa común, tres adaptadores y un solo líder

### 2.1 El mapa

```
teléfono del dueño
      │  (transporte: Telegram / WhatsApp oficial / WhatsApp no oficial)
      ▼
adaptador (canal_<transporte>.py)  ── solo sabe hablar con su red
      │  mensajes normalizados / transmitir(texto)
      ▼
canales.py  ── capa común: emparejamiento, clasificación del mensaje,
      │        parseo de decisiones, ritmo, dedup, auditoría, consultas
      ├─► TASKS del carril destino ──► runner ──► relevo (Fase 4)
      ├─► bandeja de decisiones ──► decidir_aprobacion (sin tocar)
      └─► bandeja saliente ──► avisos y respuestas vuelven al teléfono
```

- **`canales.py`** (nuevo, LF): toda la lógica que no depende del
  transporte. Funciones puras donde se pueda (parseo, clasificación,
  ritmo, emparejamiento) con el estado en archivos compartidos y los
  efectos inyectados, al estilo de `relevo.py`/`supervision.py`.
- **Adaptadores** (nuevos, LF): un objeto por transporte con el
  contrato de la Fase 4 ampliado a bidireccional:

  ```python
  class Adaptador:  # contrato (duck typing, como los destinos de avisos)
      nombre = "telegram"          # = valor de «canal» en tareas y decisiones
      def disponible(self) -> bool # credenciales presentes y red alcanzable
      def recibir(self, cursor) -> (mensajes, cursor_nuevo)
      def transmitir(self, texto, meta) -> dict | None  # {"mensaje_id": ...}
  ```

  `recibir` devuelve mensajes normalizados:
  `{"transporte", "remitente", "texto", "ts_transporte", "id_mensaje",
  "cita_id"}` (`cita_id`: el id del mensaje citado/respondido, si el
  transporte lo da; si no, `None`). Ningún adaptador decide nada: ni
  quién es el dueño, ni qué significa un texto. Solo traduce.
- **El destino `canal` de `avisos.py`** deja de ser `CanalNulo`: se
  registra **una sola vez** con `avisos.registrar_canal("canal",
  fabrica)` y `"canal"` entra en los destinos de
  `avisos-config.json`. El destino es **agnóstico del transporte**:
  en cada `enviar(aviso)` lee de `canales.json` cuál es el transporte
  activo (corrección I12 del §17 bis: una sola fuente para «el
  activo»; la clave `canal` de `avisos-config.json` deja de mandar) y
  si no hay ninguno, no encola nada. Su `enviar(aviso)` **no toca la
  red**: formatea el aviso y lo deja en la bandeja saliente (§2.3).
  Así, emitir un aviso sigue sin bloquear jamás al runner (principio
  de la Fase 4) aunque la red esté muerta, y cambiar de transporte en
  la UI surte efecto en el siguiente ciclo, sin reiniciar (§12.1).

### 2.2 Un solo líder

Los dos carriles corren el mismo programa, pero el canal es **uno**:
dos procesos haciendo polling a Telegram se robarían los `update`
(offset compartido) y dos sesiones de WhatsApp no oficial no pueden
coexistir. Por eso el servicio de canal tiene un líder único:

- Al arrancar (§12), cada carril lanza el hilo del servicio de canal.
  El hilo compite por el liderazgo en la carpeta compartida
  (`_base_tablero()`): `canal-lider.json` con
  `{"carril", "pid", "latido_ts"}`. El líder renueva su latido cada
  20 s escribiendo con el patrón de siempre (tmp + `os.replace`); un
  no-líder toma el relevo cuando el latido tiene más de 60 s (reloj de
  archivos compartidos, principio 9). No se reutiliza el lock de 15 s
  de `tablero.py`/`cuentas.py`: ese es para secciones críticas cortas,
  no para un liderazgo que dura horas.
- **Solo el líder** habla con el transporte: drena la bandeja saliente,
  recibe mensajes y los procesa (§5 y §6). Los demás procesos solo
  encolan (avisos, pedidos, decisiones de su carril ya aplicadas no:
  §6.4) y escriben en los archivos compartidos.
- Si el líder muere, el otro carril releva en ≤ 60 s + un ciclo. Si
  mueren los dos, el canal cae y el sistema sigue en local
  (principio 7); el vigilante de la Fase 4 relanza los carriles como
  siempre.
- El liderazgo es del *servicio*, no de una cuenta: el carril líder es
  además el receptor por defecto de los encargos que no nombran
  cuenta (§5.3), porque es el proceso que está procesando el mensaje
  (la receptora la pone el proceso receptor, regla I7 de la Fase 2).

**Época y pasos acotados** (corrección B3 del §17 bis: sin esto puede
haber dos líderes a la vez, y el propio ciclo se auto-depone):

- `canal-lider.json` lleva una **época**: un entero que crece en cada
  toma de liderazgo. Tomar el liderazgo es: bajo el lock de archivo
  de siempre, leer la época vigente, escribir
  `{carril, pid, epoca: anterior + 1, latido_ts}` con tmp +
  `os.replace`. El líder **relee la época antes de cada acción con
  efecto** (avanzar un cursor, transmitir, crear una tarea, crear una
  orden, aplicar una decisión) y si ya no es la suya, se detiene en
  el acto y pasa a no-líder: un líder depuesto a mitad de ciclo no
  termina «su» vuelta.
- El latido lo escribe **el mismo bucle que procesa**, nunca un hilo
  aparte: un líder colgado deja de latir y el relevo funciona; un
  líder sano no puede parecer muerto por tener el latido en otro
  hilo desatendido.
- Ningún paso del ciclo bloquea más que una fracción del umbral de
  60 s: el long poll de Telegram es de **20 s como máximo**, la
  espera de una orden entre carriles es **asíncrona** (la
  confirmación sale cuando el resultado aparece, §6.4; el líder no
  se sienta a esperar) y el acuse del acompañante se sondea en ciclos
  posteriores (§10.1), nunca con una espera larga dentro del ciclo.

### 2.3 Las bandejas (todo son archivos, como en el resto del proyecto)

En la carpeta compartida por usuario (`_token_dir()`, la de
`tablero.json` y `avisos.jsonl`):

| Pieza | Forma | Quién escribe | Quién lee |
|---|---|---|---|
| `canales.json` | JSON con revisión y lock, patrón `cuentas.py` | UI y capa común (emparejamiento) | todos |
| `canal-estado.json` | JSON, tmp + replace, **un solo escritor: el líder** | el líder | el líder y la UI (lectura) |
| `canal-registro.jsonl` | append con lock, rotación 5 MB como `avisos.jsonl` | capa común | dueño (UI), auditoría |
| `canal-salientes/` | un `.json` por mensaje (tmp + replace) | destino canal, ofrecimiento de pedidos, respuestas | el líder (transmite y borra) |
| `canal-pedidos.json` | JSON con lock | quien ofrece un pedido; el líder al transmitir; cada carril al reconciliar los suyos | líder y UI |
| `canal-entrantes.jsonl` | append con lock, **solo añadir, jamás reescribir**; rotación por generaciones (§3.3) | el listener del webhook (oficial) y el acompañante (no oficial) | el líder, con cursor `(generación, byte)` en `canal-estado.json` |
| `canal-decisiones/` | un `.json` por orden + subcarpetas `hechas/` y `consumidas/` | el líder; el carril dueño (resultados y claims) | ambos carriles |
| `canal-lider.json` | JSON con época y latido (§2.2) | el líder | los dos carriles |

Configuración y estado de máquina van **separados** (corrección I13
del §17 bis): `canales.json` guarda lo que el dueño configura y el
emparejamiento (escrituras raras, con revisión); `canal-estado.json`
guarda lo que el líder mueve con cada mensaje (cursores, dedup,
ritmo, marcas) y por eso lo escribe un solo proceso sin control de
revisión. Mezclarlos hacía que cada mensaje disputara la revisión
con la UI y que una corrupción arrastrara a la vez la configuración
y los cursores (corrección B4).

Telegram no necesita `canal-entrantes.jsonl` (su `recibir` hace el
long polling directamente en el líder); los otros dos transportes sí:
su recepción es «alguien dejó un mensaje en el archivo» y el líder lo
consume con cursor, igual que el runner consume `runner-tasks/`.

## 3. Estado compartido: `canales.json` y el registro del canal

### 3.1 `canales.json` (esquema v1)

```json
{"version": 1, "revision": 0,
 "activo": "telegram" | "whatsapp-oficial" | "whatsapp" | null,
 "transportes": {
   "<nombre>": {
     "identidad": "•••" | null,
     "emparejado_ts": 0, "revocado_ts": 0,
     "codigo": {"sha256": "…", "creado_ts": 0, "vence_ts": 0,
                "intentos": 0} | null,
     "config": { }
   }},
 "avisos_info": ["division_hecha", "encargo_terminado",
                 "subtarea_fallida", "prueba_fisica_inicio",
                 "canal_prueba"],
 "limites": {"mensajes_hora": 30, "encargos_hora": 10,
             "consultas_hora": 12}}
```

Los cursores, la dedup y el ritmo **no** viven aquí: están en
`canal-estado.json` (§3.3).

- `identidad`: la identidad emparejada del dueño **en la forma del
  transporte** (chat_id numérico de Telegram, JID de WhatsApp,
  `wa_id`). En la UI se muestra enmascarada; en el archivo va en
  claro porque no es un secreto (es un identificador, como el id de
  una cuenta Muse) — pero jamás se escribe en logs ni en el registro
  del canal sin enmascarar.
- `codigo`: solo el SHA-256 del código de emparejamiento (§4), nunca
  el código. Sin código vivo, `null`.
- `config` por transporte: solo datos **no secretos** (p. ej. el
  `phone_number_id` y el `waba_id` del oficial, el puerto del
  listener del webhook y el comando de arranque del acompañante en
  el no oficial — validado, §10.3). Los secretos van a la bóveda
  (§11).
- Escritura con el patrón de `cuentas.py`: lock de archivo con ruptura
  de huérfano a los 15 s, control optimista por `revision`, tmp +
  `os.replace`. Lectura tolerante: archivo ausente o corrupto ⇒
  configuración vacía (sin canal activo) y aviso en el log — el canal
  nunca tumba el arranque por un JSON roto. Ojo a la consecuencia
  diseñada en el §3.3: «sin canal» por corrupción **no** puede
  arrastrar los cursores, porque ya no viven en este archivo.

### 3.2 `canal-registro.jsonl` (auditoría del canal)

Una línea por hecho, con el formato de los demás registros del
proyecto: `{"ts", "evento", "transporte", ...}`. Eventos:
`emparejado`, `revocado`, `codigo_generado`, `codigo_rechazado`,
`mensaje_recibido` (solo metadatos: remitente enmascarado, longitud,
`id_mensaje` y un resumen de 80 caracteres como el `resumir()` de
`permission-layer.py` — el texto íntegro del encargo ya vive en la
tarea y en `encargos.json`; aquí no se duplica), `mensaje_ignorado`
(con motivo: `sin_emparejar`, `remitente`, `duplicado`, `ritmo`,
`no_texto`), `encargo_creado` (id de tarea y carril destino),
`consulta` (cuál), `decision` (lo entendido: decisión, código del
pedido, resultado de `decidir_aprobacion`), `decision_sin_objetivo`,
`saliente` (tipo: aviso/pedido/respuesta, con el `mensaje_id` que
devolvió el transporte), `error_transporte`. La auditoría de
aprobaciones propiamente dicha sigue siendo `APR_LOG`
(`aprobaciones-registro.jsonl`, que ya anota `resuelto_por` y el canal
en cada evento): el registro del canal es su complemento de
transporte, no un sustituto.


### 3.3 `canal-estado.json` (el estado de máquina del líder)

```json
{"version": 1,
 "transportes": {
   "<nombre>": {
     "cursor": {"generacion": 0, "byte": 0} | {"offset": 0},
     "bot_id": null,
     "vistos": ["<id_mensaje como cadena>", ...],
     "en_proceso": {"<id_mensaje>": {"tid": "t-…", "ts": 0}},
     "marca_agua_ts": 0,
     "ultimo_entrante_ts": 0
   }},
 "ritmo": {"encargos": [ts...], "consultas": [ts...],
           "mensajes": [ts...]},
 "supervision": {"acompanante_avisado_ts": 0,
                 "relanzamientos": [ts...]}}
```

- Lo escribe **solo el líder** (tmp + `os.replace`, sin revisión: un
  solo escritor no la necesita). Si se corrompe o falta, se
  reconstruye vacío con dos cautelas que lo hacen seguro
  (corrección B4): los cursores nacen **al final** de
  `canal-entrantes.jsonl` (nunca al principio: no se reprocesa la
  historia) y la marca de agua (§5.5) nace en el instante de la
  reconstrucción, así que todo lo anterior se descarta como viejo.
- `cursor`: para Telegram, el `offset` de `getUpdates`; para los
  transportes de archivo, `(generación, byte)` sobre
  `canal-entrantes.jsonl`. La **rotación por generaciones**
  (corrección I4): cuando el archivo supera 5 MB y el cursor está al
  final, el líder lo renombra a `.1` (una sola generación de
  respaldo) y la generación sube; los escritores (listener y
  acompañante) añaden siempre bajo el lock del archivo, abriendo la
  ruta *tras* tomarlo, así que una rotación entre su apertura y su
  escritura no puede colar una línea en la generación vieja.
- `vistos`: los últimos 200 `id_mensaje` procesados, **siempre como
  cadenas** (corrección I3: el `update_id` de Telegram es un entero
  y los ids de WhatsApp son cadenas; tras pasar por JSON, comparar
  entre tipos falla en silencio).
- `en_proceso`: el registro durable del §5.5 (`id_mensaje → tid`
  antes de crear la tarea).
- `bot_id` (Telegram): el id del bot según `getMe`. Si cambia (el
  dueño pegó el token de otro bot), el cursor y `vistos` se
  reinician y el emparejamiento se invalida (corrección I3): los
  offset de otro bot no significan nada aquí.
- `marca_agua_ts`: la marca de recepción (hora del PC) del último
  mensaje procesado; lo anterior a ella o a `emparejado_ts` se
  descarta como `viejo` (§5.5).
- `ultimo_entrante_ts` (oficial): cuándo escribió el dueño por última
  vez; decide si un envío va en texto libre o directo a plantilla
  (§9, corrección I7).
- `ritmo`: las marcas de la última hora para los límites del §5.6.
- `supervision`: las marcas del §10.3 (aviso de acompañante caído y
  sus relanzamientos), con sus propios topes (corrección I14).

## 4. Emparejamiento y revocación

El emparejamiento ata una identidad del transporte a «el dueño». Es el
mismo baile para los tres transportes; lo único específico es cómo se
abre el chat (§8–§10).

### 4.1 El baile

1. En la app (página Cuentas → «Canales», §12), el dueño elige el
   transporte y pulsa **Emparejar**. La app genera un código de 8
   caracteres sin ambiguos (`23456789ABCDEFGHJKMNPQRSTUVWXYZ`), lo
   muestra en grande con su caducidad (**10 minutos**) y guarda en
   `canales.json` solo su SHA-256 (con el nombre del transporte como
   sal: `sha256("<transporte>:<codigo>")`), `vence_ts` e
   `intentos = 0`. Generar un código nuevo mata el anterior.
2. El dueño escribe ese código como mensaje en el chat del canal
   (al bot de Telegram, al número de negocio, o a su propio chat en
   el no oficial). El líder lo recibe como un mensaje más.
3. Si hay un código vivo para ese transporte y el hash coincide y no
   ha vencido: la identidad del remitente queda emparejada
   (`identidad`, `emparejado_ts`), el código se quema (un solo uso),
   se anota `emparejado` en el registro, sale un aviso local de nivel
   `accion` («Canal <transporte> emparejado con •••») — para que el
   dueño lo vea en la app aunque el emparejamiento lo hubiera
   provocado otra persona con el código — y el canal responde al
   teléfono: «Emparejado ✓. Escríbeme un encargo, o «ayuda» para ver
   qué entiendo.»
4. Si el código no coincide: `intentos += 1`, se anota
   `codigo_rechazado` y **no se responde nada** (responder confirmaría
   que hay un emparejamiento en curso). A los 5 intentos el código
   muere. **Solo cuenta como intento un texto que, normalizado, tenga
   la forma de un código** (8 caracteres del alfabeto del paso 1,
   nada más en el mensaje; corrección I1 del §17 bis): un `/start`,
   un «hola» o el ruido de un desconocido no gastan intentos — sin
   esta regla, cinco curiosos que escriban al bot (los bots son
   localizables por nombre) matarían el código antes de que el dueño
   lo use. Si no hay código vivo, un mensaje con pinta de código es
   un mensaje más de un desconocido: silencio y `mensaje_ignorado`.

Propiedad que hay que decir en claro: **quien envíe primero el código
correcto se empareja**. El código es una credencial de un solo uso
con ventana de 10 minutos; por eso solo nace de un gesto deliberado
en la app, caduca rápido, la app muestra con quién quedó emparejado
el canal y revocarlo es un clic (§4.2). Es el mismo compromiso que el
emparejamiento por código de cualquier dispositivo vinculado.

### 4.2 Revocación (teléfono perdido)

- Botón **Revocar** en la app: borra `identidad`, quema cualquier
  código vivo, anota `revocado_ts` y el evento, y el canal deja de
  procesar a ese remitente en el siguiente mensaje (la identidad se
  lee de `canales.json` en cada mensaje: no hay caché que purgar).
- Re-emparejar (teléfono nuevo) = repetir el baile; el éxito del
  nuevo emparejamiento sustituye la identidad anterior.
- En el transporte no oficial hay además la desvinculación del
  dispositivo en WhatsApp (el dueño puede hacerlo desde su teléfono):
  el acompañante lo detecta y el estado pasa a «desvinculado» (§10.3);
  la capa común lo trata como una revocación de hecho y avisa.
- La revocación corta el *procesado*, no la historia: el registro del
  canal y las auditorías conservan lo que ese teléfono hizo mientras
  estuvo emparejado.

## 5. Entrada: del mensaje del dueño a la tarea

El líder procesa cada mensaje normalizado en este orden (función
`canales.procesar(base_dir, mensaje, efectos)` con los efectos
inyectados — escribir tarea, decidir, responder — para poder probar
la lógica sin red ni monolito):

### 5.1 Puertas previas (en orden, todas auditadas)

1. **Deduplicación** (§5.5): si `(transporte, id_mensaje)` ya se
   procesó, se confirma la recepción y no se hace nada más.
2. **Identidad**: si el transporte no tiene identidad emparejada, el
   único mensaje procesable es un intento de emparejamiento (§4);
   cualquier otra cosa se ignora. Si la hay y el remitente no es
   ella: ignorado (`remitente`). Sin excepciones: ni «es que escribo
   desde otro número» — para eso está re-emparejar desde la app.
3. **Tipo**: solo texto. Una nota de voz, una foto o un sticker del
   dueño reciben, como mucho, una respuesta amable («por ahora solo
   entiendo texto») con tope de una por hora, y se anotan
   (`no_texto`). Nada se convierte en tarea.
4. **Anotación**: `mensaje_recibido` en el registro (principio 5)
   antes de clasificar.
5. **Clasificación** (§5.2): hay que clasificar *antes* de aplicar
   el ritmo, porque el ritmo trata a cada clase distinto
   (corrección I2 del §17 bis).
6. **Ritmo** (§5.6): si el dueño supera el límite, los encargos y
   consultas nuevos se rechazan con una respuesta breve; las
   **decisiones nunca se rechazan por ritmo ni cuentan para él**
   (denegar una aprobación por ritmo sería fallar abierto al revés:
   el pedido sigue esperando en la app, pero el dueño cree que
   decidió; y una ronda de aprobaciones no debe bloquear los
   encargos siguientes).

### 5.2 Clasificación del texto

`canales.clasificar(texto, contexto)` — pura — devuelve una de:

- `decision`: el texto es una decisión sobre un pedido (§6), con su
  objetivo resuelto o por resolver.
- `consulta`: una pregunta de estado con respuesta inmediata y sin
  efectos (§5.4).
- `encargo`: todo lo demás. **El defecto es encargo**: el canal
  existe para mandar trabajo; un texto que no es decisión ni
  consulta es trabajo para las Muses.

El contexto para clasificar lleva: los pedidos ofrecidos y pendientes
(de `canal-pedidos.json`), si hay una decisión a medias (§6.3) y la
lista de cuentas habilitadas con carril (para el enrutado del §5.3).
La clasificación es conservadora a propósito: para que un texto sea
`decision` tiene que pasar la gramática estricta del §6.3 (verbo y
nada más que verbo, código, duración y cortesía) o ser la respuesta
a una pregunta del propio canal. Y hay un cuarto desenlace cuando el
texto *parece* decisión pero le sobra texto y hay pedidos
pendientes: **ni decisión ni encargo** — se pregunta (§6.3). «No
borres nada» dentro de un encargo jamás se lee como un rechazo
(misma regla que la clasificación de riesgos del monolito: la
negación dentro del encargo no cuenta como acción).

### 5.3 Encargos: crear la tarea

- Id de la tarea **derivado del mensaje**: `t-<fecha>-<hash>` donde
  el hash son 16 hex del SHA-256 de `"<transporte>:<id_mensaje>"`
  (válido para `_safe_id`). Es la clave de idempotencia de la
  entrada (corrección B4 del §17 bis): si el transporte reentrega el
  mensaje tras una caída del líder, la tarea regenerada tiene el
  mismo id y reescribir su archivo es inocuo; y antes de escribirla,
  el líder ya dejó anotado `id_mensaje → tid` en `en_proceso`
  (§5.5), así que ni siquiera hace falta regenerarla.
- **Enrutado por cuenta**: solo `@<cuenta>` al inicio es un enrutado
  explícito (corrección I10 del §17 bis). La forma `<cuenta>:`
  también enruta **si** lo que precede a los dos puntos es una
  cuenta habilitada con carril; si no lo es («Ojo: no toques
  producción», «Importante: …»), el texto entero es un encargo
  normal para el carril del líder, sin mensaje de error. Con
  `@<cuenta>` nombrando una cuenta inexistente o sin carril, no se
  adivina: se responde «no conozco la cuenta «x»; las que hay son:
  …» y no se crea nada (ahí el dueño sí quiso enrutar). El prefijo
  se retira del prompt solo cuando enruta.
- El archivo se escribe en el `runner-tasks/` del carril destino con
  el orden observable de siempre (tmp + `os.replace`, como
  `relevo.entregar`):

  ```json
  {"id": "t-20261116-…", "tipo": "encargo",
   "prompt": "<el texto del dueño, tal cual>",
   "canal": "telegram"}
  ```

  Sin raíz (la genera `relevo.registrar_encargo`) y sin cuenta (la
  pone el carril que lo recoge). **Si el carril destino es el B**, el
  archivo lleva además la forma derivada que ya usan la consulta de
  la Fase 2 y la entrega del relevo (`relevo.entregar`), porque la
  guardia de ese carril (`_lane_guard`) rechaza sin ejecutar todo
  task que no la traiga: `"lane": "b"`, `"cwd"` = la carpeta del
  carril B y `"archivos": ["<carril B>/encargos/<tid>.md"]` — la
  forma exacta que la excepción de entregas derivadas de
  `validate_task` acepta (corrección 3 del §14 ter de la Fase 4). Sin
  esto, un encargo enrutado a la segunda cuenta moriría en la puerta
  de su propio carril. La derivación **se reutiliza, no se
  reescribe** (corrección I9 del §17 bis): la implementación extrae
  o comparte la que ya hace `relevo.entregar`, con su orden
  observable — primero se escribe el `.md` dentro de
  `<carril B>/encargos/` (con el prompt del encargo y su cabecera de
  metadatos) y después el `.task.json` — para que ningún lector vea
  una tarea cuyos archivos aún no existen. Desde ahí, el encargo es
  indistinguible de uno nacido en la app salvo por su `canal`, que
  es exactamente lo que el diseño busca.
- Respuesta inmediata al teléfono: «Encargo recibido ✓ lo registra
  <cuenta receptora>. Te aviso cuando se divida y cuando se cierre.»
  (la cuenta receptora es la del carril destino). El aviso
  `encargo_recibido` de la Fase 4 **no** se reenvía por el destino
  canal cuando el encargo nació de ese mismo transporte (§7.2): esta
  respuesta ya es la confirmación, y dos mensajes por lo mismo es
  spam.
- Si escribir la tarea falla (disco, carril no instalado): se anota,
  se responde «no pude registrar el encargo: <motivo>» y no se finge
  éxito. El mensaje queda en el registro con su resumen: el dueño
  puede reenviarlo.

### 5.4 Consultas de estado (sin efectos)

Una consulta es **el mensaje entero** igual a la palabra clave tras
normalizar (corrección I11 del §17 bis): `estado`, `tablero`,
`pendientes` o `ayuda`, con la puntuación final que el teléfono
añada («¿estado?» vale; «estado del repo X, revísalo» es un
encargo, porque no es solo la palabra).

Respuestas inmediatas leyendo los archivos compartidos y
`canal-pedidos.json` — nunca abriendo la `cola.db` de otro carril
(aislamiento de carriles: el líder no lee bases ajenas; lo que el
otro carril quiere contar ya lo publicó en archivos compartidos o en
`canal-pedidos.json` al ofrecer sus pedidos):

- `estado`: modo de presencia, por cuenta su estado y % del tablero,
  encargos abiertos con su estado y nº de subtareas, pedidos
  esperando decisión (cuántos y el que antes vence) y tareas en
  curso que el tablero conoce.
- `tablero`: solo las cuentas con su % y estado.
- `pendientes`: los pedidos ofrecidos y aún pendientes, con su
  código corto, nivel, motivo breve y vencimiento («responde
  *aprobar XXXX*»).
- `ayuda`: la lista de lo que el canal entiende (encargos, consultas,
  decisiones y el enrutado con @cuenta).

### 5.5 Deduplicación y exactamente-una-vez en la entrada

Los transportes reentregan (Telegram confirma por offset y puede
repetir si el proceso muere entre recibir y confirmar; Meta
reintenta el webhook; el líder puede morir entre leer una línea de
`canal-entrantes.jsonl` y guardar el cursor). La entrada se hace
exactamente-una-vez con tres piezas (corrección B4 del §17 bis):

1. **Registro durable previo**: antes de crear nada, el líder anota
   en `canal-estado.json` → `en_proceso[id_mensaje] = {tid, ts}` y
   lo guarda. Si muere a mitad, al volver encuentra la anotación: la
   tarea con ese `tid` (derivado del propio mensaje, §5.3) o ya
   existe — y se da por procesado — o se crea ahora, una sola vez.
   Al completar el procesado, el id pasa a `vistos` y sale de
   `en_proceso`.
2. **`vistos`**: los últimos 200 ids procesados por transporte,
   siempre como cadenas (§3.3). Un duplicado se confirma y se
   descarta (`duplicado`) sin tocar nada más.
3. **Marca de agua**: se descarta como `viejo`, sin procesar, todo
   mensaje cuyo `ts_transporte` sea anterior a `emparejado_ts` (un
   mensaje de antes del emparejamiento no puede ser una orden del
   dueño *por el canal*) o a la marca de agua del transporte (la
   recepción del último procesado, con 5 min de holgura por relojes
   de transporte torpes). Si el cursor se pierde, se reconstruye al
   final del archivo (§3.3): la historia no se reprocesa jamás,
   aunque la dedup esté vacía.

Sin esta red, un «aprobar» reentregado llegaría dos veces a
`decidir_aprobacion` — que ya es idempotente a su manera (la
segunda vez el pedido ya no está pendiente y se apunta como
tardía) — y un encargo duplicado sí se ejecutaría dos veces: por
eso la dedup va *antes* de clasificar, no dentro de cada camino.

### 5.6 Límites de ritmo

Ventanas deslizantes de una hora sobre el `ritmo` de
`canal-estado.json` (por instalación, no por transporte: cambiar de
canal no reinicia el contador):

- `mensajes_hora` (30): cuenta todo mensaje del dueño **que no sea
  una decisión** (corrección I2: las decisiones ni se cortan ni
  cuentan); al superarlo, encargos y consultas se responden con
  «vas muy rápido…» y no se crean. Las decisiones pasan siempre
  (§5.1).
- `encargos_hora` (10) y `consultas_hora` (12): topes específicos.
- Los límites son configuración en `canales.json`, no constantes: el
  dueño puede subirlos en la app si su uso real lo pide. Su función
  no es desconfiar del dueño sino acotar el daño de un teléfono
  comprometido o de un bucle de reentregas, y dejar el exceso
  auditado.

## 6. Decisiones por chat: el parseo y la confirmación

### 6.1 Ofrecer el pedido (salida)

Cuando nace un pedido de aprobación (§12, gancho en
`_park_for_approval` y en `aprobaciones_adoptar`), el proceso que lo
crea — cualquiera de los dos carriles — hace tres cosas tras
`_apr_nuevo`. El ofrecimiento es **idempotente por `approval_id`**
(corrección B2 del §17 bis): si la entrada ya existe en
`canal-pedidos.json` (la adopción al arrancar vuelve sobre pedidos
que ya se ofrecieron), se conserva su código y su `mensaje_id` y no
se vuelve a encolar nada.

1. Lo anota en `canal-pedidos.json`:
   `{"<approval_id>": {"carril", "nivel", "raiz", "tarea",
   "codigo": "XXXX", "vence_ts", "ofrecido_ts", "mensaje_id": null}}`.
2. Si el nivel es **R1 o R2** y hay un transporte activo y emparejado,
   encola en `canal-salientes/` el texto del pedido — el que ya
   produce `texto_pedido(row)`: qué se quiere hacer, nivel,
   vencimiento en hora de Caracas y «si no respondes, NO se hace» —
   más la línea de respuesta: «Responde *aprobar XXXX*, *rechazar
   XXXX* o *espera 30 XXXX*.» El `codigo` es el alias corto del
   pedido (§6.2).
3. Si el nivel es **R3**: no se ofrece (§7.3); en `canal-pedidos.json`
   queda anotado con `"ofrecido": false` para que las consultas
   puedan decir «hay un R3 esperando **en la app**» sin código.

El líder, al transmitir el mensaje de un pedido, rellena
`mensaje_id` en `canal-pedidos.json`: ese id es el que permite
resolver el objetivo por cita (§6.2). Si el transporte cae entre el
ofrecimiento y la transmisión, el pedido sigue en la bandeja y sale
cuando vuelva — y si para entonces ya venció, el líder lo retira de
la bandeja sin enviarlo (un pedido vencido no se ofrece: confundiría;
la decisión tardía ya tiene su tratamiento en el circuito).

### 6.2 El alias corto y la resolución del objetivo

El `approval_id` completo (`apr-<raíz>-<fecha>-<hex4>`) es imposible
de teclear en un teléfono. Cada pedido ofrecido lleva un **código
corto** propio: 4 caracteres **aleatorios del alfabeto sin ambiguos
del §4.1** (que tiene letras de sobra: un código nunca es «solo
dígitos», corrección I5 del §17 bis — con dígitos, «aplazar 1024»
sería ambiguo entre código y 1024 minutos). El código se genera
**bajo el lock de `canal-pedidos.json`** y único entre los pedidos
pendientes ofrecidos de los dos carriles (los dos ofrecen a la vez);
si el azar lo repite, se sortea otro. El código no es un secreto —
el pedido entero solo lo recibe la identidad emparejada — es un
*nombre* tecleable.

Además, `canal-pedidos.json` se **reconcilia**: cada carril, en su
ciclo de servicio, contrasta *sus* entradas contra *su* `cola.db` y
marca `resuelto` (con el estado final) lo que ya no esté
`pendiente` — se decidió en la app, venció o lo aplicó una orden —
sin abrir jamás la base del otro (corrección B2). Una entrada
resuelta ya no cuenta para ninguna resolución de objetivo, y la
consulta `pendientes` las omite.

Una decisión entrante resuelve su objetivo en este orden, y en
ningún otro. Solo son **objetivos válidos** los pedidos ofrecidos
(`ofrecido: true`), pendientes y **ya transmitidos** — con
`mensaje_id` no nulo y transmitidos antes de la recepción del
mensaje entrante: un pedido que el dueño aún no ha podido ver no se
puede decidir «a ciegas» por un «sí» que venía de antes
(corrección B2):

1. **Cita**: el mensaje cita/responde (`cita_id`) al mensaje de un
   pedido válido ⇒ ese pedido. (La cita a la *notificación* de un R3
   no resuelve objetivo: §7.3.)
2. **Código**: el texto trae un código que coincide con un pedido
   válido ⇒ ese pedido.
3. **Único pendiente**: no hay cita ni código y existe exactamente
   un pedido válido ⇒ ese pedido.
4. **Ambigüedad o vacío**: hay varios o ninguno ⇒ **no se decide
   nada**. Se responde listando los pedidos con sus códigos («tienes
   2 pedidos esperando: …») o avisando de que no hay ninguno. Jamás
   se decide «el más reciente» por proximidad: con dos pedidos, un
   «sí» sin objetivo es una moneda al aire sobre acciones R2.

### 6.3 La gramática (función pura `canales.parsear_decision`)

La gramática es **estricta** (corrección B5 del §17 bis: una regla
con «palabras de sobra permitidas» convierte frases condicionales en
aprobaciones: con acentos quitados, «si puedes revisa el log» se
leía como un sí con 4 palabras detrás, y «sí pero primero haz
copia» aprobaba perdiendo la condición). La regla única:

> Una decisión es válida solo si, quitando el **verbo**, el
> **código**, la **duración** (en aplazar) y una lista cerrada de
> **cortesía** (`por favor`, `gracias`), **no queda ninguna
> palabra**. La decisión tiene que ser el mensaje entero.

Reconocimiento del verbo: primero sobre el texto *sin* normalizar
acentos, porque «sí» con tilde es afirmación y «si» sin tilde es un
condicional que **no** es verbo de decisión en ninguna lista;
después, minúsculas y espacios colapsados para el resto:

- **Aprobar**: `aprobar`, `aprobado`, `sí` (solo con tilde en el
  texto original), `ok`, `vale`, `dale`, `adelante`, `hazlo`. Con
  código en cualquier posición: «aprobar xkcd», «xkcd sí».
- **Rechazar**: `rechazar`, `rechazado`, `no`, `cancelar`,
  `descartar`. «no» con la misma regla: el mensaje entero ha de ser
  la negación (más código/cortesía). «No borres el archivo grande»
  deja palabras ⇒ no es decisión (y con pedidos pendientes dispara
  la pregunta del párrafo siguiente; sin ellos, es un encargo).
- **Aplazar**: `aplazar`, `aplaza`, `espera`, `esperar`, `posponer`
  + duración obligatoria en el mismo mensaje o en el siguiente:
  `30`, `30 min`, `30m`, `2 h`, `2 horas`, `1 hora`, `media hora`
  (30), `un cuarto de hora` (15). La duración se convierte a minutos
  y la valida `decidir_aprobacion` (1..1440): el parseo no inventa
  topes propios. «espera» sin duración ⇒ el canal pregunta «¿cuánto
  tiempo?» y anota una **decisión a medias** en `canal-pedidos.json`
  (`{"decision_en_curso": {"approval_id", "tipo": "aplazar",
  "vence_ts": ahora + 300}}`); el siguiente mensaje del dueño, si es
  solo una duración, la completa; si es otra cosa, la decisión a
  medias se descarta y el mensaje se clasifica por sí mismo. La
  decisión a medias caduca a los 5 minutos y nunca sobrevive a un
  cambio de objetivo.
- **Duración suelta** («30 min» a secas) con un único pedido válido
  pendiente y sin decisión a medias: se interpreta como su aplazar
  (es la respuesta natural a «¿cuándo lo hago?») y se confirma con
  el eco del §6.5 como cualquier otra decisión.

**La zona gris se pregunta, no se adivina**: si el mensaje *abre*
con un verbo de decisión pero le sobra texto tras quitar código,
duración y cortesía, y hay pedidos válidos pendientes, no se decide
**ni se crea el encargo**: el canal responde «¿esto es una respuesta
al pedido XKCD («…») o un encargo nuevo?» y anota una decisión a
medias de tipo `aclarar` (5 min) con el texto guardado. Si el dueño
contesta «el pedido» (o repite el código, o el verbo limpio), se
aplica la decisión sobre ese pedido; si contesta «encargo» (o manda
otro mensaje), el texto guardado se convierte en encargo. Es un
mensaje extra a cambio de no ejecutar jamás una condición perdida
ni tragarse un encargo que abría con «dale».

Todo lo que el parseo no reconoce con seguridad **no es una
decisión**: cae a la clasificación general (§5.2) y normalmente será
un encargo. Fallar hacia encargo es seguro (el encargo pasará sus
propias puertas); fallar hacia «aprobar» sería catastrófico.

### 6.4 Aplicar la decisión (y el problema de los dos carriles)

El líder llama a `decidir_aprobacion(approval_id, decision,
canal=<transporte>, minutos=...)`:

- Si el pedido es de **su propio carril**, la llamada es directa:
  la fila está en su `cola.db` y el archivo en su `esperando/`.
- Si el pedido es del **otro carril**, el líder **no** abre su base
  ni mueve sus archivos (aislamiento de carriles): deja una orden en
  `canal-decisiones/` (`{"id", "approval_id", "decision",
  "minutos", "canal", "pedida_ts"}`) y el proceso dueño la consume
  en su ciclo corto (§12) y la aplica con **su**
  `decidir_aprobacion` local — el mismo código, el mismo lock
  `_APR_LOCK`, la misma auditoría — dejando el resultado en
  `canal-decisiones/hechas/<id>.json`.

La aplicación es **exactamente-una-vez por `approval_id`, no por id
de orden** (corrección B1 del §17 bis):

- El líder, antes de crear una orden, comprueba que no haya ya una
  en vuelo para ese `approval_id` (en `canal-decisiones/` sin
  consumir o con resultado aún no leído): si la hay, **no crea otra**
  — la decisión del dueño se adjunta a la orden existente y la
  confirmación saldrá de su resultado. Así, que el dueño repita
  «aprobar XKCD» o que el transporte reentregue su mensaje no
  fabrica una segunda aplicación.
- El carril dueño, antes de aplicar una orden, toma un **claim**
  atómico: crea `canal-decisiones/consumidas/<approval_id>` con
  `os.O_EXCL`. Si ya existe, no aplica nada: responde con el
  resultado ya registrado en `hechas/`. Si el proceso muere entre
  leer la orden y dejar el resultado, al rearrancar ve el claim y la
  orden y sabe que la aplicación quedó en el aire: la resuelve
  consultando *su* fila — si ya no está `pendiente`, el resultado es
  el que `decidir_aprobacion` devuelva al llamarla de nuevo (sobre
  una fila resuelta devuelve el camino de tardía sin cambiar la
  decisión: esa es la garantía del circuito en la que este diseño se
  apoya, y queda fijada como contrato en el §17 bis); si sigue
  `pendiente`, aplica la orden. Un pedido que vence a mitad del
  traspaso cae en el mismo camino: se anota tardía, la orden queda
  gastada con ese resultado y el líder lo aprende al leer `hechas/`.
- La confirmación es **asíncrona** (corrección B3: el líder no se
  sienta 90 s a esperar con el latido en pausa). El líder encola un
  «recibido, aplicando…» solo si el resultado no está ya al crear la
  orden, y la confirmación con el mensaje del circuito sale como
  mensaje aparte en el ciclo en que `hechas/<id>.json` aparece. Si
  el carril dueño está caído, el dueño lo sabe por ese primer
  mensaje («está en manos del carril B; si está caído, se aplicará
  cuando vuelva») en vez de por un silencio.

### 6.5 La confirmación de lo entendido

Toda decisión aplicada (o intentada) recibe respuesta inmediata con
tres piezas: **qué se entendió** («Aplazar 30 min»), **de qué pedido**
(resumen: nivel, motivo breve, raíz) y **qué hizo el circuito** (el
mensaje que devuelve `decidir_aprobacion`, que ya está redactado
para el dueño: «aplazada 30 min; arranca a las …», «aprobada; vuelve
a la cola», «rechazada»). Si el circuito dice que llegó tarde o que
ya estaba resuelto, su mensaje se reenvía tal cual: ya explica que
no se ejecutó nada y cómo reencolar. Y si el «pedido» era un R3 no
ofrecido, la respuesta no viene del circuito (el canal ni lo llama,
corrección B6): es la de la capa común — «ese pedido es R3: solo se
decide en la app» — con el intento anotado en el registro del canal.

Ninguna decisión se aplica «en silencio»: si el dueño dijo algo y el
canal no le contesta qué entendió, el canal está roto por definición.


## 7. Salida: avisos, pedidos y resultados por el canal

### 7.1 Qué sale y qué no

El destino `canal` de `avisos.py` filtra antes de encolar (un aviso
que no pasa el filtro ni siquiera entra en la bandeja):

- **Nivel `accion`: siempre.** Son los que necesitan al dueño:
  aprobaciones (por su vía propia del §6.1, no por esta), pruebas
  físicas esperando, cuentas en cuarentena o sin latido, dual sin
  resolver, bloqueos. El canal es *el* sitio donde un `accion` tiene
  sentido si el dueño está fuera.
- **Nivel `info`: solo la lista `avisos_info` de `canales.json`**
  (por defecto: `division_hecha`, `encargo_terminado`,
  `subtarea_fallida`, `prueba_fisica_inicio`, `canal_prueba`). El
  registro `avisos.jsonl` lo guarda todo; el teléfono solo recibe lo
  que el dueño querría que le vibrara el bolsillo. La lista se edita
  en la app (§12).
- **Formato**: el texto del aviso tal cual (ya nace redactado para el
  dueño y acotado a 500 caracteres), con prefijo «⚠️ » si es de nivel
  `accion`. Texto plano en los tres transportes: nada de Markdown
  (el Markdown de Telegram/WhatsApp rompe con caracteres sueltos de
  un motivo cualquiera, y un aviso roto es peor que uno feo).

### 7.2 Anti-duplicados de salida

Dos avisos de la Fase 4 tienen ya su confirmación por otra vía cuando
el encargo nació del propio canal, y reenviarlos sería decir dos
veces lo mismo:

- `encargo_recibido` con `canal` del encargo == transporte activo:
  la respuesta inmediata del §5.3 ya confirmó la recepción ⇒ el
  destino no lo encola. (El destino puede saberlo: el aviso lleva la
  `tarea`, y el registro de encargos dice su canal; si no se puede
  comprobar, se envía: ante la duda, un aviso de más, no de menos.)
- `encargo_terminado` de un encargo nacido del canal: el mensaje que
  sale es el **resumen de cierre** (§7.4), que sustituye al aviso
  pelado — **pero solo si el resumen se encoló con éxito** en la
  bandeja saliente (corrección B9 del §17 bis): si el gancho del
  §7.4 no pudo encolar, el aviso `encargo_terminado` sale como red
  de seguridad, porque el dueño nunca debe quedarse sin cierre. El
  aviso sigue en `avisos.jsonl`, como todo.

### 7.3 Los R3 solo se notifican (y no se deciden ni por accidente)

Un pedido R3 con transporte emparejado genera un único mensaje de
notificación, sin código y sin vía de respuesta: «Hay un pedido R3
esperando **en la app**: <motivo>. Solo se aprueba con el PC
delante.» Es información, no una oferta: `canal-pedidos.json` lo
marca `ofrecido: false`, no tiene código y **no es objetivo
decidible por ningún camino** (ni código, ni único pendiente, ni
cita — la cita a su notificación no resuelve objetivo, §6.2).

Si el dueño lo cita y escribe «aprobar», la capa común **no llama a
`decidir_aprobacion`** (corrección B6 del §17 bis): responde «ese
pedido es R3: solo se decide en la app», lo anota como
`decision_r3_no_ofrecida` y el pedido queda intacto. La razón es de
peso: con `canal != "app"` el circuito no solo deniega un R3 — lo
**cierra y mata su tarea**. Enrutar el intento «para que el circuito
lo deniegue» le daría al canal el poder de cancelar trabajo R3 que
el dueño quizá ni quería tocar, y quien controlara la sesión del no
oficial podría vaciar todos los R3 pendientes citando y escribiendo
«ok». La muralla del circuito sigue ahí como segunda línea y se
prueba en unitarias llamándola directamente con
`canal="telegram"`; el camino normal no se apoya en ella.

### 7.4 El resumen de cierre vuelve por el canal de entrada

El cierre de un encargo ya produce su resumen
(`supervision` → `ctx["escribir_resumen"]` → `_f4_escribir_resumen`,
que lo deja en los `runner-results` de la receptora). El gancho va
**ahí, en `_f4_escribir_resumen`** — el punto único por el que pasa
todo cierre de encargo — y no en `_write_result` (corrección B9 del
§17 bis: el resultado-resumen que escribe `_f4_escribir_resumen` no
tiene por qué pasar por `_write_result`, y su `id` no es la raíz: la
tarea del encargo es `t-…` y la raíz es `enc-…`, así que una
condición `id == raiz` no se cumpliría nunca). El gancho,
`_f5_resultado_a_canal(raiz, resultado)`, identifica el encargo por
su raíz en `encargos.json` y actúa solo si nació de un transporte
(`canal` en {transportes}): encola en `canal-salientes/` un mensaje
con el resumen («Encargo <raíz>: 2 de 2 subtareas terminadas…» + el
detalle por subtarea que ya trae el texto del resumen), dirigido al
chat emparejado, y **devuelve si pudo encolar** — de eso depende la
supresión del aviso `encargo_terminado` del §7.2. Las subtareas
nunca escriben al canal por su cuenta, y un encargo nacido en la app
no genera este mensaje (su `canal` es `app` o `null`).

Un segundo gancho, en `_write_result` junto a
`_f4_resultado_a_buzon`, cubre el caso feo: una tarea con `canal` de
transporte que cierra en `necesita_decision` sin pasar por el relevo
(p. ej. la denegación instantánea de un R3 al clasificar) deja su
reporte también en el canal, para que el dueño sepa que aquello no
se hizo y por qué. Regla: resultado con `canal` de transporte,
`estado == "necesita_decision"` y sin raíz de encargo ⇒ mensaje con
el motivo del resultado, acotado. (Si la tarea denegada es una
subtarea de un encargo, el aviso inmediato también sale — el dueño
se entera en el momento — y el resumen de cierre lo recogerá
después como subtarea fallida: no es un duplicado, es el mismo
hecho en dos momentos, como en la app.)

### 7.5 La bandeja saliente en detalle

- Cada mensaje es un archivo `canal-salientes/<ts>-<uuid8>.json`:
  `{"id", "creado_ts", "tipo": "aviso"|"pedido"|"respuesta"|"resumen",
  "texto", "meta": {...}}` (`meta` lleva el `approval_id` si es un
  pedido, el `responder_a` si es la confirmación de una orden…).
  Orden de transmisión: por `creado_ts` (el nombre ya ordena).
- El líder transmite y **borra** el archivo solo tras el éxito del
  adaptador; si `transmitir` devuelve `None` o lanza, el mensaje se
  queda con un contador de intentos en su propio archivo y se
  reintenta en el siguiente ciclo, con tope de 5 intentos: al quinto
  se mueve a `canal-salientes/fallidos/` y se anota
  `error_transporte` (el aviso original sigue en `avisos.jsonl`: el
  canal nunca es la única copia de nada).
- Un pedido cuyo `vence_ts` ya pasó cuando le toca salir se retira
  sin transmitir (§6.1) y se anota.
- La bandeja es también el cortafuegos de ritmo de salida: si hay
  más de 20 mensajes esperando, los `info` nuevos se descartan al
  encolar (quedan en el registro) y los `accion` nunca se descartan.
  Un transporte caído durante horas no puede convertirse en una
  avalancha al volver.

## 8. Transporte: Telegram (`canal_telegram.py`)

El más simple de los tres: API HTTP de bots, sin URL pública (long
polling), sin acompañante, solo stdlib (`urllib`) como el resto del
proyecto.

- **Qué necesita del dueño**: crear un bot con @BotFather
  (`/newbot`) y pegar su token en la app. Nada más: ni número, ni
  cuenta de desarrollador, ni coste.
- **Credencial**: el token va a la bóveda como `canal:telegram`
  (§11). El adaptador lo pide por el getter inyectado en cada ciclo
  de polling (no lo guarda en el objeto: si el dueño lo cambia en la
  app, el siguiente ciclo ya usa el nuevo).
- **Entrada**: `getUpdates` con `offset` = cursor de
  `canal-estado.json`, `timeout` de 20 s (tope del §2.2: ningún paso
  del ciclo bloquea más que una fracción del umbral de liderazgo; el
  long poll marca el ritmo del ciclo del líder cuando Telegram es el
  transporte) y `allowed_updates: ["message"]`. Solo se avanza el
  offset tras procesar y anotar cada mensaje (principio 5): un
  mensaje cuyo registro falla se reentrega en el siguiente poll. De
  cada update se normaliza: `remitente = message.chat.id` (en un
  chat privado, el id del dueño), `id_mensaje = str(update_id)`
  (siempre cadena, §3.3), `cita_id = reply_to_message.message_id`
  si lo hay. Solo se procesan chats **privados**
  (`chat.type == "private"`, corrección I1 del §17 bis): si alguien
  añade el bot a un grupo, ese grupo tiene su propio `chat.id` y
  emparejarlo convertiría en «dueño» a todos sus miembros; los
  mensajes de grupo se ignoran enteros.
- **Salida**: `sendMessage` con `chat_id` = identidad emparejada y
  texto plano (sin `parse_mode`). Devuelve el `message_id`, que el
  líder anota donde toque (pedidos, §6.1).
- **Emparejamiento**: el dueño abre el chat con el bot y pulsa Start
  (eso no empareja nada: solo abre el chat); después manda el código
  de la app (§4). El `chat_id` se aprende de ese mensaje.
- **Disponible**: hay token en la bóveda y `getMe` responde. Si el
  token es inválido, `disponible()` es False y el estado en la UI lo
  dice («token rechazado por Telegram») en vez de reintentar en
  bucle. `getMe` sirve además para vigilar el `bot_id` (§3.3): si el
  dueño pega el token de *otro* bot, el cursor y la dedup se
  reinician y el emparejamiento se invalida, porque los `update_id`
  del bot nuevo no tienen relación con los guardados.
- **El token jamás llega a un log** (corrección I15): la URL de la
  API *es* `api.telegram.org/bot<token>/…` y las excepciones de
  urllib pueden llevarla en su texto. El adaptador captura y
  registra solo el **tipo** de la excepción y el **código HTTP**,
  nunca `str(e)` ni la URL; y la capa común pasa todo texto de error
  por un saneador (`canales.resumen_error`) que borra cualquier
  patrón con forma de token de bot antes de escribirlo, por si
  acaso.
- **Particularidades honestas**: el bot no puede escribir a quien no
  le haya abierto el chat (por eso el baile empieza en el teléfono);
  los mensajes del bot son visibles para quien tenga el teléfono,
  como en cualquier canal; Telegram es un tercero que ve el
  contenido (los resúmenes y motivos viajan en claro por su red).

## 9. Transporte: WhatsApp oficial (`canal_whatsapp_oficial.py`)

La API de WhatsApp Business Platform (Meta, Cloud API): estable y
sin riesgo de baneo por automatización, a cambio de burocracia,
número aparte y un webhook público.

- **Qué necesita del dueño**: una cuenta de Meta for Developers, una
  app con el producto WhatsApp, un número de teléfono **registrado
  en la plataforma** (en la práctica, un número aparte: registrar el
  personal lo saca de la app normal de WhatsApp), el `phone_number_id`
  y el `waba_id` (no secretos: van en `canales.json`), un token de
  acceso permanente (usuario del sistema) y el `app_secret`. Y
  exponer el webhook (siguiente punto). Tiene coste por conversación
  según la tarifa de Meta para su país: el diseño no pone cifras
  porque cambian; el volumen de este sistema (un dueño, avisos y
  encargos) es el mínimo posible.
- **Credenciales**: token ⇒ bóveda `canal:whatsapp-oficial`;
  `app_secret` ⇒ bóveda `canal:whatsapp-oficial-secret`; token de
  verificación del webhook (lo inventa el dueño al configurar Meta)
  ⇒ bóveda `canal:whatsapp-oficial-verify`.
- **Salida**: `POST graph.facebook.com/<versión>/<phone_number_id>/messages`
  con el token, `messaging_product: "whatsapp"`, `to` = `wa_id`
  emparejado, texto plano. **La ventana de 24 h**: la API solo deja
  enviar texto libre dentro de las 24 h siguientes al último mensaje
  del usuario; fuera de ventana hay que usar una plantilla aprobada.
  Consecuencia diseñada, no descubierta: los avisos espontáneos
  pueden fallar tras un día de silencio del dueño. El adaptador lo
  sabe *antes* de intentarlo: con `ultimo_entrante_ts` (§3.3) decide
  sin gastar un envío condenado (corrección I7 del §17 bis):
  - Dentro de ventana: texto libre, como siempre.
  - Fuera de ventana, con plantilla genérica configurada (nombre en
    `config`): se envía la plantilla, cuyo único trabajo es
    **provocar una respuesta** — «Tienes un aviso de Growi Bridge:
    {{1}}. Responde a este mensaje para verlo.» — donde `{{1}}` es
    una **etiqueta corta** del tipo de aviso («un pedido de
    aprobación», «un encargo terminado»), nunca el texto entero:
    Meta rechaza parámetros con saltos de línea o tabuladores y los
    limita en longitud, así que el texto de un pedido (que los
    lleva) jamás viaja como parámetro. El mensaje completo queda en
    la bandeja como `retenido_ventana` y sale en texto libre en
    cuanto el dueño responde y la ventana se abre. Si el dueño nunca
    responde, el aviso no se pierde: vive en `avisos.jsonl` y en la
    app.
  - Fuera de ventana y sin plantilla: el aviso queda en el registro
    y en la bandeja como fallido con el motivo «fuera de ventana»:
    nunca se finge enviado. Los pedidos de aprobación sufren la
    misma ventana: otro motivo para que su vencimiento (2 h en R2)
    no dependa del canal.
- **Entrada (webhook)**: Meta exige una URL HTTPS pública que el PC
  casero no tiene. El receptor es un **listener HTTP aparte**
  (corrección B8 del §17 bis): un servidor mínimo de stdlib, ligado
  **solo a 127.0.0.1** en un puerto propio (en `config`, por defecto
  8790), que sirve **únicamente** las dos rutas
  `/canal/whatsapp-oficial` y nada más. El `BridgeHandler` existente
  **no se toca**: apuntar el túnel al puerto del puente publicaría
  en internet `/put`, `/get`, `/list` y `/gateway/estado` — la
  creación de tareas del carril A tras un solo token —, así que el
  túnel apunta al puerto del listener y lo único alcanzable desde
  fuera es el webhook, que ni siquiera usa ese token. El listener
  vive en el proceso del carril A (su ciclo lo vigila el servicio de
  canales) y:
  1. `GET /canal/whatsapp-oficial` responde al apretón de manos de
     Meta: exige `hub.mode == "subscribe"` y compara
     `hub.verify_token` contra la bóveda con `hmac.compare_digest`
     (tiempo constante), devolviendo `hub.challenge` solo entonces.
  2. `POST /canal/whatsapp-oficial`: rechaza sin leer el cuerpo si
     `Content-Length` supera 256 KB (el POST no está autenticado
     hasta verificar la firma, así que el tope va antes que la
     lectura); verifica `X-Hub-Signature-256` con el `app_secret`
     (HMAC sobre el cuerpo crudo, comparado con
     `hmac.compare_digest`) **antes** de parsear nada — sin firma
     válida, 403 y ni una línea en el registro de entrantes;
     comprueba que `metadata.phone_number_id` del payload es el
     configurado (un payload firmado pero de otro número no es de
     este canal); extrae los mensajes
     (`entry[].changes[].value.messages[]`), normaliza
     (`remitente = from` (el `wa_id`), `id_mensaje = id`,
     `cita_id = context.id` si contesta a un mensaje) y los añade a
     `canal-entrantes.jsonl` bajo su lock; responde 200 solo tras
     escribir (principio 5: un 500 hace que Meta reintente, que es
     lo que queremos si el disco falla). (Corrección I8: estos
     cuatro puntos — tope de tamaño, tiempo constante, `hub.mode` y
     `phone_number_id` — quedan especificados, no a criterio del
     implementador.)
  Exponerlo es **tarea del dueño, fuera del código**: Tailscale
  Funnel o un túnel de Cloudflare que apunte **al puerto del
  listener**. La sección de la UI lo dice y el estado del canal
  muestra «webhook sin verificar» hasta que el apretón de manos
  llega. Sin exposición pública, este transporte puede *enviar*
  (dentro de ventana) pero no *recibir*: el diseño lo declara un
  estado válido pero cojo, y la UI no lo disfraza de «conectado».
  Y como el listener vive en el carril A, con el carril A caído este
  transporte no recibe aunque el B lidere (§14 lo declara).
- **Emparejamiento**: el dueño escribe desde su número personal al
  número de negocio; el código de la app (§4) ata su `wa_id`. Nadie
  más puede «ser» ese `wa_id` sin su SIM, que es la garantía de
  identidad de este transporte.
- **Disponible**: hay token y una llamada de prueba a la API
  (obtener el número) responde; el apretón de manos del webhook
  mueve el subestado de entrada a «verificado».

## 10. Transporte: WhatsApp no oficial (`canal_whatsapp.py` + `canal-whatsapp/`)

Usa el número personal del dueño como un dispositivo vinculado más
(protocolo multi-dispositivo de WhatsApp, vía la librería Baileys).
Es el que el plan marca con riesgo de baneo: gratis e inmediato, a
cambio de ir contra las condiciones de WhatsApp y de depender de una
librería que persigue sus cambios.

### 10.1 Por qué un acompañante

No hay librería Python mantenida para este protocolo; la vía real es
Node (Baileys, sin navegador — a diferencia de whatsapp-web.js, que
arrastra un Chromium). El diseño lo asume como un **proceso
acompañante tonto**, `canal-whatsapp/acompanante.js` (~200 líneas,
una sola dependencia), que solo hace I/O de transporte y habla con
el líder por archivos, con el mismo contrato que el webhook del
oficial. Su carpeta de trabajo, `canal-whatsapp/`, vive en la
**carpeta compartida por usuario** (`_token_dir()/canal-whatsapp`),
para que los dos carriles, la UI (el QR) y el propio acompañante la
encuentren sin configuración (corrección I4 del §17 bis):

- Lee `canal-whatsapp/salientes/*.json` (`{"id", "texto"}`), envía
  cada uno al JID emparejado y lo mueve a `enviados/` añadiendo el
  `id` de mensaje de WhatsApp.
- Añade al **`canal-entrantes.jsonl` compartido** (el mismo archivo
  que el webhook oficial, §2.3: una sola vía de entrantes, un solo
  cursor) todo mensaje del chat del canal que **no haya enviado él**
  (siguiente punto), normalizado (`remitente` = JID del autor,
  `id_mensaje`, `cita_id` si lo hay). **No filtra ni decide**: la
  capa común descarta lo que no sea del dueño (§5.1), como con el
  webhook oficial.
- **Descarta su propio eco** (corrección B7): el chat del canal es
  el chat del dueño consigo mismo, así que todo lo que el
  acompañante envía (pedidos, avisos, acuses, ecos de decisión)
  *reaparece* en ese chat con remitente = la identidad emparejada.
  Sin este filtro, el canal se leería a sí mismo: un «Encargo
  recibido ✓…» volvería como entrante y se convertiría en otro
  encargo, y un eco que abra con un verbo de decisión se
  reinterpretaría como decisión. La regla es mecánica: el
  acompañante conoce los ids de lo que envía (están en `enviados/`)
  y **nunca añade a entrantes un mensaje cuyo id esté ahí**; los
  mensajes del dueño escritos desde su teléfono tienen otros ids y
  sí entran. Como segunda muralla, la capa común descarta cualquier
  entrante cuyo id aparezca en `enviados/` (por si el acompañante se
  equivoca).
- Mantiene `canal-whatsapp/estado.json` con latido cada 10 s:
  `{"ts", "estado": "conectado"|"esperando_qr"|"desvinculado"|
  "error", "detalle"}` y, cuando toca, `canal-whatsapp/qr.png` con
  el código de vinculación, que la app muestra en la sección de
  canales (§12).
- Su sesión (las claves del dispositivo vinculado) vive en
  `canal-whatsapp/sesion/` con permisos 0700 (en Windows: la ACL de
  la carpeta restringida al usuario, que es lo que 0700 significa
  ahí; el instalador la aplica). Es una credencial en la práctica —
  quien la copie es el dueño en WhatsApp — y por eso: nunca sale de
  esa carpeta, la lista cerrada de `respaldo.py` no la incluye (el
  respaldo triple no se lleva la sesión: un respaldo con la sesión
  dentro sería una copia del teléfono del dueño), y desvincular en
  el teléfono la invalida al instante.
- Al arrancar toma un **pidfile con lock** (`canal-whatsapp/
  acompanante.lock`): si ya hay un acompañante vivo sobre la misma
  sesión, el segundo se sale sin tocar nada (corrección B3: dos
  líderes depuestos nunca deben acabar con dos acompañantes sobre
  la misma sesión).

El adaptador Python (`canal_whatsapp.py`) es fino: `recibir` lee el
`canal-entrantes.jsonl` compartido desde el cursor, como el oficial;
`transmitir` es **idempotente por id** (corrección I6): escribe
`salientes/<id>.json` con el id de la bandeja solo si no existe ya
un `salientes/<id>` ni un `enviados/<id>`; si el acuse aún no llegó,
no reescribe nada y solo sondea `enviados/` en ciclos posteriores
(el acuse de una cola de 20 mensajes con pausas humanas tarda más
de 30 s sin que nada haya fallado: reescribir por impaciencia
duplicaba el mensaje y perdía su `mensaje_id`, rompiendo la cita
del §6.2). Si el acompañante envió y murió antes de acusar, el
mensaje puede duplicarse al relanzarlo: en WhatsApp un aviso
duplicado es un mal menor y queda anotado; las *decisiones* no se
ven afectadas porque viven en la capa común con su dedup.

### 10.2 El chat del canal y la doble capa de emparejamiento

Este transporte tiene dos ataduras distintas, y el diseño las
separa:

1. **Vinculación del dispositivo**: el QR enlaza la PC como
   dispositivo compañero del número del dueño (lo hace WhatsApp,
   fuera de `canales.json`).
2. **Emparejamiento lógico** (§4): el chat del canal es el **chat
   del dueño consigo mismo** (su «chat personal» / notas). El código
   de la app, enviado en ese chat, ata su propio JID como identidad.
   Pero hay que decirlo con exactitud (la primera versión de esta
   sección afirmaba lo contrario): el emparejamiento, solo, **no**
   impide que una nota suya («comprar pan») se convierta en encargo
   — tras emparejar, el remitente de esa nota *es* la identidad
   emparejada. Por eso este transporte añade una regla de entrada
   que los demás no necesitan (corrección B7): un mensaje del dueño
   en este chat solo es entrada del canal si **(a)** cita/responde a
   un mensaje del canal (un pedido, un aviso), o **(b)** empieza por
   el prefijo `growi` (sin distinción de mayúsculas; el prefijo se
   retira antes de clasificar). Todo lo demás en su chat personal
   sigue siendo sus notas: ni se procesa ni se anota como encargo
   (sí como `mensaje_ignorado` con motivo `sin_prefijo`, para que el
   registro explique los silencios). El emparejamiento lógico sigue
   siendo obligatorio además por la razón general: sin él el canal
   no sabe qué JID es el dueño, y revocarlo (§4.2) apaga el
   procesado aunque la vinculación siga viva.
3. **Las dos formas del JID** (corrección I6): Baileys maneja hoy el
   JID por número y la forma LID, y WhatsApp puede cambiar cuál
   entrega. La identidad guarda **las dos formas** cuando se conocen
   (la vinculación las expone) y la comparación del §5.1 acepta
   cualquiera de ellas: un cambio de forma no debe romper el
   emparejamiento de la noche a la mañana.

### 10.3 Supervisión del acompañante

El líder vigila `estado.json`: latido viejo (> 60 s) o estado
`desvinculado`/`error` ⇒ aviso `bloqueo_dueno` por los demás
destinos, **como mucho una vez por hora con su propio tope en la
capa común** (marca en `canal-estado.json` → `supervision`,
corrección I14 del §17 bis: la dedup de `avisos.py` es de 10 min y
solo cubre tres tipos de aviso de la Fase 4, no este; apoyarse en
ella habría convertido este aviso en spam de ciclo). Y, si en
`canales.json` está el comando de arranque del acompañante (lo deja
el instalador, §12), el líder lo relanza con el patrón del
vigilante: tope de 3 relanzamientos por hora, nunca matar uno vivo.
El comando guardado se **valida antes de usarlo y antes de
guardarlo**: ha de ser exactamente el ejecutable `node` y la ruta
fija del `acompanante.js` de la instalación, sin shell ni argumentos
libres (corrección I6): `canales.json` no debe poder convertirse en
una vía de ejecución arbitraria si algo lo edita a mano. Si la
sesión se desvincula, no se relanza en bucle: se avisa y se espera
al dueño (volver a vincular es gesto suyo, con QR).

### 10.4 Riesgos, dichos en claro

- **Baneo del número**: WhatsApp puede restringir o banear el número
  por automatización no oficial. Mitigaciones diseñadas: solo el
  chat del dueño, volumen mínimo (los topes del §5.6 y §7.5), nada de
  grupos ni terceros, pausas humanas entre envíos del acompañante
  (1–3 s aleatorios). Aun así el riesgo no desaparece: es la
  decisión que el dueño toma al elegir este transporte, y el plan ya
  lo dejó escrito.
- **Fragilidad**: una actualización de WhatsApp puede romper la
  librería días. El canal cae (principio 7) y el sistema sigue.
- **Suplantación**: la sesión vinculada ES el dueño para WhatsApp.
  El daño queda acotado por la capa común: ni con la sesión se puede
  aprobar un R3, ni ejecutar nada que no pase las puertas de
  siempre, ni escribir a terceros desde el programa.

## 11. Credenciales: la bóveda manda

| Secreto | Nombre en la bóveda | Quién lo escribe | Quién lo lee |
|---|---|---|---|
| Token del bot de Telegram | `canal:telegram` | UI (campo de contraseña) | adaptador, por getter, en cada ciclo |
| Token de acceso (oficial) | `canal:whatsapp-oficial` | UI | adaptador, al transmitir |
| App secret (oficial) | `canal:whatsapp-oficial-secret` | UI | handler del webhook, al verificar la firma |
| Verify token del webhook | `canal:whatsapp-oficial-verify` | UI | handler, en el apretón de manos |
| Sesión del no oficial | carpeta `canal-whatsapp/sesion/` (0700) | el acompañante (QR) | solo el acompañante |

- Los nombres siguen el patrón de `cuentas.nombre_secreto`
  (`muse:<id>` ⇒ `canal:<transporte>`), y el almacén es el mismo
  (`_sec_get`/`_sec_set` sobre `growi-bridge/<nombre>`), con su vía
  detectada y sus degradados de la Fase 1: si la bóveda cae al
  archivo 0600, los tokens heredan esa protección y la UI lo avisa
  igual que con los secretos de cuenta.
- Los adaptadores reciben un `leer_secreto(nombre) -> str | None`
  inyectado por el monolito; no importan la bóveda ni la tocan
  directamente, y ningún secreto se guarda en el objeto adaptador
  entre ciclos.
- Rotar un token = pegar el nuevo en la app: el siguiente ciclo lo
  usa (Telegram) o la siguiente transmisión (oficial). No hay que
  reiniciar nada, y el viejo muere en la bóveda al sobrescribirse.
- El acompañante no recibe ningún secreto por línea de comandos ni
  por entorno: su único «secreto» es su carpeta de sesión, que él
  mismo crea.


## 12. Cableado en el monolito (fino) y UI

1. **Arranque** (`main()`, junto a `_iniciar_vigia_dual()` y
   `_f4_iniciar_presencia()`): `_f5_iniciar_canales()` —
   - registra en `avisos.py` el destino `canal` **una sola vez**
     (`registrar_canal("canal", fabrica_canal)`): el destino es
     agnóstico del transporte y lee el activo de `canales.json` en
     cada `enviar` (§2.1). `canales.json` es la **única** fuente del
     transporte activo (corrección I12 del §17 bis): la clave
     `canal` de `avisos-config.json` solo dice que el destino existe
     en la lista de destinos, no qué transporte usa;
   - el hilo del servicio (`_f5_servicio_hilo`) arranca **siempre**,
     haya o no transporte activo, y si no lo hay queda inactivo
     (duerme y relee `canales.json` cada ciclo): así, activar o
     cambiar de transporte en la UI surte efecto en el siguiente
     ciclo sin reiniciar nada, que es lo que el §11 promete para
     los tokens y vale igual para el transporte. El coste de la
     fase sin canal es un hilo dormido y una lectura por ciclo;
   - el servicio hace: liderazgo (§2.2, con época y latido en el
     mismo bucle), drenaje de salientes + recepción + procesado si
     es líder, reconciliación de *sus* pedidos en
     `canal-pedidos.json` (§6.2) y consumo de `canal-decisiones/`
     (los dos últimos, sea o no líder). El ciclo es de 3 s, salvo
     con Telegram, cuyo long poll de 20 s hace de reloj. Toda
     excepción del ciclo se traga con log (patrón `_f4_latido`),
     con el texto del error **saneado** por
     `canales.resumen_error` (§8, corrección I15): el canal jamás
     tumba al runner ni filtra un token a un log.
2. **Ofrecimiento de pedidos**: gancho `_f5_ofrecer_pedido(row)` al
   final de `_park_for_approval` (tras `_apr_nuevo`) y en
   `aprobaciones_adoptar` para los pedidos adoptados al arrancar:
   anota en `canal-pedidos.json`, calcula el código corto sin
   colisión con los pendientes, y encola el texto si procede
   (§6.1/§7.3). La denegación instantánea de un R3 remoto
   (`_denegar_remota_nueva`) no ofrece nada: ya nació muerta.
3. **Resultado al canal**: `_f5_resultado_a_canal(raiz, resultado)`
   en `_f4_escribir_resumen` (§7.4) para el resumen de cierre, y el
   gancho de `necesita_decision` en `_write_result` junto a
   `_f4_resultado_a_buzon`.
4. **Decisiones del otro carril**: el consumo de
   `canal-decisiones/` va en el mismo hilo del servicio (cada carril
   consume las suyas sea o no líder; el líder es quien las crea).
   Aplicar = tomar el claim de `consumidas/<approval_id>` (§6.4),
   llamar a `decidir_aprobacion` local y dejar el resultado en
   `hechas/`.
5. **Webhook del oficial**: un **listener aparte** en el proceso del
   carril A (§9, corrección B8): un servidor stdlib mínimo ligado a
   127.0.0.1 en su puerto propio que solo sirve
   `GET`/`POST /canal/whatsapp-oficial` y delega en
   `canal_whatsapp_oficial.py`. El `BridgeHandler` **no se toca**:
   sus rutas (`/put`, `/get`, `/list`, `/gateway/*`) no deben quedar
   nunca tras el túnel público. La autenticación del webhook es la
   firma de Meta (su token del plano de control ni aplica ni se
   pide). El servicio de canales del carril A arranca el listener
   si el transporte activo es el oficial, y lo para al cambiar.
6. **Presencia**: el destino `canal` **no** pasa por
   `_f4_ventana_ok()` ni por el contador silencioso — eso es del
   destino `local`. En modo presente los mensajes al teléfono salen
   igual: el teléfono es del dueño y si vibra o no lo decide su
   teléfono, no la PC. Se deja escrito porque el §12 de la Fase 4
   presentó `_f4_ventana_ok` como punto único y hay que acotar su
   alcance: ventanas y toasts *de la PC*.
7. **UI — página Cuentas, sección «Canales»** (tras «Proyectos y
   respaldo» y «Encargos y modo dual»):
   - Selector del transporte activo (ninguno / Telegram / WhatsApp
     oficial / WhatsApp no oficial) y su estado en una línea:
     `sin configurar` · `sin emparejar` · `emparejado con +58•••1234`
     · `webhook sin verificar` (oficial) · `acompañante sin latido`
     (no oficial) · `error: <motivo>`.
   - Campos de credenciales según el transporte (contraseña,
     solo escritura, como el secreto de cuenta: nunca se muestra) y
     de datos no secretos (`phone_number_id`, `waba_id`, nombre de
     plantilla opcional).
   - Botón **Emparejar**: genera el código y lo muestra en grande
     con su cuenta atrás; en el no oficial muestra además el QR si
     el acompañante lo dejó (`qr.png`).
   - Botón **Revocar emparejamiento** (con confirmación), identidad
     enmascarada, interruptor de «avisos informativos por el canal»
     y la lista `avisos_info` resultante.
   - Botón **Enviar aviso de prueba**: emite un aviso
     `canal_prueba` («Esto es una prueba del canal…») que sale por
     el destino canal: es la forma de verificar el transporte sin
     esperar a un encargo real.
   - En la tarjeta «Esperan tu aprobación» de Tareas: si el pedido
     está en `canal-pedidos.json` como ofrecido, la tarjeta lo dice
     («ofrecido por Telegram · código A1B2 · vence …»).

## 13. La app Android (especificación del prototipo opcional)

No se construye en esta fase. Queda especificada para poder
construirla después sin rediseñar nada, y es — como dice el plan —
lo primero que se recorta: **el sistema está completo sin ella**.

- **Qué es**: un clon ligero de la app de Muse con las 2 cuentas
  Muse: una lista de cuentas y un chat por cuenta. Cada cuenta
  dice qué está haciendo: tarea actual, encargos abiertos con su
  avance (subtareas hechas/total), su % de tokens del tablero y si
  está esperando algo (aprobación, alquiler, dueño). La ejecución
  sigue en la PC; el teléfono es una ventana, no un motor.
- **Qué consumiría** (todo lectura salvo dos escrituras):
  - Lectura: el puente (`/gateway/estado`, `runner-status.json` con
    `aprobaciones_pendientes`) y, por crear cuando se construya
    (fuera de esta fase), un `GET /multi/estado` que sirva en JSON
    lo que hoy vive en los archivos compartidos (`tablero.json`,
    `encargos.json`, `avisos.jsonl`, `presencia.json`) — el teléfono
    no puede leer archivos del PC.
  - Escritura, **solo por rutas `/multi/*` validadas con el token
    del dispositivo** (corrección I16 del §17 bis): un
    `POST /multi/encargo` que crea la tarea con `canal: "android"`
    pasando por la misma validación y derivación del §5.3 — para el
    carril B, el endpoint construye la forma derivada en el PC, no
    el teléfono — y un `POST /multi/decidir` que envuelva
    `decidir_aprobacion` con `canal="android"` para R1/R2 (R3
    jamás: el mismo circuito lo deniega, y aquí sí es el camino
    diseñado porque Android no es un «canal de chat» sino la app del
    dueño autenticada por dispositivo). Subir el `.task.json` por el
    `/put` general del puente queda **descartado**: usaría el token
    general y anularía la revocación por dispositivo que el
    siguiente punto promete.
- **Autenticación por dispositivo** (lo que el plan pide probar:
  revocar corta en menos de un minuto): cada teléfono emparejado
  tiene su propio token en la bóveda (`dispositivo:<id>`), distinto
  del token general del puente. Emparejar = QR en la app de
  escritorio con un código de un solo uso (el baile del §4 con otra
  ropa). Cada petición valida el token contra la lista vigente —
  sin caché más larga que la propia petición — así que **revocar
  en la app de escritorio corta el acceso en la siguiente petición**
  (< 1 min con cualquier uso normal). Los tokens caducan a los 90
  días sin uso; la app lista los dispositivos con su última vez
  visto y su botón de revocar. Teléfono perdido = revocar + el
  token muere; nada en el teléfono da acceso a la bóveda ni a las
  cuentas.
- **Transporte**: Tailscale, como ya escucha el puente (su IP de
  Tailscale está en el diseño desde el principio): sin exponer nada
  a internet, sin servidores intermedios.

## 14. Modelo de fallos

| Fallo | Comportamiento diseñado |
|---|---|
| Transporte caído (red, API, acompañante) | Los avisos quedan en `avisos.jsonl` y los salientes en la bandeja con reintentos y tope (§7.5); los pedidos siguen esperando en la app y vencen allí si toca. Nada sensible se ejecuta por «no poder preguntar»: la ausencia de canal nunca aprueba nada (principio 7) |
| El líder muere / el carril líder se cae | El otro carril toma el liderazgo en ≤ 60 s de latido viejo + un ciclo (§2.2); la bandeja y los cursores hacen el relevo sin perder mensajes (la dedup absorbe el solape) |
| Mensaje duplicado del transporte | Dedup por `(transporte, id_mensaje)` antes de clasificar (§5.5); una decisión duplicada además la absorbería `decidir_aprobacion` como tardía |
| Mensajes de un desconocido / teléfono ya revocado | Silencio + `mensaje_ignorado` auditado; ni siquiera se confirma que el canal existe |
| Código de emparejamiento filtrado | Ventana de 10 min, un solo uso, 5 intentos, aviso local `accion` al emparejar y revocación en un clic (§4). El daño máximo de un emparejamiento ajeno es el de la capa común: ni R3, ni terceros, ni shells |
| El dueño se equivoca de código al decidir | Objetivo no resuelto ⇒ no se decide nada y se le listan los pedidos con sus códigos (§6.2). Un «aprobar» ambiguo jamás se aplica al «más probable» |
| Decisión que llega tras el vencimiento | `decidir_aprobacion` la apunta como tardía y no ejecuta nada; su mensaje se reenvía al dueño tal cual (§6.5) |
| Pedido del otro carril y ese carril está caído | La orden espera en `canal-decisiones/`; al dueño se le dice que está en manos de ese carril; si el pedido vence antes, al aplicarla el circuito la trata como tardía y la confirmación lo explica. No se decide desde el carril equivocado «por ayudar» |
| Webhook oficial sin exponer / ventana de 24 h cerrada | Estados declarados en la UI, no disfrazados (§9): entrada «sin verificar» o envíos «fuera de ventana» anotados; plantilla opcional como respaldo; el aviso nunca se finge enviado |
| El carril A caído con el transporte oficial activo | El listener del webhook vive en el proceso del carril A (§9): este transporte **no recibe** aunque el carril B lidere. Meta reintenta la entrega durante horas, así que al volver A los mensajes llegan y la dedup/marca de agua ordena; la salida sí sigue por el líder B. Es un hueco declarado de este transporte, no un descuido: los otros dos transportes no lo tienen (Telegram se sondea; el acompañante es compartido) |
| Acompañante muerto o sesión desvinculada | Latido vigilado (§10.3): aviso por los demás destinos, relanzamiento con tope si hay comando configurado; desvinculación ⇒ espera al dueño, sin bucle de relanzamiento |
| Bóveda ilegible / token rotado fuera | `disponible()` falso con el motivo en la UI; el canal se declara caído y todo sigue en local. Un token en un log sería un fallo de implementación: los adaptadores no registran credenciales (prueba del §15: grep de un token canario) |
| `canales.json` corrupto | Se lee como «sin canal» y se avisa; el arranque y el runner no se enteran (mismo criterio que `cuentas.cargar`) |
| Reloj del teléfono distinto | Irrelevante: todo se decide con la hora del PC al recibir (principio 9); un mensaje con ts futuro no adelanta vencimientos ni ritmos |

## 15. Aceptación de la fase

Pruebas unitarias (módulos puros, transportes falsos inyectados,
reloj falso donde toque):

- `test_canales.py`: emparejamiento (código correcto empareja y se
  quema; caducado no; 5 intentos lo matan; el código de otro
  transporte no vale; tras revocar, el mismo remitente es un
  desconocido); clasificación (tabla de frases: decisiones que abren
  el mensaje, encargos con «no» dentro que NO son rechazos,
  consultas, enrutado `@cuenta` válido e inválido); parseo de
  decisiones (la tabla del §6.3 entera, incluidas «media hora», la
  duración suelta con único pendiente, la decisión a medias que
  caduca y la que se descarta si llega otra cosa); resolución del
  objetivo (cita > código > único; con dos pendientes y sin código
  no se decide nada); ritmo (encargos cortados al límite, decisiones
  que pasan siempre); dedup (el mismo `id_mensaje` dos veces crea un
  solo encargo); filtro del destino canal (`accion` siempre, `info`
  solo la lista, anti-duplicados del §7.2); bandeja saliente
  (reintentos, tope, pedidos vencidos que se retiran); órdenes entre
  carriles (la orden se aplica una vez y su resultado vuelve).
- Las pruebas de lo más frágil (corrección I17 del §17 bis, una por
  cada bloqueante): **liderazgo** (dos procesos que se creen líderes
  a la vez: solo actúa el de la época vigente; un líder lento con
  pasos acotados no es depuesto); **órdenes entre carriles** (el
  carril dueño caído al llegar la orden y su aplicación al volver;
  el pedido vence a mitad del traspaso ⇒ tardía con la orden
  gastada; una segunda orden para el mismo `approval_id` no se crea
  o no se aplica dos veces; el claim `consumidas/` sobrevive a una
  muerte entre leer y aplicar); **entrada exactamente-una-vez**
  (líder que muere tras anotar `en_proceso` y antes de crear la
  tarea: al volver, un solo encargo; repetición de entrantes con el
  cursor a cero y la dedup vacía: la marca de agua lo descarta todo
  como viejo); **gramática estricta** (la tabla del B5: «si puedes
  revisa el log» no aprueba, «sí pero primero haz copia» no aprueba,
  «no borres el archivo grande» no rechaza, y con pedidos pendientes
  esas frases disparan la pregunta de aclaración); **R3** (intento
  por canal sobre un R3 no ofrecido ⇒ `decidir_aprobacion` ni se
  llama y el pedido queda pendiente; y llamada directa a
  `decidir_aprobacion(..., canal="telegram")` sobre un R3 ⇒ el
  circuito deniega, como segunda muralla); **reconciliación de
  pedidos** (un pedido decidido en la app deja de contar como
  «único pendiente»; un pedido aún no transmitido no es objetivo).
- `test_canal_telegram.py`: payloads de `getUpdates` reales de
  ejemplo → mensajes normalizados (con y sin cita); el offset solo
  avanza tras procesar; `getMe` falso ⇒ no disponible; un mensaje de
  grupo no se procesa; si el `bot_id` cambia, cursor y dedup se
  reinician y el emparejamiento se invalida.
- `test_canal_whatsapp_oficial.py`: apretón de manos (verify token
  bueno/malo, `hub.mode` distinto de `subscribe` rechazado);
  `Content-Length` gigante rechazado sin leer; firma HMAC buena ⇒
  mensajes a `canal-entrantes.jsonl`; firma mala ⇒ 403 y ni una
  línea; `phone_number_id` ajeno ⇒ ignorado; payload con cita ⇒
  `cita_id`; fuera de ventana según `ultimo_entrante_ts` ⇒ plantilla
  con etiqueta corta y texto retenido, sin intento de texto libre.
- `test_canal_whatsapp.py`: el contrato de archivos con un
  acompañante falso en Python (salientes → enviados con id,
  entrantes con cursor, latido viejo detectado); **el eco propio**
  (un mensaje cuyo id está en `enviados/` jamás entra como
  entrante; un aviso del canal no se convierte en encargo); las dos
  formas de JID aceptadas; sin acompañante, el adaptador dice no
  disponible y no lanza.
- Regresión: las 265 pruebas de las fases 0–4 siguen en verde; el
  monolito compila con su CRLF intacto; un token canario pasado por
  todos los caminos del canal no aparece en ningún log ni registro
  (grep final, como la prueba del centinela de la Fase 1).

Pruebas físicas: **solo el transporte que elija el dueño se prueba
en físico completo** (es su número, su cuenta y su teléfono los que
entran en juego); para los tres, la lista es la misma en espíritu:

1. Emparejar desde la app y desde el teléfono real; el estado en la
   UI y el aviso local lo confirman; un mensaje desde otro
   número/chat no obtiene ni respuesta.
2. Un encargo escrito desde el teléfono, con los dos carriles
   reales: se divide entre las dos cuentas Muse, se cierra y el
   resumen vuelve al mismo chat, sin tocar la PC.
3. Una aprobación R2 real decidida desde el chat (aprobar) y otra
   aplazada con «espera 2» (la versión corta de los 30 del plan):
   no arranca antes de los 2 minutos y sí después, sin volver a
   preguntar.
4. Un R3 creado **en la app** (es el único origen posible de un R3
   pendiente: los de tareas con canal remoto se deniegan al nacer,
   §6.1) e intento de decidirlo desde el chat citando su
   notificación: la capa común responde «solo en la app», el intento
   queda en el registro del canal como `decision_r3_no_ofrecida` y
   — lo que se verifica mirando la app — **el pedido sigue
   pendiente, intacto** (corrección B6: la primera versión de esta
   prueba esperaba una denegación del circuito, que habría cerrado
   la tarea).
5. Revocar el emparejamiento en la app: el siguiente mensaje del
   teléfono se ignora; re-emparejar funciona.
6. Matar el transporte (cerrar el acompañante / bloquear la red /
   token inválido): un pedido R2 creado mientras tanto no se
   ejecuta ni se pierde — espera en la app — y los avisos del
   periodo están en `avisos.jsonl` aunque nunca llegaran al
   teléfono.
7. Solo oficial: el apretón de manos del webhook a través del túnel
   elegido y un mensaje entrante real recorriendo el camino entero.
   Solo no oficial: desvincular el dispositivo desde el teléfono ⇒
   la UI pasa a «desvinculado» y sale el aviso.

Límites honestos que se declaran desde ya: las físicas de los
transportes no elegidos quedan como lista preparada, no ejecutada;
la ventana de 24 h del oficial y el riesgo de baneo del no oficial
no se pueden «probar» en una tarde: se verifican sus tratamientos
(error anotado / estados), no el comportamiento de Meta o WhatsApp.

## 16. Fuera de alcance (explícito)

- Construir la app Android (§13 la deja especificada; es el primer
  recorte del plan y no bloquea nada).
- Grupos de WhatsApp o chats con terceros: el canal es el chat del
  dueño, punto. El programa no escribe a ningún otro número o chat
  por este canal.
- Entrada que no sea texto (voz, fotos, documentos): se responde
  «solo texto por ahora», no se procesa.
- Comandos directos o modo terminal por chat: el canal crea tareas
  con todas sus puertas; no hay atajos.
- Varios dueños o varias identidades emparejadas por transporte:
  una instalación, un dueño, una identidad por transporte.
- Aprobar R3 por cualquier vía remota (incluida la futura Android):
  el circuito lo deniega y esta fase no lo debilita.
- Cambiar `decidir_aprobacion`, la tabla de riesgos o los
  vencimientos: el canal se adapta al circuito, nunca al revés.
- La decisión del transporte: es del dueño y se toma en paralelo;
  este diseño funciona con cualquiera de los tres (o con ninguno:
  sin transporte elegido, la fase no instala nada y el `CanalNulo`
  sigue cumpliendo el contrato).

## 17. Revisión de Opus 5.5 y correcciones aplicadas (§ bis)

Revisión del 2026-11-16 (MWAPI, `claude-opus-5-5`) sobre el borrador
de este diseño y el anexo de hechos verificados del código. Veredicto
del revisor: «el diseño es implementable una vez corregidos B1–B9.
Las correcciones son locales (época de liderazgo, idempotencia por
`approval_id` y por `id_mensaje`, gramática estricta, filtrado del
eco propio, listener aparte para el webhook, gancho en
`_f4_escribir_resumen`) y ninguna exige tocar `decidir_aprobacion`
ni las decisiones fijas.» Todas las correcciones se han aplicado al
cuerpo (cada una cita su §); esta sección las deja numeradas.

### Bloqueantes

- **B1 — La decisión entre carriles no era idempotente ni
  transaccional.** Una orden podía aplicarse dos veces (el «aplazar»
  sobre una fila ya aprobada-aplazada no estaba cubierto), perderse
  si el carril dueño moría entre leerla y dejar el resultado, o
  gastarse sobre un pedido ya vencido sin que el líder lo supiera.
  *Aplicado en §6.4:* exactamente-una-vez por `approval_id` — el
  líder no crea una segunda orden con una en vuelo; el carril dueño
  toma un claim atómico `canal-decisiones/consumidas/<approval_id>`
  (`os.O_EXCL`) antes de aplicar; y queda fijado como contrato que
  `decidir_aprobacion` sobre una fila ya resuelta nunca cambia la
  decisión (solo anota tardía), que es la garantía que el código
  real ya da (la fila no `pendiente` cae en `_apr_tardia`).
- **B2 — El ofrecimiento no estaba sincronizado con el carril
  dueño.** `canal-pedidos.json` quedaba «pendiente» para siempre
  (nadie marcaba lo resuelto en la app o por vencimiento) y la regla
  del único pendiente podía decidir un pedido que el dueño ni había
  recibido. *Aplicado en §6.1 y §6.2:* ofrecimiento idempotente por
  `approval_id` (la adopción al arrancar no reofrece ni cambia el
  código); reconciliación por carril contra su propia `cola.db`; y
  solo son objetivos los pedidos ya transmitidos (`mensaje_id` no
  nulo, anteriores a la recepción del mensaje entrante).
- **B3 — Podían coexistir dos líderes, y el ciclo garantizaba
  latidos viejos** (long poll de 25 s + esperas de 90 s y 30 s contra
  un umbral de 60 s; latido en hilo aparte que enmascara un líder
  colgado). *Aplicado en §2.2:* época creciente en `canal-lider.json`
  tomada bajo lock, relectura de la época antes de cada acción con
  efecto, latido escrito por el mismo bucle que procesa, y pasos
  acotados (long poll ≤ 20 s, espera de órdenes asíncrona en §6.4,
  acuse del acompañante por sondeo en §10.1). El acompañante toma
  además un pidfile con lock (§10.1).
- **B4 — La entrada no era exactamente-una-vez.** Líder que muere
  entre escribir la tarea y anotar el id ⇒ encargo duplicado;
  `canales.json` corrupto ⇒ cursor a cero sobre un entrantes que no
  rota ⇒ se reprocesa la historia entera. *Aplicado en §3.3, §5.3 y
  §5.5:* registro durable `en_proceso` antes de crear nada, `tid`
  derivado del hash de `transporte:id_mensaje`, marca de agua que
  descarta lo viejo (anterior a `emparejado_ts` o a la última
  recepción) y cursor reconstruido siempre al final del archivo.
- **B5 — La gramática convertía condicionales en aprobaciones.**
  «si» sin tilde colisionaba con «sí»; la tolerancia de 4 palabras
  aprobaba «sí pero primero haz copia» perdiendo la condición; y el
  ejemplo del propio diseño («no borres el archivo grande») era un
  rechazo por la regla escrita. *Aplicado en §5.2 y §6.3:* gramática
  estricta (verbo + código + duración + cortesía, y nada más), «sí»
  reconocido solo con tilde antes de normalizar, y zona gris que se
  **pregunta** («¿respuesta al pedido o encargo nuevo?») en vez de
  adivinarse.
- **B6 — Decidir un R3 por chat destruía el pedido.** Con
  `canal != "app"`, `decidir_aprobacion` no solo deniega un R3: lo
  cierra y mata su tarea; enrutarlo «para que lo deniegue» daba al
  canal el poder de cancelar trabajo R3. *Aplicado en §1, §6.2,
  §6.5, §7.3 y §15:* la capa común nunca llama al circuito con un
  pedido no ofrecido; responde «solo en la app», lo anota como
  `decision_r3_no_ofrecida` y el pedido queda intacto. La muralla
  del circuito se prueba en unitarias con llamada directa. La
  física 4 se reescribió: R3 creado en la app, intento por chat, y
  el pedido **sigue pendiente**.
- **B7 — En el no oficial, el canal se leía a sí mismo.** El chat es
  el del dueño consigo mismo: todo lo enviado por el acompañante
  reaparece con la identidad emparejada (bucle de encargos y ecos
  leídos como decisiones). Y era falso que el emparejamiento
  impidiera que una nota («comprar pan») se volviera encargo.
  *Aplicado en §10.1 y §10.2:* el acompañante nunca añade a
  entrantes un id que esté en `enviados/` (y la capa común repite el
  filtro), y en este transporte solo procesa mensajes citados a
  mensajes del canal o con el prefijo `growi`.
- **B8 — El túnel al puerto del puente publicaría el puente entero**
  (`/put`, `/get`, `/list`, `/gateway/*`) en internet, con el
  webhook además sin token. *Aplicado en §9 y §12.5:* listener
  aparte, solo 127.0.0.1, puerto propio, únicamente las dos rutas
  del webhook; el `BridgeHandler` no se toca y el túnel apunta al
  listener.
- **B9 — El resumen de cierre podía no salir nunca.** El gancho
  estaba en `_write_result`, pero el resumen lo escribe
  `_f4_escribir_resumen` (que no pasa necesariamente por ahí) y la
  condición `id == raiz` era falsa (la tarea es `t-…`, la raíz
  `enc-…`); con `encargo_terminado` ya suprimido, el dueño no
  recibía nada. *Aplicado en §7.2 y §7.4:* el gancho va en
  `_f4_escribir_resumen`, identificado por la raíz en
  `encargos.json`, y el aviso solo se suprime si el resumen se
  encoló con éxito.

### Importantes

- **I1 — Qué cuenta como intento de emparejamiento.** Solo un texto
  con forma exacta de código gasta intentos (un `/start` o cinco
  curiosos no matan el código); en Telegram solo se procesan chats
  privados. *§4.1 y §8.*
- **I2 — Orden de las puertas.** Clasificar va antes que el ritmo, y
  las decisiones ni se cortan ni cuentan para `mensajes_hora`.
  *§5.1 y §5.6.*
- **I3 — Ids de dedup sin tipo y cambio de bot.** Ids siempre como
  cadenas; el `bot_id` de `getMe` se guarda y, si cambia, cursor y
  dedup se reinician y el emparejamiento se invalida. *§3.3 y §8.*
- **I4 — Un solo archivo de entrantes.** El del §2.3 y el del §10.1
  eran dos caminos distintos para el mismo archivo: queda el
  compartido, solo-añadir, con rotación por generaciones y cursor
  `(generación, byte)`; `canal-whatsapp/` vive en la carpeta
  compartida y se fija qué significa 0700 en Windows (ACL del
  usuario). *§2.3, §3.3 y §10.1.*
- **I5 — Código corto solo con dígitos choca con la duración**
  («aplazar 1024»). Códigos de 4 caracteres aleatorios del alfabeto
  sin ambiguos, generados bajo el lock de `canal-pedidos.json`.
  *§6.2.*
- **I6 — Acuses del acompañante e identidad.** `transmitir`
  idempotente por id (no reescribe si `salientes/<id>` o
  `enviados/<id>` existen; el acuse se sondea en ciclos); el comando
  de arranque se valida como `node` + ruta fija, sin shell; la
  identidad acepta las dos formas de JID (número y LID). *§10.1,
  §10.2 y §10.3.*
- **I7 — La plantilla de respaldo no transporta un pedido** (Meta
  rechaza parámetros con saltos de línea y los limita). La plantilla
  lleva una etiqueta corta y su trabajo es provocar la respuesta
  que abre la ventana; el texto completo viaja después, retenido en
  la bandeja; `ultimo_entrante_ts` evita gastar un envío condenado.
  *§3.3 y §9.*
- **I8 — Huecos del webhook.** Tope de `Content-Length` (256 KB)
  antes de leer, comparaciones en tiempo constante
  (`hmac.compare_digest`), `hub.mode == "subscribe"` exigido,
  `phone_number_id` del payload contrastado, y el hueco «carril A
  caído ⇒ el oficial no recibe» declarado en el modelo de fallos.
  *§9 y §14.*
- **I9 — El encargo al carril B no decía quién escribe el `.md`.**
  Se reutiliza la derivación de `relevo.entregar` (no una copia),
  con su orden: primero el `.md`, después la tarea. *§5.3.*
- **I10 — El prefijo `<cuenta>:` daba falsos positivos.** Solo
  `@cuenta` es enrutado explícito; `<cuenta>:` enruta solo si
  coincide con una cuenta real; si no, el texto es un encargo
  normal sin mensaje de error. *§5.3.*
- **I11 — Cómo se reconoce una consulta.** El mensaje entero igual a
  la palabra clave; «estado del repo X, revísalo» es un encargo.
  *§5.4.*
- **I12 — Dos fuentes del transporte activo.** `canales.json` es la
  única; el destino `canal` de avisos es agnóstico y lee el activo
  al enviar; el hilo de servicio arranca siempre y queda inactivo
  sin transporte, así cambiar de transporte no exige reiniciar.
  *§2.1 y §12.1.*
- **I13 — `canales.json` mezclaba configuración y estado.**
  Separado `canal-estado.json` (cursores, dedup, ritmo, marcas),
  escrito solo por el líder y sin control de revisión. *§2.3, §3.1
  y §3.3.*
- **I14 — La dedup de la Fase 4 no cubre `bloqueo_dueno`** (es de
  10 min y solo para tres tipos). El aviso de acompañante caído
  lleva su propio tope de una hora en la capa común. *§10.3.*
- **I15 — El token de Telegram va en la URL** y las excepciones de
  urllib pueden filtrarlo a un log. El adaptador registra solo tipo
  y código HTTP, y la capa común sanea todo texto de error
  (`canales.resumen_error`). *§8 y §12.1.*
- **I16 — La Android chocaba con su propia autenticación** (crear
  por `/put` con el token general anulaba la revocación por
  dispositivo). Escrituras solo por `/multi/*` con el token del
  dispositivo; la derivación del carril B se hace en el PC. *§13.*
- **I17 — Faltaban las pruebas de lo más frágil.** Añadidas:
  liderazgo con época y líder lento, órdenes con el carril dueño
  caído y vencimiento a mitad de traspaso, segunda orden para el
  mismo `approval_id`, eco propio del no oficial, frases
  condicionales del B5, repetición de entrantes con cursor a cero,
  reconciliación de pedidos y el R3 que queda intacto. *§15.*

### Lo que la revisión no cambió

Las decisiones fijas quedan como estaban: la capa común completa y
los adaptadores sustituibles sin elegir transporte; el
emparejamiento con código de un solo uso; las decisiones solo por
`decidir_aprobacion`; R3 jamás por canal remoto; la bóveda como
único sitio de secretos; la Android fuera de la fase y solo
especificada; y la presencia sin efecto sobre el canal. Ninguna
corrección exigió tocar el circuito de aprobaciones ni los módulos
de las fases anteriores: todos los cambios son de la capa nueva.

## 17 ter. Correcciones de las pruebas físicas (2026-11-16)

Pruebas con la app real (dos carriles) contra un servidor falso de la
Bot API de Telegram en local (getMe/getUpdates/sendMessage con la
forma real; base inyectada con la costura `GROWI_PRUEBAS=1` +
`GROWI_TELEGRAM_API`, el mismo patrón que la sonda dual y las specs
de la Fase 4). Dos defectos reales cazados y corregidos:

1. **Emparejar era imposible (bloqueante).** El ciclo del líder
   volvía en cuanto la cuenta no estaba emparejada, y el único sitio
   donde un código se consume es el procesado de mensajes de ese
   mismo ciclo: el código nunca podía llegar. Las pruebas unitarias
   no lo veían porque prueban `canales.procesar` directamente, sin la
   puerta del monolito. Corrección: `canales.codigo_vigente()` y la
   puerta del ciclo deja pasar la escucha durante la ventana de un
   código vigente (sin emparejar no se procesa nada más: lo garantiza
   `procesar`). Cubierto por `test_codigo_vigente_solo_en_su_ventana`.
2. **Carrera al arrancar entre carriles.** Los dos procesos escribían
   `avisos-config.json` con el mismo nombre temporal al registrar el
   destino «canal»; uno de los dos moría con FileNotFoundError al
   reemplazar. Corrección: el temporal lleva el pid del proceso.

Verificado en vivo tras las correcciones: emparejamiento completo
(un chat ajeno con código inventado no empareja; un grupo con el
código bueno se ignora; el dueño en privado empareja y recibe la
confirmación, con la identidad enmascarada en el aviso), un encargo
mandado por Telegram que se divide (plan de reserva), avisa de la
subtarea fallida y devuelve su resumen de cierre por el mismo canal,
un pedido R2 de prueba física ofrecido por Telegram y aprobado con
«aprobar PEY7» (el permiso de un solo uso quedó consumido al recoger
la tarea, como manda la Fase 4), y un pedido R3 que el canal NO
ofrece: solo avisa de que espera en la app y sigue pendiente,
intacto. La marca de agua de la §B4 también se vio en acción: los
mensajes con fecha anterior a la marca se descartan como
reproducciones (en Telegram real las fechas son las de envío; solo
afectó a los mensajes falsos con fecha vieja de la primera prueba).

Límite honesto: la prueba con el bot real de Telegram (token de
@BotFather del dueño y su teléfono) queda para la PC del dueño, como
la lista de la Fase 0; todo lo demás del canal quedó probado contra
la forma real de la API.
