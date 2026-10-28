# ESTADO — Banner «Sin conexión con la nube» fiel al runner (t-estado-banner-nube-045)

Rama `Claude`, 28-oct-2026.

- Prueba: `pruebas/prueba_banner_nube.py`. Arranca la app real desde una copia, en el puerto de prueba 8797.
- Evidencia: `pruebas/evidencia/banner-nube/` (`evidencia.json` + 6 capturas).

## 1. Diagnóstico
- **Cómo decidía el banner** (`_refresh_conn_widgets`): `conn_state() in ("local", "sin")`.
  `conn_state()` solo lee el **sondeo del mapa de disponibilidad** (`_AV["rows"]`, fila `claude`). Hay
  conexión si esa fila está en `ok`/`aviso` **y** la ruta es `directo`, o es `proxy` con `state["proxy_on"]`.
  Si no, y Ollama responde, `local`.
- **Dónde divergía**: el runner elige el motor por `engines.json`, el router y los respaldos, y lo ejecuta (lo
  apunta en `runner-status.json` → `current` y en cada `result.json`). El banner **nunca miraba eso**.
  - Un sondeo lento o fallido, o una ruta por proxy sin `proxy_on` (lo que pasa en la copia de prueba), bastaba
    para que saliera «trabajando con el modelo local» aunque el runner siguiera en Opus.
  - Se ve en la evidencia: en (a) el mapa dice `local` y el runner está en `claude-opus-5-5`.

## LISTO
2. **Probe fiel al runner** (`runner_modelo_probe`):
   - Lee `runner-status.json`, la misma fuente del panel: la tarea en curso (motor y `modelo_real`) o, si no
     hay, la **última ejecución**.
   - `ultima_ejecucion` es un campo nuevo que el latido escribe: motor, modelo real, estado y error. Al
     arrancar se toma del `result.json` más reciente, una sola vez.
   - Devuelve `nube`, `local` (con el modelo), `sin_ejecuciones` o `ilegible`.
3. **Banner solo cuando toca** (`cloud_banner_decidir`):
   - **Alarma** (raya naranja) solo si el runner no alcanza la nube de verdad:
     - su última ejecución en la nube falló **por red**; o
     - el sondeo falló **dos veces seguidas**: un fallo suelto lanza una comprobación a los 20 s y no alarma.
   - Con un modelo local, **informa** (raya azul, texto suave): «Trabajando con el modelo local <modelo>».
4. **En vivo**: el tic de la ventana (cada ~5 s) repinta el banner. Leer el archivo es un JSON pequeño, así que
   no congela la ventana y no hace falta reiniciar.
5. **Sin falsos**:
   - Si `runner-status.json` no se lee, o lleva más de 3 min sin latido: «No se pudo leer el estado del runner
     (motivo)», en gris. Ni alarma ni silencio.
   - Un fallo del propio probe también cae ahí.

## Evidencia (la ventana se repinta sola; la prueba no llama al banner)
| Caso | Probe | Banner |
|---|---|---|
| (a) runner en Opus + 1 fallo suelto del sondeo (el mapa dice `local`) | `nube`, `claude-opus-5-5` | **oculto**. Captura `a-opus-sin-banner` |
| (b) runner en local | `local`, `hermes-3-8b-q4_k_m` | «Trabajando con el modelo local hermes-3-8b-q4_k_m (última ejecución …)», raya azul. Captura `b-local-informa` |
| (c1) la última ejecución en la nube falló por red (`Connection error (getaddrinfo failed)`) | `nube`, `fallo_red: true` | «Sin conexión con la nube: el runner no alcanza claude-opus-5-5 (su última ejecución falló por red)», raya naranja. Captura `c-nube-inalcanzable` |
| (c2) el sondeo falla y la comprobación también | `nube` | «… (el sondeo de la nube falló dos veces seguidas)». Captura `c2-sondeo-falla-dos-veces` |
| (d) la nube vuelve (sondeo `ok`) | `nube` | **se quita solo**, sin reiniciar. Captura `d-nube-vuelve` |
| (e) `runner-status.json` roto | `ilegible: JSONDecodeError` | — |
| (e) runner sin latido (simulado: umbral a −1) | `ilegible` | «No se pudo leer el estado del runner (…)», raya gris. Captura `e-no-se-pudo-leer` |
| Tracebacks | — | 0 |

## FALTA
- **La barra lateral** («● Solo local (sin nube)»), los avisos y el router de la app siguen con `conn_state()`
  del mapa. En la captura (b), la barra lateral dice «Solo local» y el banner no alarma. Unificarlo todo es
  t-estado-consistencia-045 (#19): una sola fuente de verdad.
- **«Ver el mapa»** sigue yendo a Estado sin bajar al mapa: eso es t-estado-mapa-045 (#3).
- **El caso «sin latido»** se simuló bajando el umbral. Un runner caído de verdad deja de escribir y el probe
  da «no da señales desde hace N min».

## CÓMO PROBARLO
- `python pruebas/prueba_banner_nube.py`.
- En la app: con el runner en Opus no hay banner. Si encolas una tarea a `llama`, el banner informa del modelo
  local.
