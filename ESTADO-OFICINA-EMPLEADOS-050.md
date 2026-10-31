# ESTADO — t-oficina-empleados-050 (Oficina 0.5.0, spec 11 de 18)

**Fecha:** 30 oct 2026. **Veredicto:** LISTO el sistema y la detección real. El arte es BORRADOR (mismo bloqueo de licencia y paleta que los specs 9 y 10). **La prueba de entrecerrar los ojos NO pasa del todo:** queda medida y anotada abajo.

## Dónde está
- Empleados: `oficina/arte/generar_empleados.py` → `assets/office/characters/skins/{sonny,opus,haiku,dex,blender,tripo,hermes_directo,hermes_ollama,mensajero}/`.
- `estatura_px` en `skin.json` (Opus +2, Haiku −2): `paperdoll.estatura()` estira o encoge las piernas. Los pies se quedan en su sitio y la cabeza chibi no cambia.
- `oficina/personal/deteccion.py` (solo lectura) contiene tres cosas:
  - `detectar()`
  - `silla_especialista()`
  - `revisor_de()`
- Capturas: `oficina/arte/vista_empleados.py`.

## LISTO (evidencia en `pruebas/evidencia/oficina-empleados-050/`)
| # | Subfunción | Evidencia | Resultado |
|---|---|---|---|
| 1 / a | 9 empleados con su `skin.json` | `hoja-14-x4.png` | Sin corbata, con un detalle cada uno: Sonny gorra naranja al revés + taza; Opus gafas redondas + bufanda (+2 px); Dex teclado bajo el brazo; Blender delantal + cubo naranja/azul; Tripo delantal + cohete blanco; Hermes Directo chip dorado; Hermes Ollama gorra blanca; Mensajero gorra marrón + bandolera; Haiku pequeña (−2 px), naranja claro, con bloc. `validate_skins.py`: los 14 skins OK. |
| 2 / b | Sillas vacías de Gemini con cartel | `gemini-sillas-vacias.png` | «Flash — por instalar» y «Pro — por instalar», con cartel «Gemini — en obras» y polvo. Gemi está porque agy responde, pero el departamento no tiene empleados. |
| 3 / c | Especialistas | `deteccion.silla_especialista()` | Sin tarea: sala de espera. Con una tarea que los usa: se sientan en el departamento de su motor (probado: Blender + claude → claude; Blender + llama → local). **FALTA en parte:** el plano no tiene sillas de visita en cada departamento, y cola-live no dice qué skill o herramienta usa cada tarea. Hoy la oficina no puede saberlo, así que no los mueve. |
| 4 / d | Haiku y la revisión | `deteccion.revisor_de()` | Haiku tiene su escritorio pequeño en la esquina de Claude (`plano.json`). La regla honesta es: **se ve revisando quien revisa de verdad** (`runner-live.revision.motor/modelo`). Hoy, en la app instalada, la revisión la hace **ollama**: `revisor_de` devuelve `hermes_ollama`, no Haiku. Haiku solo aparece revisando cuando la revisión corre con claude-haiku. |
| 5 / e | Detección real | `deteccion-real.json` | Contra `runner-status.json` de la app instalada (solo lectura), `engines.json`, skills y `blender.exe`: **13 de 14 detectados**. **Mensajero 3D: silla vacía** («meshy: falta la clave en APIs»). Tripo sí: skill de Bridge (`growi-bridge\skills\tripo`). Blender: herramienta de Bridge (Blender 5.2). Gemi: agy con sesión iniciada. Claude, Codex, llama y ollama disponibles. Los modelos Sonnet, Opus y Haiku se dan por presentes porque Claude Code está; el alias no se prueba por separado (anotado en el motivo). |
| 6 / f | Prueba de entrecerrar los ojos | `entrecerrar-ojos.png`, `vista-empleados.json` | Medida objetiva: cada silueta a 16×24 con desenfoque, distancia media por píxel. **Resultado:** los pares más parecidos son Luma~Tripo 5,6 (los dos con coleta oscura), Hermes Directo~Blender 5,7 y Blender~Tripo 6,6 (mismo delantal gris). Están más cerca que el par Hermes, que sí debe parecerse. El más distinto es Growi~Opus (40,6). Growi, Opus, Gemi, Cody y Sonny se distinguen bien. **No pasa del todo:** cubo, cohete y chip son demasiado pequeños para leerse borrosos. |
| 7 / g | Coordinador nocturno | `plano.json` (`silla_vigilante`) | Su puesto junto a la entrada lleva el cartel «Turno de noche». **Su color está POR DEFINIR con Leandro:** FALTA, no se inventa skin. |
| 8 / h | Runa | `runa-mesa-despacho.png` | En la mesa de despacho, bajo el tablero de la cola, con tableta y pin ámbar «1». |
| 9 / i | Fortalezas y proveedores | abajo | Ningún proveedor tiene silla ni sprite en la v1. |

## Contexto (§11–§13), tal como lo da el spec
- **Claude** (Clau, Opus, Sonny, Haiku): código agentic largo, documentos y planes, revisión y QA (Haiku), razonamiento pesado (Opus).
- **Codex** (Cody, Dex): código a escala de repo. Astra es la máquina del taller de Codex, no una persona.
- **Gemini** (Gemi, en obras): multimodal, contexto enorme, ecosistema Google, con agy como vía sin clave API.
- **Mantenimiento** (Luma, Hermes Directo, Hermes Ollama): limpieza y orden, tareas pequeñas y rápidas, privacidad y respaldo sin nube.
- **Skills:** cuarto de herramientas compartido; ninguna es de un departamento.
- **Subagentes:** cuadrilla flotante.
- **Proveedores externos:** Gumloop, DeepSeek, Firecrawl, Bright Data, Apify, Resend, ElevenLabs, Meshy, Leonardo, API de Claude de pago, Zenmux, Meta Ads, Stripe/Shopify, GitHub, Railway/Hostinger/VPS, Descript, Granola, Mobbin/MagicPatterns/Framer. **Sin silla, sin escritorio y sin sprite en la v1:** trabajan fuera y Runa los llama desde su tableta.

## FALTA
1. **Arte final con retoque humano.** Que las siluetas de Blender, Tripo y Luma, y la de Hermes Directo frente a Blender, se distingan más: delantal de distinto color o tamaño de accesorio. La medida para repetirla está en `vista_empleados.py`.
2. **Sillas de visita** para los especialistas, y que cola-live publique las skills o herramientas de cada tarea.
3. **Color del vigilante:** lo decide Leandro.
4. El texto de las capturas usa la fuente por defecto de Pillow («—» y «á» salen como cuadros). Es solo en la captura de revisión.

## COMO PROBARLO
```
python oficina\arte\generar_empleados.py
python oficina\arte\validate_skins.py --autoprueba
python oficina\personal\deteccion.py            # detección real contra la app instalada
python oficina\arte\vista_empleados.py salida\  # hoja de los 14, entrecerrar, Gemini, Runa
```
