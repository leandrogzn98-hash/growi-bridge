# ESTADO — Auditoría final de la 0.4.5 (t-auditoria-045)

Rama `Claude`, 29-oct-2026. Solo audita, mide y reporta: **no se reconstruyó ninguna pantalla** ni se tocó
`growi-bridge.py`. La app instalada no se tocó.

- Prueba: `pruebas/prueba_auditoria.py 100 | 150`, con `pruebas/captura_oculta.py`.
  - Nada se ve ni roba el foco: la ventana se muestra con alpha 0, deja pasar los clics, va al fondo del orden Z,
    sin botón en la barra de tareas y sin activarse.
  - Se lee con `PrintWindow` y en cada captura se anota si cambió la ventana en primer plano: `foco_igual: true`
    en las 14.
- Evidencia: `pruebas/evidencia/auditoria/evidencia-100-ctk.json` y `evidencia-150-ctk.json`.
- Capturas en `pruebas/evidencia/auditoria/capturas-045/`, con copia en `share\outbox\capturas-045\`.
- La fuente de los criterios es `REVISION-UIUX-0.2.0.md`, que está en el repo: 62/100, con sus 6 bloques
  anti-slop.

## LISTO

### (a) Capturas (14, tema Oscuro Raycast, ventana de 940×680 a 100 %)
| Pantalla | 100 % | 150 % (DPI simulado, `GROWI_BRIDGE_DPI=144`) |
|---|---|---|
| Tareas | `100-tareas.png` | `150-tareas.png` |
| Modelos | `100-modelos.png` | `150-modelos.png` |
| Ajustes | `100-ajustes.png` | `150-ajustes.png` |
| Estado | `100-estado.png` | `150-estado.png` |
| Recursos | `100-recursos.png` | `150-recursos.png` |
| Configuración inicial | `100-configuracion-inicial.png` | `150-configuracion-inicial.png` |

Además, `*-estado-otra.png` (la vuelta a Estado con la que se midió la barra lateral).

### (b) Lista de comprobación
Leyenda de la evidencia:
- **hoy**: medido el 29-oct en esta prueba, o en una prueba oculta re-ejecutada hoy (ver «Pruebas re-ejecutadas»).
- **previa**: evidencia del commit de ese spec del 28-oct. Esas pruebas no usan el arnés oculto y abrirían
  ventanas, así que no se re-ejecutaron.

| # | Punto | Veredicto | Evidencia |
|---|---|---|---|
| 1 | Tokens exactos | **Pasa con 2 desvíos documentados** | hoy. bg `#0F0F0F`, tarjeta `#1A1A1C`, línea `#2C2C2E`, suave `#9A9AA0`, verde `#34C759`, aviso `#FA5102`, azul `#0A84FF` y acento `#FF6363` exactos. Texto `#F5F5F6` (no `#F5F5F7`) y error `#E64C51` (no `#E5484D`, que da 4,44:1 < AA): decisión de t-tokens-raycast-045. Fuente Inter instalada y en uso; IDs en Consolas |
| 2 | Barra lateral más oscura que el contenido | **Falla (leve)** | hoy. Barra `#141416`, contenido `#0F0F0F`: la barra es **más clara** que el contenido. Solo es más oscura que la tarjeta, que es como lo leyó t-tokens-raycast-045 |
| 3 | Densidad 32-36 px | **Pasa** | hoy. `Treeview`, `Tareas.Treeview` y `Res.Treeview`: 34 px a 100 % y 51 px a 150 % (= 34 × 1,5) |
| 4 | Sin gradientes morado-rosa | **Pasa** | hoy. 0 gradientes en el código (`gradient`/`degradad` solo aparece en la columna `degradado` de la cola) y ninguno en las 14 capturas |
| 5 | `#FF6363` solo en acciones primarias | **Falla** | hoy, botones con el acento a la vista. **Tareas**: Enviar ✓ y Pedir cosecha ✗. **Modelos**: Añadir regla, Comprobar mi PC, Descargar, Generar…, Instalar y Probar ✗. **Ajustes**: Guardar ✗. **Estado**: Pararlo (aviso de Avast) y Exportar mis conversaciones ✗. **Configuración inicial**: Siguiente (primaria del asistente) ✓ |
| 6 | Barra lateral 232 px, contadores reales, tarjeta del guardrail | **Pasa** | hoy: ancho real 232 px a 100 % y 348 px a 150 %; tarjeta «Preguntarme siempre · 0 en espera» en todas las capturas. previa: contadores reales (`barra-lateral/`) |
| 7 | Estadísticas y filtros de Tareas con números reales | **Pasa** | hoy: «En curso 0 / Aprobadas hoy 0 / Gasto de hoy $0.00» con la cola vacía de la copia. previa: `tareas-estadisticas/` (54 filas, píldoras que cuadran) |
| 8 | Historial de gasto con total acumulado y por día | **Pasa** | hoy: `prueba_historial_gasto.py 100` re-ejecutada |
| 9 | Tarea en curso fijada con «trabajando ahora» | **Pasa** | previa: `tareas-estadisticas/100-a-fijada-y-54-filas.png` y `150-…` |
| 10 | Detalle y compositor debajo de la tabla | **Pasa** | hoy: `prueba_tareas_detalle.py 100/150` y `prueba_tareas_compositor.py 100` re-ejecutadas |
| 11 | Campo Ctrl+K en el encabezado | **Pasa, con un desvío visual** | hoy: el campo está en el encabezado de Tareas (`100-tareas.png`) y `prueba_tareas_ctrlk.py 100` se re-ejecutó. **Desvío**: el `ttk.Entry` dibuja un **borde blanco** de 1 px sobre el tema oscuro, en vez de la línea `#2C2C2E` |
| 12 | «Ver el mapa» baja y resalta | **Pasa** | previa: `estado-mapa/100-a-despues-resaltado.png` y `150-…` |
| 13 | Banner de la nube según el modelo real del runner | **Pasa** | hoy: t-estado-consistencia-045, caso (d), con Opus en curso y la sonda fallando 3 veces: sin banner ni toast. previa: `banner-nube/` |
| 14 | Consistencia de estado | **Pasa** | hoy: `ESTADO-ESTADO-CONSISTENCIA-045.md` (arriba, abajo y parcial a 100 y 150 %); en las 14 capturas, «Todo encendido» va con «● Conectado» |
| 15 | Mascota sin tapar el cierre del detalle | **Pasa** | hoy: `prueba_mascota_solape.py 100/150` re-ejecutadas |
| 16 | Foco de teclado visible en lo convertido | **Pasa** | hoy: anillo azul en «Siguiente» (`*-configuracion-inicial.png`). previa: `teclado-foco/3..5-foco-*.png` |
| 17 | Arranque medido por página | **Medido; Modelos falla la regla de 300 ms** | hoy. `build_gui` 10,5 s (100 %) y 11,1 s (150 %), en línea con los 10-15 s de los specs anteriores. Abrir cada página la primera vez y la segunda: Tareas 31/22 ms, **Modelos 3552/1662 ms**, Ajustes 938/24 ms, Estado 9/10 ms, Recursos 9/5 ms (a 150 % parecido: Modelos 3870/1537). Modelos y la primera apertura de Ajustes bloquean la ventana más de 300 ms sin esqueleto |
| 18 | Nada de móvil | **Pasa** | hoy: el código solo tiene dos textos que mencionan el móvil («En el móvil no está», «Compárala con el móvil»); ningún layout, breakpoint ni prueba |
| 19 | Sin «·» en textos visibles (P0 de la 0.2.0) | **Falla** | hoy, textos con «·» a la vista (100 %): Tareas 3, **Modelos 50**, Ajustes 12, Estado 10, Recursos 2. Dos están en la barra lateral, en todas las páginas: «Versión 0.2.0-alpha · carril A» y «equivalente Max $0.00 · 0 tareas terminadas» |
| 20 | Sin etiquetas en MAYÚSCULAS de 9 px (P0 de la 0.2.0) | **Pasa** | hoy: 0. Los `PY_VAR*` que salen en la medida son nombres de variable de un widget, no texto visible; no aparecen en ninguna captura |
| 21 | DPI 150 %: nada se corta | **Falla** | hoy, 150 %: **Estado**, tarjetas de Salud y del aviso de Avast cortadas por la derecha («…(Claude Code) · co»); **Recursos**, tarjeta «Disco libre» cortada (también a 100 %); **Tareas**, «revisadas y aprobadas ho» y «real · $0.00 equivalente N» cortados; **Modelos**, ruta del registro de Tripo cortada |

