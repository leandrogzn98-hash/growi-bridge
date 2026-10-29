# ESTADO — De 79 a 80+ en la auditoría de la 0.4.5 (#22, arreglo de t-auditoria-045)

Rama `Claude`, 29-oct-2026.
- Los criterios y los pesos son los de `ESTADO-AUDITORIA-045.md`, sin cambios.
- Solo se quitaron defectos: ninguna pantalla se rehízo y el diseño no se tocó.
- La app instalada no se tocó.

**Resultado: 86/100** (antes 79; la 0.2.0 dio 62). La meta de 80+ se cumple, medida y no estimada.

## LISTO
1. **Los «·» fuera de lo visible** (F1-F4). Eran 74 líneas de `growi-bridge.py` y el nombre de un motor en
   `engines.json`.
   - La regla general: « · » pasa a «, ».
   - Donde la frase lo pide, a «: » o «; ». Ejemplos:
     - «Sin clave: pon tu clave…», «Conectada: …», «Error: …»;
     - la cadena de motores «principal, equivalente Max: »;
     - la leyenda de la matriz «✓ = lo hace sin preguntar; ? = …»;
     - los atajos «Alt + 1 o Ctrl + 1».
   - El motor «Ollama · Hermes 3 8B (local $0)» pasa a «Hermes 3 8B en Ollama (local $0)». Se comprobó que ningún
     código ni el runner lo usan como clave.
   - Se dejaron a propósito, porque no se ven en la app: 2 docstrings, 1 comentario, las cabeceras que se escriben
     en los archivos de memoria (2) y la cabecera del `.md` de una transcripción.
   - **Medido: 0 textos con «·» a la vista** en las 5 pantallas y en la configuración inicial, a 100 % y 150 %.
     Antes: 3 / 50 / 12 / 10 / 2.
2. **Acento `#FF6363` solo en la acción primaria** (F5-F7). Se quitó `accent=True` de 11 botones, que pasan al
   botón normal del tema:
   - Pedir cosecha;
   - Añadir regla (Modelos);
   - Comprobar mi PC;
   - Instalar;
   - Descargar, y su variante «Reanudar (N %)»;
   - Probar (nuevo motor);
   - Generar…;
   - Guardar (claves);
   - Pararlo (aviso de Avast);
   - Exportar mis conversaciones.

   **Medido**: con acento solo quedan **Enviar** (Tareas) y **Siguiente** (configuración inicial). Abrir resultados
   lo conserva, pero no sale en las capturas porque el detalle está cerrado.
3. **Borde blanco del campo Ctrl+K** (F12). En el tema oscuro, `TEntry` no redefinía `lightcolor`/`darkcolor` del
   clam, que pintaba un filo blanco por dentro.
   - Ahora llevan el color del campo y el borde es la línea del tema (`#2C2C2E`). Ver `_theme_styles`.
   - Los dos se añadieron a `_TTK_OSCURO`, así que al volver al tema claro se restauran como estaban.
   - Captura: `100-tareas.png` y `150-tareas.png`, con borde gris fino y sin blanco.
4. **Paso 3 no hizo falta**: con 1 y 2 la nota pasó de 80, así que los cortes a 150 %, los 3,5 s de Modelos y el
   color de la barra lateral siguen en FALTA.

### Puntuación antes / después (mismos bloques y pesos)
| Pantalla | Cliché /10 | Kit SaaS /15 | Cromo /20 | Contenido /15 | Logo /10 | DPI /15 | Lista 0.4.5 /15 | Antes | **Después** |
|---|---|---|---|---|---|---|---|---|---|
| Tareas | 10 | 11 | 15 → **20** (0 «·», acento solo en Enviar) | 14 | 6 | 9 | 13 → **15** (Ctrl+K sin borde blanco) | 78 | **85** |
| Modelos | 10 | 11 | 6 → **20** (de 50 «·» a 0; 0 botones con acento) | 14 | 6 | 13 | 9 (sigue tardando 3,5 s) | 69 | **83** |
| Ajustes | 10 | 13 | 13 → **20** | 15 | 6 | 14 | 13 | 84 | **91** |
| Estado | 10 | 12 | 13 → **20** | 15 | 8 | 9 | 14 | 81 | **88** |
| Recursos | 10 | 12 | 18 → **20** (la barra lateral sin «·») | 14 | 6 | 8 | 14 | 82 | **84** |
| Configuración inicial | 10 | 14 | 20 | 15 | 5 | 15 | 15 | 94 | 94 |

