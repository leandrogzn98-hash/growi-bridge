# ESTADO — t-oficina-estados-050 (Oficina 0.5.0, spec 8 de 18)

**Fecha:** 30 oct 2026, 23:10. **Veredicto:** LISTO las 8 subfunciones. Hay una FALTA de fuente: la tabla original de §3.4 no está en este PC, así que las T1–T21 están reconstruidas. La app instalada no se tocó.

## Dónde está
- `oficina/estados/estados.py`:
  - `derivar_estado()` pura, `EstadoTarea` (nivel 1) y la tabla `TRANSICIONES` (T1–T24)
  - `PROHIBIDAS`, `transicion()`, `Memoria`, `comprobar_serie()` y `asignar()`
  - `actividad_sin_tarea()` y `gerente_rutina()`
- `oficina/estados/simulador.py`: las 24 transiciones, las prohibidas, los umbrales y dormir. 54 casos.
- Prototipo: `oficina/protocolo/oficina_proto.py` deriva ahora con `estados.py`. El parche es `parches/parche_oficina_estados_050.py`. `P.derivar` queda solo para «sin instalar», que es del spec 11.
- Copias de trabajo en `%USERPROFILE%\growi-bridge\share\inbox\oficina\{estados,protocolo}\`.

## LISTO (evidencia en `pruebas/evidencia/oficina-estados-050/`)
| # | Subfunción | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | `derivar_estado()` pura, orden de §3.3 | `estados.py`, `simulador.json` | La primera regla que casa, gana: sin señal → sin tarea / dormir → esperando aprobación → terminado / fallido (60 s) → en pausa → en revisión → en ronda → trabajando → en cola. Si nada casa: sin señal («las fuentes no coinciden»). No lee archivos ni tiene efectos. |
| 2 / b | 24 transiciones y prohibidas | `simulador.json` | T1–T24 probadas una por una. Prohibidas: esperando → trabajando sin aprobación registrada, o «aprobando» en el chat, da sin señal + registro `fuera_de_tabla`; hablar con el agente o cambiar el guardrail deja la tarea retenida; sin tarea + runner-live de una tarea que no está en la cola sigue sin tarea; fallido → trabajando con la misma tarea da sin señal; dos agentes trabajando a la vez lo marca `comprobar_serie`. T16 exige un evento «aprobada» con `canal` app o WhatsApp en `aprobaciones-registro.jsonl` (el registro real trae `canal: "app"`). |
| 3 / c | Umbrales | `estados.py` (constantes comentadas), casos «umbral» | runner-live > 15 s = señal perdida. runner-status > 120 s = latido muerto, **solo si no hay runner-live fresco** (probado: status de 200 s con live de 4 s sigue «trabajando»). cola-live > 60 s = vieja. Terminado / fallido se ven 60 s. Contrastado con el runner real: cola-live se reescribe cada ≤ 10 s y runner-live cada ~5 s con tarea (corridas de `lote_live_repo` y `captura_revisando`). No hizo falta ajustar ninguno. |
| 4 / d | «Revisando» sin inventarlo | `captura-revisando.json`, `orquestacion-durante-revision.json` | **Medido** con el runner del repo (motor ollama + revisión real, $0). Durante la revisión, `.orquestacion.json` dice `"estado": "revisando"` (de 16,8 s a 23,0 s) y `runner-live.json` también, unos 2 s después. `cola.db` y `cola-live.json` siguen en `en_curso`: **duda 14 respondida**, la cola no tiene estado de revisión. Regla: en revisión si `.orquestacion.json` o `runner-live` (de esa tarea) dicen «revisando». Código: `_family_update(raiz, estado="revisando")` y `live_set("tarea", estado="revisando")`. |
| 5 / e | Dos niveles | `EstadoTarea` / `derivar_estado`, caso «niveles separados» | La tarea fallida se ve «falló» 60 s; después el empleado queda «sin tarea» y toma la siguiente (T20 + T2). |
| 6 / f | Sin tarea y gerente | `f-sin-tarea-3s.png`, casos de actividades | Sin tarea: respiro de 1 px, parpadeo, mirar el tablón, estirarse; nunca teclea (1200 muestras). Gerente: mira el tablón 4 s, ronda de 2,5 s por mesa y espera mirando el teléfono. Si algo espera aprobación, se queda junto al tablón (se ve en la captura, con Opus retenido). Con el Bridge caído: junto al teléfono, en gris. |
| 7 / g | Simulador verde | `simulador.json` | **54/54 OK** y cobertura de T1–T24 completa. |
| 8 / h | Dormir | `h-dormidos-11s.png`, `h-clic-despierta-16s.png`, `h-tarea-despierta-23s.png`, `demo-estados.json` | En el prototipo, con archivos coherentes de un Bridge falso y `--sueno-min 0.1` (DEMO, rotulado), 8 personajes se duermen (T22): 6 px más bajos, cabeza ladeada, ojos de dos rayitas, respiración de 1 px cada 4 s y **una sola** «Z» compartida que sube y se desvanece (sin sonido). Un clic en Luma la despierta (T24, `PostMessage` sin mover el ratón). Una tarea que el runner toma despierta a Hermes Directo (T23). El vigilante nunca duerme (Leandro tampoco: probado en el simulador). Dormido con su tarea en cola, sigue dormido: no la toma él. 0 transiciones fuera de tabla. |

Presupuesto §8 con la máquina de estados dentro (`presupuesto.json`): RAM 63 MiB (tope 350), CPU 0,43 % de media del PC (tope 2 %).

## Decisiones tomadas (para revisar cuando aparezca la investigación)
- **T1–T21 reconstruidas.** §3.4 no está en este PC. Salen de los estados y de las prohibiciones del spec. Las ids T1–T21 pueden no coincidir con la numeración original; T22–T24 sí son las del spec. Hay salidas dobles (T13: ronda → trabajando | revisión; T14: pausa → trabajando | en cola; T16: aprobada → trabajando | en cola).
- **Volver de «sin señal» no es una transición:** es re-derivar desde cero (`resync`), porque la oficina no sabe qué pasó mientras no veía.
- **Una tarea nueva reinicia al agente:** la comprobación pasa a ser «sin tarea → nuevo» (si no, cada sondeo que se salta un estado intermedio daría sin señal).
- **Dormido con tarea que aún no corre:** sigue dormido y lo despierta la toma del runner (T23 es dormir → trabajando, y el spec no admite otra transición nueva).
- **Runa y Growi** no se duermen mientras la cola tenga tareas vivas (despachar y orquestar la cola es su tarea). Su rutina se muestra como actividad, no como un estado inventado.
- **11 estados visibles** = sin señal, sin tarea, esperando aprobación, terminado, fallido, en pausa, en revisión, en ronda, trabajando, en cola (los 10) + dormir.

## FALTA
1. `INVESTIGACION-0.5.0-oficina.md` (§3) y `PALETA-Y-SKINS.md` (§14) no están en este PC: contrastar la tabla y la pose de dormir cuando aparezcan.
2. Turno de noche y vigilante (§9): `Memoria.despertar(…, por="vigilante")` existe y está probado, pero no hay reloj de noche ni ronda del vigilante. Es de los specs del vigilante y del ciclo de vida.
3. Especialistas (Blender, Tripo): todavía no reciben tarea, porque falta saber qué tarea usa qué skill (spec 11). Hoy solo pueden estar sin tarea o durmiendo.
4. Las etiquetas largas se cortan en el prototipo («sin tarea · junt…»). Es arte y layout de los specs 9–11.

## COMO PROBARLO
```
python oficina\estados\simulador.py                       # 54/54
python pruebas\oficina_estados_050\demo_estados.py        # prototipo: dormir, clic, tarea que despierta (25 s)
```
Captura real de «revisando»: `python pruebas\oficina_estados_050\captura_revisando.py`. Corre una tarea local de $0 en `_prueba-estados-050`.