**Pruebas re-ejecutadas** (29-oct, todas ocultas, en serie):
- Pruebas: historial_gasto 100, tareas_detalle 100 y 150, tareas_compositor 100, tareas_ctrlk 100, mascota_solape
  100 y 150, estado_tarjetas 100, recursos_graficos 100, modelos_tarjetas 100, ajustes_secciones 100 y
  onboarding_piel 100.
- Resultado: 12 de 12 salen con código 0, sin `error_prueba` y con 0 tracebacks.
- Contra la evidencia commiteada de cada spec, **ningún resultado verdadero/falso cambió**. En historial_gasto
  cambian los días sembrados, que dependen de la fecha (ahora 27, 28 y 29-oct), y los tres se verifican.
- Después se restauró la evidencia commiteada de esos specs: esta auditoría no la reescribe.

**Contraste** (hoy): texto/fondo 17,6:1; suave/tarjeta 6,2:1; verde/tarjeta 9,5:1; error/tarjeta 4,57:1;
azul/tarjeta 4,76:1. Todo AA. El acento `#FF6363` lleva texto oscuro: el blanco daría 2,91:1 y no se usa.

### (c) Puntuación
Mismos 6 bloques de la auditoría 0.2.0, más la lista funcional de la 0.4.5. La 0.2.0 no traía pesos, así que los
pesos son míos y van fijados aquí:
- Looks cliché: 10.
- Kit SaaS: 15.
- Cromo de plantilla («·», MAYÚSCULAS, acento mal usado): 20.
- Contenido (datos reales, estados vacíos y de error): 15.
- Logo intercambiable: 10.
- DPI 150 %: 15.
- Lista 0.4.5 de la pantalla: 15.

