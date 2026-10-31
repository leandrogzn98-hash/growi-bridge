# ESTADO — t-oficina-bocadillos-050 (Oficina 0.5.0, spec 16 de 18)

**Fecha:** 31 oct 2026, 00:10. **Veredicto:** LISTO 6 de las 7 subfunciones. La de los avisos (5) queda **sin cola compartida**: la cola de avisos oficina↔app con deduplicación no existe (duda 20) y, como pide el spec, **no la inventé**. Sí está la política, lista para enchufarse. La oficina no emite avisos propios porque la app ya avisa de los 3 eventos que deben avisarse.

## Dónde está
- `oficina/bocadillos/bocadillos.py`: `resumen_hablado()`, `Bocadillo`, `Gestor`, `estilo()` (las 3 señales), `politica_aviso()`, `LogDiario`, `te_necesitan()`.
- Prototipo: `parches/parche_oficina_bocadillos_050.py`. Reproducible: aplicado al commit anterior da el archivo idéntico.
- Pruebas: `pruebas/oficina_bocadillos_050/prueba_bocadillos.py` (lógica + Hermes real) y `demo_bocadillos.py` (ventana con runner real).

## LISTO (evidencia en `pruebas/evidencia/oficina-bocadillos-050/`)
| # | Subfunción | Resultado |
|---|---|---|
| 1 / a | Bocadillo real | Una respuesta larga se queda en la **primera frase literal** (139 caracteres, cita textual) y el texto completo va al log (`log-ejemplo.md`). Una frase de más de 140 se corta a 140 con «...». Borde de 2 px del color del departamento y punto verde «real». Duración de 2 s + 60 ms por carácter (entre 3 y 10 s), con fundido de 300 ms. El clic lo fija 30 s. En pantalla (`bocadillo-contador.png`): el bocadillo de Growi, con borde ámbar de gerencia y cola hacia el sprite. **Corregido:** se salía por el borde izquierdo; ahora se queda dentro de la ventana. |
| 2 / b | Cola | Con 4 personajes a la vez se ven 3, y el 4.º sale cuando se libera un hueco. Si a un mismo personaje le llega un 3.º, se descarta el más viejo. Nunca hay 2 visibles del mismo. |
| 3 / c | Real o decorativo | Las 3 señales. Real: diálogo con cola recta, punto verde y referencia al log. Decorativo: nube ondulada, gris en cursiva, sin marca, «charla de oficina», `ref_log = None` y **sin entrada en el log**. |
| 4 / d | Resumen hablado con Hermes | **Probado de verdad** con Hermes 3 8B en Ollama ($0), con 5 intentos en dos corridas: **4 de 5 y 3 de 5** cupieron en 140 caracteres (el más largo, 156). No es fiable, así que la vía es la **primera frase literal**, que no depende del modelo. No se finge un resumen. |
| 5 / e | Avisos | `politica_aviso()`: terminada, esperando aprobación y error *avisarían* (clave de dedup `tarea:evento`), pero **la app ya los avisa**: `_watch_families` manda un toast por raíz+estado (aprobada, sin revisión, necesita decisión, fallida) y la espera va en el popup del guardrail. Por la regla «un evento = un aviso», la oficina no los repite. Aceptada, encolada, charla, progreso y resumen no avisan. Texto de aviso con actor + acción + objeto en menos de 15 palabras. |
| 6 / f | Log diario | `<app>/oficina/AAAA-MM-DD.md`: quién → a quién · canal · tipo: texto · costo. La charla no va. En la demo real, la línea del teléfono se escribió sola («Leandro → Growi · teléfono al gerente · …»). Al cerrar el día, un resumen de 3 líneas (cerradas, pendientes, errores) va arriba. Más de 90 días: **se mueve** a `oficina/archivo/` (probado con un día de hace 95 días; no se borra). Búsqueda por texto simple. |
| 7 / g | «Te necesitan: N» | Arriba, desde cola-live: 2 retenidas → «2»; sin señal → «—» (nunca 0); cola vacía → «0». Se ve en las capturas. |

## FALTA
1. **Cola de avisos compartida oficina↔app con dedup (duda 20): no existe.** El toast de la app es `pystray.notify` dentro de su proceso. Mientras no exista, los eventos que solo ve la oficina («no contesta» del spec 13, el recordatorio de 30 min del spec 14) quedan en el log y en los bocadillos, sin toast. Antes de cerrar la 0.5.0 hay que decidir dónde vive esa cola: en la app o en un `avisos.jsonl` con dedup por `tarea:evento`.
2. **Botón «Historial de la oficina» en la app principal** y la tarjeta con el resumen de ayer en el tablón: `LogDiario` tiene `ruta(día)` y `buscar()`, pero la app no tiene el botón (toca `growi-bridge.py`; se haría al instalar).
3. **Bocadillo de varias líneas:** hoy es una sola línea cortada a 260 px. El spec permite hasta 4 líneas. El texto completo sigue en el log.
4. Tipografía pixel: se usa Segoe UI 12 px. Es del arte final.

## COMO PROBARLO
```
python pruebas\oficina_bocadillos_050\prueba_bocadillos.py   # incluye 5 llamadas reales a Hermes en Ollama ($0)
python pruebas\oficina_bocadillos_050\demo_bocadillos.py     # ventana: bocadillo de Growi + log del día + contador
```
