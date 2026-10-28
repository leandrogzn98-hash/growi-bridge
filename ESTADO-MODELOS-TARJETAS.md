# ESTADO — Las 4 tarjetas de Modelos en CustomTkinter (t-modelos-tarjetas-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_modelos_tarjetas.py <dpi> [variante]`. Es **oculta** y usa el arnés
  `pruebas/arnes_oculto.py`.
  - Siembra `rules.json` con 2 reglas, una encendida y otra apagada.
  - Los motores, Ollama y la ficha del PC son los **reales** de este PC.
- Evidencia: `pruebas/evidencia/modelos-tarjetas/evidencia-*.json`.

## LISTO
1. **Las 4 tarjetas en CTk**: Tu PC, Quién responde, Qué puede hacer y Reglas. Se construyen con el kit del piloto
   (`_mdl4_construir`): `CTkFrame` con esquinas 10, `CTkLabel`, `CTkButton` y `CTkEntry`, con los colores de
   THEME.
   - El contenido es el mismo, y también los `_widgets["mdl_..."]` y los manejadores: `start_pc_check`,
     `_on_engine_pick`, `_toggle_ability`, `mcp_herramienta_interruptor`, `_add_rule`, `_toggle_rule` y
     `_remove_rule`.
   - Los renderizadores usan `.configure`, que vale en Tk y en CTk, y el kit de su caja.
   - Los interruptores de habilidades y reglas son el mismo `CTkSwitch` de la barra lateral, así que no
     conviven dos estilos.
   - «Dónde te habla» y las listas (Treeview) no se tocan.
2. **Automático primero, con ✓.** En CTk, «Quién responde» es una lista de tarjetas.
   - La primera es «Automático (recomendado)».
   - La elegida lleva **✓**, borde azul y su botón en «Elegido».
   - Las demás llevan «Elegir»; también vale un clic en la tarjeta.
   - El desplegable de siempre sigue como modelo de datos (oculto en CTk). Elegir una tarjeta pasa por
     `_on_engine_pick` y se guarda igual que antes.
3. **Coste por motor** (`motor_coste_txt`):
   - Claude Sonnet, Opus y Haiku: la tarifa de lista de `engines.json` (`precios.por_millon`). Con plan Max añade
     «equivalente, no dinero».
   - Ollama y llama: «$0: corre en tu PC».
   - Codex, motores añadidos y APIs: el **gasto medido** por tarea completada si existe; si no, «**sin datos**».
   - Automático: «sin precio fijo», porque depende del motor que elija.
4. **Tarjeta grande por motor.** Cada una lleva un **punto de color con su estado** (`motor_estado_txt`) y el
   coste. El estado sale sin llamadas lentas: la ventana no se congela.
5. **Respaldo, foco, arranque y DPI.**
   - Respaldo **por tarjeta**: sin CTk, CTk roto, `piloto_ctk: false` o `GROWI_BRIDGE_CTK=0` → la clásica, con
     el desplegable a la vista e interruptores `Canvas`.
   - Foco: los botones son paradas de Tab con Espacio e Intro; el «Elegido» desactivado no lo es.
   - Arranque: ver la tabla. Las tarjetas de motor, las habilidades y las reglas se dibujan **la primera vez que
     se abre Modelos**, porque dibujarlas al arrancar costaba ~2,4 s.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) 4 tarjetas en CTk, mismo contenido | `ctk: true` en las 4; `mdl_specs` / `mdl_specs_detail` `CTkLabel`, `mdl_check_btn` `CTkButton`, cajas `CTkFrame`, `mdl_rule_entry` `CTkEntry`. Tu PC: «RTX 3060 Laptop, 6 GB VRAM, 15 GB RAM y 79 GB libres» = `pc_specs_summary`. Habilidades: 8 de 8 con interruptor CTk. Reglas: interruptores `[true, false]` = `rules.json`. Añadir regla → 3 en el archivo; apagar la 1.ª con su interruptor → `on: false` en el archivo |
| (b) Automático primero con ✓ | primera tarjeta «Automático (recomendado)», ✓, elegida, `settings.motor = "auto"`, ninguna otra con ✓. Elegir «Claude Sonnet» → el ✓ pasa a Sonnet, `motor` se quita y `default_engine = "sonnet"` |
| (c) coste real o «sin datos» | Sonnet «$2 / $10 por millón (entrada / salida, de lista) · con tu plan es equivalente, no dinero»; Opus $4 / $20; Haiku $0.1 / $0.5; **Codex «sin datos»** (no hay tareas medidas); Hermes 3 8B por Ollama «$0: corre en tu PC». Estados: «Disponible» o «Instalado en tu PC (Ollama)» |
| (d) respaldo | `clasica`, `sinctk` y `flag`: las 4 en clásica, `Label`, desplegable visible (10 valores, el primero «Automático (recomendado)»), 8 interruptores `Canvas`, reglas igual; **0 tracebacks** |
| foco | botones `takefocus 1` y Espacio enlazado |
| DPI, ventana al mínimo | 100 %: contenido 478 ≥ línea 291 y estado 450. 150 %: 717 ≥ 444 y 675 → cabe |
| (e) arranque (`build_gui`, 100 %, tandas alternadas) | dibujando todo al arrancar: antes 13,7 / 12,6 / 12,3 / 12,5 s y después 15,8 / 15,2 / 14,6 / 15,2 s (**+2,4 s**). Por eso se difiere. Ya diferido: después 12,9 / 14,5 s y antes 12,8 / 14,2 s, dentro del ruido. Las 4 tarjetas solas: 8-20 ms cada una |

## FALTA
- **(f) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro (no abrir ventanas). Para tomarlas:
  `PRUEBA_VER=1 python pruebas/prueba_modelos_tarjetas.py 100` (y `150`).
- El coste de Codex y de los motores añadidos depende de que haya tareas medidas. En este PC no hay, así que
  dicen «sin datos».
- El estado de los motores HTTP es el que se comprobó al armar la lista: la tarjeta no vuelve a llamar al
  servidor, para no congelar la ventana.

## CÓMO PROBARLO
- `python pruebas/prueba_modelos_tarjetas.py 100`, y `150`, `100 clasica`, `100 sinctk` y `100 flag`.
- En la app: Modelos → «Quién responde». Automático va primero con ✓; cada motor muestra su estado y su coste.
