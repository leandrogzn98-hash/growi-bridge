# ESTADO — MCP Streamable HTTP: servidor y cliente (t-mcp-streamable-http)

Rama `Claude`. Pruebas:
- `pruebas/prueba_mcp.py`: copia aislada, sin interfaz. Peticiones HTTP reales al servidor, el cliente contra
  DeepWiki real y el runner con un motor falso.
- `pruebas/prueba_mcp_gui.py`: la app real, desde una copia, en el puerto de prueba 8797, con el MCP en 8817.

Evidencia en `pruebas/evidencia/mcp/`: `evidencia.json`, `evidencia-gui.json` y 3 capturas.

## LISTO
1. **Diseño con fuentes, marcado como PROPUESTA**: `DISENO-MCP.md`.
   - Cita la spec MCP vigente (2026-07-28, leída en vivo): transportes, Streamable HTTP y herramientas.
   - Cita también la decisión 17.
   - Cubre lo que expone el servidor, lo que consume el cliente (DeepWiki, con su justificación) y lo que no se
     expone jamás.
2. **Servidor Streamable HTTP en loopback** (`McpHandler`, `mcp_servidor_arrancar`):
   - **Red**: solo 127.0.0.1; apagado por defecto (`mcp_servidor`); puerto = puente + 20.
   - **Acceso**: token del gateway; valida `Origin` y `Host`.
   - **Protocolo**: cabeceras `MCP-Protocol-Version` / `Mcp-Method` / `Mcp-Name` con el error `-32020`; GET → 405;
     notificaciones → 202.
   - **Herramientas**: las 4 del diseño, descritas con datos (`MCP_HERRAMIENTAS`).
3. **Cliente MCP** (`mcp_llamar`):
   - Habla la era vigente y, si el servidor es de la anterior, cae a `initialize` con sesión.
   - Lee respuestas JSON o SSE.
   - Consume **DeepWiki real**. Sus herramientas salen en Modelos → «Qué puede hacer», cada una con su
     interruptor: se pintan desde la última lista vista, sin red en la interfaz.
   - También salen en la ventana MCP (Ctrl+K → «MCP»), con casillas.
   - El runner las usa con `herramienta: {id: "mcp", …}`. **Apagada, no se usa.**
4. **Guardrail por MCP**: `bridge_encolar_tarea` deja la tarea con `canal: "mcp"`, y pasa por el mismo guardrail
   y las mismas políticas que cualquier tarea:
   - R2 → `esperando_aprobacion` y el motor **no** se llama;
   - R3 → se deniega al instante (canal remoto).
   - Ninguna herramienta puede tocar el guardrail, las políticas ni los secretos.

## Evidencia (una por subfunción)
| Criterio | Resultado real |
|---|---|
| (a) diseño | `DISENO-MCP.md`, marcado como PROPUESTA, con 3 URLs de la spec + la decisión 17 |
| (b) sin token | **401** `falta el token o no es el bueno` |
| (b) Origin ajeno (`https://atacante.example`) | **403** `Origin no permitido` |
| (b) cabecera que no coincide | **400** `-32020 Mcp-Method no coincide con el cuerpo` |
| (b) GET | **405** |
| (b) con token | **200**, `tools/list` → `bridge_estado`, `bridge_cola`, `bridge_memoria_buscar`, `bridge_encolar_tarea` |
| (b) loopback | escucha en `('127.0.0.1', 8817)`; desde la IP de la LAN (192.168.100.80) **no conecta** |
| cliente → servidor propio | era 2026-07-28, `tools/call bridge_cola` → `resultType: complete` |
| (c) DeepWiki real | `tools/list` (era 2025-06-18, con respaldo) → `ask_wiki_question`, `read_wiki_contents`, `read_wiki_structure` |
| (c) desde el runner | `read_wiki_structure` sobre `modelcontextprotocol/python-sdk` → `status: ok`, motor `mcp:deepwiki (herramienta)`, con el índice real de la wiki |
| (c) interruptor (GUI) | las 3 filas «MCP · deepwiki: …» salen en «Qué puede hacer». Al apagar una **con el ratón** se escribe `mcp_herramientas_apagadas: ["deepwiki:ask_wiki_question"]` y el runner responde «está apagada: no se usa». Capturas 1-3 |
| (d) R2 por MCP («Borra el archivo …») | `esperando_aprobacion`, aprobación `pendiente`, motivo «borrar archivos (R2, deducido del encargo: «borra»)», **motor no llamado** |
| (d) R3 por MCP («rm -rf») | `necesita_decision`, `denegada`: «R3 pedida por canal remoto (mcp): denegada al instante; R3 solo se aprueba en la app», motor no llamado |
| Tracebacks | 0 en las dos pruebas |

## FALTA
- **Clientes reales con la era 2026-07-28**: no se probó un cliente MCP de terceros, como Claude Desktop o
  Claude Code, contra el servidor del Bridge. Sí se probó el cliente propio con la era vigente, y peticiones
  HTTP a mano.
- **El diseño está sin aprobar**: es una PROPUESTA. Leandro decide si las 4 herramientas y DeepWiki se quedan.
- **App instalada**: no se tocó. El servidor queda **apagado** hasta que se encienda en la ventana MCP.

## CÓMO PROBARLO
1. `python pruebas/prueba_mcp.py`: necesita internet para DeepWiki. Mira `pruebas/evidencia/mcp/evidencia.json`.
2. `python pruebas/prueba_mcp_gui.py`: abre la app de prueba, apaga una herramienta MCP con el ratón y abre la
   ventana MCP.
3. En la app real:
   1. Ctrl+K → «MCP» → «Encender / apagar».
   2. Con el token del gateway, haz `POST http://127.0.0.1:8807/mcp` con las cabeceras `Authorization: Bearer …`,
      `MCP-Protocol-Version: 2026-07-28` y `Mcp-Method: tools/list`.
