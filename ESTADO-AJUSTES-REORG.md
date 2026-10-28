# Estado: Ajustes reorganizado (t-ajustes-reorg)

Rama `Claude`, 28 oct 2026. **LISTO**, con las FALTA de abajo.

La página Ajustes (versión CustomTkinter, `_build_ajustes_ctk`) queda así:
- 6 grupos en el orden del spec, más «Datos y respaldo» y «Zona peligrosa»;
- filas planas con «etiqueta a la izquierda, control a la derecha», separadas
  por líneas de 1 px y **sin tarjetas grises**;
- buscador arriba;
- cada ajuste se guarda solo.

**No se añadió ningún ajuste nuevo.** Lo que no existía queda como FALTA.

## Qué hay en cada grupo
| Grupo | Filas |
|---|---|
| General | Al cerrar la ventana · Iniciar al encender la PC · Actualización automática · No suspender mientras trabaja |
| Apariencia | Tema (Claro / Oscuro / Según el sistema + tema por nombre) |
| Conexión | Proxy (estado + **Probar**) · Modo del proxy (Mi proxy / Usar proxy del sistema / Sin proxy, el mismo `set_proxy_mode` de Estado) · Ajustes avanzados del proxy (siguen plegados en Estado; botón Abrir) |
| Motores y modelos | Motor por defecto (lo dice `engines.json`) · Carpeta de modelos · Comprobar mi PC (lleva a Modelos) · Claves (la superficie de claves se mudó aquí desde el final de la página) |
| Permisos y seguridad | Preguntarme siempre · Preguntarme solo lo delicado · Carpetas (lleva a Carpetas) · Exportar mis conversaciones |
| Notificaciones y atajos | Los atajos (lista, captura y reasignación existentes) |
| Datos y respaldo | **Exportar configuración** · **Importar configuración** («Se aplica al reiniciar») · Configuración inicial · Inbox/Outbox/versión/actualizaciones/Salir |
| **Zona peligrosa** (título y línea en rojo, al final) | Hazlo sin preguntar (pide doble confirmación, `_on_guardrail`) · Apagar/Reiniciar PC (confirmación + 60 s) |

## Código (`growi-bridge.py`)
- `_build_ajustes_ctk`: cambió todo el bloque desde la cabecera (nuevas
  `section`/`row`/`side_row`, buscador `_buscar` / `_ir_a`, los grupos).
  Las claves de `_widgets` que usa el resto de la app se mantienen.
- Nuevas `config_exportar`, `config_importar`, `config_exportar_ui` y
  `config_importar_ui`.
  - **Exportar** escribe un `.json` con `settings.json` (menos `lane`,
    `bridge_port`, `onboarding_done` y `close_toast_shown`) y las carpetas.
    **Nunca** lleva `proxy.json`, `secret.txt`, el token ni las claves.
  - **Importar** valida el archivo, guarda `.<fecha>.bak` de `settings.json` y
    `folders.json`, pide confirmación y dice «Se aplica al reiniciar».
- `build_gui`: `_build_claves` dibuja en el hueco de «Motores y modelos».
- La copia previa al cambio no se guardó como `.bak` en el repo (está en git:
  commit anterior).

## Verificación (con evidencia real)
`pruebas/prueba_ajustes_reorg.py` arranca **la app real** (`main()` de una
copia en `%TEMP%`, puerto de prueba 8797) y desde su bucle de Tk usa Ajustes
con **ratón y teclado de verdad** (`SetCursorPos`/`mouse_event`, `SendInput`).
Evidencia en `pruebas/evidencia/ajustes-reorg/`.

| | Prueba | Resultado |
|---|---|---|
| a | Grupos en orden, filas, ajustes que siguen funcionando | Títulos leídos de la página: General, Apariencia, Conexión, Motores y modelos, Permisos y seguridad, Notificaciones y atajos, Datos y respaldo, Zona peligrosa. Filas: 4/1/3/4/5/16/4/2. Capturas `1-ajustes-arriba.png` y `4-zona-peligrosa.png`. Siguen funcionando: el clic en «No suspender» guarda; «Probar» lanza `proxy_test_ui` (captura 2: «Comprobando la conexión…»); el tema muestra su selector; el buscador lleva a cada grupo |
| b | Escribir «proxy» en el buscador | `→ Conexión · Proxy`, la página se desplaza (yview 0,17) y resalta la fila (captura `2-buscar-proxy.png`). Otros: tema → Apariencia, atajo → Notificaciones y atajos, carpetas → Permisos y seguridad, exportar config → Datos y respaldo, motor → Motores y modelos |
| c | Clic real en un interruptor, sin botón Guardar | `keep_awake` en `settings.json`: true → **false** tras el clic (y vuelta a true); el log dice «no suspender mientras trabaja desactivado». En la página no hay ningún botón «Guardar» |
| d | Zona peligrosa separada con confirmación | Grupo propio al final, con título y línea en rojo: «Hazlo sin preguntar» (doble confirmación existente) y Apagar/Reiniciar PC (confirmación + 60 s) |
| e | Ningún ajuste nuevo | Antes: los 3 interruptores, Al cerrar, Atajos, Configuración inicial, Apariencia, 3 niveles de permisos, Este PC, Carpetas/versión y Claves. Después: los mismos más **enlaces** a cosas que ya existían (Probar proxy, modo del proxy de Estado, Modelos, Carpetas, Exportar conversaciones) y el exportar/importar configuración que pide el propio spec (P2). Ninguna clave nueva en `settings.json` |
| P2 | Exportar/importar configuración | `exportar-importar.json`: exporta 3 ajustes y 2 carpetas, sin `lane`/`bridge_port` y **sin la clave del proxy**. Importar en otra instalación cambia ajustes y carpetas, conserva su carril y puerto, deja `settings.json.<fecha>.bak` y `folders.json.<fecha>.bak`, y rechaza un JSON ajeno |

Log de la app de prueba: 0 tracebacks.

## FALTA
- **Tamaño de texto / densidad** (General) y **Reducir movimiento**
  (Apariencia): no existen en la app. El spec no deja inventarlos, así que no
  están.
- **Notificaciones: los 4 interruptores** (tarea terminada, proxy caído, sync
  fallida, cuota): no existen como ajustes. El grupo «Notificaciones y atajos»
  solo tiene los atajos.
- **Borrar datos locales:** no existe en la app. La zona peligrosa tiene
  «Hazlo sin preguntar» y Apagar/Reiniciar; no se creó un borrado nuevo (en
  modo no interactivo no se construye algo que borra sin una decisión).
- **La página clásica** (`_build_ajustes_tk`, que solo se usa si
  CustomTkinter no carga) sigue con el orden viejo.
- **El buscador no está en la paleta Ctrl+K:** sigue su patrón (escribir →
  salta y resalta), pero no está integrado en ella.

## Cómo probarlo
```
python pruebas/prueba_ajustes_reorg.py        # la app real de prueba en 8797, con raton/teclado
```
Para el reinicio real de la app instalada, que lo haga Leandro tras integrar
(Ajustes → buscar «proxy»).
