# ESTADO — Voz con ElevenLabs, BYOK (t-voz-elevenlabs)

Rama `Claude`. Prueba: `pruebas/prueba_voz.py`. Usa la app real en una copia (puerto 8797) **sin clave de
ElevenLabs**; no gasta cuota. Evidencia: `pruebas/evidencia/voz-elevenlabs/` (`evidencia.json` + 2 capturas).

## LISTO
1. **ElevenLabs BYOK**: es un proveedor más en Ajustes → Claves («ElevenLabs (voz)»). La clave va al
   Credential Manager, nunca a un JSON, con proveedor + etiqueta.
   - «Probar clave» pide la suscripción (`/v1/user/subscription`), que **no gasta**.
   - La cabecera es `xi-api-key`.
   - Ventana «Narrar con voz» (Ctrl+K): selector de voces de la cuenta, con **las españolas primero** y las
     demás marcadas «(no es en español)»; modelos `eleven_v4` / `eleven_v4_turbo`.
   - **Sin clave: «Sin clave… No se finge ninguna voz»** y el botón Narrar desactivado.
2. **Contador real**: `character_count` / `character_limit` de ElevenLabs, leído al abrir, antes de cada
   narración y después. Se muestra con su fuente. **Aviso al 80 %** en rojo en la ventana, y un toast tras
   una narración que lo cruce.
3. **Aprobación por narración**: antes de generar, una confirmación con la voz, el texto, los caracteres y lo
   que suponen («73 de los 1.800 que te quedan este mes, 0,7 % de la cuota»). Sin el sí, `voz_narrar` **no
   llama a ElevenLabs** y no escribe nada.
4. **Salida junto al proyecto**: `narracion-<fecha>.mp3` + `.txt` en la carpeta elegida (por defecto
   `outbox\narraciones`). El `.txt` lleva el texto, la voz (y si no es española), el modelo y la cuota
   antes → después según ElevenLabs. Cada narración queda en `voz-registro.jsonl`.

## Evidencia
| Criterio | Resultado |
|---|---|
| sin clave | `voz_estado` → «sin clave de ElevenLabs en Ajustes → Claves»; ventana con botón desactivado (captura 1); narrar aprobado sin clave → «no se finge una voz» |
| (c) sin aprobación | `voz_narrar(aprobado=False)` → «no aprobada: no se generó nada»; **0 llamadas** a ElevenLabs; 0 archivos. Por la ventana, «no» en la confirmación → nada generado |
| (d) aviso 80 % | con un contador **SIMULADO** (8.200 / 10.000, marcado así en pantalla) → «Llevas el 82 %… queda poco.» (captura 2) |
| voz no española | «OJO: esta voz no está marcada como española.» |
| Tracebacks | 0 |

## FALTA
- **(a) Una narración real en español con su .mp3** y **(b) el contador real antes y después**: no se
  hicieron. En esta sesión **no se autorizó usar las credenciales** del usuario, y la copia de prueba no
  tiene clave. Además cada tts gasta cuota y necesita el sí de Leandro.
- Para cerrarlo:
  1. poner la clave en Ajustes → Claves → ElevenLabs y pulsar «Probar clave» (no gasta);
  2. Ctrl+K → «Narrar con voz»;
  3. elegir una voz española y un texto corto;
  4. aceptar, y comprobar el .mp3 y el contador antes → después.
- Los nombres de modelo `eleven_v4` / `eleven_v4_turbo` son los del spec. Con la clave, `/v1/models` (no
  gasta) dirá si coinciden.

## COMO PROBARLO
`python pruebas/prueba_voz.py` → `pruebas/evidencia/voz-elevenlabs/`. En la app: Ctrl+K → «Narrar con voz».
