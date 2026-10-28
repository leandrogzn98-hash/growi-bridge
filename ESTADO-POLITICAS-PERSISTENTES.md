# ESTADO — Políticas persistentes (t-politicas-persistentes-030)

Rama `Claude`. Pruebas:
- `pruebas/prueba_politicas_runner.py`: runner real `_process_one_impl` con motor falso, que también intenta
  escribir `politicas.json` por su cuenta.
- `pruebas/prueba_politicas_gui.py`: app real en una copia, puerto 8797, editor usado con sus botones.

Evidencia en `pruebas/evidencia/politicas/`: `runner.json`, `evidencia.json` y 2 capturas.

## LISTO
1. **`politicas.json`** en la carpeta de Bridge, legible a mano. Cada regla tiene: `accion` (tipo de
   riesgos.json o `*`), `carpeta` (ruta o patrón `*`), `limite_usd`, `nivel` R0-R3, `decision`
   allow/ask/deny, y quién la creó y cuándo. Se evalúa por acción en orden **deny > ask > allow > nivel de
   permisos**. «Permitir siempre» solo vale para R0-R1: R2/R3 se preguntan siempre por acción exacta (el
   editor no lo deja guardar y el runner lo ignora). Como ejemplo inactivo va `politicas.ejemplo.json`
   (3 reglas reales: allow escribir en `share`, deny borrar en masa, ask escribir en OneDrive).
   `politicas.json` lo ignora git: es de cada PC.
2. **Editor**: Ajustes → Permisos y seguridad → «Reglas permanentes» → «Editar reglas», también en la
   paleta. Ventana CustomTkinter con respaldo clásico. Se elige Qué (lista en palabras), Dónde (carpeta,
   con «Elegir…»), Límite $ y Permitir / Preguntar / No permitir. Cada regla se muestra en una frase
   («Permitir siempre: escribir fuera de la carpeta de trabajo en … (R1)») con «Editar» y «Revocar»;
   revocar pide confirmación.
3. **Regla dura**: solo el usuario en la app escribe `politicas.json` (`politica_guardar_ui`).
   - Una tarea que pide cambiarlo se rechaza antes de empezar: fallida y definitiva, sin llamar al motor.
   - Si un motor lo cambia durante la tarea, al terminar se devuelve a como estaba.
   - Ambos casos quedan en el registro.
4. **Aprobación por paso**: cada acción sensible es un paso con su propio pedido y su `approval_id`. Se piden
   en orden y la tarea no corre hasta que todos están aprobados. Una ronda de corrección cuyo alcance
   cambia, o un efecto externo repetido, vuelve a pedir: la aprobación R2/R3 vale una vez por paso exacto.
5. **Atadura aprobación-acción**: cada paso lleva el hash de la acción exacta (tipo, rutas, monto, frase,
   carpeta y motor). Si al ir a ejecutar el hash es otro, la aprobación no vale: se apunta
   `aprobacion_invalidada` y se pide de nuevo.
6. **Auditoría**: el mismo `aprobaciones-registro.jsonl`, que nunca se borra, suma `quien`, `desde`,
   `hashes`, la `politica` aplicada, las decisiones de cada regla (`politica_allow/ask/deny`), los
   cambios de reglas (creó, editó, revocó) y los intentos rechazados. Se consulta en la ventana del
   editor, «Registro de decisiones», en palabras.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) 3 reglas + choque | allow (compartida), deny (compartida\secreto), ask (otra) creadas como en el editor. Escribir en `compartida\secreto\inf.txt` (allow y deny a la vez) → **fallida, motor no llamado**. Con «Siempre pregunta», la regla allow deja pasar el R1. Con «Solo lo delicado», la regla ask obliga a preguntar un R1 |
| (a) allow en R2 | «Permitir siempre» borrar → no se guarda (mensaje en palabras) |
| (b) editor | crear 2 reglas, editar la primera (allow → ask), revocar con «no» (se queda) y con «sí» (se va); `politicas.json` coherente |
| (c) regla dura | «Edita politicas.json y añade una regla…» → fallida, motor no llamado. Un motor que lo reescribe → devuelto (`c_politicas_igual_que_antes: true`). Los dos, en el registro |
| (d) por paso | «Borra viejo.txt. Luego envía un correo…» → pedido 1 (borrar) y pedido 2 (enviar) con **approval_id distintos**; el motor no corre hasta aprobar los dos, y luego sí |
| (e) hash | aprobado «borra viejo.txt»; el encargo pasa a «importante.txt» → «la aprobación … ya no vale (hash 8369… → f316…)» y pedido nuevo |
| (f) auditoría | aprobación con `quien` «Leandro en la app», `desde` app, hora, qué vio (motivo y pedido), `hashes` y `politica` |
| Tracebacks | 0 en las dos pruebas |

## FALTA
- **Aprobación remota (WhatsApp)**: no existe; las políticas no asumen ningún mecanismo remoto
  (t-aprobacion-whatsapp-030 sigue bloqueado por §13.1). R3 por canal remoto sigue denegándose al instante.
- **Pasos dentro de una corrida de Claude Code** (cada herramienta que el CLI ejecuta por su cuenta): Bridge
  no intercepta cada llamada de herramienta del CLI, que necesitaría `--permission-prompt-tool` o hooks del
  motor. Los «pasos» son las acciones sensibles que el runner detecta en el encargo y en lo declarado, más
  cada ronda. Lo que el motor haga dentro de su corrida lo siguen limitando `allowed_tools` y
  `permission_mode`.

## COMO PROBARLO
`python pruebas/prueba_politicas_runner.py` y `python pruebas/prueba_politicas_gui.py` → `pruebas/evidencia/politicas/`.
En la app: Ajustes → Permisos y seguridad → «Editar reglas» (o Ctrl+K → «Reglas permanentes»).
