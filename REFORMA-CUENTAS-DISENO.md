# Reforma de cuentas — diseño breve

Rama `reforma-cuentas` sobre `correcciones-prueba-real`. Pedida por el dueño
el 2026-11-16 tras probar la ronda de correcciones: el formulario de Cuentas
(nombre, identificador, asistente, carril, «Secreto (nuevo)») no se entiende,
y los secretos de trabajo deben ser globales, no por cuenta.

## 1. La verdad del código: la clave la crea el programa

En el Growi original, `load_secret()` crea un secreto aleatorio si no hay
uno y el registro dice «pásaselo a tu asistente para que se conecte»: **el
programa genera la clave y el dueño se la pasa a su Muse en su chat**; con
ella, la Muse se conecta a su carril del puente (`gateway_token()` la lee
de la bóveda por cuenta). El formulario de la Fase 1 pide TECLEAR un secreto
nuevo: de ahí el enredo del dueño («¿qué le voy a pasar al programa?»). Al
programa no se le pasa ninguna clave: solo el nombre de la cuenta.

Iniciar sesión con correo y clave de Meta dentro del programa no es
posible: Meta no ofrece a programas de terceros entrar con la contraseña
del dueño, y ningún programa debería guardarla. Queda fuera de alcance.

## 2. El alta nueva

El formulario de Cuentas pasa a ser SOLO de alta, con dos datos:

1. **«Nombre de la cuenta (o tu correo)»** — texto libre: como el dueño
   reconoce a la cuenta («Rayo», «lu@correo…»).
2. **«Cómo se conecta»** — servidor / local / ambas, cada opción con su
   línea llana: servidor = «se conecta desde su espacio a este PC»; local =
   «trabaja solo dentro de este PC»; ambas = «las dos: si falla la red,
   sigue en local y al volver se reconcilia».

Automático, sin preguntar:

- **Identificador**: `cuentas.derivar_id(nombre, ids_existentes)` —
  minúsculas, sin acentos (NFKD), espacios y caracteres no válidos a
  guiones, recortado al patrón `_RX_ID` (2–32, empieza/termina en
  letra/dígito); si choca con un id vivo o con una lápida, sufijo `-2`,
  `-3`…; si el nombre no produce nada válido, base «cuenta».
- **Carril**: `cuentas.carril_libre(reg)` — el primer carril («a», luego
  «b») sin cuenta habilitada; si no hay ninguno, la cuenta nace sin carril
  y la UI avisa que hay que liberar uno (el registro ya admite `None`).
- **Asistente**: `None` (el perfil activo del carril, como la cuenta de
  compatibilidad).

**La clave**: al guardar una cuenta nueva, el monolito genera
`secrets.token_urlsafe(32)`, la guarda con `_sec_set(muse:<id>)` y, si la
cuenta es la principal, escribe también `secret.txt` (regla B4 de la
Fase 1: `browser-server.py` lo sigue leyendo). Después la muestra **una
sola vez** en un diálogo acotado (`_acotar_ventana`):

- Título: «La clave de {nombre}».
- Texto llano: qué es («la clave de conexión de esta cuenta»), qué hacer
  («pásasela a tu Muse en su chat, en la app de Muse: con ella se
  conecta a este programa»), y que solo se muestra esta vez.
- La clave en un campo de solo lectura seleccionable + botón «Copiar
  clave» (portapapeles de Tk) + botón «Ya la pasé» que cierra.

Mostrarla una vez al crearla es el flujo del Growi original (su
`secret.txt` era legible por el dueño); la regla «nunca se muestra» sigue
valiendo para las claves YA guardadas: ninguna pantalla las vuelve a
enseñar. Si el dueño pierde la nueva antes de pasarla, usa «Nueva clave».

**«Nueva clave»** por cuenta (en la lista): confirma que la anterior deja
de valer, genera otra, la guarda igual (bóveda + `secret.txt` si es la
principal), invalida la caché del registro (`_CUENTAS_CACHE`) y la muestra
una vez en el mismo diálogo.

