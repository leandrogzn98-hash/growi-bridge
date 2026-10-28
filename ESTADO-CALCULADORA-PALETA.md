# Estado: calculadora en la paleta (t-calculadora-paleta)

Rama `Claude`, 28 oct 2026. **LISTO.**

Si lo que escribes en la paleta (Ctrl+K) es una cuenta, el primer ítem es el
resultado («120*0.4 = 48») e Intro lo copia al portapapeles. Si no es una
cuenta, la paleta busca como siempre.

## Código (`growi-bridge.py`, justo antes de `_palette_sections`)
- `calc_evaluar(q)`: decide si el texto es una cuenta y la resuelve.
  - **Es cuenta** solo si tiene únicamente cifras, espacios, `. , + - * / %`
    y paréntesis, **y** al menos un operador entre números. «2026» o
    «3 tareas» no lo son.
  - **Coma decimal:** si hay coma y ningún punto, la coma es el decimal
    (279,58). Si no, las comas se quitan (1,000).
  - **Evaluación segura:** `ast.parse(mode="eval")` y un recorrido propio
    (`_calc_nodo`) que solo acepta números, `+ - * / %` y signo. **Nunca
    `eval()`.** Cualquier otro nodo (nombres, llamadas, atributos, potencias)
    devuelve «no es una cuenta» y la paleta sigue normal.
  - **Sin crash:** división por cero → «no se puede dividir entre cero»;
    operandos o resultado > 1e15 → «el número es demasiado grande».
- `_calc_item(q)`: el ítem «Calculadora», que va primero.
  `_calc_copiar(valor)` copia con el portapapeles de Tk y muestra el aviso
  «Copiado: 48».
- `_palette_sections`: si es cuenta, devuelve la sección «Calculadora». En
  `_open_palette` se expone `_palette["st"]` (las filas que se ven) para las
  pruebas.
- **Sin divisas ni científica:** no hay tasas, `^`, potencias ni funciones.

## Verificación (app real, teclado de verdad)
`pruebas/prueba_calculadora.py` usa la app en 8797, copia aislada: abre la
paleta, escribe con `SendInput`, pulsa Intro y lee el **portapapeles de
Windows** (`GetClipboardData`). Evidencia en `pruebas/evidencia/calculadora/`.

| | Escrito | Primer ítem / resultado |
|---|---|---|
| a | `120*0.4` | **«120*0.4 = 48»** (captura `1-calculo.png`) |
| b | Intro | Portapapeles de Windows = **«48»**; log «paleta: calculadora: copiado 48» |
| a | `279,58/1070` | «279,58/1070 = 0,2612897196» (coma decimal) |
| a | `1500*0.4` | «1500*0.4 = 600» |
| c | `__import__('os').system('calc')` | **No se evalúa**: la paleta sigue normal («Pedírselo a la IA: …»). No se abrió ninguna calculadora (tasklist: 0 procesos «calc») |
| c | `120/0` | «120/0: no se puede dividir entre cero» (sin crash) |
| c | `99999999999999999*99999999999` | «…: el número es demasiado grande» |
| d | `100 USD a Bs` | No es cuenta: búsqueda normal, **sin tasa inventada** |
| e | `ajustes` | «Ir a Ajustes»: la búsqueda normal sigue igual |
| e | `2026` | No es cuenta (no hay operador): búsqueda normal |

Log sin tracebacks.

## FALTA
Nada del spec. Por decisión del spec no hay conversor de divisas ni funciones
científicas.
