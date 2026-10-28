# ESTADO — Teclado y foco (t-teclado-foco)

Rama `Claude`. Prueba: `pruebas/prueba_teclado_foco.py`. Usa la app real en una copia (puerto 8797)
**manejada solo con el teclado de verdad** (SendInput). Un único clic inicial en un texto inocuo trae la
ventana al frente: Windows no deja a otro proceso robar el foco. Evidencia: `pruebas/evidencia/teclado-foco/`
(`evidencia.json` + 5 capturas).

## LISTO
1. **Alt + 1..9 / Alt + 0 → páginas**, igual que Ctrl + número: 1 Estado, 2 Carpetas, 3 Skills,
   4 Pantalla, 5 APIs, 6 Modelos, 7 Tareas, 8 Ajustes, 9 Registro, 0 Recursos. Son las 8 del spec más
   Registro y Recursos. Dentro de la paleta, Alt + N sigue eligiendo la fila N. Los atajos salen en la lista
   «?» y en la tabla de reservados de Ajustes → Atajos.
2. **«?» abre la lista de atajos** desde cualquier sitio salvo un campo de texto, donde «?» se escribe. La
   lista es buscable e incluye los de la app y los personalizados (con su combinación actual). Se cierra con
   Esc o con «?» si la búsqueda está vacía. Se detecta por el carácter, así vale con el teclado real (keysym
   `question`) y con texto inyectado (`??`).
3. **Listas con flechas**:
   - Tareas y Skills (Treeview): al entrar con Tab queda elegida la primera fila; Arriba/Abajo mueven;
     **Intro** abre el detalle de la tarea o la carpeta de la skill.
   - Modelos (filas): Arriba/Abajo pasan de fila en fila.
   - La paleta ya lo hacía y sigue igual.
4. **Un solo anillo de foco**: 2 px, **#0066CC** en claro (contraste medido 5,11:1 con el fondo). En oscuro
   se elige el primer azul que llegue a 3:1 contra fondo y tarjetas, calculado, no supuesto. Hay un único
   anillo dibujado encima del control con foco, que lo sigue al hacer scroll. Los controles que ya pintan su
   anillo (interruptores, botón de encendido, campos con borde de foco) lo pintan con ese mismo color, así
   que nunca hay dos.
   - Los botones, interruptores y casillas de **CustomTkinter** ahora entran en el **Tab** y responden a
     Espacio/Intro (antes no se podían alcanzar con el teclado).
   - Los botones de la barra lateral salen del Tab: ponían el rectángulo punteado de Windows, otro estilo.
     Se llega a sus páginas con Alt/Ctrl + número.
5. **Esc cierra** la ventana de delante: la paleta (como antes), la cajita de la mascota y los diálogos
   (reglas, revisor, prueba de corte…). En la ventana principal no hace nada. El Esc del onboarding se
   suma en vez de pisarlo. **Ctrl+K** sigue abriendo y cerrando la paleta.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) Alt + 1..9, 0 | las 10 combinaciones llevan a estado, carpetas, skills, pantalla, apis, modelos, tareas, ajustes, registro, recursos |
| (b) «?» | se abre (19 atajos); buscar «tareas» deja 2 filas; **Esc** la cierra; «?» con la búsqueda vacía la cierra; «?» en el campo de Tareas **se escribe** y no abre nada |
| (c) Tareas | al entrar: `t-teclado-1`; **Abajo** → `t-teclado-2`; **Intro** → detalle «t-teclado-2, pendiente…» |
| (c) paleta | Ctrl+K, escribir «ir a carpetas», **Intro** → página Carpetas y paleta cerrada |
| (d) foco | color #0066CC (5,11:1). Tab en Estado (interruptor, anillo propio azul), Tareas (botón ttk, 1 anillo) y Ajustes (interruptor CTk, 1 anillo): capturas 3-5, nunca dos |
| (e) Esc | paleta cerrada; cajita «Escríbeme» 1 → 0; diálogo «Reglas permanentes» cerrado |
| Tracebacks | 0 |

## FALTA
- El tema oscuro no se probó en esta prueba. El cálculo del color está y elige por contraste medido (≥ 3:1);
  falta una captura en oscuro.
- El orden de Tab es el de creación de los controles: lógico de arriba abajo en cada página, pero no se
  auditó control por control en todas las páginas.

## COMO PROBARLO
`python pruebas/prueba_teclado_foco.py` → `pruebas/evidencia/teclado-foco/`. En la app: pulsa «?».
