# ESTADO — Ajustes en secciones con filas (t-ajustes-secciones-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_ajustes_secciones.py <dpi> [variante]`. Es **oculta**.
  - **Nada real se ejecuta en el PC**: `set_autostart` (schtasks), `pc_power` (`shutdown /t 60`) y `pc_abort`
    (`shutdown /a`) se sustituyen por registradores **antes** de construir la ventana. Las confirmaciones se
    contestan solas.
  - Variantes: `ctk` a 100 % y 150 %, `clasica`, `sinctk`, `flag` y `texto150` (150 % de texto + 150 % de DPI).
- Evidencia: `pruebas/evidencia/ajustes-secciones/evidencia-*.json`.

## LISTO
Se construyó **encima** del piloto y de t-ajustes-reorg, que ya dejaron Ajustes en secciones con encabezado en
sentence case semibold y filas de título + descripción + control a la derecha. No se rehízo nada.

1. **Secciones con filas:**
   - **Guardrail**, en la sección «Permisos y seguridad»: ahora con **las 3 opciones como radio**.
     - «Hazlo sin preguntar» pasa por la **misma doble confirmación** de siempre (`_on_guardrail`: aviso y escribir
       «sin preguntar»).
     - Su botón de la zona peligrosa sigue allí.
   - **Motores**, al final de «Motores, modelos y suscripciones»: una fila por motor, «Estado: <motor>». Lleva el
     estado real como descripción (el último healthcheck, lo mismo que las tarjetas de Estado) y, a la derecha, un
     **punto de color con el estado corto**: Disponible, No disponible, Sin datos o Desactivado.
   - **Apariencia**: el tema segmentado (Claro / Oscuro / Según el sistema, sin cambios), **Tamaño del texto**
     (100 / 125 / 150 %, segmentado) y **Mascota** (interruptor).
2. **Ajustes nuevos: uno, y es el que pide el spec.**
   - «Tamaño del texto» no existía. El spec lo pide expresamente (subfunciones 1 y 4) y a la vez dice «sin ajustes
     nuevos»: se resolvió a favor del texto explícito del spec. Es el único.
   - El interruptor de la Mascota **no** es un ajuste nuevo: es el mismo `mascot` del pie de la barra lateral, con
     el mismo manejador (`mascota_poner`), y los dos interruptores se siguen el uno al otro.
   - Las filas de estado de motores son de lectura.
3. **Mismo comportamiento.** Los mismos manejadores: interruptores, tema, «Al cerrar la ventana», Apagar o
   Reiniciar el PC con confirmación y 60 s de margen, y «Cancelar apagado».
4. **Tamaño del texto.**
   - Es un factor más sobre la escala de **toda** la interfaz (fuentes, medidas fijas y CTk), como el DPI, así que
     todo crece en proporción.
   - Se guarda en `settings.json` (`tamano_texto`) y se aplica al abrir la app. La fila lo dice: «Se aplica al
     reiniciar», la misma convención de las demás filas de ese tipo.
   - Para que quepa a 150 % de texto + 150 % de DPI (225 % en total), la **lista de secciones de la barra lateral
     hace scroll** cuando de verdad no cabe en la pantalla. Es un Canvas con la altura de la lista mientras cabe:
     a 100 % y a 150 % no cambia nada. Funciona con la rueda, y el Tab trae la fila enfocada a la vista.
5. **Respaldo.** La clásica sigue intacta y además tiene el tamaño del texto (radios) y el interruptor de la
   mascota. Con el import roto, `piloto_ctk: false` o `GROWI_BRIDGE_CTK=0` sale la clásica.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) secciones y filas | secciones: General, Apariencia, Conexión, Motores, modelos y suscripciones, Permisos y seguridad, Zona peligrosa. Filas «Tamaño del texto», «Mascota», «Reducir movimiento», «Tema», «Antes de actuar» y «Pedir permiso si puede costar mucho» presentes. Radios del guardrail: los 3 |
| (b) Guardrail | `siempre` → settings `siempre`; `delicado` → `delicado`; `nunca` → settings `nunca` **tras** «confirmar: Hazlo sin preguntar» y «escribir: sin preguntar» |
| (b) Motores | 6 filas; Claude, Codex y Ollama «Disponible», llama, meshy y gemini «No disponible» con su motivo; cada texto = `estado_salud_filas()` → cuadra en las 6 |
| (b) Apariencia | tema claro → `apariencia: claro`, oscuro → `oscuro`, sistema → `sistema`; tamaño 125 / 150 / 100 → `tamano_texto` guardado; con `tamano_texto: 150` al abrir: «DPI de la ventana: 144 (150 % de escalado), texto al 150 %: 225 % en total», `SCALE = 2.25`. Mascota: `false` → `true`, y el interruptor de la barra lateral la sigue |
| (c) prueba funcional | **15/15** en CTk y en la clásica (`sinctk` y `flag` también): autostart ×2 (llama a `set_autostart`), auto_update ×2 y keep_awake ×2 (cambian en settings), «Al cerrar» ×3, y Apagar PC y Reiniciar PC (confirma, `pc_power` con 60 s y Cancelar → `pc_abort`) |
| (d) 150 % + 150 % | escala 225 %: la barra lateral pedía 1323 px y caben 1000; con la lista en scroll pide **893 → cabe** («la lista de secciones hace scroll (270 de 700 px)»). A 150 % solo: 967 px, sin scroll, igual que antes |
| (e) respaldo | `clasica`, `sinctk` y `flag`: página clásica con los 3 radios, el tamaño del texto (radios) y la mascota (`Canvas`); 15/15; **0 tracebacks** |
| arranque (`build_gui`, 100 %) | antes 14,2 / 13,4 s; después 13,9 / 15,3 s, dentro del ruido |

## FALTA
- **(c) La «22/22» del piloto**: su script no está en este repo (vive en `share\inbox` del PC con
  `ESTADO-PILOTO-CUSTOMTKINTER.md`). Se hizo una prueba propia de los mismos controles: **15/15**, sin efectos
  reales.
- **(d) «Nada se sale ni se corta» en la página entera a 225 %: no se pudo comprobar.** Con la ventana oculta, Tk
  no reparte el espacio al tamaño real. A tamaño pedido, varias filas (de Ajustes y de otras páginas) piden más
  ancho que el contenido; en la ventana real las encogen pack y grid y su texto se re-parte (`wrap_to`), pero
  verlo exige una captura con la ventana visible, que queda **a pedido de Leandro**:
  `PRUEBA_VER=1 python pruebas/prueba_ajustes_secciones.py 150 texto150`.
- **(f) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro.
- El tamaño del texto se aplica al reabrir, no en caliente: cambiar la escala de toda la interfaz en caliente
  exigiría rehacer todas las páginas.

## CÓMO PROBARLO
- `python pruebas/prueba_ajustes_secciones.py 100`, y `150`, `100 clasica`, `100 sinctk`, `100 flag` y
  `150 texto150`.
- En la app: Ajustes → Apariencia (Tamaño del texto y Mascota), Permisos y seguridad (3 radios) y Motores (Estado:
  <motor>).
