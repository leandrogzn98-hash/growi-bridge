# EVIDENCIA-MEMORIA — t-memoria-pc (generada 2026-10-26 12:12 por r8_evidencia.py)

Todo lo de abajo es salida real copiada de archivos o de comandos corridos ahora. Memoria real: C:\Users\forte\growi-bridge\memory. Copias de prueba aisladas: C:\Users\forte\growi-bridge\_prueba-memoria\m5 (código final).

## Criterio 1 — python -m py_compile growi-bridge.py (corrido ahora en growi-bridge-app)

```
> cd C:\Users\forte\growi-bridge\share\inbox\growi-bridge-app
> python -m py_compile growi-bridge.py
código de salida: 0 — SIN ERRORES
md5 del archivo compilado: f63bde6e800bc80e26007679e33af028
```

## Criterio 2 — memory\MEMORY.md y memory\2026-10-26.md (la nota de hoy DEL PC) existen y se editan

```
C:\Users\forte\growi-bridge\memory\MEMORY.md: existe=True, 7344 bytes, UTF-8 válido, escribible=True, solo lectura=False
C:\Users\forte\growi-bridge\memory\2026-10-26.md: existe=True, 1094 bytes, UTF-8 válido, escribible=True, solo lectura=False

-- primeras líneas de la nota de hoy del PC (C:\Users\forte\growi-bridge\memory\2026-10-26.md):
# 2026-10-26 — nota de la VM (Growi)

Nota dejada por la VM para la prueba de sync por diferencia con el PC

-- editada con un editor normal (cmd echo >>) en la copia m5: la línea añadida a mano llegó al prompt:
en el prompt enviado al motor (transcript ronda-0): MARCA-MEMORY-EDITADA-A-MANO: SÍ
en el prompt enviado al motor (transcript ronda-0): MARCA-HOY-26OCT: SÍ
```

## Criterio 3 — una tarea recibe MEMORY.md + hoy + ayer y NO notas más viejas

```
-- registro de la app (growi-bridge.log de la copia m5), tarea real m5-c con Hermes:
2026-10-26T11:47:05-04:00 memoria [m5-c]: inyectados MEMORY.md (1463 car.), 2026-10-26.md (406 car.), 2026-10-25.md (103 car.); total 2322 car.; 3 notas más viejas no se cargan

-- prompt que recibió el motor (transcript ronda-0 de m5-c):
en el prompt enviado al motor (transcript ronda-0): MARCA-MEMORY-EDITADA-A-MANO: SÍ
en el prompt enviado al motor (transcript ronda-0): MARCA-HOY-26OCT: SÍ
en el prompt enviado al motor (transcript ronda-0): MARCA-AYER-25OCT: SÍ
en el prompt enviado al motor (transcript ronda-0): MARCA-VIEJA-19OCT: NO

-- sin nota de ayer (hoy simulado 2026-10-28):
2026-10-26T11:47:08-04:00 memoria [consola-114708]: inyectados MEMORY.md (1463 car.), 2026-10-28.md (191 car.); no existe 2026-10-27.md: se carga solo la de hoy; total 2039 car.; 5 notas más viejas no se cargan
```

## Criterio 4 — una tarea larga dispara el flush y el hecho queda en la nota ANTES de seguir

```
-- registro (growi-bridge.log de m5), tarea larga m5-d de 2 fases:
2026-10-26T11:47:19-04:00 runner [m5-d]: terminado: ok duracion=2.8s costo=0.0
2026-10-26T11:47:20-04:00 memoria [m5-d]: flush: la tarea se acerca al límite de contexto (3983 de 2500 tokens; el flush salta a partir de 2200 = 2500 − reserva 250 − umbral suave 50); turno silencioso con llama (encargo + resultado en el prompt)
2026-10-26T11:47:21-04:00 memoria [m5-d]: flush: 1 hechos añadidos a C:\Users\forte\growi-bridge\_prueba-memoria\m5\memory\2026-10-26.md
2026-10-26T11:47:24-04:00 runner [m5-d]: aprobada; encolo la siguiente fase m5-d-f2

-- nota diaria C:\Users\forte\growi-bridge\_prueba-memoria\m5\memory\2026-10-26.md, líneas 12-14:
## 11:47 · PC · flush (m5-d): cerca del límite de contexto (3983/2500 tokens) — lo destiló llama, sin verificar
- Código de lote comprobado: TURQUESA-9182


-- fin de fase sin estar cerca del límite:
{"ok": true, "r": "{'motivo': 'terminó la fase «fase 1 de 3» de m5-fase', 'contexto_tokens': 8192, 'fuente_contexto': '--ctx-size 8192 de servidor.args', 'umbral_tokens': 7210, 'tokens_usados': 1437, 'motor': 'llama', 'hecho': True, 'escrito_en': 'C:\\\\Users\\\\forte\\\\growi-bridge\\\\_prueba-memoria\\\\m5\\\\memory\\\\2026-10-26.md', 'cost_usd': 0.0, 'en_la_nota': True}"}
```

