# Diseño MCP de Growi Bridge — PROPUESTA

> **Es una PROPUESTA, no un diseño aprobado.** La investigación 0.3.0 solo nombra «MCP Streamable HTTP + cliente
> MCP» (§12), sin alcance. Lo de abajo sale de la especificación MCP vigente, leída en vivo el 28-oct-2026, y lo
> construido en `growi-bridge.py` la sigue. Leandro decide si se queda así.

## Fuentes (leídas en vivo, 28-oct-2026)
1. Transportes, revisión vigente **2026-07-28**:
   - https://modelcontextprotocol.io/specification/latest/basic/transports
2. Streamable HTTP:
   - https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
   - un solo endpoint POST;
   - el servidor **DEBE validar `Origin`** (si no es válido, 403) y **DEBERÍA** escuchar solo en 127.0.0.1 si es local;
   - las cabeceras `MCP-Protocol-Version`, `Mcp-Method` y `Mcp-Name` deben coincidir con el cuerpo; si no, 400 con `-32020` (HeaderMismatch);
   - sin sesiones;
   - un GET recibe 405;
   - una notificación recibe 202;
   - compatibilidad hacia atrás: si el servidor es de la era anterior, el cliente cae a `initialize` + `Mcp-Session-Id`.
3. Herramientas:
   - https://modelcontextprotocol.io/specification/2026-07-28/server/tools
   - `tools/list` devuelve `resultType: "complete"` y `tools[{name, title, description, inputSchema}]`;
   - `tools/call` devuelve `content[]`, `structuredContent` e `isError`;
   - una herramienta desconocida es `-32602`.
4. Decisión 17 de la adenda §14 (motor universal por descriptor): **lo que se expone se describe con datos**. Las
   herramientas son la tabla `MCP_HERRAMIENTAS` y los servidores externos son `MCP_CLIENTES_DEF` (y
   `settings.mcp_clientes`), no código a medida.

## Servidor MCP del Bridge (lo que expone)
- **Dónde**: `http://127.0.0.1:<puerto del puente + 20>/mcp` (8807 en la app; 8817 en las pruebas). Solo
  loopback, **apagado por defecto** (Ajustes → `mcp_servidor`, o Ctrl+K → «MCP»).
- **Cada petición**:
  - `Authorization: Bearer <token del gateway>`, comparado con `hmac.compare_digest`; sin él, 401;
  - `Origin` ausente o de la lista del gateway; si no, 403;
  - `Host` local;
  - las cabeceras deben coincidir con el cuerpo; si no, `-32020`.
- No hay reverse proxy casero ni puerto abierto a la LAN.

| Herramienta | Nivel | Qué hace | Esquema de entrada |
|---|---|---|---|
| `bridge_estado` | R0 | Si el Bridge está vivo, desde cuándo, el runner y los motores disponibles | `{}` |
| `bridge_cola` | R0 | Cuántos encargos hay en la cola, por estado | `{}` |
| `bridge_memoria_buscar` | R0 | Busca en la memoria (texto + origen, máx. 10) | `{q: string}` |
| `bridge_encolar_tarea` | según el encargo | Deja un encargo en la cola con `canal: "mcp"`. Pasa por el **mismo guardrail y las mismas políticas** que cualquier tarea: R2 espera aprobación en la app y R3 se deniega al instante (canal remoto) | `{prompt: string, cwd?: string}` (el runner valida `cwd` contra las carpetas permitidas) |

## Lo que NO se expone jamás (`MCP_NUNCA`)
- Secretos ni tokens.
- Credenciales ni claves de API.
- Cambiar permisos, guardrail o políticas. Una herramienta MCP no puede bajar el guardrail ni crear políticas:
  no existe ninguna herramienta que lo haga.
- Control de escritorio por clics o capturas de pantalla.
- Acciones sensibles sin aprobación.

## Cliente MCP (lo que consume)
- **DeepWiki** (`https://mcp.deepwiki.com/mcp`). **Por qué este**:
  - es público, de solo lectura y no pide cuenta ni clave: no hay que gastar ni dar credenciales;
  - sirve a lo que hace el asistente: documentación de repos de GitHub, para tareas de código;
  - es un servidor MCP real en producción, no un mock.
- **Herramientas**: las que el servidor anuncia en `tools/list` (hoy `ask_wiki_question`, `read_wiki_contents` y
  `read_wiki_structure`). Cada una sale en Modelos → «Qué puede hacer» con su interruptor. **Apagada, el runner
  no la usa.**
- **Uso desde el runner**: una tarea con `"herramienta": {"id": "mcp", "servidor": "deepwiki", "tool": "…", "args": {…}}`.
  No llama a ningún motor.
- **Era**: DeepWiki responde con la era anterior (2025-06-18), así que el cliente usa el respaldo con
  `initialize`. Contra el propio servidor del Bridge habla la vigente (2026-07-28).
- **Añadir otro servidor** es un dato en `settings.mcp_clientes` (`id`, `url`, `para`), no código.
