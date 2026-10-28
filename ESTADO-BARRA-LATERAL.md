# ESTADO — Barra lateral 0.4.5 (t-barra-lateral-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_barra_lateral.py 100`, `… 150` y `… 100 clasica` (`GROWI_BRIDGE_CTK=0`).
  - Arranca la app real desde una copia, en el puerto de prueba 8796, en tema oscuro.
  - **Ventana siempre oculta** (pedido de Leandro: el PC está en uso). La raíz nace en `withdraw()`;
    `show_window` y la mascota se neutralizan. Se mide con `cget`/`winfo_req*`, y los clics corren el manejador
    enlazado al evento. Capturas solo con `PRUEBA_VER=1`.
  - Empieza sin tareas ni gasto (contadores en 0). Después siembra 7 tareas, 2 resultados de hoy, 2 fallos del
    mapa y 3 modelos (contadores en N).
- Evidencia: `pruebas/evidencia/barra-lateral/`: `evidencia-100-ctk.json`, `evidencia-150-ctk.json`,
  `evidencia-100-clasica.json` y capturas `100-ctk-*` y `150-ctk-*`.

## LISTO
1. **Barra fija de 232 px** (`BARRA_PX`), con el fondo `sidebar` de los tokens. Marca compacta:
   - avatar `growi.png` de 40 px y «Growi Bridge»;
   - debajo, a todo el ancho, «Versión … · carril A» y los permisos. Al lado del avatar se cortaban a 150 %, por
     eso se movieron debajo.
2. **Navegación con iconos y contadores reales.**
   - Iconos de trazo de **Segoe Fluent Icons** (viene con Windows 11). Si no está, Segoe MDL2 Assets; si
     tampoco, sin iconos.
   - Glifos: Estado E9D9 (pulso), Carpetas E8B7, Skills EA86 (pieza), Pantalla E7F4, APIs E8D7 (llave),
     Modelos E9F5, Tareas E9D5 (lista), Recursos E9D2 (gráfico), Ajustes E713 y Registro EA37. Se revisaron
     en la captura.
   - Contador nuevo en **Estado**: las filas del mapa de disponibilidad en «falla». Tareas y Modelos usan los
     contadores que ya había (cola y `ollama list`).
   - El 0 se muestra. La fila activa queda resaltada entera: icono, texto y contador.
3. **Medidor «Consumo hoy»** sale de `day_by_model()`, la misma fuente que el consumo vivo y la estadística
   «Gasto de hoy».
   - En grande, el dinero **real**. Debajo, «equivalente Max $X · N tareas terminadas».
   - El real y el equivalente **no se suman**: el equivalente no es dinero pagado.
   - Si no se puede leer, dice «sin dato». Un clic lleva a Tareas.
4. **Tarjeta del guardrail, fija abajo.**
   - Muestra el nivel en palabras: «Hazlo sin preguntar» con punto verde; los otros niveles con punto azul.
   - Debajo, «N en espera de tu aprobación», del mismo hilo que la fila de Tareas (`_ESP`). Si no se puede leer
     lo dice.
   - Clic, Intro o Espacio llaman a `abrir_permisos()`, el mismo de «Cambiar nivel»: lleva a Ajustes → Permisos.
5. **Interruptor de la mascota en CustomTkinter** (`CTkSwitch`).
   - Mismo comportamiento y mismo ajuste (`mascot`) que el clásico.
   - Funciona igual con `set_switch()` de `refresh_ui`.
   - Foco con borde azul; Espacio e Intro lo cambian.
6. **Respaldo clásico.** Con `GROWI_BRIDGE_CTK=0`, `piloto_ctk: false` o CTk roto, sale el interruptor clásico.
   El resto de la barra es Tk de todos modos.
   - Foco visible en la navegación (como antes), en el medidor y en la tarjeta (borde de 2 px `#0A84FF`), y en el
     interruptor.
7. **Cabe a la altura mínima.** `_sidebar_need` ahora cuenta el medidor y la tarjeta. En pantallas bajas (150 % en
   1080 px) se compacta en este orden:
   1. las filas de la navegación (ya existía);
   2. el detalle del medidor, que sigue estando en Tareas;
   3. si aún no cabe, la fila «Buscar acciones». Ctrl+K funciona igual.

