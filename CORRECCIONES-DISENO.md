# Correcciones de la primera prueba real del dueño — diseño breve

Rama `correcciones-prueba-real` (sobre `fase-6-seguridad`). El dueño descargó la
rama, la instaló en su Linux real y reportó cinco cosas:

1. No ve nada de lo agregado: le sale igual que antes.
2. Hay ventanas más grandes que la pantalla y no puede bajar hasta ver todas
   las opciones.
3. No encuentra dónde agregar sus dos cuentas Muse ni cómo «loguearse».
4. No hay chat local en el programa (cree que el original tampoco lo tenía) y
   pide agregarlo.
5. En Recursos solo ve la información de su PC, no dónde limitar: pide los %
   (ya existen, pero no los vio) y, como extra posterior, campos manuales
   absolutos (p. ej. 5 GB de RAM, 4 núcleos de CPU, 2 GB de GPU).

## Causa raíz verificada en el código

- En todo el monolito no hay ni un solo marco con scroll (0 `ScrollableFrame`):
  las páginas largas (Cuentas, con Tablero y Canales debajo; Recursos, otro
  tanto) se cortan si no caben en pantalla y no hay forma de bajar. Explica el
  punto 2 y, en cascada, el 1, el 3 y el 5: casi todo lo nuevo vive debajo del
  corte.
- El archivo `VERSION` sigue diciendo 0.4.6, la del Growi original: el
  programa se identifica como el de siempre.
- La página «Cuentas» sí existe, con el alta completa, y la sección
  «Multi-Muse» de Recursos sí tiene los % por modo; el dueño no llegó a
  verlos.

Orden de la ronda (el del dueño): 1 scroll/tamaño, 2 versión, 3 cuentas que se
entiendan, 4 chat local, y DESPUÉS 5 límites absolutos.

## 1. Scroll y tamaño

- Cada página de la barra lateral monta su contenido dentro de un marco con
  scroll (barra visible y rueda del ratón), con el mecanismo que ya usa la app
  (CustomTkinter) y sin cambiar cómo se conmutan las páginas.
- Ventana principal: la geometría inicial se acota a la pantalla del equipo
  (ancho y alto disponibles menos un margen), en cualquier resolución.
- Diálogos (ventanas secundarias): altura acotada a la pantalla; si el
  contenido es largo, también con scroll.
- Aceptación: a 1366×768, TODAS las páginas se recorren enteras.

## 2. Versión e identidad del build

- `VERSION`: 0.4.6 → 0.5.0.
- La marca «Multi-Muse» se ve donde el dueño mira: título de la ventana y/o
  página Estado, junto a la versión (p. ej. «Growi Bridge 0.5.0 ·
  Multi-Muse»). Si el código ya muestra la versión en algún sitio, se
  completa ahí en vez de duplicar.

## 3. Cuentas, que se entienda

- Encabezado de la página «Cuentas» con texto guía breve, en lenguaje del
  dueño: qué es una cuenta Muse dentro de Growi, que «entrar» con una
  cuenta es guardar su secreto en la bóveda (no se vuelve a mostrar, como una
  contraseña guardada) y los pasos para agregar la segunda cuenta.
- Etiquetas del formulario en ese mismo lenguaje («Agregar cuenta Muse»,
  «Secreto de la cuenta (se guarda en la bóveda, no se muestra)», …). Sin
  cambiar el modelo de datos ni el flujo de guardado.
- Aviso al arrancar, una vez y sin bloquear (aviso en la propia app), cuando
  el registro solo contiene la cuenta migrada: «Solo tienes una cuenta Muse
  configurada. Agrega la segunda en la página Cuentas para que trabajen las
  dos.» No se repite si ya hay dos o más cuentas habilitadas.

## 4. Chat local (nuevo)

- Página «Chat» en la barra lateral, con: selector de cuenta (las cuentas
  Muse habilitadas que tienen carril; por defecto, la del carril de esta
  copia), área de conversación con scroll, caja de texto y botón «Enviar».
- Enviar un mensaje crea una tarea normal por la maquinaria existente: se
  escribe `<tid>.task.json` en la carpeta de tareas del runner del carril de
  la cuenta elegida (`_dir_carril`), con el prompt = el mensaje y la forma
  derivada del propio programa (cwd = APP_DIR del carril destino, archivos =
  [`<APP_DIR>/chats/<tid>.md`]), la misma idea que encargos/ y consultas/ en
  las fases 4 y 2. `validate_task` acepta esa forma derivada exacta
  (`chats/`) con la misma estrictud; no se abre ninguna regla general nueva.
- La página vigila la carpeta de resultados del carril destino y, al llegar
  `<tid>.result.json`, añade la respuesta a la conversación: la salida del
  motor si la tarea terminó, o el motivo si falló. Sin respuesta no hay
  cuelgue: la burbuja queda marcada como fallida con su motivo.
- El chat no tiene atajos: la tarea pasa por la cola, el runner, la capa de
  permisos y la presencia como cualquier otra. Lo que el motor responda es lo
  que se muestra; el chat no inventa respuestas.

## 5. Límites absolutos opcionales (después de 1–4)

- `recursos.py`: la configuración por modo admite además un bloque opcional
  `absolutos` con `cpu_nucleos`, `ram_gb` y `gpu_gb` (cada uno opcional;
  vacío = sin tope absoluto en ese recurso).
- `limites()`: el tope efectivo de cada recurso es el MENOR entre el tope por
  % y el tope absoluto, cuando ambos existen; el estado compartido declara
  por recurso qué tope mandó (`pct` o `absoluto`) para que la UI y el
  resultado lo digan con honestidad.
- UI «Multi-Muse» (Recursos): junto a los % de cada modo, tres campos
  opcionales («RAM máx. (GB, opcional)», «CPU máx. (núcleos, opcional)»,
  «GPU máx. (GB, opcional)»). En blanco = solo manda el %.
- El gobernador y systemd-run no cambian de interfaz: consumen `limites()`
  como hoy. La GPU sigue gobernada por admisión; el tope absoluto de VRAM
  acota esa admisión.

## Pruebas de la ronda

- Unitarias: las 409 existentes en verde + nuevas para los topes absolutos
  de `recursos` y para la forma derivada `chats/` de `validate_task`.
- Físicas, con la UI real a 1366×768 (Xvfb): recorrer todas las páginas
  enteras con scroll; arranque con solo la cuenta migrada → aviso visible →
  alta de la segunda cuenta completada desde la UI; chat con mensaje a cada
  carril de prueba y respuesta (o motivo) visible en la página.
- El monolito conserva su CRLF al 100 % tras los parches.