| Pantalla | Cliché /10 | Kit SaaS /15 | Cromo /20 | Contenido /15 | Logo /10 | DPI /15 | Lista 0.4.5 /15 | **Total** |
|---|---|---|---|---|---|---|---|---|
| Tareas | 10 | 11 (tarjetas iguales en fila) | 15 (3 «·», Pedir cosecha en acento) | 14 | 6 | 9 (estadísticas cortadas) | 13 (borde blanco del Ctrl+K) | **78** |
| Modelos | 10 | 11 | 6 (50 «·», 6 botones en acento) | 14 | 6 | 13 (ruta cortada) | 9 (3,5 s al abrir) | **69** |
| Ajustes | 10 | 13 (filas con divisor, no tarjetas) | 13 (12 «·», Guardar en acento) | 15 | 6 | 14 | 13 (0,9 s la primera vez) | **84** |
| Estado | 10 | 12 (rejilla de tarjetas de Salud) | 13 (10 «·», 2 botones en acento) | 15 | 8 (el orbe del botón) | 9 (tarjetas cortadas) | 14 | **81** |
| Recursos | 10 | 12 (4 tarjetas iguales) | 18 (solo la barra) | 14 | 6 | 8 (Disco libre cortada a 100 y 150 %) | 14 | **82** |
| Configuración inicial | 10 | 14 | 20 | 15 | 5 (sin mascota) | 15 | 15 | **94** |

- **Puntuación final: 79/100** = media de las 5 pantallas de trabajo (78 + 69 + 84 + 81 + 82 = 394 / 5 = 78,8).
  La configuración inicial se ve una vez y no entra en la media; con ella serían 81 (488 / 6).
- **Frente a la 0.2.0**: de 62 a 79, **+17**.
  - Resuelto de lo que se midió hoy:
    - DPI: la geometría escala (barra 348 px y filas 51 px a 150 %), aunque quedan cortes (F8-F11);
    - cierre: Ajustes → «Al cerrar la ventana», con Preguntarme / Minimizar a la bandeja / Salir del todo;
    - etiquetas en MAYÚSCULAS: 0;
    - contraste: todo AA.
  - La gramática de la paleta Ctrl+K no se volvió a auditar aquí.
  - Sin resolver: los «·».

### (e) ¿Meta 80+? **No: 79, falta 1 punto.**
Por qué, en orden de peso:
1. **Los «·»**. Es el P0 de texto de la 0.2.0 y sigue sin resolver: Modelos tiene 50 y la barra lateral lo lleva a
   todas las páginas. Junto con el acento, deja Cromo en 6/20 en Modelos y en 13/20 en Ajustes y Estado.
2. **Contenido cortado a 150 %** (Estado, Recursos, Tareas).
3. **El acento `#FF6363` fuera de las acciones primarias** (10 botones).
4. **Modelos bloquea 3,5 s** al abrirse.

Estimación, no medida: quitar los «·» de la barra lateral y de Modelos subiría Cromo unos 8 puntos en Modelos y
1-2 en las demás, lo que basta para pasar de 80. Con los cortes de 150 % arreglados, la nota quedaría cerca de 85.

## FALTA
(d) Cada desvío, con su pantalla, elemento y captura. Ninguno se arregló aquí: el spec solo audita. El coordinador
decide si abre un spec de arreglo.

