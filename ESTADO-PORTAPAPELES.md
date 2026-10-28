# ESTADO — Historial del portapapeles (t-portapapeles)

Rama `Claude`. Prueba: `pruebas/prueba_portapapeles.py`. Usa una copia aislada y **el portapapeles real de
Windows**: guarda lo que hubiera copiado antes y lo devuelve al terminar. Evidencia:
`pruebas/evidencia/portapapeles/evidencia.json`.

## LISTO
1. **Solo texto, 30 días**: un hilo mira cada segundo el número de secuencia del portapapeles y, si cambió y
   el historial está encendido, lee **solo texto** (`CF_UNICODETEXT`) y lo guarda con su fecha. Pasados 30
   días se borra solo (al guardar), y hay un tope de 2.000. Nada de imágenes ni archivos.
2. **Buscable desde la paleta**: lo que escribes en Ctrl+K también busca en lo copiado (por palabras, lo más
   reciente primero, sin IA). Sale en la sección «Portapapeles (Intro: copiar)» e **Intro lo copia de
   vuelta**.
3. **Nunca contraseñas ni nada sensible**:
   - Se respeta lo que los gestores de contraseñas marcan como no-monitorizable
     (`ExcludeClipboardContentFromMonitorProcessing`, `Clipboard Viewer Ignore`,
     `CanIncludeInClipboardHistory = 0`).
   - No se guarda lo que copien las apps que marques como sensibles (`portapapeles_apps_sensibles`, por
     nombre del .exe).
   - No se guarda lo que **parece** contraseña, clave o token (`sk-…`, `ghp_…`, `AKIA…`, JWT, hex/base64
     largos, o una sola palabra de 8-64 con 3 tipos de carácter).
   - En el registro solo queda «no guardado (motivo)», nunca el contenido.
   - Si algo se cuela: en «Ver…» se borra un ítem en un clic o se marca **«No guardar nunca esto»**, que
     guarda el hash, no el texto.
4. **Opt-in y apagado en un clic**: **apagado por defecto**. Se enciende en Ajustes → Datos y respaldo →
   «Historial del portapapeles», con la explicación («Guarda lo que copias, solo texto, 30 días, en tu PC…»).
   Apagarlo **borra lo guardado**, con confirmación; si dices «no», el interruptor vuelve a encendido.
5. **Todo local**: `portapapeles.json` en la carpeta de Bridge, **fuera de `share\`**, que es lo único que ve
   el puente. Git lo ignora y la exportación de configuración no lo incluye. «Ver…» (Ajustes o Ctrl+K)
   enseña todo lo guardado, con «Borrar todo».

## Evidencia
| Criterio | Resultado |
|---|---|
| apagado por defecto | `pp_activo: false`; lo copiado con el historial apagado → 0 guardados |
| (a) 3 textos | «Precio para Aqualine…», «Brief de Summit Maker…» y «Mensaje para Angelis…», cada uno con su fecha |
| (c) secretos | `Xk9#pL2$qW7!` y `sk-ant-api03-…` copiados de verdad → **no guardados** («parece una contraseña, clave o token»); sigue habiendo 3 |
| (b) paleta | buscar «summit taller» → «Brief de Summit Maker…»; Intro → el portapapeles real tiene ese texto |
| «no guardar nunca» | marcado el de Angelis; al copiarlo otra vez → «no guardado (marcado no guardar nunca esto)» |
| (e) local | `app\portapapeles.json`; `dentro_de_share: false`; el puente no lo nombra; la exportación de config tampoco |
| (d) apagar | 3 guardados → apagar → el archivo **ya no existe**, historial apagado |
| Tracebacks | 0 |

## FALTA
- La detección de «parece contraseña» es una heurística: una frase de varias palabras con datos sensibles sí
  se guarda. Para eso están «Borrar» y «No guardar nunca esto», y la lista de apps sensibles.
- La lista de apps sensibles se edita en `settings.json` (`portapapeles_apps_sensibles`); no tiene editor en
  Ajustes.

## COMO PROBARLO
`python pruebas/prueba_portapapeles.py` (usa tu portapapeles y lo devuelve como estaba). En la app: Ajustes →
Datos y respaldo → «Historial del portapapeles».
