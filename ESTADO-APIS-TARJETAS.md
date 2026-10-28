# ESTADO — Tarjetas de conexión de APIs (t-apis-tarjetas-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_apis_tarjetas.py <dpi> [variante]`. Es **oculta** y usa el arnés
  `pruebas/arnes_oculto.py`.
  - Usa **claves falsas** contra un servidor local, `127.0.0.1:8793`: responde 200 a la buena y 401 a la mala.
    No sale nada a internet ni se gasta.
  - Las claves van a un archivo DPAPI de la copia (`GROWI_BRIDGE_CRED_BACKEND=dpapi`), **nunca** al
    Administrador de credenciales real. El arnés lo fuerza ya en todas las pruebas.
- Evidencia: `pruebas/evidencia/apis-tarjetas/evidencia-*.json`.

## LISTO
1. **Tarjetas de conexión.** Arriba de la página APIs hay una sección nueva, «Conexiones», con **una tarjeta por
   proveedor**: los 9 de `CRED_ORDER`.
   - En CTk, cada tarjeta es un `CTkFrame` con esquinas 10 y borde de 1 px.
   - Cada una lleva el nombre, un **punto de estado** con su **texto** y **su botón de acción**.
   - Las claves por fila de abajo («Claves», t-credenciales-keyring) ya eran CTk y no cambian.
2. **Estado real** (`claves_conexion_estado`), nunca un verde inventado:
   - **Sin clave**: «Sin clave · pon tu clave en APIs…» (patrón AirOps), punto gris, botón «Poner clave».
   - **Guardada sin probar**: lo dice, con «Probar».
   - **Conectada / Error**: lo que dio la última «Probar» (sin gastar), con fecha y hora y el texto del proveedor.
     Sale de `credenciales_pruebas`, lo mismo que guarda `cred_probar`.
   - **Ninguna activa**: naranja, con «Ver claves».
   - **Probando…**: mientras corre la prueba, con el botón desactivado.
3. **Mismos manejadores.**
   - «Probar» es `_claves_probar(cuenta de la activa)`, el mismo «Probar clave» de la fila.
   - «Poner clave» abre el formulario «Añadir o reemplazar una clave» con ese proveedor y su URL base, y pone el
     cursor en la clave.
   - «Ver claves» baja a las claves.
   - Tras una prueba, solo se repintan las tarjetas, porque el formulario puede tener texto a medias.
4. **Respaldo y foco.**
   - Con el import roto, `piloto_ctk: false` o `GROWI_BRIDGE_CTK=0`, toda la página sale con `_KitTk`: tarjetas
     `tk.Frame` y botones `ttk.Button`, el mismo código.
   - Cada botón de tarjeta es parada de Tab con Espacio e Intro (CTk) o es un `ttk.Button` (clásica). El anillo
     es el global.
5. **DPI.** El texto de estado va en su propia línea (wrap 440) y la línea del nombre y el botón pide 143-183 px:
   cabe a ventana mínima a 100 % y a 150 %.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) todas las tarjetas en CTk | `kit _KitCtk`, 9 tarjetas = `CRED_ORDER`, `CTkFrame` con esquinas 10, botones `CTkButton` |
| (b) estado real, con clave y sin clave | OpenAI (clave buena) → «Conectada · «prueba» ••••cdef (28/10 12:23). Clave válida (200)…». Groq (clave mala) → «Error · … Clave incorrecta (401): «clave falsa de la prueba»…». xAI (guardada, inactiva) → «ninguna activa». Anthropic → «Sin clave · pon tu clave en APIs». Coinciden con `credenciales_pruebas` (`ok true` / `false`) → `b_cuadra: true`. El servidor local recibió `/v1/models` y `/openai/v1/models`; nada fue a internet |
| (c) acciones iguales | «Poner clave» (Anthropic) → formulario en «Anthropic» con `https://api.anthropic.com`. El «Probar clave» de la fila sigue funcionando y la tarjeta se queda en «conectada» |
| (d) respaldo | `clasica`, `sinctk` y `flag`: `_KitTk`, las 9 tarjetas, (b) y (c) igual, **0 tracebacks** |
| foco | las 9: `takefocus 1` y Espacio enlazado (CTk); `ttk.Button` en la clásica |
| DPI, ventana al mínimo | 100 %: contenido 478 px ≥ texto 440 y línea 143. 150 %: 717 ≥ 660 y 171 → cabe |
| (e) arranque | `build_gui`: antes 14,3 / 13,8 s; después 13,3 / 14,0 s, sin cambio, porque APIs se dibuja al abrirla. El dibujo de APIs al abrir: antes 1140 / 904 ms; después 312 / 899 ms. Es ruido de la máquina; las 9 tarjetas no añaden un coste medible |

## FALTA
- **(f) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro (no abrir ventanas mientras usa el PC).
  Para tomarlas: `PRUEBA_VER=1 python pruebas/prueba_apis_tarjetas.py 100` (y `150`).
- Probado con claves **falsas** contra un servidor local, no con claves reales: las credenciales son de Leandro.
- Las tarjetas solo están en la página APIs. Ajustes → Claves sigue igual, sin duplicarlas.

## CÓMO PROBARLO
- `python pruebas/prueba_apis_tarjetas.py 100`, y `150`, `100 clasica`, `100 sinctk` y `100 flag`.
- En la app: APIs → «Conexiones». Pulsa «Probar» en la tarjeta de un proveedor con clave.
