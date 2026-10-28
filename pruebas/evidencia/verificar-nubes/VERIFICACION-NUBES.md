# Verificación de Groq y Gemini

Medido el 2026-10-28 a las 04:50. Prueba: «Escribe tres frutas, una por línea.».

| Camino | Contesta sin clave | Llamada real | Latencia | Tokens | Costo (esta / típica 2.000+500) | Límites |
|---|---|---|---|---|---|---|
| Groq directo | 403 Forbidden sin hablar de la clave: rechaza esta IP (¿bloqueo por región?) (216 ms) | sin clave de Groq en Ajustes → Claves: la llamada real no se hizo (FALTA previa; no se inventa ni se pide prestada) | — ms | —+— | — | — |
| Groq por el proxy | llega: pide clave (lo esperado sin clave) (412 ms) | sin clave de Groq en Ajustes → Claves: la llamada real no se hizo (FALTA previa; no se inventa ni se pide prestada) | — ms | —+— | — | — |
| Gemini directo | llega: pide clave (lo esperado sin clave) (188 ms) | sin clave de Google Gemini en Ajustes → Claves: la llamada real no se hizo (FALTA previa; no se inventa ni se pide prestada) | — ms | —+— | — | — |

**Conclusión:** Ninguno entra al router todavía: Groq directo: sin clave de Groq en Ajustes → Claves: la llamada real no se hizo (FALTA previa; no se inventa ni se pide prestada); Groq por el proxy: sin clave de Groq en Ajustes → Claves: la llamada real no se hizo (FALTA previa; no se inventa ni se pide prestada); Gemini directo: sin clave de Google Gemini en Ajustes → Claves: la llamada real no se hizo (FALTA previa; no se inventa ni se pide prestada)

Regla: un camino entra al router automático solo si su llamada real salió bien aquí.
