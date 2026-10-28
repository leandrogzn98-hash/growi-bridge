# Estado: detector de Avast (t-detector-avast)

Rama `Claude`, 28 oct 2026. **LISTO.**

## 1. Comparación con t-ip-estable (fase A), lo primero
Leídos `share\outbox\ESTADO-IP-ESTABLE*.md` (sobre todo la corrección 3) y el
código (bloque `t-ip-estable`, que dice «el detector de Avast vive aquí:
t-detector-avast no se construye aparte»).

| Subfunción | ¿Existía? | Qué se hizo aquí |
|---|---|---|
| 2. Detectar el servicio de Avast VPN **en vivo** y avisar «¿Lo paro?» | **SÍ** (`avast_servicios` / `avast_comprobar`). Nombre real buscado en vivo: **`SecureLine`** («Avast VPN», `VpnSvc.exe`). Aviso «Avast VPN está activo: puede cortar el túnel. ¿Lo paro?», verificado con el servicio real arrancado | Solo verificado. Hoy en este PC: `SecureLine`, parado, inicio manual |
| 5. Parar Avast con confirmación; nunca solo | **SÍ** (`_avast_accion` / `avast_parar` / `avast_inicio`). Probado sin administrador (dice «hace falta administrador» y no finge) y con él (STOPPED) | Solo verificado (en el código y en su ESTADO). No se paró nada en esta sesión |
| 4. Registro de caídas con causa | **A medias.** Se escribía en `tunel-caidas.log` (proxy caído, Tailscale caído, apagón), pero la app **solo mostraba el número** | **Nuevo:** botón **«Ver caídas del túnel»** (Estado → Salida a internet) con el registro, lo más nuevo arriba (`tunel_caidas_ui`) |
| 3. Vigilar Tailscale atascado en «Starting…» + botón de reinicio | **NO**: solo se miraba si la IP de Tailscale estaba o no | **Nuevo:** `_ts_vigia()` (cada ~60 s en el vigía de salida) lee `tailscale status --json` → `BackendState`. Más de **5 min** en `Starting` → aviso una vez + caída apuntada con la causa probable («Avast VPN («SecureLine») está activo y compite por las rutas» si corre, o «el servicio de Tailscale se quedó colgado arrancando»). Al volver a `Running` se apunta la vuelta. En la tarjeta: texto con la causa y **«Reiniciar el servicio de Tailscale…»** (solo activo con el aviso), que **pide confirmación** y hace `Restart-Service -Name 'Tailscale'` (el servicio se llama `Tailscale`, comprobado con `sc query`). Nunca reinicia solo |

## Verificación (`pruebas/prueba_detector_avast.py` → `pruebas/evidencia/detector-avast/evidencia.json`)
| Prueba | Resultado |
|---|---|
| Datos reales | `tailscale status --json` → **Running**; servicios de Avast reales: `SecureLine` («Avast VPN»), **stopped**, inicio **manual** |
| «Starting…» (tiempo simulado; atascar Tailscale de verdad cortaría el túnel en uso) | 0 min y 3 min: sin aviso. **6 min:** aviso «Tailscale atascado arrancando» y caída apuntada: «cayó: Tailscale (VM↔PC) \| causa probable: el servicio de Tailscale se quedó colgado arrancando \| lleva 6 min en «Starting…»». Vuelta a `Running`: «volvió: Tailscale (VM↔PC)» |
| Registro consultable | La ventana «Caídas del túnel» muestra esas líneas, lo más nuevo arriba |
| Reinicio sin pedirlo | `tailscale_reiniciar_ui` pregunta («Voy a reiniciar el servicio «Tailscale»… ¿Lo reinicio?»); con **No**, **0 comandos** lanzados |

## FALTA / notas
- No se reinició el servicio de verdad: cortaría el túnel que usa la VM.
  `Restart-Service` necesita administrador; la app corre elevada.
- La causa «Avast activo» sale cuando `SecureLine` está running. Hoy está
  parado, así que la prueba dio la otra causa; el camino es el mismo `if`.
