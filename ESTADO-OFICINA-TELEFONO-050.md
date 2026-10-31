# ESTADO — t-oficina-telefono-050 (Oficina 0.5.0, spec 12 de 18)

**Fecha:** 30 oct 2026, 23:15. **Veredicto:** LISTO las 6 subfunciones, verificadas contra un runner real en instancias aisladas (motor ollama, $0). La app instalada no se tocó.

## Dónde está
- `oficina/telefono/telefono.py`: `clasificar()` por reglas, `resumen_cola()` y la clase `Telefono` (máximo 1 en espera, una confirmación por mensaje, aviso a los 3 s).
- Prototipo: `oficina/protocolo/oficina_proto.py`. El campo «Pedirle algo» del spec 5 es ahora el teléfono. Parche reproducible: `parches/parche_oficina_telefono_050.py`, comprobado aplicándolo al archivo del commit anterior (sale idéntico).
- Pruebas: `pruebas/oficina_telefono_050/prueba_telefono.py` (lógica + runner real) y `demo_telefono.py` (ventana y teclas).

## LISTO (evidencia en `pruebas/evidencia/oficina-telefono-050/`)
| # | Subfunción | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | El teléfono como UI | `a-telefono-cerrado.png`, `a-telefono-abierto-escribiendo.png` | Icono fijo abajo a la derecha y tecla **T**. Una sola línea con «Enviar», sin historial ni lista de mensajes. Muestra el guardrail actual (de cola-live) y el motor sugerido (el del último encargo; Claude por defecto). Sin Bridge, el encargo queda como borrador «pendiente de enviar» (solo se lista lo pendiente, nunca un historial). **Corregido en la prueba:** la T que abre el teléfono también se escribía en el campo («tPídele…»). Ahora se descarta. |
| 2 / b | Animación de leer honesta | `b-growi-leyendo.png`, `b-respuesta-con-id.png`, `resultado.json` | Growi pasa a «al teléfono» con «…» desde el envío hasta que la tarea existe: `.task.json` a los 0,01–0,07 s y fila en cola.db a los 3,1–8,0 s (la apunta el runner al recogerla). A los 3 s sin nada, aparece «Dame un momento, estoy revisando.». Lo más que estuvo sin nada visible fueron **3,0 s** (nunca 5). Si falla, cuelga con el error real. |
| 3 / c | Clasificación por reglas | `resultado.json` (`c_clasificacion`) | 7 de 7 casos, sin modelo: pregunta («¿cómo va la cola?» → resumen hablado desde cola-live), tarea, corrección («Corrige lo de Codex…» → «le paso tu corrección a Codex»), aprobación, fuera de la oficina (2). |
| 4 / d | La tarea se crea como la app | `resultado.json` (`d_retenida`, `b_en_cola`) | Va por `oficina/encolar/encolar.py` → `encolar_tarea()`. Con guardrail «siempre», «borra el archivo viejo.txt» queda retenida (R2) y el teléfono dice «t-20261030-230512 queda por aprobar: apruébala en la app». Una sin retención: «t-20261030-230520 en curso». **Corregido en la prueba:** el teléfono confirmaba con el primer estado registrado («en_cola»), medio segundo antes de que el runner aplicara el guardrail. Ahora espera hasta 3 s a que el runner decida. |
| 5 / e | Una confirmación por mensaje | `resultado.json` (`e_cola_de_uno`) | 3 mensajes seguidos: el 1.º se lee, el 2.º espera y el 3.º no cabe («lleno»). 2 confirmaciones para 2 mensajes. «Dame un momento» no cuenta como confirmación. |
| 6 / f | Lo que no es el teléfono | `resultado.json` (`f_fuera`, `no_aprueba`) | «¿Quién ganó el partido anoche?» → «Eso no es de la oficina.». «¿Qué hora es?» → «Son las 23:05.». «Sí, apruébalo» → «Aprobar es en la app (Tareas) o por WhatsApp con su código; desde la oficina no.». |

## Decisiones
- **Campo `canal` (FALTA 4 del spec 4):** las tareas del teléfono van **sin** `canal`, así que el runner las trata como de la app. Un R3 se aparca esperando aprobación en la app. Con `canal: "oficina"` se denegaría al instante (todo canal distinto de `app` cuenta como remoto). Nada se aprueba desde la oficina.
- **Pregunta que necesita razonar:** hoy no se llama a ningún modelo. El teléfono responde con el resumen de la cola y lo demás lo trata como tarea o «fuera». El spec permite una llamada al modelo; queda sin implementar a propósito (coste y latencia). FALTA menor.
- **Corrección:** se encola como tarea nueva para ese departamento, con el mismo `encolar_tarea`. No se enlaza con la tarea anterior (`tarea_padre`), porque el teléfono no sabe cuál era sin preguntar.

## FALTA
1. Prueba contra la app instalada (requiere instalar el `growi-bridge.py` del repo y reiniciar: lo hace Leandro).
2. El gerente no «camina ni señala» hacia el departamento al pasar una corrección: eso es del paseo y el pathfinding (spec 14). Hoy solo sale el bocadillo.
3. Sin llamada al modelo para preguntas que necesitan razonar (ver Decisiones).

## COMO PROBARLO
```
python pruebas\oficina_telefono_050\prueba_telefono.py   # clasificación + runner real (~1 min, $0)
python pruebas\oficina_telefono_050\demo_telefono.py     # ventana: T, escribir, Enter, bocadillo con id
```
