# BUGS-046-VIDEO

Portado a la rama Claude el 2026-10-31 (el runner los hizo sobre el growi-bridge.py de main). Prueba oculta: `python pruebas/prueba_bugs_046.py` (15/15 ok). Nada de esto se ha visto todavía en pantalla.

## B1 — Freeze al arrancar («No responde» ~5 s en «Comprobando la conexión…»)
Estado: **corregido en código; prueba oculta ok** (la medida del arranque con datos reales va en la prueba aislada del despliegue).

- `start_availability` ya no pinta el mapa desde el hilo del chequeo: usa `_ui_call(_render_avail)` (la rama Claude ya lo tenía desde la 0.4.5).
- `migrar_apis_json()` (almacén de claves) sale del camino síncrono de `main()` y corre en un hilo.
- El chequeo de conexión ya corría en hilos (`run_availability`); el spinner sigue en `_spin_avail`.
- Pendiente: correr `_prueba-bugs-render/medir_arranque.py` y confirmar que no queda ningún hueco largo del hilo de la UI.

## B8 — Scroll con artefactos (letras solapadas)
Estado: **corregido en código; prueba oculta ok** (4 deltas de touchpad = 1 paso; muesca arriba/abajo = −1/+1). Falta verlo a ojo.

- `_scrollable`: la rueda acumula `delta/120` y mueve pasos enteros (el touchpad ya no salta una unidad por evento) y llama `update_idletasks()` tras cada scroll.
- `_scrollable`: el `scrollregion` se reajusta una vez por tanda (`after_idle`) y no en cada `<Configure>`.
- Pendiente: comprobar a ojo con captura (solo a pedido de Leandro).

## B3 — Botones «Usar» en rojo (página APIs)
Estado: **corregido en código; prueba oculta ok** (acento #6aa9ff). Falta verlo a ojo.

- Causa: en el tema «Oscuro Raycast» el token `blue` y el acento eran #FF6363 (coral/rojo); todo botón primario salía rojo.
- Arreglo: `temas/oscuro-raycast.json` usa azul #6AA9FF en `accent` (`accent_hover` #85baff; texto oscuro encima). El rojo queda para errores y acciones destructivas. En la rama Claude el token `blue` ya era #0A84FF (0.4.5) y se deja así, con el resto de tokens 0.4.5.
- `pruebas/prueba_tokens_raycast.py` todavía espera el rojo #FF6363 en los botones primarios: hay que actualizarla (abre ventanas reales, no se corrió).

## B4 — «Ver nombre exacto» en rojo (página Modelos)
Estado: **corregido en código** (también en la variante clásica de la página Modelos nueva; en CustomTkinter ya era un botón neutro). Falta verlo a ojo.

- Causa: el botón usaba `THEME["blue"]` (rojo en Raycast). No es un error de resolución: solo alterna mostrar el id del motor.
- Arreglo: color neutro (`muted`, y `text` al pasar el ratón) y, además, el tema ya no pinta el azul en rojo.

## B5 — «Generar…» en rojo (Modelos, Tripo 3D)
Estado: **corregido en código; sin probar** (necesita la página de Tripo abierta: va en la prueba aislada).

- Causa del color: el botón es de acento y el acento de Raycast era rojo (ver B3).
- Sin clave de Tripo: el botón pasa a «Poner clave de Tripo…», la tarjeta dice que falta la clave y al pulsarlo lleva a Ajustes → APIs (antes no explicaba nada).

## B7 — «el motor local no responde» en rojo (Modelos)
Estado: **corregido en código; prueba oculta ok** (apagado = `muted`; no instalado y puerto ajeno siguen en `red`).

- `llm_textos`: motor apagado con el puerto libre muestra «Apagado (arranca bajo demanda)…» en gris (`muted`). El botón «Arrancar» ya se habilita en ese caso.
- Siguen en rojo, a propósito, los errores reales: no instalado, puerto ocupado por otro programa, proceso que no contesta.

## B2 — Estado miente («Conectado — sales por EEUU» con Tailscale caído)
Estado: **corregido en código; prueba oculta ok** (sonda en False = «● Tailscale caído» en rojo; la sonda real contesta True en este PC).

- Causa: `conn_text()` solo miraba la nube y el proxy; nada probaba la ruta Tailscale por la que la VM llega al puente.
- Arreglo: `_tailscale_sonda()` (fuera del hilo de la UI) comprueba que exista la IP de Tailscale de este PC y conecta de verdad a `ip:puerto` del puente. El vigía (cada ~30 s) y el arranque guardan el resultado en `_IPX["tailscale"]` y refrescan la barra.
- Con la sonda en `False`, `conn_text()` dice «● Tailscale caído» (en rojo) en lugar de «Conectado»; si el túnel está en `ninguno` o el puente está apagado no hay nada que probar y no cambia nada.

## B6 — «Quitar» en filas «Sin atajo» (Ajustes → Atajos)
Estado: **corregido en código; prueba oculta ok** (sin atajo solo «Asignar», con atajo solo «Quitar»; los 13 campos reales llevan el alternador).

- `_atajo_botones()` crea «Quitar» y «Asignar» y `_CampoAtajo.refrescar()` alterna: con atajo, solo «Quitar»; sin atajo, solo «Asignar» (empieza la captura, igual que pulsar el campo). Vale para las dos superficies (CustomTkinter y clásica) y para el formulario de atajos de comandos.

## B10 — Credenciales sin guía (Meshy, Gemini: «no está guardada» en rojo)
Estado: **corregido en código; prueba oculta ok** (fila sin clave con «Configurar»; guardada, sin botón).

- En el panel Gateway (Estado → Motores → Credencial), cada fila con la clave sin guardar muestra ahora un botón «Configurar» (`_gw_configurar`): abre la página APIs con el proveedor de esa fila elegido, su URL base y la etiqueta «principal» rellenas, y el cursor en la casilla de la clave. El botón desaparece cuando la clave queda guardada.
- Al portarlo a la rama Claude se usa el botón de fila que ya tiene el panel (6.º elemento `acc` de `_gw_rows`, el mismo de «Comprobar»), dentro del redibujo incremental, en vez de una 3.ª columna aparte.
