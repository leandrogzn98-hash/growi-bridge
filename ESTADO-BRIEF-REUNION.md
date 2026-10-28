# ESTADO — Brief de reunión (t-brief-reunion)

Rama `Claude`. Prueba: `pruebas/prueba_brief.py`. Usa una copia aislada con memoria propia de **líneas de
prueba**, marcadas así: no son las de Leandro. El calendario es un archivo iCal local, leído por la misma
función que lee la dirección secreta de Google Calendar. Evidencia: `pruebas/evidencia/brief/`
(`evidencia.json` + `brief-william.txt`).

## LISTO
1. **Brief de 30 segundos**: Ctrl+K → «brief para la reunión con William» (o «brief William») abre la tarjeta:
   - **Última vez**, con su fecha;
   - **Acordado**, **Pendiente** y **Cobro**, hasta 5 cada uno, lo más reciente primero;
   - las **tareas** del runner con esa persona y sus **eventos** del calendario;
   - una línea de **fuentes**: qué se miró y qué no.

   Es una tarjeta, no un documento. La clasificación es por palabras: «acord/confirm/quedamos» → acordado;
   «pendiente/falta/enviar» → pendiente; «$/cobr/pag/factur» → cobro. Sin IA.
2. **Solo fuentes que controla**: la memoria (MEMORY.md por secciones con fecha, y las notas diarias), las
   tareas del runner y su calendario de Google por la **dirección secreta iCal** (Ajustes → Datos →
   «Calendario… Conectar…»: solo lectura, sin OAuth ni correos). **Cada dato lleva su origen** (fuente y
   fecha); un dato sin fecha ni fuente **no entra**, y se dice cuántos quedaron fuera.
3. **Bajo demanda o 30 min antes**: a petición es inmediato. Un vigía (cada 5 min) mira los eventos que
   empiezan en 25-35 min; si el evento tiene persona (asistentes o «con X» en el título), deja su brief en
   `outbox\briefs\` y avisa, **una sola vez**. Sin persona, no hay brief.
4. **Nunca captura de pantalla, chats ni llamadas**: ninguna de esas fuentes existe en el código del brief, y
   la tarjeta lo dice («no_usadas: captura de pantalla, WhatsApp y llamadas: nunca»). Sin calendario, el
   brief lo dice y sigue con lo que hay.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) tarjeta | Última vez 2026-10-25 «William confirmó que paga el 1 de noviembre»; Acordado «3 anuncios por mes»; Pendiente «enviar el guion del anuncio 2»; Cobro «$150 por octubre»; Tareas «guion del anuncio 2 — aprobada» |
| (b) origen | `b_todos_con_origen: true` («[MEMORY.md (sección del 2026-10-20)]», «[nota diaria del 2026-10-25]», «[tareas del runner: …]»); la línea sin fecha («prefiere que le escriban por la mañana») **no entra**: «(1 dato(s) sin fecha ni fuente no entran)» |
| (c) 30 min antes | 2 eventos a +30 min: «Llamada con William» (con persona) → `brief-…-william.txt`; «Bloque de foco» (sin persona) → **nada**; la 2.ª vuelta no repite |
| (d) sin calendario | «calendario no conectado (pega la dirección secreta iCal…)»; el brief sale igual con memoria y tareas, sin inventar |
| paleta | «brief para la reunión con William» → «Brief para la reunión con William (30 s, con su origen)» |
| Tracebacks | 0 |

## FALTA
- **Con los datos reales de MEMORY.md**: esta prueba usa líneas de prueba. La memoria real vive en la app
  instalada, que no se toca. En la app: Ctrl+K → «brief para la reunión con William».
- **El calendario real de Google**: hay que pegar la dirección secreta iCal en Ajustes. Sin ella, el automático
  de 30 min no tiene eventos que mirar.
- La clasificación por palabras es simple: una línea puede caer en «acordado» cuando también es un cobro. El
  origen siempre se ve.

## COMO PROBARLO
`python pruebas/prueba_brief.py` → `pruebas/evidencia/brief/`. En la app: Ctrl+K → «brief para la reunión con …».
