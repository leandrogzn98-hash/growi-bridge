# ESTADO — Tokens Raycast en el tema oscuro (t-tokens-raycast-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_tokens_raycast.py <oscuro|claro> <100|150>`. Arranca la app real desde una copia, en el
  puerto de prueba 8797, con 4 tareas sembradas, y **mide por píxel** en la captura.
- Evidencia: `pruebas/evidencia/tokens-raycast/`: `oscuro-100`, `oscuro-150` y `claro-100`, cada uno con `.json`
  y capturas de Estado, Tareas y Modelos.

## LISTO
1. **Tokens en THEME** (`temas/oscuro-raycast.json`, el tema oscuro por defecto):
   - ventana `#0F0F0F`, tarjeta `#1A1A1C`, línea `#2C2C2E`;
   - texto suave `#9A9AA0`;
   - acento `#FF6363` (fijo `accent`, solo en botones primarios), encendido `#34C759`;
   - aviso `#FA5102`, en curso `#0A84FF` (token `blue`).
   - Dos desviaciones mínimas, por una razón técnica:
     - **El texto es `#F5F5F6`, no `#F5F5F7`.** `#F5F5F7` es exactamente la tarjeta del tema claro, y la tabla
       que traduce colores entre temas confundía el texto con la tarjeta: con `#F5F5F7` los títulos y la barra
       lateral **salían invisibles** (se vio en la captura y se corrigió).
     - **El texto de error es `#E64C51`, no `#E5484D`.** Sobre la tarjeta, `#E5484D` da **4,44:1** y el tema exige
       4,5:1 (el validador lo rechaza). `#E64C51` da 4,57:1 y a la vista es el mismo rojo.
   - El tema claro **no cambia**: `claro.json` está intacto.
2. **Fondo de ventana y tarjetas**: las tarjetas clásicas (`_card`) llevan ahora un borde fino de 1 px en el token
   línea, sin sombra, igual que las de CustomTkinter, que ya lo tenían.
3. **Fuente**:
   - En el tema oscuro, **Inter**, que está instalada: `Inter (TrueType)` en el registro de fuentes de Windows.
     Si un PC no la tiene, cae a Segoe UI y lo dice en el log (`fuente_instalada`). En uso: `fuente_en_uso:
     "Inter"`.
   - El tema claro sigue con Segoe UI.
   - Los **IDs de tarea van en Consolas**: la tabla de Tareas usa el estilo `Tareas.Treeview`.
4. **Densidad**:
   - Las filas de todas las tablas (`Treeview`, `Res.Treeview` y `Tareas.Treeview`) miden **34 px a 100 %**
     (`FILA_PX`).
   - El estado de la fila de Tareas es **punto + etiqueta** (`● en curso`), con el color del estado.
   - Las etiquetas de sección siguen en sentence case y negrita: no había mayúsculas de 9 px.
5. **Regla del acento**:
   - El botón primario clásico (`Accent.TButton`) usa el acento del tema: en oscuro `#FF6363`; en claro el
     mismo azul `#0066CC` de siempre.
   - Las casillas y los radios del guardrail (Ajustes) usaban el acento rojo. Ahora usan el token `blue`: no son
     acciones primarias.
   - **Sin gradientes**: Tk no los dibuja y no hay ninguno.
6. **Barra lateral**: `#141416`, un paso más oscura que la tarjeta.
   - Ojo: el spec dice «ligeramente más oscuro que el contenido», y el contenido (`#0F0F0F`) es aún más oscuro.
     Se siguió la definición del paréntesis: un paso más oscuro que el token tarjeta.

Arreglo de paso: el resumen de Tareas (`tasks_summary`) no tenía ancho de corte y se salía por la izquierda. Ya
corta a 660 px.

## Evidencia (medida, no supuesta)
| Criterio | oscuro 100 % | oscuro 150 % | claro 100 % |
|---|---|---|---|
| (a) píxel ventana / tarjeta / borde / barra lateral | `#0F0F0F` / `#1A1A1C` / `#2C2C2E` / `#141416` | igual | `#FFFFFF` / `#F5F5F7` / `#E5E5EA` / `#F5F5F7` (los tokens de siempre) |
| (c) `#FF6363` fuera de un botón (las 10 páginas recorridas, widget por widget) | **0** | **0** | — (acento azul) |
| (c) dónde sí está `#FF6363` | solo en los botones primarios de cada tarjeta: Guardar, Probar, Instalar, Descargar, Generar…, Pedir cosecha, Validar skills, Exportar | igual | — |
| (d) alto de fila medido en Tareas (`bbox` fila 2 − fila 1) | **34 px** | **51 px** (= 34 a 100 %) | **34 px** |
| (e) fuente de los IDs | `Consolas 10`, `t-ajustar-logo-0428` | igual | igual |
| fuente en uso | Inter | Inter | Segoe UI |
| Tracebacks | 0 | 0 | 0 |

(f) Las capturas a 100 % y 150 % están en `pruebas/evidencia/tokens-raycast/` (`*-estado.png`, `*-tareas.png`,
`*-modelos.png`). El 150 % es **simulado** (`GROWI_BRIDGE_DPI=144`), como en el piloto.

## FALTA
- **Fuente monoespaciada por columna**: ttk.Treeview solo admite una fuente por tabla. Toda la tabla de Tareas va
  en Consolas: los IDs y las cifras quedan alineados, pero también el texto de estado y de motor.
- **El estado como «punto de color + etiqueta»**: el color se aplica a toda la fila, porque ttk no colorea una
  sola celda. Las insignias grandes no existían.
- **Pesos intermedios**: Inter solo está instalada en Regular y Bold, así que las etiquetas «semibold» del tema
  oscuro salen en negrita.
- **Contraste en los botones grises de CTk**: sin revisar uno a uno. Queda para la auditoría (t-auditoria-045).

## CÓMO PROBARLO
- `python pruebas/prueba_tokens_raycast.py oscuro 100`, `… oscuro 150` y `… claro 100`.
- En la app: Ajustes → Apariencia → Oscuro.
