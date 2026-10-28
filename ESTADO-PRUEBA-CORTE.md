# ESTADO — Prueba de corte de luz (t-prueba-corte)

Rama `Claude`. Prueba del formulario: `pruebas/prueba_corte_ui.py` (app real en una copia, puerto 8797; **no
corta la luz**). Evidencia: `pruebas/evidencia/prueba-corte/` (`evidencia.json` + 2 capturas).

## LISTO
1. **Protocolo escrito**: `PROTOCOLO-PRUEBA-CORTE.md`. Dice qué se corta (la luz del PC entero), cuándo
   (una vez al mes, a mitad de una tarea de más de 5 min), cómo (breaker o desenchufar; nunca la app;
   si no es de verdad, «simulado») y qué se mide en los 8 puntos (tarea, descarga GGUF, sync, sesión de
   Claude Code, estado de la app, túnel, reloj, dos instancias). Para cada punto dice dónde mirar y qué
   cuenta como «sobrevivió», según lo que la app hace hoy. Se sigue sin el asistente. En la app:
   Ctrl+K → «Prueba de corte de luz», con resumen, «Abrir el protocolo completo» y «Abrir
   resiliencia.log». El protocolo viaja con las actualizaciones (archivo opcional de `UPDATE_FILES`).
2. **`resiliencia.log`** en la carpeta de Bridge: cabecera y una línea por prueba
   (`fecha | tipo | qué se cortó | qué se perdió | qué se reanudó solo | qué hubo que hacer a mano | notas`).
   Es acumulativo (solo se añade) y git lo ignora porque es de cada PC. El formulario no guarda una
   prueba «real» sin decir qué se cortó.
3. **Checklist de preparación**: en el protocolo y, en vivo, en la ventana. Mira si hay una tarea larga
   en curso, una descarga a medias (`models\*.part`), la pestaña abierta, el túnel y la hora del PC.
   Si no hay tarea larga lo dice, y «Registrar "sin prueba este mes"» deja la línea con un clic.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) protocolo | `PROTOCOLO-PRUEBA-CORTE.md` + ventana desde la paleta (`a_protocolo_en_la_app: true`) |
| (b) resiliencia.log | cabecera + «sin prueba» + una línea **marcada `simulado`** («SIMULADO en la prueba automática: no se cortó la luz»), en el log de la COPIA |
| (c) checklist | sin tarea en curso → «la prueba no se hace (regístralo como sin prueba este mes)»; túnel activo; hora del PC |
| Tracebacks | 0 |

## FALTA
- **(d) La primera prueba real NO está hecha.** El corte lo provoca Leandro, nunca el agente, y esta sesión
  corrió sin nadie delante. **Fecha propuesta: sábado 7 de noviembre de 2026, 10:00**, con una tarea
  larga en curso. Procedimiento listo en `PROTOCOLO-PRUEBA-CORTE.md`. No se simuló ningún corte para
  hacerlo pasar por real; la única línea «simulado» es de la prueba del formulario, en una copia.
- Dos puntos del protocolo que la app **todavía no cubre**:
  - el estado de la app (pestaña y tarea elegida) no se guarda en cada cambio, así que tras un corte
    abre en Estado;
  - el reloj no se compara con el VPS al arrancar, así que se mira a mano (`w32tm /query /status`).

  El protocolo los apunta para medirlos; arreglarlos es otro spec.

## COMO PROBARLO
`python pruebas/prueba_corte_ui.py` → `pruebas/evidencia/prueba-corte/`. En la app: Ctrl+K → «Prueba de corte».
