# Índice — 0.4.5 rediseño de interfaz de Growi Bridge (20 specs)

**Fecha:** 26 oct 2026. **Fuente:** `~/workspace/shared-bridge/diseno-045/NOTAS-DISENO.md` (dirección Raycast, 5 pantallas, decisión SOLO PC de Leandro 26 oct 07:05) + `~/workspace/shared-bridge/investigacion-ui-045/INFORME.md` (10 referencias Mobbin + patrones + dudas §C) + veredicto del piloto CustomTkinter (`ESTADO-PILOTO-CUSTOMTKINTER.md` en `~/workspace/shared/inbox/`, spec `t-piloto-customtkinter-030`): SEGUIR con CustomTkinter, superficie por superficie, siempre con la página clásica como respaldo; nunca convertir toda la app de una vez. **Carpeta:** `~/workspace/shared-bridge/opus-tasks-045/` — 20 archivos `.task.json`, todos `model: opus`, `timeout_min: 60`, `permission_mode: acceptEdits`, `allowed_tools: "Read,Write,Bash,Glob,Grep"`, `cwd: C:\Users\forte\growi-bridge\share\inbox`, prompts en español de ~6.900 a ~9.700 caracteres, validados con `json.load` (claves exactas, 6 criterios top-level cada uno, ids únicos con prefijo `t-` y sufijo `-045`).

**Pre-requisito (no es 0.4.5, es cerrarlo antes):** la Fase B completa (39 specs de `opus-tasks-040/` verificados + `CADENA-ESTADO-040.json` en fase `completa`). Todos los specs asumen la Fase B terminada y construyen encima; ninguno toca VERSION. La cadena `cadena-045.py` no envía nada hasta que su propio estado (`CADENA-ESTADO-045.json`) diga fase `diseno-045` Y la Fase B esté completa.

**Alcance: SOLO PC (decisión de Leandro 26 oct 2026, 07:05).** Ningún spec pide nada de móvil: ni layouts, ni breakpoints, ni pruebas, ni capturas en móvil. El P1 de la mascota queda reducido a escritorio (que no tape el botón de cerrar del detalle según el scroll); la parte móvil del hallazgo queda DESCARTADA.

**Reglas que mandan (del piloto + Fase A):**
1. **«Ni flojo ni a medias» = función completa con subfunciones.** Cada spec enumera función principal + subfunciones obligatorias y la verificación cubre CADA una por separado.
2. **CustomTkinter superficie por superficie, con fallback clásico.** Solo se convierten las superficies que el veredicto nombra (Carpetas, tarjetas APIs, tarjetas Modelos, configuración inicial, pie de la barra lateral) + las superficies NUEVAS de filas y controles de la 0.4.5. NO se convierten: tablas (Treeview), Registro, botón grande (Canvas), mascota, Ctrl+K. CTk NO trae blur/liquid glass ni lector de pantalla completo (eso sería PySide6, no más CTk).
3. **Sin datos inventados.** Costes, contadores, estados y métricas son reales o dicen «sin datos» / «no se pudo leer el estado». Nunca un verde falso ni un cero falso.
4. **El prototipo HTML, MagicPatterns y Framer son REFERENCIA, no código a copiar.** La app sigue siendo Python/Tkinter en el PC. No se inventan funciones que el diseño no pida.

## Decisiones cerradas al escribir los specs (para revisión del coordinador)

1. **Etiquetas de sección en sentence case semibold** (regla anti-plantilla del piloto, de la auditoría REVISION-UIUX-0.2.0). La referencia Linear de mayúsculas 0.75rem del INFORME queda descartada para Growi Bridge. Spec: `t-tokens-raycast-045`.
2. **Tema claro: no se rediseña.** Conserva sus tokens actuales con el mismo layout nuevo. El rediseño es el tema oscuro Raycast. Spec: `t-tokens-raycast-045`.
3. **Color del vigilante nocturno: #0A84FF (azul).** Nunca ámbar (el ámbar es del manager Growi). Spec: `t-tokens-raycast-045`.
4. **Densidad: filas de 32–36 px** (Linear), estado = punto de color + etiqueta, IDs de tarea en monoespaciada (Consolas). Spec: `t-tokens-raycast-045`.
5. **Meta de auditoría: 80+/100** frente al 62/100 de la auditoría 0.2.0, con los mismos criterios (o la lista del spec si REVISION-UIUX-0.2.0.md no está en el PC). Spec: `t-auditoria-045`.
6. **Cadena propia (`cadena-045.py`), no dentro de la cadena de Fase B.** Motivo en `CRON-045.md`: una cadena por release (precedente 030/040/050), gate propio sobre Fase B completa, estado y log separados por release.

