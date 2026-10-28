# ESTADO — La mascota no tapa el ✕ del detalle (t-mascota-solape-045, P1 de escritorio)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_mascota_solape.py <dpi>`. Es **oculta**.
  - Sin ventana visible no hay coordenadas de pantalla reales, así que la prueba mide la **lógica** con la
    **geometría real**:
    - la mascota donde la pone la app (`_mascot_pos`: esquina inferior derecha de esta pantalla de 1920×1080);
    - el ✕ del detalle con la ventana maximizada, en 4 alturas de scroll: arriba, medio, abajo y la del hallazgo
      (justo debajo de la mascota).
  - La ventana de la mascota es un registrador de `withdraw` y `deiconify`.
- Evidencia: `pruebas/evidencia/mascota-solape/evidencia-100-ctk.json` y `evidencia-150-ctk.json`.

## LISTO
1. **Reproducido (por geometría).** Con la ventana maximizada, el ✕ del detalle (#10: cabecera, a la derecha) cae
   dentro del rectángulo de la mascota en dos alturas de scroll: «abajo» (y=940) y la del hallazgo (y=980), a
   100 %. La mascota es otra ventana, encima de todo, en esa esquina.
2. **Arreglo en escritorio.** Se eligió la vía que menos toca la mascota (`mascota_solape_paso`, cada 250 ms):
   - mientras el detalle está abierto **y** su ✕ cae debajo de la mascota (con 6 px de aire), la ventana de la
     mascota se **aparta** (`withdraw`);
   - **vuelve sola** (`deiconify` y encima de todo) en cuanto deja de taparlo, o al cerrar el detalle;
   - en las demás posiciones no se toca.
   - Se descartó reservar el hueco en la página: la mascota está en la esquina de la **pantalla**, no de la
     ventana, y ningún margen dentro de la ventana lo evita en todos los tamaños y scrolls.
3. **Sin tocar la mascota por dentro.** Sigue en Tk clásico con su color mágico. No se llama a `hide_mascot` ni se
   escribe `settings.json`. Su posición, sus estados (t-mascota-estados), su arrastre y su interruptor (#5 y
   Ajustes) no cambian. Si la apagas con su interruptor, el vigilante no hace nada.
4. **Nada de móvil.** Ningún cambio, prueba ni captura de móvil.
5. **Verificación por scroll.** Las 4 posiciones, a 100 % y a 150 % (tabla).

## Evidencia
| Criterio | 100 % (mascota en 1772-1900 × 932-1060) | 150 % (mascota en 1698-1890 × 858-1050) |
|---|---|---|
| arriba | ✕ en y=160: no toca, mascota en su sitio | y=240: no toca |
| medio | y=540: no toca | y=540: no toca |
| abajo | y=940: **toca → `withdraw`** | y=870: **toca → `withdraw`** |
| hallazgo | y=980: toca → sigue apartada | y=930: toca → sigue apartada |
| (b) ✕ pulsable en todas | `cerrar_tapado: false` en las 4 → `b_pulsable_en_todas: true` | igual |
| (d) cerrar y reabrir | ✕ de verdad: selección vacía → `deiconify` + `topmost` (vuelve); reabrir → `withdraw` otra vez | igual |
| (c) fuera del detalle | visible; `mascot` en settings sin cambiar (false → false); sin ventana (apagada) el vigilante no hace nada | igual |
| Log | «mascota: apartada mientras tapa el ✕ del detalle de Tareas (vuelve sola)» / «mascota: de vuelta en su sitio» | igual |
| Tracebacks | 0 | 0 |

## FALTA
- **(a) Captura del antes y (f) capturas del después: no se tomaron.** Leandro pidió no abrir ventanas mientras usa
  el PC, y la mascota y el ✕ solo existen en pantalla con la app visible. El solape y el arreglo se comprobaron por
  geometría (tabla). Para las capturas, cuando Leandro quiera: abrir la app, maximizarla, Tareas → elegir una
  tarea, bajar hasta que el detalle quede en la esquina inferior derecha: la mascota se aparta y vuelve al subir.
- El vigilante mira cada 250 ms: durante un scroll rápido, el ✕ puede quedar tapado como mucho ese cuarto de
  segundo.

## CÓMO PROBARLO
- `python pruebas/prueba_mascota_solape.py 100` (y `150`).
- En la app (visible): lo de arriba. El log dice cuándo se aparta y cuándo vuelve.