## Criterio 5 — /nuevo guarda un snapshot con nombre descriptivo sin perder el anterior; «recuerda esto» va al archivo correcto y se confirma

```
-- /nuevo por la paleta y por el chat (copia m5), confirmación de la app:
ventana de confirmación: True; textos: ['Guardado en la memoria', 'Sesión nueva. La anterior (4 tareas) quedó resumida en C:\\Users\\forte\\growi-bridge\\_prueba-memoria\\m5\\memory\\snapshot-2026-10-26-resumen-tarea-m5.md.']
ventana de confirmación: True; textos: ['Guardado en la memoria', 'Sesión nueva. La anterior (1 tareas) quedó resumida en C:\\Users\\forte\\growi-bridge\\_prueba-memoria\\m5\\memory\\snapshot-2026-10-26-escribir-tres-frutas.md.']
fila de estado bajo Enviar: '✓ Sesión nueva. La anterior (1 tareas) quedó resumida en C:\\Users\\forte\\growi-bridge\\_prueba-memoria\\m5\\memory\\snapshot-2026-10-26-escribir-tr'
snapshots antes: []
/nuevo #1 (paleta) creó: ['snapshot-2026-10-26-resumen-tarea-m5.md']
/nuevo #2 (chat) creó: ['snapshot-2026-10-26-escribir-tres-frutas.md']
los snapshots del #1 siguen intactos tras el #2 (md5 igual): True
sesiones archivadas: ['sesion-20261026-115037.md', 'sesion-20261026-115044.md']
archivos snapshot en m5\memory: ['snapshot-2026-10-26-escribir-tres-frutas.md', 'snapshot-2026-10-26-resumen-tarea-m5.md']

-- «recuerda esto: prueba de memoria 25 oct» en la memoria REAL: confirmación de la app (consola, 11:56):
Guardado en la nota de hoy (2026-10-26.md): «prueba de memoria 25 oct». Porque es de un día concreto («25 oct»). Archivo: C:\Users\forte\growi-bridge\memory\2026-10-26.md
-- C:\Users\forte\growi-bridge\memory\2026-10-26.md, líneas donde está:
18: ## 11:56 · PC · recuerda esto (consola)
19: - prueba de memoria 25 oct
20:   - Pedido tal cual: «recuerda esto: prueba de memoria 25 oct»
-- share\outbox\memoria-registro.jsonl:
{"at": "2026-10-26T11:56:32-04:00", "evento": "recuerda", "origen": "consola", "archivo": "C:\\Users\\forte\\growi-bridge\\memory\\2026-10-26.md", "destino": "nota", "porque": "es de un día concreto («25 oct»)", "hecho": "prueba de memoria 25 oct", "comprobado": true}
-- por la ventana (chat de Tareas y paleta, copia m5):
ventana de confirmación: True; textos: ['Guardado en la memoria', 'Guardado en la nota de hoy (2026-10-26.md): «prueba de memoria 25 oct». Porque es de un día concreto («25 oct»). Archivo: C:\\Users\\forte\\growi-bridge\\_prueba-memoria\\m5\\memory\\2026-10-26.md']
ventana de confirmación: True; textos: ['Guardado en la memoria', 'Guardado en MEMORY.md (hechos duraderos), sección «2026-10-26 — Recordado por el usuario»: «prefiero que los ESTADO digan siempre lo que quedó sin verificar». Porque es duradero («prefiero»). Archivo: C:\\Users\\forte\\growi-bridge\\_prueba-memoria\\m5\\memory\\MEMORY.md']
ventana de confirmación: True; textos: ['Guardado en la memoria', 'Sesión nueva. La anterior (4 tareas) quedó resumida en C:\\Users\\forte\\growi-bridge\\_prueba-memoria\\m5\\memory\\snapshot-2026-10-26-resumen-tarea-m5.md.']
ventana de confirmación: True; textos: ['Guardado en la memoria', 'Sesión nueva. La anterior (1 tareas) quedó resumida en C:\\Users\\forte\\growi-bridge\\_prueba-memoria\\m5\\memory\\snapshot-2026-10-26-escribir-tres-frutas.md.']
```

