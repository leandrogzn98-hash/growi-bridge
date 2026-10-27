# Pruebas de la memoria (t-memoria-pc) — cómo repetirlas

La memoria vive en `C:\Users\forte\growi-bridge\memory\` (MEMORY.md + una nota por día).
Desde la consola, con la versión de esta carpeta y sin ventana:

```
set GROWI_BRIDGE_SHARE=C:\Users\forte\growi-bridge\share
set GROWI_BRIDGE_MEMORIA=C:\Users\forte\growi-bridge\memory
set PYTHONIOENCODING=utf-8
```

## «recuerda esto» (prueba f)

Comando ejecutado sobre la memoria real el 26 oct 2026 a las 11:56:

```
python growi-bridge.py --recuerda "recuerda esto: prueba de memoria 25 oct"
```

Respuesta real de la app (la confirmación de dónde quedó):

```
Guardado en la nota de hoy (2026-10-26.md): «prueba de memoria 25 oct». Porque es de un día concreto («25 oct»). Archivo: C:\Users\forte\growi-bridge\memory\2026-10-26.md
```

Quedó en la nota del día (es un hecho de un día concreto; un «prefiero…» o «siempre…»
iría a MEMORY.md). Lo que hay en `memory\2026-10-26.md`:

```
## 11:56 · PC · recuerda esto (consola)
- prueba de memoria 25 oct
  - Pedido tal cual: «recuerda esto: prueba de memoria 25 oct»
```

Comprobado leyendo el archivo (solo lectura), con la búsqueda por texto de la app:

```
python growi-bridge.py --buscar-memoria "prueba de memoria 25 oct"
memory\2026-10-26.md:6: - prueba de memoria 25 oct
memory\2026-10-26.md:7: - Pedido tal cual: «recuerda esto: prueba de memoria 25 oct»
```

Y en `share\outbox\memoria-registro.jsonl`: `"evento": "recuerda", "destino": "nota",
"hecho": "prueba de memoria 25 oct", "comprobado": true`.

En la ventana, lo mismo con Ctrl+K o con el chat de Tareas: «recuerda esto: prueba de
memoria 25 oct» → ventanita «Guardado en la memoria» con «Abrir el archivo» (capturas en
`share\outbox\capturas-memoria\r5-f1-*.png` y `r5-f2-*.png`).

## Las demás (en copias aisladas, nunca la app real)

Desde `C:\Users\forte\growi-bridge\share\outbox\capturas-memoria\scripts\`:
`prep_m5.py` y `arrancar_m5.py` (la copia de prueba), luego `r5_c.py` (carga MEMORY.md + hoy +
ayer), `r5_d.py` (flush), `r5_ef.py` (/nuevo y «recuerda esto» por la ventana), `r5_g2.py` y
`r5_g_cab.py` (sync por diferencia y conflicto). Evidencia en `..\evidencia\`. Detalle en
`share\outbox\ESTADO-MEMORIA.md` y `ESTADO-MEMORIA-CORRECCION.md`.

## Sync con la VM real (hecha el 26 oct 2026 a las 12:06)

Growi dejó `share\inbox\memoria-semilla\MEMORY.md` y `share\inbox\memoria-vm\2026-10-26.md` a
las 12:06, tras el pedido de `share\outbox\memoria-pc\PEDIDO-A-GROWI.md`. Antes de mezclar se
hizo una copia completa en `C:\Users\forte\growi-bridge\_respaldo-memoria-pre-sync-20261026\`.

```
python growi-bridge.py --sync-memoria C:\Users\forte\growi-bridge\share\inbox\memoria-semilla
python growi-bridge.py --sync-memoria C:\Users\forte\growi-bridge\share\inbox\memoria-vm
```

Resultado real:
- **Semilla:** 9 secciones nuevas añadidas a MEMORY.md (Quién es Leandro, Familia, Metas,
  Deudas, Gastos, Venturas y clientes, Reglas de trabajo con Growi, Personas clave,
  Herramientas). 0 conflictos.
- **Nota de la VM:** se tomó su cabecera; la del PC era la que pone Bridge por defecto y quedó
  guardada en `memory\sync\anteriores\`.
- **Lo del PC sigue intacto:** las 4 secciones del PC en MEMORY.md, y la sección «recuerda
  esto» con el marcador en la nota de hoy.
- **Repetir las dos syncs** no cambia ningún archivo (0 añadidas, 0 actualizadas).
- **Lo del PC para la VM** quedó en `share\outbox\memoria-pc\diferencia.json`.

Evidencia: `share\outbox\capturas-memoria\evidencia\r7-primera-sync-real.txt` y
`r7-verificacion-sync-real.txt`. Para comprobarlo:
`python share\outbox\capturas-memoria\scripts\r7_verificar_sync_real.py`.

El conflicto (la misma sección editada en los dos lados) se probó con datos simulados en una copia
aislada (`r5-g-sync.txt`), no con la VM real: no se fuerza un conflicto sobre la memoria de verdad.
