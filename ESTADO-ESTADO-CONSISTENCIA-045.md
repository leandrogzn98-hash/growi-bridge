# ESTADO — Un solo estado de conexión en toda la pantalla (t-estado-consistencia-045)

Rama `Claude`, 29-oct-2026. Pedido de Leandro del 27 oct (captura de las 09:20): «Todo encendido» en verde y
«Sin conexión» en rojo **a la vez**. La pantalla medía dos cosas por separado, los procesos locales y la sonda
`conn_state` de nube/modelo, y cada una pintaba su propio veredicto.

- Prueba: `pruebas/prueba_estado_consistencia.py 100 | 150`. Es **oculta** (arnés `arnes_oculto`, instancia de
  prueba en %TEMP% con su propio share, puerto 8773). No abre ventanas ni roba el foco.
- Evidencia: `pruebas/evidencia/estado-consistencia/evidencia-100-ctk.json` y `evidencia-150-ctk.json`.
- La app instalada (`C:\Users\forte\growi-bridge\`) no se tocó.

## LISTO
1. **Fuente única de verdad**: `estado_unico()` en `growi-bridge.py` (bloque «Estado único», junto al plano de
   control del gateway, `_GW`).
   - Calcula `nivel` (comprobando / arriba / parcial / abajo), `puente`, `runner`, `proxy`, `nube_caida`,
     `caidos`, `texto`, `color` y la decisión del `banner`.
   - Sus fuentes:
     - el plano de control del gateway (`GET /gateway/estado` por 127.0.0.1 con token, cada 3 s). Una lectura de
       más de 15 s ya no cuenta como «el puente responde».
     - el runner;
     - la última prueba del proxy;
     - la nube, como **un dato más** (`runner_modelo_probe` + `cloud_banner_decidir`).
   - El sondeo del gateway ahora corre siempre, no solo con la página Estado a la vista, porque es la fuente del
     estado único. `_gw_render` guarda el dato aunque el panel no esté dibujado.
   - El último cálculo queda en `_EU`, para quien no debe recalcular (la bandeja).
2. **Todo lo que pinta estado lee de ahí**:
   - la pastilla de la barra lateral y la del proxy (`_refresh_conn_widgets`);
   - el banner (`_refresh_cloud_banner`): ya no llama a la sonda por su lado;
   - el botón de encendido y su texto (`draw_power`, `refresh_ui`);
   - los puntos de Servicios (`refresh_ui`);
   - las tarjetas de Salud (`estado_salud_filas`);
   - nuevo en este cierre: el **icono de la bandeja** (`_tray_kind`), su etiqueta «Estado del proxy» y la línea de
     proxy de `_auto_salud`. Antes leían `conn_state` / `conn_text` sueltos.
3. **Regla de consistencia**:
   - arriba → nadie dice «Sin conexión»;
   - abajo (puente apagado o sin responder) → nadie dice «Todo encendido» ni pinta un servicio en verde; el botón
     se apaga y las tarjetas dicen «No se puede comprobar: el puente está apagado»;
   - nunca un estado mixto.
4. **Estados parciales**: con el puente arriba y un servicio caído, el texto nombra lo que cayó:
   - «● Parcial: Proxy sin responder», «… Runner …», o «la nube no responde (solo el modelo local)»;
   - el botón dice «Encendido, pero: Proxy sin responder» y va en aviso `#FA5102`, nunca en verde completo;
   - el punto del proxy va en `#FA5102`, igual que su tarjeta.
5. **El runner manda sobre la sonda**: si el runner tiene ahora una tarea en la nube (Opus) sin fallo de red
   (`_probe_runner_en_nube`), no hay alarma de nube en ningún indicador.
   - Nuevo en este cierre: tampoco salen los **toasts** «Sin conexión: ni nube ni modelo local» / «Sin nube: uso el
     modelo local» (`_after_availability`). Eran la última alarma que salía de la sonda directa.
   - El desvío al modelo local (`state["nube_caida"]`) sigue igual: solo se calla el aviso.

## Evidencia (100 % y 150 %, mismos resultados)
| Caso | Barra lateral | Botón | Servicios (puntos) | Banner | Bandeja | Regla |
|---|---|---|---|---|---|---|
| (a) arriba | «● Conectado» | «Todo encendido» | puente y runner verdes; proxy gris «No se usa» | oculto | `ok` | sin «Sin conexión» |
| (b) abajo (`stop_bridge()` de verdad) | «● Sin conexión: el puente está apagado» | igual, en rojo, anillo apagado | ninguno verde; tarjetas «No se puede comprobar…» | oculto | `sin` | sin «Todo encendido», 0 verdes |
| (c) parcial (puente arriba, prueba del proxy = falla) | «● Parcial: Proxy sin responder» | «Encendido, pero: Proxy sin responder» en `#FA5102` | puente y runner verdes, proxy `#FA5102` | oculto | `local` | ni «Todo encendido» ni «Sin conexión» |
| (d) Opus en curso, sonda `conn_state = sin` y 3 fallos | «● Conectado» | «Todo encendido» | los 3 verdes | oculto | `ok` | ninguna alarma; toasts de conexión: **0** |

- Tracebacks en el log: 0 en las dos corridas.
- Gate (`python gate-calidad.py --archivos growi-bridge.py pruebas/prueba_estado_consistencia.py`): **PASA**.
  py_compile, ruff, mypy y pytest (9 passed) en verde; el smoke (copia oculta, puerto 8797) da `/gateway/salud` 200
  a los 23 s, sale limpio y el log no tiene tracebacks.

## FALTA
- **El proxy real en el caso (a)**: depende de `HTTPS_PROXY` en el entorno de quien corre la prueba.
  - En la corrida del 28-oct estaba puesto: proxy verde, «● Conectado — sales por EEUU», 792 ms.
  - En la del 29-oct no estaba: proxy gris «No se usa».
  - Las dos cumplen la regla. El proxy verde junto a «Todo encendido» se ve también en el caso (d).
- **Caso (c)**: no se puede apagar el proxy real del VPS desde aquí. La caída se simula con la fila de la prueba
  del proxy en «falla». El puente sí se detiene y se vuelve a arrancar de verdad.
- **Runner caído con el puente arriba**: solo está cubierto por código. La lógica es la misma que la del proxy
  («Parcial: el runner está apagado»), pero no se probó aparte.
- **Capturas**: no se tomaron, a pedido de Leandro (no abrir ventanas). La evidencia es el texto y el color real de
  cada widget, leídos de la instancia de prueba.
- **Reinicio de la app instalada**: lo hace Leandro. No se reinició nada real.

## CÓMO PROBARLO
- `python pruebas/prueba_estado_consistencia.py 100` y `… 150`. Mira en el JSON, en cada caso, `regla`
  (`dice_sin_conexion`, `dice_todo_encendido`, `puntos_verdes`), `bandeja` y, en `d_opus`, `toasts_de_conexion`.
- En la app, página Estado:
  - **arriba**: todo encendido → barra lateral «Conectado», botón «Todo encendido».
  - **abajo**: apaga el interruptor del Puente → todo dice «Sin conexión: el puente está apagado» y nada queda en
    verde.
  - **parcial**: con el proxy configurado, que no responda → «Parcial: Proxy sin responder» y botón en naranja.
  - **Opus en curso**: con una tarea en marcha no sale el banner rojo de la nube ni el toast, aunque la sonda falle.