## Criterio 6 — sync por diferencia: solo se añade lo nuevo, no se pisa lo del PC; conflicto con las dos versiones y aviso

```
-- secciones de C:\Users\forte\growi-bridge\memory\MEMORY.md AHORA (133 líneas; las 9 de la VM van al final, las 4 del PC siguen):
8: ## 2026-10-26 — Origen de esta memoria
11: ## 2026-10-26 — Reglas del usuario (de rules.json)
15: ## 2026-10-26 — Datos del PC (de la configuración de Bridge)
20: ## 2026-10-26 — Decisiones
24: ## Quién es Leandro
35: ## Familia
44: ## Metas
56: ## Deudas ($1.360 en total, meta: saldar antes de fin de 2026)
63: ## Gastos mensuales (aprox. $786)
68: ## Venturas y clientes
91: ## Reglas de trabajo con Growi (las que mandan)
111: ## Personas clave
124: ## Herramientas y cuentas (sin claves; las claves viven en bóveda, nunca aquí)

-- primera sync REAL con la VM (26 oct 12:06; Growi dejó share\inbox\memoria-semilla y memoria-vm):
===== sync desde share/inbox/memoria-semilla
  "anadidas": 9,
  "actualizadas": 1,
  "conflictos": [],
  "iguales": 0,
  "solo_pc": 4,
===== sync desde share/inbox/memoria-vm
  "anadidas": 0,
  "actualizadas": 1,
  "conflictos": [],
  "iguales": 0,
  "solo_pc": 1,

-- verificación (r7_verificar_sync_real.py, contra la copia previa _respaldo-memoria-pre-sync-20261026):
MEMORY.md: secciones del PC que siguen intactas: 4/4 {'2026-10-26 — Origen de esta memoria': True, '2026-10-26 — Reglas del usuario (de rules.json)': True, '2026-10-26 — Datos del PC (de la configuración de Bridge)': True, '2026-10-26 — Decisiones': True}
2026-10-26.md: secciones del PC que siguen intactas: 1/1 {'11:56 · PC · recuerda esto (consola)': True}
cabecera anterior del PC guardada: 2026-10-26-20261026-120643.md (335 bytes)
cabecera anterior del PC guardada: MEMORY-20261026-120643.md (1430 bytes)
de la VM en MEMORY.md: «Quién es Leandro» True, «Reglas de trabajo con Growi» True
de la VM en la nota de hoy: «Decisión de Leandro 11:38» True
marcador del PC sigue en la nota de hoy: True
repetir sync desde memoria-semilla: exit 0; "anadidas": 0,; "actualizadas": 0,; "iguales": 10,
repetir sync desde memoria-vm: exit 0; "anadidas": 0,; "actualizadas": 0,; "iguales": 1,
ningún archivo de memory\ cambió al repetir: True
conflictos: ninguno

-- conflicto (simulado en la copia aislada m5, como pide el spec: «un conflicto simulado»):
== g2 conflicto (misma sección del 2026-10-26 editada en los dos lados):
MEMORY.md del PC no se pisó (idéntica): True
versiones guardadas en MEMORY--2026-10-26-decisiones--vm-20261026-114646.md: VM-CONFLICTO=True, PC-CONFLICTO=True
CONFLICTOS.md: - 20261026-114646: MEMORY.md → «2026-10-26 — Decisiones»: las dos versiones en conflictos\MEMORY--2026-10-26-decisiones--vm-20261026-114646.md
aviso en la app (state['memoria_aviso']): 'Memoria: 1 conflicto(s) con la VM; están las dos versiones en C:\\Users\\forte\\growi-bridge\\_prueba-memoria\\m5\\memory\\conflictos'
aviso en el registro: 2026-10-26T11:46:46-04:00 memoria: AVISO Memoria: 1 conflicto(s) con la VM; están las dos versiones en C:\Users\forte\growi-bridge\_prueba-memoria\m5\memory\conflictos: MEMORY.md «2026-10-26 — Decisiones»
```

Nota: la línea de «2026-10-26 — Origen de esta memoria» que dice «Lo de la VM entra con la primera sync» la escribió Bridge antes de la sync y quedó desfasada. No se cambió porque el arnés denegó editar memory\MEMORY.md; Leandro puede borrarla o actualizarla a mano. Las 9 secciones de la VM están en las líneas que lista el criterio 6.
