# Lo que faltó (log al detener la sesión, 28-oct-2026)

Rama `Claude`. Se detuvo a pedido de Leandro en la **fase 4, spec #5**. Todo lo terminado está commiteado y
pusheado: cada spec tiene su `ESTADO-*.md`, y el resumen está en `ESTADO-FASE-3.md` y `ESTADO-FASE-4.md`.

## 1. A medias: fase 4 #5 `t-barra-lateral-045` (SIN commitear)
El cambio está en `growi-bridge.py`, sin commitear. Compila, pero **no se probó**. Copia del diff:
`pendiente-barra-lateral-045.patch`. Para descartarlo: `git checkout growi-bridge.py`. Para retomarlo: dejar el
archivo como está.

Hecho en código, sin probar:
- barra de 232 px;
- marca compacta: avatar de 40 px, «Growi Bridge» y «Versión … · carril A»;
- iconos de Segoe Fluent Icons en la navegación;
- contador de Estado: filas del mapa en «falla»;
- medidor «Consumo hoy», de `day_by_model`;
- tarjeta del guardrail abajo: nivel, «N en espera», y clic o Intro → Ajustes → Permisos;
- interruptor de la mascota en CTk, con el clásico de respaldo;
- el tiempo de construcción de la barra, en el log.

Falta:
- La prueba GUI de las verificaciones (a) a (g) del spec:
  - 232 px medidos;
  - contadores con 0 y con N;
  - el medidor cuadra con el gasto real;
  - la tarjeta cambia al cambiar el nivel y su clic abre Permisos;
  - el interruptor persiste;
  - con CTk bloqueado (`GROWI_BRIDGE_CTK=0`) sale la barra clásica;
  - capturas a 100 % y 150 %.
- Comprobar que todo cabe a la altura mínima de la ventana y que los glifos de los iconos son los adecuados.
- Medir el arranque **antes y después** (la versión anterior no registra el tiempo).
- Los botones de navegación siguen en Tk clásico, con icono. No se convirtieron a CTk.
- Escribir `ESTADO-BARRA-LATERAL.md`, pasar el gate, commit y push.

## 2. Sin empezar: fase 4, specs #6 a #20 (`specs/opus-tasks-045/INDICE-045.md`)
6. t-carpetas-ctk-045
7. t-apis-tarjetas-045
8. t-modelos-tarjetas-045
9. t-onboarding-piel-045
10. t-tareas-detalle-045. Debe resolver también que la tabla de Tareas es más ancha que la ventana a 150 %.
11. t-tareas-compositor-045
12. t-tareas-ctrlk-045
13. t-estado-tarjetas-045
14. t-recursos-graficos-045
15. t-ajustes-secciones-045
16. t-ajustes-matriz-045
17. t-mascota-solape-045
18. t-historial-gasto-045
19. t-estado-consistencia-045. La barra lateral sigue usando el sondeo del mapa (`conn_state`) mientras el
    banner usa el runner, y pueden contradecirse.
20. t-auditoria-045

Cuando se terminen hay que escribir el cierre de `ESTADO-FASE-4.md`.

## 3. Fase 3: saltados, bloqueados y parciales (detalle en `ESTADO-FASE-3.md`)
- **Saltados por la GPU ocupada** (Ollama del usuario: 4,2 de 6 GB) o por descargas de ~10 GB a la app
  instalada:
  - 02 t-autocalibracion-vram;
  - 08 t-catalogo-030;
  - 12 t-embeddings-8081;
  - 14 t-evaluar-hermes4;
  - 18 t-lote-evaluar-modelos-040;
  - 41 t-vision-gemma3-4b.
- **23 t-matriz-estados**: saltado porque depende de t-estados-vacios y t-estados-error, que no están hechos.
- **26 t-motor-opencode**: el permiso para instalar OpenCode con npm fue denegado.
- **Parciales**:
  - 37 t-spike-whatsapp: falta la prueba en vivo.
  - 39 t-transcribe-whisper: faster-whisper no está instalado (la instalación se denegó).
  - 40 t-verificar-groq-gemini: faltan las llamadas con clave. Ver credenciales, abajo.
  - 42 t-voz-elevenlabs: sin clave.
- **040plus**:
  - #1 t-canal-whatsapp: saltado.
  - #9 t-proxy-alquiler: bloqueado. Faltan el túnel cifrado, la consulta legal y el plan del VPS.
  - #11 t-claude-ai-custom-connector: detenido en la definición. Hay una pregunta concreta para Leandro en su
    ESTADO.
- **FALTAs dentro de specs LISTOS**: cada `ESTADO-*.md` tiene su sección FALTA. Las más importantes:
  - MCP: no se probó con un cliente MCP de terceros, y el diseño es una PROPUESTA sin aprobar.
  - Gadget: no se abrió ningún COM físico (los 4 COM del PC son Bluetooth).
  - El 150 % de DPI siempre fue **simulado** (`GROWI_BRIDGE_DPI=144`).

## 4. Pendiente de Leandro (no lo puede hacer el agente)
- **Credenciales y claves**: el acceso estaba denegado; afecta a 40 y 42.
- **Liberar la GPU** para los specs del catálogo y los modelos locales.
- **Revisar la app instalada**: durante la prueba del gadget, unas teclas y un clic simulados se perdieron y la
  ventana de la app instalada pasó al frente. No hay evidencia de cambios, pero conviene mirarla.
- **Responder**: la pregunta sobre «Muse.ai»; la aprobación del diseño MCP; los bloqueadores del proxy.
- **Reiniciar la app instalada** con la rama `Claude` cuando quiera probar todo en real. Nunca se tocó
  `C:\Users\forte\growi-bridge\`.
