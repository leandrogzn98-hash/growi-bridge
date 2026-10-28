# ESTADO — Onboarding con fallos (t-onboarding-fallos)

Rama `Claude`. Prueba: `pruebas/prueba_onboarding_fallos.py` (app real en una copia, puerto 8797,
`onboarding_done=False`). Evidencia: `pruebas/evidencia/onboarding-fallos/` (`evidencia.json` + 4 capturas).

## Qué se hizo
- **Detección con plan A/B** (`onboarding_detect`): sondea internet (con tope de tiempo por chequeo, nunca
  bloquea; lo que no responde queda en `sin_comprobar`), VRAM (`_ob_vram_gb`) y CLIs. Sin internet → plan B:
  el paso «conectar» se salta solo con nota y queda pendiente «conectar la nube cuando vuelva internet».
- **Salidas por fallo**:
  - sin Claude → «Por instalar», motor local por defecto y pendiente «instalar Claude Code e iniciar sesión»;
  - modelo que cabe (`ob_modelo_que_cabe`): con 6 GB propone un 3-4B en vez de Hermes 8B;
  - proxy caído en el paso 4 → «El proxy no responde ahora. Puedes seguir con el modelo local y reintentarlo
    luego.» con **Reintentar** / **Seguir sin proxy** (queda pendiente);
  - «Otro» pide dos datos (nombre + comando) o «Lo configuro luego».
- **Progreso guardado** (`onboarding_paso`): cerrar a la mitad y reabrir sigue en el mismo paso. Saltar un paso
  lo deja como pendiente.
- **Checklist persistente en Estado** («Para terminar de configurar»): se tacha sola por detección, muestra
  primero lo pendiente (máx. 3 + «… y N más»), se refresca cada 5 s y desaparece cuando no queda nada
  (nunca «0 de 5»).
- **Reinstalación**: si ya hay configuración pregunta «¿La usamos tal cual?» y, si sí, no repite el onboarding.
- **Primera victoria con tarea real**: el ejemplo es «Mira mi carpeta de Descargas y dime cómo la ordenarías…
  (no muevas nada todavía)»; al terminar va al chat. La paleta muestra una vez «Para empezar, pídele algo
  real» con 3 sugerencias.
- **El guardarraíl nunca cambia sin confirmación**: pulsar Siguiente sin tocar el nivel lo conserva; cambiarlo
  pregunta explícitamente y si se dice «no» se queda igual.

## Evidencia (evidencia.json)
| Criterio | Resultado |
|---|---|
| Plan B detectado | `plan: "B"`, `internet: false`, paso 0 → paso 2 con nota |
| Sin Claude | pendiente «instalar Claude Code…», motor por defecto local (Hermes) |
| Guardarraíl, Siguiente sin cambiar | `delicado → delicado`, 0 preguntas |
| Guardarraíl, cambiar y decir no | sigue `delicado`; pregunta «Esto cambia los permisos… ¿Lo cambio?» |
| Reabrir a la mitad | sigue en el paso 2 |
| Saltar → pendiente | «elegir tus carpetas» en pendientes |
| Proxy caído | texto + botones visibles; «Seguir sin proxy» → pendiente |
| «Otro» | `asistente_otro = {MiIA, miia -p "{prompt}"}` + pendiente |
| Checklist | se tachan solos «instalar Claude» y «elegir carpetas»; capturas 3 |
| Reinstalación | pregunta «Ya tienes una configuración…»; `onboarding_done: true` sin overlay |
| Paleta | 1ª vez «Para empezar, pídele algo real»; 2ª vez ya no sale |
| Tracebacks en log | 0 |

## FALTA / notas
- «Primera victoria en < 2 min» con un modelo real: no se lanzó una tarea real de motor (gasta GPU/cuota y la
  GPU está ocupada con el Ollama del usuario). Se verificó que el ejemplo llega al chat con el motor local
  elegido; el cronometraje real queda como FALTA.
- El plan B en la prueba se simula haciendo que el sondeo a google no responda (no se corta la red real).
