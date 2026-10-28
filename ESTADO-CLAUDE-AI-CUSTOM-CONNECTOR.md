# ESTADO — «Muse.ai» por Custom Connector (t-claude-ai-custom-connector)

Rama `Claude`, 28-oct-2026. **Se detuvo en la subfunción 1, como manda el spec.** La definición quedó resuelta con
fuentes, y la respuesta es que **no es un motor**: el conector va en la dirección contraria. Construir lo de las
subfunciones 2-4 contradice la definición y la regla de no exponer nada a internet. **No se construyó nada.**

## 1. Definición: RESUELTA, con fuente
- **Fuente del repo**: `INVESTIGACION-0.2.0.md`, sección MCP, punto (c), y las fuentes de la línea 648, verificadas
  contra las páginas de Meta el 26-sep-2026. La investigación 0.3.0 no la trae, pero la 0.2.0 sí:
  - «Muse.ai» es **Muse, el asistente de Meta** (la app de consumo). Es el «tu asistente Muse» del `README.md` y
    sale en el onboarding: Muse / Claude Code / Grok / …
  - La app de consumo **no documenta añadir servidores MCP**. Se conecta con «Custom Connectors» contra una API o
    una CLI.
  - **Muse Code** sí es cliente MCP completo, con stdio y Streamable HTTP.
  - La vía propuesta: «Custom Connector contra la API del Bridge (vía túnel o VPS), o Muse Code».
- **Verificación en vivo (búsqueda web, 28-oct-2026)**:
  - [parallel.ai: Meta Muse custom integrations](https://parallel.ai/articles/meta-muse-custom-integrations).
  - [CData: How to Connect Your Business Apps to Meta Muse](https://www.cdata.com/blog/muse).
  - Lo que dicen: Muse escribe sus Custom Connectors contra servicios con API, CLI o endpoint MCP. Las claves se
    guardan en su «Secure Credentials Store». El servicio **tiene que ser alcanzable desde internet**: el ejemplo
    de Home Assistant lo exige.
  - Ojo: son fuentes de proveedores. No encontré la página de Meta con la interfaz exacta.
- **Lo que no es**:
  - No es claude.ai, la opción (a) del spec.
  - No es la API de Anthropic, la opción (b).
  - No hay una API pública de Muse para usarla **como motor** con una clave BYOK: no se encontró ninguna fuente que
    la documente, y no se inventa.

## Por qué no se construyen las subfunciones 2-4
- **No es un motor**. El Custom Connector lo ejecuta Muse desde la nube de Meta **hacia** el Bridge, y el Bridge
  es el servidor.
  - Un descriptor de motor en `engines.json` (subfunción 2), con la clave BYOK (subfunción 3) y la tarea corta
    (subfunción 4), supone lo contrario: que el Bridge llama a Muse. No hay un endpoint documentado al que llamar.
- **Exponer el Bridge a internet** (túnel o VPS) choca con dos cosas:
  - la regla «no exponer webhook público ni bot nuevo» (INVESTIGACION-0.3.0 §11);
  - la regla del servidor MCP: loopback y token, porque hay 1.100+ gateways expuestos.
  - Además depende del **túnel cifrado**, que sigue bloqueado: ver `ESTADO-PROXY-ALQUILER.md`, bloqueador 1.
- **Lo que ya existe y sirve sin exponer nada**: Muse Code, o cualquier cliente MCP **en este PC**, puede usar el
  servidor MCP del Bridge (`t-mcp-streamable-http`) en `http://127.0.0.1:<puente+20>/mcp` con el token del
  gateway. No hace falta código nuevo.

## LISTO
- La definición, resuelta y documentada con su fuente del repo y la búsqueda en vivo (verificación a).

## FALTA (bloqueado, no inventado)
- (b) descriptor, (c) credencial en Credential Manager y (d) tarea corta real: **no se construyen**. No hay un
  servicio-motor definido al que llamar.
- **La pregunta concreta para Leandro**: ¿quieres que **Muse (Meta), desde su nube, llame a tu Bridge**?
  - Si es sí, hace falta un endpoint público: el túnel o VPS cifrado, con token y lista de herramientas R0. Es
    exactamente el bloqueador 1 del proxy.
  - Si te basta con Muse Code en este PC, ya funciona con el servidor MCP local y no hay nada más que hacer.
  - Si «Muse.ai» era otra cosa (un servicio con API para usar como motor), dime la URL de su API y el spec se
    retoma desde la subfunción 2.

## CÓMO PROBARLO
- Leer las fuentes citadas arriba y `INVESTIGACION-0.2.0.md` (sección MCP, punto c).
- Para la vía local, Muse Code como cliente MCP: `python pruebas/prueba_mcp.py` demuestra el servidor en loopback.