| # | Pantalla | Elemento | Desvío | Captura |
|---|---|---|---|---|
| F1 | Todas (barra lateral) | Pie de marca y «Consumo hoy» | «Versión 0.2.0-alpha · carril A» y «equivalente Max $0.00 · 0 tareas terminadas»: meta-strings con «·» | `100-*.png` |
| F2 | Modelos | Filas del catálogo, «Contexto en tu tarjeta», «Coste», cadena de motores | 48 textos con «·» (p. ej. «0.6 GB en disco · necesita ~1.5 GB…», «4k ✓ 18 % · 8k ✓ 25 % · …», «principal · equivalente Max ·») | `100-modelos.png` y el JSON (`paginas.modelos.medido`) |
| F3 | Ajustes / Estado | Estado de los motores | «Disponible · 2.1.312 (Claude Code) · comprobado 14:25» y parecidos: 10 y 8 textos | `100-ajustes.png`, `100-estado.png` |
| F4 | Tareas | Tarjeta «Gasto de hoy» | «real · $0.00 equivalente Max · local $0» | `100-tareas.png` |
| F5 | Modelos | Botones Añadir regla, Comprobar mi PC, Descargar, Generar…, Instalar, Probar | Acento `#FF6363` en acciones secundarias | JSON `botones_con_acento` (más abajo de la página que la captura) |
| F6 | Estado | «Pararlo» (aviso de Avast) y «Exportar mis conversaciones» | Acento en acciones que no son la primaria | `100-estado.png` (Pararlo) |
| F7 | Tareas / Ajustes | «Pedir cosecha» y «Guardar» | Acento fuera de Enviar y Abrir resultados | JSON `botones_con_acento` |
| F8 | Estado (150 %) | Tarjetas de Salud y del aviso de Avast | Cortadas por la derecha: el contenido es más ancho que el área visible | `150-estado.png` |
| F9 | Recursos (100 y 150 %) | Fila de 4 tarjetas (CPU, RAM, GPU, Disco libre) | «Disco libre» cortada por la derecha | `100-recursos.png`, `150-recursos.png` |
| F10 | Tareas (150 %) | Estadísticas «Aprobadas hoy» y «Gasto de hoy» | Texto cortado: «revisadas y aprobadas ho», «real · $0.00 equivalente N» | `150-tareas.png` |
| F11 | Modelos (150 %) | Registro de Tripo | Ruta cortada («…tripo-gast») | `150-modelos.png` |
| F12 | Tareas | Campo «Buscar o pedirle algo (Ctrl K)» | `ttk.Entry` con borde blanco en el tema oscuro (debería ser `#2C2C2E`) | `100-tareas.png`, `150-tareas.png` |
| F13 | Todas | Barra lateral | `#141416`, más **clara** que el contenido `#0F0F0F`; el diseño pide «ligeramente más oscura» | `100-*.png` |
| F14 | Modelos / Ajustes | Abrir la página | Modelos 3,5 s cada vez que se abre (1,5-1,7 s la segunda); Ajustes 0,9 s la primera. Más de 300 ms bloqueando, sin esqueleto | JSON `paginas.*.abrir_ms` |

**Lo que no se pudo verificar hoy:**
- Mapa, banner, foco, estadísticas, tarea fijada y contadores de la barra lateral: sus pruebas
  (`prueba_estado_mapa.py`, `prueba_banner_nube.py`, `prueba_teclado_foco.py`, `prueba_tareas_estadisticas.py`,
  `prueba_barra_lateral.py`) abren ventanas y no se re-ejecutaron. Su veredicto se apoya en la evidencia del 28-oct
  y en que su código sigue ahí.
- El 150 % es **simulado** (`GROWI_BRIDGE_DPI=144`, como en el piloto), no un monitor real a 150 %.
- Las capturas se hicieron con la cola vacía de la copia de prueba. No muestran la tabla con filas, el detalle
  abierto ni una tarea fijada; esos puntos se verificaron con sus pruebas.
- La barra lateral dice «Versión 0.2.0-alpha» porque `VERSION` no se toca en ningún spec. Es un dato, no un desvío
  de diseño.

## CÓMO PROBARLO
- `python pruebas/prueba_auditoria.py 100` y `python pruebas/prueba_auditoria.py 150`. Tarda unos 3 min cada una y
  no muestra nada. Deja las capturas en `pruebas/evidencia/auditoria/capturas-045/` y las medidas en
  `evidencia-<dpi>-ctk.json`:
  - `paginas.<p>.medido`: «·», MAYÚSCULAS, botones con acento y filas;
  - `abrir_ms`;
  - `tokens`, `contraste`, `barra_lateral` y `estatico`.
- Para mirar una pantalla con los ojos: abre la app, tema Oscuro Raycast, y compara con la captura de la misma
  pantalla.
