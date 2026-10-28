# Estado: lote de la mascota 0.4.0 (t-lote-mascota-040)

Junta **t-mascota-estados** (spec 21) y **t-mascota-memoria-minima**
(spec 22). Rama `Claude`, 28 oct 2026. **LISTO**, con las FALTA de abajo.

## Parte 1: los 4 estados (t-mascota-estados)
Cada estado es **un fotograma de postura** que se queda hasta que el estado
cambia: sin animaciones largas y sin sonido. Lo decide `mascota_estado()`
dentro del bucle de la mascota, por prioridad: el fallo (un momento) > sin
internet > proxy caído > esperando aprobación.

| Estado | Condición real | Postura | Aviso |
|---|---|---|---|
| Proxy caído | fila «proxy» del mapa en rojo, o `_IPX["proxy_caido"]` | jersey → **impermeable amarillo**, algo encogida | **1 toast por caída**: «Se cayó el proxy. Trabajo con el modelo local.» |
| Sin internet | fila «internet» en rojo | **dormida de lado** con una manta y «z» | ninguno (lo dice la barra de estado) |
| Esperando aprobación | hay tareas retenidas (`tareas_en_espera`, el mismo dato de la bandeja) | **«te toca»**: distintivo de una mano levantada | ninguna palabra |
| Tarea fallida | `_after_run` termina en `fallida` → `mascota_evento("fallo")` | **baja la cabeza una vez** (2,5 s) y vuelve al reposo | ninguno (el reporte vive en la fila) |

Las posturas se **derivan** con PIL de los fotogramas reales
(`mascota_posturas_pil`). El **arte definitivo es FALTA**: no hay en
`mascot/` fotogramas de esas posturas (el saludo no tiene ninguno con una sola
mano en alto).

### Las 6 reglas anti-molestia (en el código, con su prueba)
| # | Regla | Cómo | Prueba |
|---|---|---|---|
| 1 | Máximo una intervención por evento | `mascota_evento` registra cada evento; el toast del proxy sale una vez por caída | La misma caída dos veces → **1 toast**; el mismo fallo otra vez → `False` |
| 2 | Nunca un pop-up no pedido | **Clic = saludo corto, no abre la cajita** (antes la abría). Si acaba de saludar, nada. La cajita solo desde el menú | 2 clics reales → **0 cajitas abiertas** |
| 3 | Nunca dos veces seguidas lo mismo | `mascota_decir`: lo mismo otra vez → variante corta o silencio | «¡Listo!», (silencio), «Hecho.», (silencio) |
| 4 | Lo malo no se celebra ni se dramatiza | Fallo = cabeza baja 2,5 s y vuelta al reposo; proxy = impermeable | 3 s después del fallo: **reposo** |
| 5 | Todo estado tiene salida | Menú **«Descansar 1 hora»** (apaga estados y celebraciones); las animaciones terminan solas | Con el proxy caído y «Descansar» → estado **ninguno** |
| 6 | La mascota no es el sistema de notificaciones | El menú solo trae Escribirle, Abrir, Buscar, Descansar, ¿Te molestó?, Ocultar: **ningún «Reintentar» ni «Pasar al local»** | Menú leído en la prueba |

### Validación preparada
Menú **«¿Te molestó la mascota?»** (Sí / No) → se apunta en
`mascota-validacion.jsonl`, con la fecha de inicio de la prueba
(`validacion_desde` en la memoria, desde el primer arranque con la mascota).
**FALTA la semana de uso real.** El procedimiento: usar la app 7 días con los
estados y luego contestar en el menú. Si sale «Sí» una sola vez, se recortan
estados (se apaga el estado que molestó).

## Parte 2: memoria mínima (t-mascota-memoria-minima)
- **No repetir** (`mascota_decir`): ver la regla 3.
- **No celebrar lo rutinario** (`mascota_tarea_aprobada`, desde
  `_celebrate_milestone`): solo la **primera tarea del día** y los hitos reales
  (7 días seguidos, cada 100 tareas), una vez cada uno. Ya no se celebran la
  1, 10, 25 y 50.
- **Clic = saludo:** ver la regla 2.
- **En disco:** `mascota-memoria.json` junto a la app (JSON legible: lo último
  dicho, lo último celebrado, días con tarea, hitos, descansar, inicio de la
  validación). Se puede borrar a mano. Está en `.gitignore`.

## Verificación (app real en 8797 con la mascota visible; `pruebas/prueba_mascota.py` → `pruebas/evidencia/mascota/`)
- **(a) Los estados con su condición real:**
  - **proxy caído**, de verdad: el proxy apunta a un puerto cerrado y el mapa
    lo midió: «El proxy no responde: rechaza la conexión…»;
  - **esperando**, una tarea real retenida: «Borra los archivos…» con
    permisos «siempre» → `t-borrar` en espera;
  - **fallo**, una tarea real por el runner con un motor que sale con error;
  - **sin internet**, simulado en el mapa (no se puede cortar internet del PC).
  - Capturas de la mascota en pantalla: `capturas-estados.png` (reposo,
    impermeable, dormida, «te toca», cabeza baja). Posturas aisladas:
    `posturas.png`.
- **(b)** Las 6 reglas, ver la tabla.
- **Memoria:**
  - (a) no repite;
  - (b) primera del día «primera tarea del día», la segunda `None`;
  - (c) clic = saludo, 0 cajitas;
  - (d) **tras «reiniciar»** (otra carga del módulo sobre la misma carpeta):
    no vuelve a celebrar hoy y no repite «¡Listo!».
- Log sin tracebacks.

## FALTA
- **Arte definitivo de las 4 posturas** (hoy son derivadas con PIL).
- **La semana de validación real** (procedimiento escrito arriba).
- Las capturas tienen detrás el escritorio real (texto de otra ventana): la
  mascota es transparente fuera de su figura.