La lista de cuentas muestra por cuenta: nombre · carril («carril A»,
«carril B» o «sin carril») · conexión · habilitada/deshabilitada ·
«clave: en la bóveda / SIN clave». Acciones: Nueva clave ·
Deshabilitar/Habilitar · Borrar, con las reglas de siempre de
`cuentas.py`/la UI (la principal no se deshabilita ni se borra). La
edición de campos técnicos (id, asistente, permisos) desaparece del
formulario; el esquema de `cuentas.py` no cambia.

La guía superior de Cuentas se reescribe al flujo real: agregar la cuenta
→ copiar la clave que el programa crea → pasársela a la Muse en su chat.
El aviso de arranque con una sola cuenta se mantiene.

## 3. Bóveda compartida (los secretos globales)

Módulo nuevo `compartida.py` (LF), con el patrón de `cuentas.py`:

- Registro de NOMBRES en la carpeta compartida (`_token_dir()` del
  monolito): `boveda-compartida.json`, entradas
  `{etiqueta, nota, creada}` — **jamás valores**. Etiqueta:
  `[a-z0-9][a-z0-9-_]{0,40}`. Lock entre procesos (O_EXCL, ruptura a los
  15 s) + revisión optimista + escritura atómica.
- Valores solo en el almacén de credenciales, con el nombre
  `compartido:<etiqueta>` (`_sec_set/_sec_get/_sec_del` del monolito,
  servicio `growi-bridge` como todo lo demás).
- Acceso auditado: `_compartida_usar(etiqueta, cuenta=None)` en el
  monolito lee el valor y deja asiento en la capa de permisos con la
  cuenta que lo usa (por defecto, la de este carril). Es el camino para
  que el código del programa tome un secreto compartido; en esta ronda
  ningún motor recibe valores crudos por esta vía.
- UI: sección «Bóveda compartida» en la página Cuentas, bajo la lista:
  explicación llana («guardas una sola vez las contraseñas y claves de
  trabajo; las dos cuentas pueden usarlas cuando una tarea lo necesite;
  viven en la bóveda y nunca se muestran»), campos Etiqueta + Valor (solo
  escritura) + Nota, botón «Guardar en la bóveda compartida», lista de
  etiquetas con nota y fecha, y «Borrar» por entrada (registro + valor).

Alcance honesto: las claves de APIs de Ajustes → Claves YA son globales
hoy y no se migran en esta ronda. Con el almacén del sistema (keyring)
los valores se comparten entre los dos carriles; con el respaldo en
archivo local (sin keyring) cada copia del programa tiene su archivo —
la misma limitación declarada en la Fase 1.

## 4. Lo que NO cambia

`cuentas.py` solo gana dos funciones puras (`derivar_id`, `carril_libre`);
esquema, validación, migración de `secret.txt`, `gateway_token`, la
bóveda por cuenta para la clave de conexión, permisos y auditoría quedan
como están.

## 5. Pruebas

Unitarias: `derivar_id` (acentos, choques, lápidas, vacío, nombre largo),
`carril_libre` (a libre, a ocupado → b, ambos ocupados → None, cuenta
deshabilitada no ocupa), `compartida` (el registro en disco no contiene el
valor — centinela —, agregar/quitar/listar, etiqueta inválida, duplicada)
y la suite previa entera en verde (422).

Físicas a 1366×768 con la UI real: alta de «Rayo» con el formulario nuevo
→ diálogo con la clave y botón Copiar → el registro queda con el id
derivado y su carril; «Nueva clave» cambia el valor de la bóveda; alta de
la segunda cuenta → el otro carril; bóveda compartida: guardar un secreto
de juguete y ver su etiqueta en la lista; el valor no aparece en ningún
JSON del disco (grep centinela).
