# ESTADO — Verificar Groq y Gemini (t-verificar-groq-gemini)

Rama `Claude`. Prueba: `pruebas/prueba_verificar_nubes.py`, en una copia **sin claves** (no lee las del
usuario). Evidencia: `pruebas/evidencia/verificar-nubes/` (`evidencia.json` + `VERIFICACION-NUBES.md`).

## LISTO
- **`verificar_nubes()`** (Ctrl+K → «Verificar Groq y Gemini») recorre tres caminos: Groq directo, Groq por
  el proxy y Gemini directo sin proxy. Para cada uno:
  1. **Sondeo real sin clave**: ¿contesta el servidor desde esta IP y cómo?
  2. **La prueba corta de siempre** («Escribe tres frutas, una por línea»), con la clave activa de Ajustes →
     Claves (Credential Manager). Mide latencia, tokens, costo de esta llamada, costo de una tarea típica
     (2.000 + 500 tokens) y las cabeceras de límite (`x-ratelimit-*`) si las manda.
     - Groq usa `llama-3.1-8b-instant`.
     - Gemini usa el primer modelo **Flash-Lite** (o Flash) que la API lista en vivo, sin adivinar el
       nombre.
- **Informe** para el router: `VERIFICACION-NUBES.json` + `.md` en la carpeta de Bridge (git lo ignora, es
  de cada PC). `nube_verificada(camino)` solo da True si la **llamada real** de ese camino salió bien. Sin
  eso no entra: es la regla dura del spec.

## Lo medido de verdad (28-oct-2026, sin clave)
| Camino | HTTP sin clave | Latencia | Lectura |
|---|---|---|---|
| Groq directo (IP de Venezuela) | **403 `{"error":{"message":"Forbidden"}}`** | 216-286 ms | **rechaza esta IP antes de mirar la clave**: por el proxy contesta el 401 normal. Apunta a bloqueo por región |
| Groq por el proxy (VPS, EE. UU.) | 401 `invalid_api_key` | 412-427 ms | llega; pide clave |
| Gemini directo (IP de Venezuela) | 403 «Method doesn't allow unregistered callers…» | 188-201 ms | llega; pide clave (es la respuesta normal sin clave) |

**Conclusión de hoy:**
- **Ningún camino entra al router todavía**: faltan las llamadas reales con clave.
- El sondeo ya adelanta que **Groq directo desde Venezuela no responde (403 Forbidden)**. Si se usa Groq,
  sería **por el proxy**.
- **Gemini directo sí llega sin proxy** (falta confirmarlo con una llamada con clave, que es la que dice si
  la región está permitida).

## FALTA
- **(a)(b)(c) Las llamadas reales con clave**: no se hicieron. En esta sesión **no se autorizó tocar las
  credenciales** del usuario (ni siquiera ver si hay claves de Groq o Gemini guardadas). El spec lo trata
  como FALTA previa: «no se inventa ni se pide prestada». Hacen falta:
  - una clave de Groq;
  - una de Gemini (AI Studio) en Ajustes → Claves;
  - después, Ctrl+K → «Verificar Groq y Gemini».

  Gasta como mucho ~$0,00001 en Groq y $0 en la capa gratis de Gemini.
- **Límites vivos del free tier de Gemini**: solo los dicen la respuesta con clave (cabeceras / 429) o AI
  Studio. Pendiente de lo anterior.
- El escalón «gemini» de la cadena de t-router-fallbacks es **agy** (CLI con sesión de Google), no esta API:
  lo que mide este informe no lo cambia.

## COMO PROBARLO
`python pruebas/prueba_verificar_nubes.py` (sin claves: sondeos reales + FALTA). Con claves: en la app,
Ctrl+K → «Verificar Groq y Gemini», y mirar `VERIFICACION-NUBES.md` en la carpeta de Bridge.
