# ESTADO — Estado con tarjetas de salud y de métrica (t-estado-tarjetas-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_estado_tarjetas.py <dpi> [variante]`. Es **oculta**.
  - Siembra resultados de 3 días: hoy 3, con 30, 60 y 90 s y $0.10, $0.20 y $0.05; ayer 2; hace 5 días 1.
  - Tras el arranque, deja en `motores-salud.json` a claude sano y a meshy **sin registro**. El healthcheck del
    arranque reescribe ese archivo, por eso se prepara después.
- Evidencia: `pruebas/evidencia/estado-tarjetas/evidencia-*.json`.

## LISTO
1. **Tarjetas de salud.** Sección «Salud», bajo el botón de encendido, con una tarjeta CTk (`CTkFrame`, esquinas 10,
   borde de 1 px) por servicio y por motor, en dos columnas. Cada una lleva punto de color y estado **real**:
   - **Puente / Runner**: el estado del propio servicio (encendido y puerto; encendido y cuántas en cola).
   - **Proxy**: la última prueba (la fila `proxy` del mapa, con su frase y su ms). Sin prueba: «sin datos».
   - **Cada motor de `engines.json`**: el último healthcheck de `motores-salud.json` (disponible y versión con la
     hora, o el motivo). Sin registro: «**sin datos: aún no se comprobó**». Desactivado: lo dice.
2. **Tarjetas de métrica.** 4 tarjetas con **número grande** y **sparkline** de los últimos 7 días:
   - Tareas terminadas hoy (`*.result.json` por `finished_at`).
   - Tiempo mediano hoy (`duration_s`).
   - Gasto real hoy y Equivalente Max hoy, de **`day_by_model`**, la misma fuente que el consumo vivo y la barra
     lateral. Real y equivalente van **separados**: el equivalente «no es dinero real».
   - La línea es un Canvas: solo se dibuja la gráfica, con el día de hoy marcado. Sin ningún dato: «sin datos».
3. **Tarjeta del mapa.** «Mapa de disponibilidad» sigue con su estilo de tokens (#1). «Ver el mapa» conserva el
   resaltado del #3: borde azul `#0A84FF` y fondo elevado durante 3 s. No se reconstruyó.
4. **Banner.** La decisión es la misma (`runner_modelo_probe` y `cloud_banner_decidir`, sin cambios). Se corrigió
   **un fallo de cómo se mostraba**: se escondía comprobando `winfo_ismapped()`, que es falso siempre que Estado
   no está a la vista. Un banner que dejaba de tocar mientras estabas en otra página seguía puesto al volver. Ahora
   usa `winfo_manager()`.
5. **Respaldo, foco, arranque y DPI.**
   - Sin CTk, con `piloto_ctk: false` o con `GROWI_BRIDGE_CTK=0`, las mismas tarjetas salen con `tk.Frame`.
   - Las tarjetas son de lectura: no hay controles nuevos que enfocar. El encendido, los interruptores y el mapa
     siguen con su foco.
   - Los textos van en `tk.Label` sobre la tarjeta CTk: un `CTkLabel` por renglón alargaba el arranque.
   - Las tarjetas se dibujan **nada más abrir la ventana**, con «Cargando…» mientras tanto (como t-carga-300ms).
   - El texto se parte al ancho real de cada tarjeta: dos columnas caben a ventana mínima a 100 % y a 150 %.
   - Se repintan al abrir Estado y cada 10 s mientras está a la vista. Las métricas, solo si cambian los
     resultados o el día.

## Evidencia (100 % CTk; 150 % y las 3 de respaldo dan lo mismo)
| Criterio | Resultado |
|---|---|
| (a) salud real | Puente «Encendido, puerto 8781» (= `state.bridge`); Runner «Encendido · 0 en cola»; Proxy «Conectado — sales por EEUU (814 ms)»; Claude «Disponible · 2.1.312 · comprobado 14:37»; Codex «Disponible · codex-cli 0.160.1»; Ollama «Disponible · ollama version is 0.40.10»; Local Hermes (llama) **rojo** «No disponible: sin respuesta de 127.0.0.1:8080 en 2 s»; Gemini rojo «sin credencial…»; **Meshy «sin datos: aún no se comprobó»** (gris) |
| (b) métricas = fuente | pantalla: Tareas **3** («6 en 7 días»), Tiempo mediano **1:00**, Gasto real **$0.00**, Equivalente Max **$0.35** («$0.80 en 7 días»). Fuente `estado_metricas`: tareas `[0,1,0,0,0,2,3]`, medianas `[–,20,–,–,–,45,60]`, equivalente `[0,0.15,0,0,0,0.30,0.35]`; `day_by_model()` de hoy: real 0, equivalente 0.35 → **cuadra** con lo sembrado (3 hoy, mediana de 30/60/90 = 60 s, 0.10+0.20+0.05) |
| (c) sparkline | tareas: 7 puntos, línea y punto de hoy en el Canvas (y=4, el máximo); mediana: 3 puntos (los días con dato); gasto real: 7 puntos planos en 0 (no se inventa una curva) |
| (d) mapa | «Ver el mapa» → borde 2 px (3 px a 150 %) `#0A84FF`, 85 widgets resaltados |
| (e) banner | probe `nube` (claude-opus-5-5) → `mostrar: false` y el banner **no** está empaquetado → cuadra |
| (f) respaldo | `clasica`, `sinctk` y `flag`: `_KitTk`, tarjetas `Frame`, (a) a (e) igual; **0 tracebacks** |
| DPI, ventana al mínimo | media columna 247 px (100 %) y 370 px (150 %); el texto más ancho con su margen ocupa 238 y 363 → caben 2 columnas |
| arranque (`build_gui`, 100 %, alternado) | antes 14,8 / 14,9 s; después 13,4 / 13,0 s, dentro del ruido. Las tarjetas se dibujan justo después de abrir: **347-371 ms** |

## FALTA
- **(g) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro. Para tomarlas:
  `PRUEBA_VER=1 python pruebas/prueba_estado_tarjetas.py 100` (y `150`).
- La tarjeta Servicios (con los interruptores) y el panel del gateway se quedan como estaban. Que la barra
  lateral, el banner, el encendido y Servicios digan lo mismo es el #19, `t-estado-consistencia-045`.

## CÓMO PROBARLO
- `python pruebas/prueba_estado_tarjetas.py 100`, y `150`, `100 clasica`, `100 sinctk` y `100 flag`.
- En la app: Estado, bajo el botón de encendido: «Salud» y «Métricas».
