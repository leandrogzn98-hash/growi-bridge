# ESTADO — Configuración inicial en CustomTkinter (t-onboarding-piel-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_onboarding_piel.py <dpi> [variante]`. Es **oculta** y usa el arnés
  `pruebas/arnes_oculto.py`.
  - Arranca con `onboarding_done: false` y recorre los 4 pasos.
  - En el paso 2 mete una **clave inválida** («corta»).
  - En el paso 4, las comprobaciones son reales: proxy, asistente y carpetas.
  - Variantes: `ctk` a 100 % y 150 %, `clasica`, `sinctk`, `flag` y `rota`. `rota` dibuja la chrome CTk y
    luego hace fallar el cuerpo.
- Evidencia: `pruebas/evidencia/onboarding-piel/evidencia-*.json`.

## LISTO
1. **Configuración inicial en CTk.**
   - Fondo con **textura de puntos sutil**: un Canvas con puntos de 1 px cada 22 px, en un gris apenas distinto
     del fondo (`#252525` sobre `#0F0F0F` en oscuro). Se repinta al cambiar el tamaño.
   - **Tarjeta centrada**: `CTkFrame` con esquinas 10 y borde de 1 px. Mide min(680 px, ventana − 40) de ancho y
     el 94 % del alto, y va centrada en los dos ejes.
2. **Puntos de paso arriba.** 4 círculos: azul `#0A84FF` los hechos y el actual, contorno gris los que faltan.
   Al lado, «Paso N de 4». El titular y el texto de cada paso son los mismos de siempre.
3. **Mismo contenido y misma validación.**
   - Los 4 pasos, en el mismo orden y con los mismos textos, opciones y avisos: «¿Quién te ayuda?», «Conectar»,
     «Tus carpetas» y «Comprobación».
   - Los controles son CTk: `CTkRadioButton`, `CTkCheckBox`, `CTkEntry` y `CTkButton`. Usan las mismas
     variables (`choice`, `level`, `folder_vars`, `otro_*`).
   - El guardado y la validación son **compartidos** con la clásica: `_ob_save_step`, `_ob_next`, `_ob_finish`,
     `_ob_run_checks` y `proxy_test_ui`. Los mensajes no pueden diferir.
   - `_ob_cfg` y `_ObCfg` traducen `fg` a `text_color`, para que el mismo código cambie textos y colores en Tk y en
     CTk.
4. **Respaldo y foco.**
   - Sin CTk, con `piloto_ctk: false` o con `GROWI_BRIDGE_CTK=0` sale la pantalla clásica de siempre, intacta.
   - Si CTk **falla al dibujar** un paso, se vuelve a abrir en clásica **desde el mismo paso**
     (`onboarding_paso`).
   - Foco: radios, casillas y botones son paradas de Tab con Espacio (`_teclado_ctk_patch`). El campo de la clave
     es un `CTkEntry`, que toma el foco de forma nativa. El anillo azul es el global.
5. **DPI.** Los textos parten a 600 px como mucho (CTk los escala) y caben en la tarjeta a ventana mínima.

## Evidencia
| Criterio | Resultado |
|---|---|
| (a) CTk, tarjeta centrada y puntos | `piel: ctk`; tarjeta `CTkFrame` con esquinas 10, `place(relx=0.5, rely=0.5, anchor=center)`; textura: 1312 puntos a 900×700 en `#252525`; puntos de paso: `[azul, -, -, -]` → `[azul, azul, -, -]` → … → 4 azules |
| (b) 4 pasos, mismo contenido y validación | CTk y las 4 de respaldo dan **lo mismo**: títulos «¿Quién te ayuda?», «Conectar», «Tus carpetas» y «Comprobación»; botones «Siguiente» y «Lo haré más tarde» (paso 2), «Empezar a hablar» (paso 4); «Atrás» desactivado solo en el paso 1. Clave inválida → **el mismo mensaje**: «clave de Anthropic «principal»: no se guardó: la clave está vacía, es muy corta o tiene espacios dentro». Paso 4 real: proxy «✓ Conectado — sales por EEUU (532 ms)», motor «✓ Claude Code 2.1.312 listo, con sesión Max.», carpetas «✓ Veo 2 carpeta(s)…». Al terminar: `onboarding_done: true`, `assistant: claude`, página Tareas y el ejemplo en el chat |
| (c) respaldo | `clasica`, `sinctk` («ModuleNotFoundError … se usa la clásica»), `flag` y `rota` («CustomTkinter falló al dibujar … se usa la clásica»): pantalla clásica, los 4 pasos, el mismo mensaje, **0 tracebacks** |
| (d) foco | paso 1: 6 `CTkRadioButton`; paso 2: `CTkEntry` y 2 `CTkButton`; paso 3: 4 `CTkCheckBox`, 3 `CTkRadioButton` y 1 `CTkButton`; paso 4: 3 `CTkButton`. Todos con `takefocus 1` y Espacio enlazado (el `CTkEntry`, foco nativo) |
| (e) arranque | `build_gui`: antes 11,3 / 11,5 s; después 11,2 / 11,2 s, igual, porque la pantalla se abre después. Dibujar el primer paso: CTk **391-397 ms**, clásica 329 ms |
| DPI, ventana al mínimo | 100 %: tarjeta 680 ≥ texto 662. 150 %: 1020 ≥ 993 → cabe |

## FALTA
- **(f) Capturas a 100 % y 150 %: no se tomaron**, a pedido de Leandro (no abrir ventanas). Para tomarlas:
  `PRUEBA_VER=1 python pruebas/prueba_onboarding_piel.py 100` (y `150`).
- Oculta, Tk no recorre el orden de Tab: se comprobó cada control, no el recorrido con la ventana visible.
- Visto de paso, fuera de este spec: si `CTkRadioButton` está roto para toda la app, el Ajustes CTk de la fase A
  no cae a la clásica y el arranque falla. Este spec solo cubre el respaldo de la configuración inicial.

## CÓMO PROBARLO
- `python pruebas/prueba_onboarding_piel.py 100`, y `150`, `100 clasica`, `100 sinctk`, `100 flag` y `100 rota`.
- En la app: Ajustes → «Volver a hacer la configuración inicial» (o desde la paleta Ctrl+K).
