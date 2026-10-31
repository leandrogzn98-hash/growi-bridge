# ESTADO — t-oficina-vagancia-050 (Oficina 0.5.0, spec 15 de 18)

**Fecha:** 31 oct 2026, 01:20. **Veredicto:** LISTO las 9 subfunciones. Se verificó con un reloj simulado (horas de vagancia en segundos) y en el prototipo con el Bridge falso del spec 8. Los frames son BORRADOR (licencia).

## Dónde está
- `oficina/vagancia/vagancia.py`: reglas R1–R5 como código, `Oficina` / `Agente`, `ACTIVIDADES`, `EVENTOS_RAROS`, `prueba_de_fuego()`.
- `oficina/vagancia/frases.json`: catálogo cerrado y editable (24 de charla + 10 sueltas).
- Prototipo: `parches/parche_oficina_vagancia_050.py` (vagancia para los sin tarea, tecla **V** = oficina seria).
- Frames: `oficina/arte/generar_vagancia.py` → `skins/<id>/vagancia.png` + `.json`.
- Pruebas: `pruebas/oficina_vagancia_050/prueba_vagancia.py` y `demo_vagancia.py`.

## LISTO (evidencia en `pruebas/evidencia/oficina-vagancia-050/`)
| # | Subfunción | Resultado |
|---|---|---|
| a · R1 | `badge()` devuelve siempre el estado real. En el prototipo la etiqueta es «estado real · actividad» («sin tarea · café»). Un agente trabajando o esperando aprobación no hace vagancia. |
| a · R2 | Sonny a mitad de un café (le faltaban segundos para terminar): llega «trabajando» y la actividad se cancela en el acto, liberando la máquina. Se llama desde el mismo bucle que deriva los estados, sin sondeo aparte. |
| a · R3 | 10 min de vagancia con `socket.socket` sustituido para que falle al primer uso: **0 sockets**. El módulo no importa urllib, requests ni socket, y no escribe en la cola. Frases de una lista fija; decisión por aritmética y semilla. |
| a · R4 | Con `vagancia_activa = False` (tecla V en el prototipo, rotulado abajo), todas las actividades quedan en None: quietos, con su estado. |
| a · R5 | 7 agentes durante 4 h simuladas: el uso simultáneo máximo de cada punto nunca pasa su capacidad (café 2, ventana 2, baño 1, planta 1, pasillo 3). |
| b | Tick cada 5 s, con espera de 3–8 s antes del primero y elección ponderada entre las 3 mejores. Semilla `id + fecha`: dos sesiones de 3 h idénticas (`reproducible: true`). Cuatro necesidades con su caída por minuto y curva horaria (8–10 h café; 13–15 h café y distracción; desde las 17 h social y distracción). |
| c | 0 repeticiones seguidas por agente en 3 h. **Corregido en la prueba:** el comodín «pasear» se repetía cuando nada puntuaba. Ahora alterna con estirarse. |
| d | Las 8 actividades salen en 3 h simuladas: café 67, estirarse 166, ventana 108, charlar 78, celular 123, pelota 112, baño 48, pasear 205. A4 sin otro ocioso puntúa 0. **Corregido en la prueba:** «charlar» no salía nunca porque se exigía que el otro estuviera parado del todo; el spec pide «otro agente ocioso». En el prototipo, `h-dormidos-11s.png` muestra estirarse, pasear, pelota, charlar, baño, ventana y celular. Aplazadas A5, A7, A10 y A11, documentadas y sin hacer a medias. |
| e | Catálogo de 24 + 10 en `frases.json`, editable. Las 34 pasan la prueba de fuego. Las 5 trampas («ya terminé la tarea», «revisando lo de Codex», «van 3 de 5», «listo el informe», «¡ya acabé!») se detectan. **La prueba quitó «huele a café recién hecho»** («hecho» podría leerse como estado): ahora es «huele a café». Límite de 1 bocadillo por personaje cada 10 min y 1 por oficina cada 3 min; casi siempre «...». |
| f | Eventos raros en 40 h simuladas (log local `vagancia-raros.jsonl`): flor 27, bostezo 25, pájaro 25, café derramado 12, duelo de miradas 9. Cooldown mínimo de 1 h por evento. **El «todos disimulan» del gerente no existe en la v1.** |
| g | 30 frames: caminar con taza 4, servirse café 5, beber 3, estirarse 4, bostezar 3, ventana 2, gesticular 3, celular 2, pelota 2, fundido del baño 2. «Pasear» reutiliza «caminar». Hoja en `frames-vagancia-sonny-x4.png`. BORRADOR. |
| h | Con solo café + pasillo: ninguna actividad de baño ni ventana, y café sí. Nada se rompe. |
| i | Dormir no es vagancia: Sonny dormido 10 min no entra en el tick ni tiene actividades. Apagar la vagancia no lo toca. |

## FALTA
1. Las frases en registro venezolano suave no están validadas con Leandro (duda 31). Se cambian en `frases.json`.
2. Las probabilidades de los eventos raros son de diseño (duda 30). El log local sirve para calibrarlas la primera semana.
3. Los frames son borrador: retoque humano, y el celular girando la silla queda pendiente del arte final. El celular se dibuja con el sprite apartado del teclado.
4. La caminata real hacia el punto de interés (pathfinding del spec 14) no está conectada a la ventana del prototipo, que no tiene mundo ni cámara: la actividad se muestra como etiqueta. En el visor del paseo sí hay mundo; unirlos es del spec 18.

## COMO PROBARLO
```
python pruebas\oficina_vagancia_050\prueba_vagancia.py   # R1-R5, tick, 8 actividades, frases, raros, dormir (~1 min)
python pruebas\oficina_vagancia_050\demo_vagancia.py     # prototipo: vagancia de los ociosos; tecla V
```