Arreglos de paso:
- **Gate**: el smoke lanza la app con todas sus ventanas ocultas (`lanzar-oculto.py`).
- **Gate**: el tope del smoke pasa de **30 a 60 s**. Con el PC en uso, la app abre el puente en 25-34 s, y HEAD
  tarda lo mismo (25,1 s las dos versiones en la misma medida).

## Evidencia (100 % CTk / 150 % CTk / 100 % clásica)
| Criterio | Resultado |
|---|---|
| (a) 232 px y marca | ancho `232` (150 %: `348` = S(232)); textos «Growi Bridge» y «Versión 0.2.0-alpha · carril A / Con permisos de administrador»; avatar sí; iconos Segoe Fluent Icons |
| (b) contadores con 0 | Estado `0` · Modelos `0` · Tareas `0` (las 3 variantes) |
| (b) contadores con N | pantalla Estado 2 · Modelos 3 · Tareas 7 = esperado 2 · 3 · 7 (las 3 variantes) |
| (c) Consumo hoy | con 0: «$0.00 real / equivalente Max $0.00 · 0 tareas terminadas». Con N: «$0.00 real / equivalente Max $0.38 · 2 tareas terminadas»; `day_by_model`: real 0, equiv 0.38, n 2 → **cuadra** |
| (d) guardrail | inicial «Preguntarme siempre» (azul) → radio real de Ajustes «solo lo delicado» → settings `delicado` y la tarjeta «Preguntarme solo lo delicado» → `nunca`: «Hazlo sin preguntar» con `#34C759`. Clic → página `ajustes`; Intro → `ajustes`. Foco: `takefocus 1`, borde `#0A84FF` |
| (e) interruptor | CTk (`_SwitchBarra`) y clásico (`Canvas`): off → clic → settings `mascot: true`, dibujo on, mascota on → clic → `false`, off. `set_switch(True)` cambia el dibujo sin tocar el ajuste |
| (f) CTk bloqueado | `GROWI_BRIDGE_CTK=0`: interruptor `Canvas`, log «interruptor clásico», todo lo anterior igual, **0 tracebacks** |
| altura mínima | 100 %: minsize 820×763, la barra pide 711 px → cabe. 150 %: minsize 1230×967 (+31 px de título = 998 < 1032 del área de trabajo), la barra pide 865 → cabe, compactada |
| Tracebacks | 0 en el log de las 3 variantes |

**Arranque** (`build_gui`, misma prueba, 100 % CTk, 3 tandas alternadas, PC en uso):
- antes (HEAD): 21,2 / 19,1 / 16,6 s;
- después: 29,0 / 21,0 / 17,0 s.

El ruido de la máquina es mayor que la diferencia. La barra en sí se mide en el log: **145-303 ms**, interruptor
CTk incluido. Con `GROWI_BRIDGE_CTK=0`, `build_gui` tarda 2,8-5,3 s. Casi todo el resto es el Ajustes de CTk
(ver la observación en `ESTADO-FASE-3.md`).

(g) **Capturas** a 100 % y 150 % (simulado, `GROWI_BRIDGE_DPI=144`) en `pruebas/evidencia/barra-lateral/`: ceros,
con N, guardrail «nunca», tras el clic y, a 100 %, altura mínima. Se tomaron **antes** de que Leandro pidiera no
mostrar ventanas. El resalte de fila entera es posterior a las capturas: lo comprueba la prueba oculta, no hay
captura nueva. Para tomarlas otra vez, a pedido: `PRUEBA_VER=1 python pruebas/prueba_barra_lateral.py 150`.

## FALTA
- Los **botones de navegación siguen en Tk clásico** con icono, como pide la regla CTk: solo el pie se convierte.
- **150 % real** de Windows: sigue simulado, como en todo el 0.4.5.
- La barra lateral sigue usando el sondeo del mapa para «conectado» (`conn_chip`). Eso es el #19.

## CÓMO PROBARLO
- `python pruebas/prueba_barra_lateral.py 100` (y `150`, y `100 clasica`). Es oculta: no abre ventanas.
- En la app: la barra a la izquierda. Cambiar el nivel en Ajustes cambia la tarjeta; un clic en la tarjeta lleva a
  Permisos.