- **Final, media de las 5 pantallas de trabajo: 86/100.** Son 431 / 5 = 86,2; antes 394 / 5 = 78,8. Con la
  configuración inicial sería 87.
- Solo se movieron los bloques donde se quitó el defecto. Los cortes a 150 % (DPI), el tiempo de Modelos y Ajustes
  y el resto quedan con la misma nota que en la auditoría.

### Verificación
- `python pruebas/prueba_auditoria.py 100` y `… 150`, después de los cambios:
  - código 0, sin `error_prueba` y 0 tracebacks;
  - 14 capturas nuevas en `pruebas/evidencia/auditoria/capturas-045/`, copiadas a `share\outbox\capturas-045\`;
  - las de antes siguen en el commit `1350840`.
- **Foco**: la captura ahora apunta también `foco_nuestro`, que dice si la ventana activa llegó a ser la de la app.
  Da `false` en las 14.
  - En dos capturas (Tareas a 150 % y Modelos a 100 %) cambió la ventana en primer plano mientras tanto. Fue otra
    ventana del usuario, no la de la prueba.
- `python -m py_compile growi-bridge.py`: sin errores. `engines.json` es JSON válido.
- **Gate** (`gate-calidad.py --archivos growi-bridge.py engines.json pruebas/captura_oculta.py`): **PASA**.
  - py_compile, ruff, mypy y pytest en verde;
  - smoke: copia oculta, `/gateway/salud` 200 a los 23,6 s, log sin tracebacks.

## FALTA
- Quedan de la auditoría y no se arreglaron, porque la meta ya se había alcanzado y el pedido era parar al llegar:
  - **F8-F11, cortes a 150 %**: tarjetas de Estado y aviso de Avast; «Disco libre» en Recursos (también a 100 %);
    estadísticas de Tareas («revisadas y aprobadas ho», «real, $0.00 equivalente M…»); ruta de Tripo.
  - **F13**: la barra lateral `#141416` sigue más clara que el contenido `#0F0F0F`.
  - **F14**: Modelos tarda 3,2-4,8 s en abrirse y Ajustes 0,6-1,3 s la primera vez, sin esqueleto.
- Los textos con «·» que no se ven en la app (archivos de memoria y cabecera de transcripción) se dejaron como
  están.
- El 150 % sigue siendo simulado (`GROWI_BRIDGE_DPI=144`).
- Mapa, banner y foco se apoyan en la evidencia del 28-oct, igual que en la auditoría.

## CÓMO PROBARLO
- `python pruebas/prueba_auditoria.py 100` y `python pruebas/prueba_auditoria.py 150`. Es oculta: nada se ve ni roba
  el foco. En `pruebas/evidencia/auditoria/evidencia-<dpi>-ctk.json`, en cada página:
  - `paginas.<p>.medido.textos_con_punto_medio` debe estar vacío;
  - `botones_con_acento` solo debe tener Enviar (Tareas) o Siguiente (configuración inicial);
  - `foco_nuestro` debe ser `false`.
- En la app, con el tema Oscuro Raycast:
  - la barra lateral dice «Versión …, carril A» y «equivalente Max $…, N tareas terminadas»;
  - en Modelos ya no hay «·» y sus botones no son rojos;
  - el campo «Buscar o pedirle algo (Ctrl K)» de Tareas tiene un borde gris fino.
