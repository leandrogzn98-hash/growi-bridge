# ESTADO — t-oficina-ciclo-vida-050 (Oficina 0.5.0, spec 18 de 18: cierra la fase)

**Fecha:** 31 oct 2026, 11:10. **Veredicto:** LISTO las 8 subfunciones, cada una verificada por separado en una copia aislada (`%USERPROFILE%\growi-bridge\_prueba-ciclo-vida\`). Toda la evidencia es posterior a la última edición del código (código ≤ 11:00:10; evidencia ≥ 11:04). La app instalada NO se tocó ni se reinició: está abierta y no lleva este código (ver COMO PROBARLO).

## Dónde está
- **App** (`growi-bridge.py`):
  - botón «Oficina · Abrir/Cerrar» en el pie de la barra lateral, encima de la mascota (`sb_oficina_btn`, `_oficina_ui()`); siguen Ctrl+Shift+O, Ctrl+K y la bandeja;
  - Ctrl+K → «Abrir la oficina en DEMO (sin agentes reales)»: `oficina_abrir(demo=True)`;
  - **Job Object** con KILL_ON_JOB_CLOSE (`_oficina_job`): la oficina se lanza suspendida, se mete en el job y se reanuda (`NtResumeProcess`). Así entra también el hijo que crea el `python.exe` lanzador de un venv. Si la app muere, aunque sea de golpe o al apagar el PC, Windows mata la oficina;
  - huérfanas: `_oficina_huerfana_limpiar()` al arrancar y antes de abrir. Si `oficina.pid.json` es de un Bridge muerto y el proceso es de verdad `oficina_proto.py` (psutil), lo cierra. Si es de un Bridge vivo, no lanza otra;
  - código 6 (cerrada por la escalera, falta de recursos): no se reabre sola. Solo con `"oficina_reabrir_con_recursos": true` en settings.json, la app mira cada 60 s y la reabre cuando la RAM en uso baja del 60 %. Por defecto: apagado;
  - gancho de prueba `GROWI_OFICINA_SIN_JOB` (para verificar el latido solo).
- **Oficina** (`oficina/protocolo/oficina_proto.py` + nuevo `oficina/ciclo/ciclo.py`):
  - `--demo`: fuentes simuladas en `datos\demo\outbox` (marcadas `_ejemplo` y `_demo`), nunca en el share del Bridge. Rótulo «DEMO — sin agentes reales» en el título de la ventana, en la cabecera, en una franja fija abajo (sale en cada captura) y en cada línea del log. No carga `encolar`, el teléfono descarta lo escrito (ni borrador) y los borradores van a `datos\demo\`. Si una fuente cualquiera trae `_ejemplo`, también se rotula y se bloquea el encolado;
  - faro (rojo/ámbar, parpadea) sobre la mesa de cada agente en `esperando_aprobacion`, banner ámbar con «Te necesitan: N» y los nombres, y la tecla **N**, que centra la cámara (zoom ×2, suave, 8 s; Esc vuelve) en el que espera y recorre a los demás en orden de llegada;
  - aprobación espacializada: el que espera camina a velocidad fija (90 px/s) a la mesa del gerente (2 puestos; el resto espera en su silla con su faro) y vuelve al resolverse. Se muestra una tarjeta con nivel, tarea, motivo, comando exacto (las `palabras` del pedido), encargo, estado y desde cuándo, y dónde se aprueba. **Sin botones.** Lee `outbox\aprobaciones\*.pedido.json` solo en lectura (`leer_pedidos`);
  - gerencia más ancha (200 px) para que quepan los que esperan; `--pulsar n@6` es un gancho de prueba.
- **Instalador**: `parches/instalar_oficina_050.py` (lo corre Leandro con la app cerrada; si la app de esa carpeta está abierta, sale sin tocar nada). Probado en una copia temporal.
- **Pruebas**: `pruebas/oficina_ciclo_vida_050/` (`prueba_ciclo_vida.py`, `host_app.py`, `prueba_boton.py`, `prueba_sin_aprobar.py`, `prueba_presupuesto.py`). **Evidencia**: `pruebas/evidencia/oficina-ciclo-vida-050/`.

## LISTO (evidencia en `pruebas/evidencia/oficina-ciclo-vida-050/`)
| # | Verificación | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | Abrir y cerrar desde la app 3 veces | `ciclo-vida-salida.json` → `a_abrir_cerrar_3`; `a-boton-salida.json` | Las 3: PID guardado = PID real, en Job Object, cierre «pidió cerrar» (código 4) en 0,87 / 0,64 / 0,67 s, 0 procesos y sin `oficina.pid.json` después. Botón de la barra lateral con la ventana real construida (`build_gui`): «Abrir» → pulsar → oficina viva y «Cerrar» → pulsar → «Abrir», cerrada. La captura de pantalla salió negra (esta sesión no puede capturar el escritorio): la prueba del botón es funcional, no visual. |
| 1 / b | Con una abierta, abrir otra vez | `b_segunda_instancia` | La 2.ª «app» no lanza nada («ya hay una abierta (pid …) de otro Bridge vivo»); los procesos son los mismos antes y después. Además sigue el mutex de la propia oficina (código 3, spec 5). |
| 2 / c | Al iniciar, NO se abre sola | `c_no_se_abre_sola` | Importar la app y correr lo que hace al arrancar (`_oficina_huerfana_limpiar`): 0 procesos de oficina. En `main()` solo se añadió esa limpieza; ningún camino llama a `oficina_abrir` sin una acción del usuario. Sin red: transporte por archivos, 0 puertos (DECISION-MOTOR). |
| 3 / d | La app muere | `d1_app_muerta_job`, `d2_app_colgada_latido`, `d3_sin_job_latido` | **d1** taskkill /F de la app: la oficina muere con ella en 0,68 s (Job Object). **d2** app colgada (suspendida: existe pero no late): «Bridge no disponible: el Bridge no responde: último latido hace 15 s» y autocierre a los 17,1 s de colgarse. **d3** sin Job Object y app muerta: «Bridge no disponible: el proceso del Bridge (pid …) ya no existe», cierre en 3,35 s. Sin restos en ninguno de los tres. |
| 4 / e | Cerrar la app con la oficina abierta | `e_salir_app` | `quit_app()` real: «cerrada al salir de la app», 0 procesos en 0,64 s. |
| 4 | Huérfana de una app anterior / falta de recursos | `s_huerfana_al_arrancar`, `r_falta_recursos` | Oficina viva con su Bridge muerto y el pid file presente: se limpia al arrancar en 0,51 s. Código 6: «cerrada por falta de recursos; no se reabre sola», nada programado y 0 procesos. |
| 5 / f | DEMO | `f_demo`, `f-demo-4s.png`, `f-demo-36s.png`, `demo-salida.txt` | Abierta desde la app en DEMO: todas las líneas del log de esa oficina llevan «[DEMO — sin agentes reales]», no carga `encolar` y la cola real queda igual (cola.db: no existía antes ni después; 0 encargos en runner-tasks). Rótulo visible arriba y en la franja de abajo de cada captura. |
| 6 / g | Faro + banner + N | `g-n-primero-46s.png`, `g-n-segundo-50s.png`, `g-camara-n-dos-esperando.txt`, `f-demo-36s.png` | Faro sobre la mesa vacía de Hermes Ollama y de Haiku, banner «Te necesitan: 2 · espera tu aprobación: Hermes Ollama, Haiku…». N centra en hermes_ollama y la 2.ª N en haiku (log). |
| 7 / h | Aprobación espacializada, sin aprobar en la oficina | `h-mesa-gerente-12s.png`, `h-sin-aprobar.json` | Hermes camina a la mesa del gerente y aparece su tarjeta: «R2 (con tu sí) · Comando: «borra las copias viejas de *.bak» · … Se aprueba en la app (Tareas) o por WhatsApp. Aquí no se aprueba ni se rechaza nada.» Comprobación estática del código de la oficina: 0 llamadas a aprobar o rechazar, 0 `sqlite3.connect`, 0 Allow/Deny, y `leer_pedidos` solo lee. |
| 8 | Cierre de la fase | este archivo | Abajo. |
| §8 | Presupuesto | `presupuesto-salida.json` | DEMO con 2 esperando, faro, paseo y la cámara N: RAM máx. 48,8 MiB (tope 350); CPU 0,39 % de media del equipo (máx. 0,88 %); 6,2 % de un núcleo. VRAM 0 (Pygame-ce pinta por software, spec 1). Ojo: el PC estaba con RAM > 80 % y la escalera bajó al nivel 2. |

**Sin auto-denegación en la oficina:** la oficina no tiene temporizador ni deniega nada. El vencimiento del pedido («Si no respondes, NO se hace») es una política de la app (`riesgos.json`, 0.3.0/0.4.0) que ya existía: no se tocó ni se revirtió. Cambiarla es decisión del dueño, no de este spec.

## FALTA (de este spec)
1. **Prueba contra la app instalada**: no se hizo, para no reiniciarla (está abierta). Pasos en COMO PROBARLO.
2. **«.exe versionado» e instalador**: la oficina sigue siendo `oficina_proto.py` + Pygame-ce del venv de mediciones. No hay PyInstaller ni un export de Godot (DECISION-MOTOR fijó Godot, pero la escena Godot no existe). Lo que se entrega es el instalador por script (`parches/instalar_oficina_050.py`), sin auto-update ni descargas.
3. **«Cierre del sistema»** no se probó apagando el PC. Está cubierto por el mismo mecanismo que d1 (el job se cierra al morir la app), pero no hay evidencia de un apagado real.
4. **Reapertura por recursos**: mide solo RAM (la app no mide VRAM). Viene apagada por defecto y no se probó la reapertura en sí, solo que sin configurarla no reabre.
5. **«Centrar la cámara»**: el prototipo cabe entero en la ventana, así que N hace zoom ×2 centrado en el agente. En la escena final con mundo más grande, el mismo `Camara.recorte` sirve para desplazar.
6. **Captura del botón**: negra desde esta sesión. Falta ver el botón con los ojos en la app real.

## Cierre de la 0.5.0: los 17 specs anteriores
Todos dejaron ESTADO. Repo: `ESTADO-OFICINA-*-050.md` (15). Specs 2 y 3: `share\inbox\growi-bridge-app\ESTADO-t-oficina-cola-live-050.md` y `…consumo-vivo-050.md`.

| # | Spec | FALTA abierta (resumen; detalle en su ESTADO) |
|---|---|---|
| 1 | mediciones | GPU integrada no probada; CPU ≤2 % se cumple sobre el equipo, no sobre un núcleo; sin sesión larga (throttling). |
| 2 | cola-live | Su ESTADO original dice «nada verificado» (falló por PATH: `pedido-revision-t-lote-live-050.json`). Integrado y verificado después en el repo (657b493). Falta medir §8 aparte y el reinicio real. |
| 3 | consumo-vivo | Sin sección FALTA. Integrado con el 2 (657b493). |
| 4 | encolar-externa | Sin prueba contra el runner instalado; guardrail real «nunca» (un R2 se ejecutaría sin preguntar); campo `canal` sin decidir; diferencias del encolado externo (fallback local, etiqueta del motor). |
| 5 | protocolo | Prueba contra la app instalada; colores provisionales; Pygame-ce no está en el Python del Bridge. |
| 6 | motor | Sin `export_presets.cfg` ni icono (quedaba para el 18: sigue abierto, ver FALTA 2). |
| 7 | plano | Depto de Diseño no añadido; colores provisionales. |
| 8 | estados | T1–T21 reconstruidas (falta la tabla original §3.4); sin reloj de noche ni ronda del vigilante; especialistas sin tarea. |
| 9 | arte-base | Paleta de 24 incompleta (falta PALETA-Y-SKINS §1); retoque humano (licencia); `.pxo`; Pixelorama no instalado. |
| 10 | skins | Retoque humano; colores provisionales; defectos de arte anotados; compositor solo en Pillow. |
| 11 | empleados | Arte final; sillas de visita; color del vigilante (lo decide Leandro). |
| 12 | teléfono | Prueba contra la app instalada; sin modelo para preguntas que razonan. |
| 13 | llamadas | Cambios del runner (urgente, lanzado_at) solo en el repo; animación del auricular (arte). |
| 14 | paseo | El paseo no está dentro de la ventana de la oficina (visor aparte); sin modo «corregir». |
| 15 | vagancia | Frases sin validar con Leandro; probabilidades de diseño; la caminata al punto de interés no está conectada. |
| 16 | bocadillos | Cola de avisos compartida oficina↔app (no existe); botón «Historial de la oficina» en la app; bocadillo multilínea. |
| 17 | rendimiento | CPU en reposo > 2 % de un núcleo; RAM minimizada 62 MB (> 50); cesión por VRAM con un modelo real sin provocar; sin instalador. |

**Comunes a toda la fase:** `INVESTIGACION-0.5.0-oficina.md` y `PALETA-Y-SKINS.md` no están en este PC (todo se construyó desde los specs); el arte es BORRADOR; nada de la 0.5.0 está instalado en la app de Leandro (hace falta el `growi-bridge.py` del repo y un reinicio).

**Lo que entrega la 0.5.0:** la oficina como proceso aparte que observa al Bridge por archivos (cola-live, runner-live, runner-status, latido), con estados derivados honestos («sin señal», «—»), teléfono al gerente y llamadas reales, encolado por la misma función de la app, vagancia y sueño honestos, bocadillos con log diario, escalera de rendimiento, y ahora el ciclo de vida completo desde la app: botón, sin huérfanos, DEMO rotulado, faro + N y aprobación espacializada sin aprobar desde la oficina. Lo que NO entrega: el motor final en Godot (es un prototipo Pygame-ce) ni el arte final.

**Fase 2 (fuera de la 0.5.0):** editor de layout, modo desktop pet, modo replay, tablero KPI, historial dueño↔agente y fantasmas para paralelizar (nunca como BagIdea). Preguntas por Telegram: no entra, porque el canal del dueño es WhatsApp.

## COMO PROBARLO
Aislado (no toca la instalación):
```
python pruebas\oficina_ciclo_vida_050\prueba_ciclo_vida.py   # a b c d1 d2 d3 e f r s -> ciclo-vida-salida.json
python pruebas\oficina_ciclo_vida_050\prueba_boton.py        # boton de la barra lateral
python pruebas\oficina_ciclo_vida_050\prueba_sin_aprobar.py  # h (estatico)
python pruebas\oficina_ciclo_vida_050\prueba_presupuesto.py  # RAM/CPU con DEMO
```
En la app de Leandro (hay que cerrarla y abrirla):
1. Cerrar Growi Bridge (bandeja → Salir).
2. `python parches\instalar_oficina_050.py`. Copia `growi-bridge.py` y `share\inbox\oficina\` con `.bak` y, si hace falta, fija `oficina_pygame_dir`. Nota: el `growi-bridge.py` del repo trae también todo lo pendiente de instalar de la rama Claude (specs 5–17 de la 0.5.0 y 0.5.2).
3. Abrir la app. En la barra lateral, abajo: **Oficina → Abrir**. Se abre la ventana y el botón pasa a «Cerrar». Pulsarlo la cierra.
4. Ctrl+K → «Abrir la oficina en DEMO (sin agentes reales)» para enseñarla sin agentes: rótulo DEMO arriba y abajo; N lleva a quien espera aprobación.
5. Salir de la app con la oficina abierta: la oficina se cierra con ella.
6. Para deshacer: restaurar los `.pre-oficina-050-<fecha>.bak`.