## Orden de ejecución

El orden de envío es el de esta tabla, sin saltos. Dentro de ese orden, respetar las dependencias.

| # | Spec | Qué cubre | Depende de |
|---|---|---|---|
| 1 | `t-tokens-raycast-045` | Tokens Raycast oscuros en THEME + cromo de la app (fondos, tarjetas, bordes, fuente, densidad). Base de toda la 0.4.5. | — (Fase B completa como gate) |
| 2 | `t-estado-banner-nube-045` | BUG: banner «Sin conexión con la nube» es falsa alarma; el probe conn_state() debe coincidir con el modelo real del runner. | t-tokens-raycast-045 |
| 3 | `t-estado-mapa-045` | BUG: botón «Ver el mapa» solo hace show_page("estado"); debe bajar hasta la tarjeta «Mapa de disponibilidad» y resaltarla. | t-tokens-raycast-045; t-mapa-ampliado (Fase B) |
| 4 | `t-tareas-estadisticas-045` | BUG: tarea en curso fijada arriba con «trabajando ahora» + fila de 3 estadísticas (En curso / Aprobadas hoy / Gasto de hoy) + píldoras de filtro por estado. | t-tokens-raycast-045; t-consumo-vivo (0.2.0); t-cola-visible-030 (Fase A) |
| 5 | `t-barra-lateral-045` | Barra lateral 232 px CTk: marca, navegación con contadores, medidor «Consumo hoy», tarjeta de guardrail abajo, pie con interruptor de la mascota. | t-tokens-raycast-045; t-guardrail-visible (Fase A); piloto CTk |
| 6 | `t-carpetas-ctk-045` | Conversión a CTk de la página Carpetas (filas + botones, mismo comportamiento). | t-tokens-raycast-045; piloto CTk |
| 7 | `t-apis-tarjetas-045` | Conversión a CTk de las tarjetas de APIs (estado real por tarjeta). | t-tokens-raycast-045; piloto CTk; t-credenciales-keyring (Fase A) |
| 8 | `t-modelos-tarjetas-045` | Conversión a CTk de las 4 tarjetas de Modelos (Tu PC, Quién responde, Qué puede hacer, Reglas) + Auto primero con checkmark + coste por modelo. | t-tokens-raycast-045; piloto CTk; t-modelo-por-superficie-auto (Fase B) |
| 9 | `t-onboarding-piel-045` | Conversión a CTk de la configuración inicial: tarjeta centrada con puntos de paso, mismo contenido y validación. | t-tokens-raycast-045; piloto CTk; t-onboarding-fallos (Fase B) |
| 10 | `t-tareas-detalle-045` | Detalle debajo de la tabla (no modal) + línea de tiempo de verificación + «Abrir resultados» / «Volver a la cola». | t-tokens-raycast-045; t-tareas-estadisticas-045; t-criterios-tipados-030 (Fase A) |
| 11 | `t-tareas-compositor-045` | Compositor «Pedirle algo a Growi…» + selector «Automático (recomendado)» + Enviar (encola real). | t-tokens-raycast-045; t-tareas-detalle-045; t-cola-visible-030 (Fase A) |
| 12 | `t-tareas-ctrlk-045` | Campo «Buscar o pedirle algo» en el encabezado de Tareas (buscar + pedir; router automático). Paleta Ctrl+K sin tocar. | t-tokens-raycast-045; t-tareas-compositor-045; t-teclado-foco (Fase B) |
| 13 | `t-estado-tarjetas-045` | Pantalla Estado como tarjetas de salud + tarjetas de métrica (número grande + sparkline). Reutiliza banner y mapa. | t-tokens-raycast-045; t-estado-banner-nube-045; t-estado-mapa-045; t-panel-estado-gateway (Fase B) |
| 14 | `t-recursos-graficos-045` | Pantalla Recursos: gráficos de línea CPU/Memoria + selector de rango + tarjetas de métrica. Lista de procesos sin cambios. | t-tokens-raycast-045; t-estado-tarjetas-045; t-semaforo-vram-v2 (Fase A) |
| 15 | `t-ajustes-secciones-045` | Ajustes en secciones con filas (Guardrail, Motores, Apariencia) encima del piloto CTk y de t-ajustes-reorg. Sin ajustes nuevos. | t-tokens-raycast-045; piloto CTk; t-ajustes-reorg (Fase B); t-temas-oscuro-sistema (Fase A) |
| 16 | `t-ajustes-matriz-045` | Matriz motor × permiso (lectura) + notificaciones de la cola en Ajustes. | t-tokens-raycast-045; t-ajustes-secciones-045; t-politicas-persistentes-030 (Fase B) |
| 17 | `t-mascota-solape-045` | P1 escritorio: la mascota flotante no debe tapar el botón de cerrar del detalle en ningún scroll. Nada de móvil. | t-tareas-detalle-045; t-mascota-estados (Fase B) |
| 18 | `t-historial-gasto-045` | Historial de gasto en Tareas: persistencia diaria (JSON por día), Total acumulado + tabla por día (más reciente primero), siembra solo con cifras verificadas; los "hoy" no cambian. Pedido de Leandro 27 oct 2026 (ayer ~$424, hoy ~$118, sin sumatoria). | t-tareas-estadisticas-045 |
| 19 | `t-estado-consistencia-045` | Consistencia de estado en Estado: una sola fuente de verdad (plano de control del gateway) para barra lateral, banner, botón de encendido y Servicios; nunca "Todo encendido" + "Sin conexión" a la vez; estados parciales que nombran el servicio caído. Pedido de Leandro 27 oct 2026 (captura 09:20: todo encendido en verde y a la vez "Sin conexión"). | t-estado-banner-nube-045; t-estado-tarjetas-045; t-estado-mapa-045 |
| 20 | `t-auditoria-045` | Auditoría final: capturas 100%/150% de las 5 pantallas, lista de comprobación, puntuación sobre 100, meta 80+. Solo audita, no reconstruye. | Los 19 anteriores |

