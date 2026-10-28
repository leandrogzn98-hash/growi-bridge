# ESTADO — Matriz motor × permiso y avisos de la cola en Ajustes (t-ajustes-matriz-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_ajustes_matriz.py <dpi> [variante]`. Es **oculta**.
  - Siembra `politicas.json` con dos reglas reales: «No permitir nunca: escribir fuera» y «Preguntar siempre:
    leer».
  - Pone el guardrail en «delicado».
- Evidencia: `pruebas/evidencia/ajustes-matriz/evidencia-*.json`.

## LISTO
1. **Matriz motor × permiso.** Sección nueva en Ajustes, «Qué puede hacer cada motor» (tarjeta `CTkFrame` con
   esquinas 10).
   - Filas: los motores de `engines.json`. Columnas: 7 tipos de acción de `riesgos.json`, con su nivel: Leer R0,
     Escribir fuera R1, Gastar R2, Borrar R2, Publicar R2, Enviar R2 y Borrar en masa R3.
   - Cada celda dice **lo mismo que decidiría el runner**: `politica_decidir` sobre `politicas.json` y, si no hay
     regla, el guardrail (`pregunta_desde` con `_desde`). R3 se pregunta siempre.
   - Una regla tuya lleva «*». Un motor sin herramientas (`_cap(eng, "herramientas")`) muestra «—»: solo responde
     texto.
   - Las celdas usan símbolo y color (✓ sin preguntar, ? pregunta, ✕ nunca, — solo texto), con su leyenda debajo.
     Así caben a ventana mínima; el valor en palabras queda en la celda (`_valor`).
   - **No se creó ningún motor de políticas** ni se cambió qué puede hacer nadie: es presentación.
2. **De lectura.** Las celdas son etiquetas sin manejadores y sin foco. La leyenda dice dónde se cambia: arriba, en
   «Permisos y seguridad», y en «Reglas permanentes».
3. **Avisos de la cola.** Sección nueva, «Avisos de la cola», con tarea en espera, tarea fallida y tarea aprobada.
   - **La app no tiene ningún ajuste de notificaciones**, así que no hay ningún toggle.
   - Cada fila dice lo que pasa hoy de verdad:
     - en espera: ventana emergente y bandeja;
     - fallida: solo avisa si fallan 3 seguidas (la cola se pausa);
     - aprobada: no avisa.
   - A la derecha de cada fila: «**sin notificaciones configuradas**», como pide el spec. No se inventó un toggle
     que no hace nada.
4. **Aviso en línea.** Un motor sin su credencial (`acceso_motor`) lleva en su fila «Sin clave · pon tu clave en
   APIs para que pueda trabajar», en vez de huecos. Un motor desactivado lo dice igual.
5. **Respaldo, foco, arranque y DPI.**
   - En la clásica, la misma matriz y los mismos avisos van en tarjetas `tk.Frame`.
   - No hay toggles que enfocar: la sección es de lectura.

## Evidencia (100 % CTk; 150 % y las 3 de respaldo dan lo mismo)
| Criterio | Resultado |
|---|---|
| (a) permisos reales, 2 motores | Claude y Codex: Leer «Pregunta *» (tu regla ask), Escribir fuera «No *» (tu regla deny), Gastar, Borrar, Publicar y Enviar «Pregunta» (R2 con «delicado»), Borrar en masa «Pregunta» (R3). Calculado aparte con `politica_decidir` + `_desde` → **cuadra** en los dos. Llama y Ollama: «—» (sin herramientas) |
| (b) de lectura | celdas sin ningún manejador ni foco; tras «pulsarlas», `politicas.json` y el guardrail siguen iguales |
| (c) avisos | las 3 filas: «sin notificaciones configuradas»; 0 toggles en la sección |
| (d) sin clave | Meshy y Gemini: «Sin clave · pon tu clave en APIs para que pueda trabajar.» |
| (e) respaldo | `clasica`, `sinctk` y `flag`: tarjeta `Frame`, lo mismo; **0 tracebacks** |
| DPI, ventana al mínimo | la rejilla pide 465 px con 478 de contenido (100 %) y 678 con 717 (150 %) → cabe |
| arranque (`build_gui`, 100 %) | antes 15,9 / 14,6 s; después 14,2 / 14,1 s, igual |

## FALTA
- **(f) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro. Para tomarlas:
  `PRUEBA_VER=1 python pruebas/prueba_ajustes_matriz.py 100` (y `150`).
- Notificaciones configurables para la cola: no existen y el spec prohíbe inventarlas. Si Leandro las quiere, es
  otro spec.

## CÓMO PROBARLO
- `python pruebas/prueba_ajustes_matriz.py 100`, y `150`, `100 clasica`, `100 sinctk` y `100 flag`.
- En la app: Ajustes → «Qué puede hacer cada motor» y «Avisos de la cola», encima de la zona peligrosa.
