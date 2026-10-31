# ESTADO — t-oficina-protocolo-050 (Oficina 0.5.0, spec 5 de 18)

**Fecha:** 30 oct 2026, 22:20. **Veredicto:** LISTO las 6 subfunciones, verificadas por separado en instancias aisladas. La app instalada NO se tocó ni se reinició.

Prototipo Pygame-ce del protocolo por archivos: proceso aparte que lee los archivos del Bridge, deriva el estado de cada sprite y se cierra solo si el Bridge desaparece. No es la oficina final (cuadrados de color, no arte).

## Dónde está
- Prototipo: `oficina/protocolo/oficina_proto.py` (ventana, render, latido, borradores) y `oficina/protocolo/protocolo.py` (lectura segura, fuentes en hilos, `Latido`, `derivar()` provisional, `Borradores`). Copia de trabajo en `%USERPROFILE%\growi-bridge\share\inbox\oficina\protocolo\` (donde lo busca la app).
- App: `growi-bridge.py` del repo lleva el parche (`oficina_abrir / oficina_cerrar / oficina_alternar`, latido cada 5 s en `share\outbox\bridge-latido.json`, `oficina.pid.json`, Ctrl+Shift+O, Ctrl+K «Abrir o cerrar la oficina», menú de la bandeja, cierre al salir). Script del parche: `parches/parche_oficina_protocolo_050.py` (anclas exactas, conserva CRLF, hace `.bak`).
- Pygame-ce 2.5.8: del venv de las mediciones (`oficina/mediciones/.venv`), por `settings.json → oficina_pygame_dir`. El Python del Bridge no lo tiene instalado; no se instaló nada nuevo.

## LISTO (evidencia en `%USERPROFILE%\growi-bridge\_prueba-oficina-protocolo\evidencia\`)
| # | Subfunción | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | Prototipo, 16 sprites (14 personajes + Runa + vigilante; el roster viejo decía 15), 30 FPS, estado derivado | `a-ejemplo-6s.png`, `a-ejemplo-8s.png` | Corre con archivos de EJEMPLO (`_ejemplo: true`, la ventana lo rotula «DATOS DE EJEMPLO — no son del runner»). |
| 2 / b | Lectura segura: 3 reintentos de 100 ms, JSON a medias = «viejo», >200 ms = último valor bueno con su edad | `b-lento-medias-12s.png`, `cdef-salida.json` | Con archivos presentes, lecturas de 1–6 ms (p50), todas a tiempo. Ausentes: 200 ms (los 3 reintentos), sin congelar el render. |
| 3 / c | Latido y autocierre | `c-no-disponible.png`, `cdef-salida.json` | Bridge (pid) muerto: «Bridge no disponible», salida con código 2 a los 5,9 s de matarlo (3 s de aviso). Solo latido ausente (sin pid): salida a los 13,8 s del último latido (límite 15 s). Sin proceso huérfano en ninguno de los dos casos (`tasklist`). |
| 4 / d | «Sin señal» | `d-ausentes.png`, `d2-borrador-pendiente.png`, `d2-borrador-salida.json` | Sin archivos: los 16 en gris con «?», «sin señal»; ninguno «trabajando». Un encargo escrito sin Bridge queda en `borradores.json` como «pendiente de enviar», sobrevive a un cierre brusco, se ve en ámbar y no se envía. |
| 5 / e | Ciclo de vida desde la app, una sola instancia | `e2-ciclo-app-salida.json`, `cdef-salida.json` | Con el `growi-bridge.py` del repo parcheado: importar no abre la oficina; abrir lanza el subproceso y guarda el PID; una 2.ª apertura no lanza otra; cerrar = «pidió cerrar» por el latido, sale en 0,84 s con código 4, sin proceso ni PID file; si la oficina muere, la app sigue y lo anota. Mutex: una 2.ª oficina sale con código 3. |
| 6 / f | Informe de protocolo | este archivo + `cdef-salida.json` | Abajo. |

## Informe de protocolo (medido)
- Lecturas (3 corridas): `runner-live`, `cola-live` y `runner-status` presentes p50 1,3–3,5 ms, máx. 5,9 ms, 100 % a tiempo; ausentes 201–211 ms (3 intentos de 100 ms: es el coste esperado de «ausente»). `engines.json` p50 2–4 ms, máx. 16 ms. Carpeta de skills p50 8–26 ms. Latido p50 0,6–1,6 ms, máx. 15 ms, 100 % a tiempo.
- Render: 29–30 FPS en todas las corridas; peor fotograma 43–56 ms (el guardado de la captura y el arranque). Sin fotogramas >50 ms en la caída del Bridge.
- Ritmos aplicados: runner-live 2 s con tarea / 10 s sin ella, cola-live 5 s, runner-status 10 s, engines + skills 60 s, latido 1 s; con el Bridge caído todo pasa a 10 s y se sigue intentando.
- Presupuesto §8 (`g-presupuesto-salida.json`, 25 s a 30 FPS): RAM 60 MiB (tope 350), CPU 0,78 % de media del PC (máx. 1,27 %, tope 2 %). VRAM: `nvidia-smi` no da memoria por proceso en esta GPU (`[N/A]`); el spec 1 midió Pygame-ce con 0 VRAM (render por software de SDL).
- Para pasar a Godot: el protocolo no cambia (mismos archivos, mismos ritmos, mismo latido `{pid, t, cerrar}`, mismos códigos de salida). Hay que portar a GDScript `leer_json` (reintentos), `Latido.comprobar`, la comprobación del pid (en Godot: `OS.is_process_running`) y el mutex (en Godot: comprobar un puerto o un archivo de bloqueo, porque no hay mutex con nombre nativo). La lectura en hilos pasa a `Thread` o a `WorkerThreadPool`.

## Corrección hecha en este spec
- **Congelamiento de ~950 ms al caer el Bridge** (medido: fotograma de 953 ms, FPS 0 en ese segundo). Causa, vista con `faulthandler`: `texto()` recortaba los textos largos de 2 en 2 caracteres llamando a `font.size()` en cada paso y renderizaba todo en cada fotograma. Ahora recorta por búsqueda binaria y guarda las superficies ya renderizadas. Después: peor fotograma 43 ms. Copia previa: `oficina_proto.py.pre-texto-cache.bak`.
- Nota de proceso: la carpeta `ejemplos/` está vacía; los archivos de ejemplo válidos son los del `share\outbox` de la instancia aislada. La primera corrida de c los tomó de `ejemplos/` y midió «ausente» sin saberlo; se repitió con los buenos.

## FALTA
1. **Prueba contra la app instalada**: no se hizo, para no reiniciarla. El `growi-bridge.py` instalado no lleva el parche. Pasos abajo.
2. **`derivar()` es provisional**: solo da trabajando / en cola / sin tarea / sin señal / sin instalar. El definitivo, con las 24 transiciones, es el spec 8 (t-oficina-estados-050).
3. **Colores por departamento provisionales**: los hex de PALETA-Y-SKINS §2 no están en este PC.
4. **Fuentes ausentes**: `INVESTIGACION-0.5.0-oficina.md` y `PALETA-Y-SKINS.md` no están en este PC. Se trabajó con el spec, el índice y los ESTADO previos.
5. **Pygame-ce no está en el Python del Bridge**: se usa el del venv de mediciones. Para usarlo en otro PC: `python -m pip install pygame-ce==2.5.8` o fijar `oficina_pygame_dir`.
6. **Campo `canal` de las tareas de la oficina** (FALTA 4 del spec 4): sigue sin decidir. La oficina encola sin `canal` (la tratan como `app`). Lo decide el spec 12 (teléfono).

## COMO PROBARLO
Aislado (no toca la instalación), con los scripts del scratchpad copiados a `_prueba-oficina-protocolo\scripts\`:
```
python oficina_cdef.py        # c, c2, d, e, f -> evidencia\cdef-salida.json + capturas
python oficina_borrador.py    # d2: borrador «pendiente de enviar»
python oficina_ciclo.py       # e2: abrir / 2.ª apertura / cerrar / muerte de la oficina, con el repo parcheado
python oficina_presupuesto.py # RAM / CPU
```
Contra la app instalada (lo hace Leandro, la app tiene que cerrarse y abrirse):
1. Cerrar Growi Bridge. `python parches\parche_oficina_protocolo_050.py %USERPROFILE%\growi-bridge\growi-bridge.py` (hace `.pre-oficina-protocolo.bak`).
2. Abrir la app. Ctrl+Shift+O (o Ctrl+K → «Abrir o cerrar la oficina», o el menú de la bandeja): se abre la ventana de la oficina; Ctrl+Shift+O otra vez la cierra.
3. Salir de la app con la oficina abierta: la oficina se cierra sola.
4. Para deshacer: restaurar `growi-bridge.py.pre-oficina-protocolo.bak`.