## Qué NO se hace en la 0.4.5 (recordatorio para quien encole)

Nada de móvil (decisión de Leandro 26 oct). No convertir tablas, Registro, botón grande (Canvas), mascota ni paleta Ctrl+K. No migrar a PySide6/Qt (el salto caro no es este release). No reconstruir Framer/MagicPatterns en Tkinter (son referencia). No tocar el carril B (`growi-bridge-lane2\`) ni la extensión (`growi-bridge-browser\`). No inventar funciones que el diseño no pida (sin paywall Pro, sin gradientes morado-rosa, sin modismos de Mac). El icono de bandeja del carril B sigue siendo tarea aparte (t-fix-icono-barra-020). Las pantallas Modelos, Estado y Recursos en Framer y el avatar «G» por el PNG real son trabajo de diseño fuera de la cadena, no specs de código.

## Dudas abiertas que los specs NO cierran (para el coordinador)

- **Saldo real de MagicPatterns**: la API no lo expone; mirar el dashboard web antes de lanzar más pantallas de diseño. No afecta a la cadena (los specs no usan MagicPatterns).
- **¿Dónde vive la mascota en la nueva interfaz?** Los specs la dejan donde está (flotante + pie de la barra lateral) y solo arreglan el solape en escritorio. Si Leandro quiere moverla, es otro spec.
- **DPI 150% real**: el piloto verificó con 150% simulado (`GROWI_BRIDGE_DPI=144`); ningún spec exige 150% real de Windows. La auditoría (spec 20) lo deja anotado si no se ve.
- **Instalador sin actualizar**: el piloto dejó como FALTA añadir `customtkinter==6.0.0` a los dos `.bat`. Ningún spec de la 0.4.5 lo incluye (es trabajo manual en el PC, fuera de la cadena); si no se hace, una instalación nueva tendrá las páginas clásicas.

## Fusiones en lotes (27 oct 2026, ver LOTES.md)
- **t-lote-tarjetas-045** fusiona `t-apis-tarjetas-045` + `t-modelos-tarjetas-045` (misma conversión de tarjetas a CustomTkinter con respaldo clásico, foco y arranque medido; 12 criterios, sonnet). Los archivos originales quedan como referencia; en `cadena-045.py` (ORDEN) solo va el lote, en la posición de `t-apis-tarjetas-045`.
