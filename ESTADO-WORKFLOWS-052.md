# ESTADO — t-workflows-052 (0.5.2, componente 3 de 5: workflows reutilizables)

**Fecha:** 30 oct 2026, 22:30. **Veredicto:** LISTO. 8 de 8 casos pasan en la instancia aislada (`%USERPROFILE%\growi-bridge\_prueba-workflows-052\`), con el `growi-bridge.py` de este commit. La app instalada no se tocó.

## Qué es
`workflows\<id>.json` junto a `growi-bridge.py`: parámetros, motor, `al_fallar` y pasos (`id`, `prompt`, `depende_de`, `criterios`, `motor`, `acciones`, `revisar`, `al_fallar`, `titulo`). «Ejecutar» lo compila a un plan con fases del motor de planes de siempre (`encolar_workflow()`, escritura atómica y exclusiva en `runner-tasks\`). No hay un segundo ejecutor. Formato y uso: `LEEME-growi-bridge.md`, sección «Workflows reutilizables». Ejemplos: `workflows/resumen-reunion.json`, `workflows/pipeline-video.json`.

## LISTO (evidencia: `pruebas/evidencia/workflows-052/resultado.json` y `growi-bridge-aislada.log`; prueba: `pruebas/prueba_workflows_052.py`)
| Criterio | Caso | Resultado |
|---|---|---|
| `wf_validar` rechaza antes de ejecutar | a | Rechaza, con su motivo: ciclo, dependencia que no existe, `{x}` sin declarar, `{resultado:p}` de un paso no anterior, motor que no existe, id raro, sin pasos, JSON roto. Si falta un parámetro, no se encola nada («falta: ¿Qué archivo?»). |
| Orden y `{resultado:p}` | d | 3 ejecuciones reales con Haiku. Cada paso empieza después de que termina el anterior. `tres.txt` = `rojo / verde / VERDE-n`: el archivo pasa de un paso al siguiente y `{resultado:verde}` llega relleno. |
| Costo estimado | b, d | Sale del historial del mismo paso (suma de medianas, rango de extremos), avisa si es otra versión de los pasos y cae a tareas parecidas o al estimado grueso. codex/agy: «$0 extra»; locales: «$0 local». |
| Umbral por plan | f | Si el peor caso pasa el umbral, Ejecutar no encola y ofrece «Ejecutar igual». |
| 3 ejecuciones de 3 pasos con Haiku | d | 1.ª: estimado grueso $0.004 contra $0.044 real (**+964 %**). 2.ª: «basado en 1 ejecución previa», $0.044 contra $0.046 (**+3 %**). 3.ª: «basado en 2 ejecuciones previas», $0.045 contra $0.047 (**+4 %**). Todo en equivalente Max: $0 real (suscripción). |
| Guardrail paso a paso y fallo a mitad | e | Con guardrail «siempre», el paso 1 (codex) queda retenido en `esperando_aprobacion` y el 2 no arranca. Al aprobarlo, termina y escribe su archivo. El paso 2 (gemini, desactivado) falla con `pedir_decision`: el plan queda en `necesita_decision` y el 3.º nunca se encola. |
| Guardar como workflow, tarjeta, gateway | b, c, f | «Guardar como workflow» escribe un workflow válido desde un plan, sin pisar archivos. La tarjeta funciona con CustomTkinter y con Tk clásico. `/gateway/workflows` responde 200 con token y 401 sin él. |
| Sin ventanas ni foco | todos | Las tareas se lanzan ocultas (`CREATE_NO_WINDOW`); la prueba anula `messagebox`. |

## Corrección antes de este commit
La primera corrida (16:11) falló en d y e: los pasos no podían escribir archivos («Claude requested permissions to write … but you haven't granted it yet», según el transcript de Claude Code). Las fases salían sin `allowed_tools` ni `permission_mode`. `_wf_permisos()` les da los mismos permisos que «Pedirle algo» (Read, Write, Edit, Bash + acceptEdits, según lo que diga el descriptor de cada motor). Ese arreglo se escribió a las 16:25, **después** de aquella corrida, y no se había vuelto a probar. Corrida de verificación: 22:07–22:25, todo OK.

## FALTA
- **App instalada sin este componente.** El `growi-bridge.py` instalado solo lleva el multimotor. Para activarlo hay que copiar el del repo (con `.bak`) y reiniciar la app; eso lo hace Leandro, porque reiniciar corta el runner.
- **Error del estimado sin historial:** el estimado grueso por tokens se quedó en una décima parte del real (+964 %). Con historial cae a ±5 %. Si se quiere un primer estimado mejor, hay que calibrar la cuenta por tokens con los costos reales de Haiku (no se hizo).
- `pipeline-video` necesita las skills de vídeo (`edicion-video`), que están en el repo. No se ejecutó de punta a punta: cuesta tiempo de render.

## COMO PROBARLO
```
set PYTHONIOENCODING=utf-8
python pruebas\prueba_workflows_052.py     # ~15 min; usa Haiku y Codex (suscripción, $0 real)
```
En la app (tras instalar este `growi-bridge.py` y reiniciar): Tareas → tablero de agentes → tarjeta «Workflows» → «Resumen de reunión» → Ejecutar.
