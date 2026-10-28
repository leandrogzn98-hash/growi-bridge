# Prueba de corte de luz — protocolo

Para seguirlo solo, sin el asistente delante. En la app: **Ctrl+K → «Prueba de corte»**. Ahí están este
protocolo, el checklist con lo que la app ve en ese momento y el formulario que escribe en
`resiliencia.log`.

## Qué, cuándo y cómo
- **Qué se corta:** la luz del PC entero. Nada de cerrar la app ni apagar desde Windows.
- **Cuándo:** una vez al mes, a mitad de una tarea larga (que lleve más de 5 minutos trabajando).
- **Cómo:** desenchufar el PC o bajar el breaker. **No simulado.** Si por lo que sea no se corta de verdad
  (cerrar la app, matar el proceso), la línea del registro se marca `simulado`.
- **Quién:** lo provoca Leandro. El asistente nunca apaga el PC por su cuenta.
- Se espera 1 minuto, se vuelve a dar la luz y se enciende el PC. No se toca nada durante 5 minutos: lo que
  se mide es qué vuelve **solo**.

## Checklist de preparación (antes de cortar)
1. Hay **una tarea larga en curso** (Tareas: una fila «en curso» que lleve más de 5 min). Si no hay ninguna,
   la prueba **no se hace**: se registra «sin prueba este mes: no había tarea larga».
2. Si hay una **descarga de modelo a medias** (Modelos → descargas), se deja corriendo; si no, se anota
   «sin descarga».
3. La app está abierta en una **pestaña concreta** (por ejemplo, Tareas con la tarea seleccionada). Se apunta
   cuál.
4. Se apunta la **hora del reloj** del PC y la del móvil.
5. El **túnel** (Estado → Gateway → Acceso remoto) está activo, o se apunta que no.
6. Se apunta la hora exacta del corte.

## Qué se mide en cada punto y qué cuenta como «sobrevivió»
| Punto | Dónde mirarlo al volver | Sobrevivió si… |
|---|---|---|
| **Tarea a medias** (cola SQLite + session_id + paso) | Estado → Gateway → Cola («Al arrancar: se re-encoló…») y Tareas → la fila de la tarea | vuelve sola a la cola y sigue **desde el checkpoint** con `--resume`; o, si no se puede, se repite diciendo por qué. Nunca desaparece sin aviso |
| **Descarga GGUF** (~5 GB) | Modelos → descargas; `models\<archivo>.part` y `.download.json` | sigue desde los bytes que ya estaban en disco (Range) y al final cuadra el sha256. Si el hash falla, borra y avisa |
| **Sync a medias** (copias de exportación) | la carpeta destino: ningún archivo final a medias, solo `.parcial` | nunca se marca como completo algo a medias; al seguir, solo se copia lo que falta y se comprueba el hash |
| **Sesión de Claude Code** | Tareas → detalle («Recuperada tras corte… se reanudó desde el checkpoint») | `--resume` con el session_id guardado. Si la sesión se perdió, sigue en una sesión nueva con el resumen del checkpoint **y lo dice** |
| **Estado de la app** (pestaña, tarea elegida) | la ventana al abrir | **Hoy NO se guarda**: abre en Estado. Se anota qué se perdió (para medir cuando se arregle) |
| **Túnel / relay** (Tailscale) | Estado → Gateway → Acceso remoto | vuelve solo a «activo» en menos de 2 min tras arrancar (el vigía lo reintenta cada 30 s) |
| **Reloj del sistema** | compararlo con el móvil; `w32tm /query /status` en PowerShell | la diferencia es menor de 5 min. **Hoy la app NO lo compara con el VPS**: se mira a mano. Si difiere, los certificados TLS fallan y el proxy «no conecta» sin causa visible |
| **Dos instancias** (mutex) | abrir la app dos veces | la segunda no arranca otra copia: trae la primera al frente |

## Cómo se registra
Una línea por prueba en `resiliencia.log` (carpeta de Growi Bridge), mejor desde el formulario de la app.
Formato (campos separados por ` | `):

```
fecha | tipo (real / simulado / sin prueba) | qué se cortó | qué se perdió | qué se reanudó solo | qué hubo que hacer a mano | notas
```

Ejemplos:
```
2026-11-07 10:12 | real | breaker, tarea t-informe a los 9 min y descarga Hermes a 2,1/4,9 GB | pestaña Tareas (abrió en Estado) | tarea (checkpoint, --resume), descarga (Range), túnel en 40 s | nada | reloj OK (+3 s)
2026-12-05 09:00 | sin prueba | — | — | — | — | sin prueba este mes: no había tarea larga
```
El registro es acumulativo: nunca se borra una línea. La mejora se mide comparando las columnas «se perdió»
y «a mano» de un mes a otro.
