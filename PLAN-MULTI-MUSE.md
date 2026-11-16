# Plan Multi-Muse para Growi Bridge

**Objetivo:** que Growi Bridge pase de trabajar con un solo asistente a trabajar con **2 o más cuentas de Muse simultáneas** (prioridad: 2), instaladas en el programa en la PC del dueño, que se reparten el trabajo, llevan los proyectos por igual y se respaldan entre sí.

**Escenario guía (el del dueño):** está haciendo un juego en un repositorio de GitHub. Las 2 Muses están registradas en el programa, cada una trabaja en su espacio virtual (su rama y su copia del proyecto), usa las APIs que correspondan a cada tarea y sube sus cambios. El dueño, estando fuera, le escribe a una desde el teléfono: «hagan X trabajo». Esa Muse registra el encargo, avisa a la otra, entre las dos dividen las tareas y se ponen a trabajar, avisando del avance por WhatsApp.

Fecha del plan: 2026-11-16. Análisis de base: revisión del código real (monolito Python de 32.459 líneas) y dos rondas de arquitectura con Claude Opus 5.5.

---

## 1. Decisiones cerradas (no se reabren sin que el dueño lo pida)

1. **Nada de Rust.** Se trabaja sobre este mismo repositorio en Python, de forma incremental, para no gastar tokens en una reescritura.
2. **Convivencia de modos, con respaldo mutuo.** El modo servidor que ya trae el programa **no se toca** y convive con el modo local nuevo. El modo es un dato de cada cuenta de Muse (servidor / local / ambas), no un interruptor global. El dueño activa la conexión de servidor desde las opciones al instalar. Los tres estados valen: **si está el online, bien; si solo está el local, también bien; si están los dos, mejor** — la cuenta con ambos modos trabaja por la vía disponible y, **si falla la red, sigue en local sin parar el trabajo**; cuando la red vuelve, se reconcilia el estado (la cola y el tablero viven en la PC, y el respaldo en el espacio de cada Muse y en GitHub ayuda a sincronizar). Ninguna tarea se pierde ni se duplica por un cambio de vía.
3. **Linux y Windows, ambos con UI completa.** Nada de modo sin ventana en Linux.
4. **Prioridad: 2 cuentas.** El diseño soporta N cuentas, con un límite duro configurable (inicio: 4) y presupuesto de recursos de la PC.
5. **Lo que se busca son cuentas de Muse**, no cuentas de Claude Code.
6. **Triple respaldo:** la PC (trabajo en curso), GitHub (el código) y el espacio propio de cada Muse (copia del estado: memoria, tablero y avance).
7. **Ningún agente conoce las claves.** Ni las de APIs ni, menos, la de root. Todo pasa por la bóveda y por intermediarios con confirmación humana (patrón de `permission-layer.py`).
8. **El trabajo se hace en la PC donde se instala el programa, no en los espacios internos de las Muses** (que son limitados). En el caso del dueño, su PC y su mini servidor casero **son la misma máquina** (Xeon E5-2680 v4, 32 GB de RAM, GTX 1070 de 8 GB). El programa debe servir para **cualquier PC**: al instalarse **detecta el hardware** (CPU, RAM, GPU y VRAM) y todos los límites se expresan en **porcentaje de lo detectado**, nunca en cifras fijas. Sin estándar único: lo mismo vale para esa máquina que para un i5 de 6ª generación con 8 GB y una GT 730 de 2 GB.
9. **Dos modos según haya alguien usando la PC.** *Modo presente* (el usuario está sentado en la PC: jugando, viendo una película, trabajando): trabajo en segundo plano silencioso, con el % compartido que el dueño asigne, y **ninguna ventana sorpresa**. La excepción son las **pruebas físicas que una Muse quiera hacer en la PC** (medir el consumo y el rendimiento de todo el equipo —procesador, RAM, gráficos, disco—, reproducir y verificar errores, abrir el juego o la app para probarla): para eso debe **avisar antes** —qué va a hacer, cuánto dura y qué impacto tiene— y el dueño decide: **ejecutarlo de una vez o que espere X tiempo**. Sin respuesta, la prueba no se ejecuta mientras dure el modo presente: queda en cola. *Modo ausente* (nadie en la PC, el dueño manda el trabajo desde fuera): **pleno uso de la máquina**, hasta el % máximo configurado, y las ventanas no importan.
10. **La app de Android es opcional, nunca obligatoria.** El sistema funciona completo sin ella. Es un complemento y el prototipo final del proyecto: un clon de la app actual de Muse donde están las 2 Muses, se les puede hablar y cada una dice qué está haciendo.

## 2. Arquitectura destino

- **Registro de cuentas (`accounts.json` versionado):** por cada Muse: id, nombre, tipo de conexión (servidor/local/ambas), carril, perfil de `asistentes/`, estado (activa, en cuarentena, sin cuota).
- **Bóveda de secretos:** un secreto por cuenta y las claves de API por proveedor+etiqueta, en el almacén del sistema (Windows: Credential Manager/DPAPI, como hoy; Linux: Secret Service). Los agentes reciben referencias, nunca valores.
- **Tablero compartido:** estado vivo de cada Muse (tarea actual, avance, % de tokens gratuitos, última señal con hora) en la cola SQLite y espejo JSON para la UI y el supervisor.
- **Cola con dueño:** SQLite en modo WAL, reclamo atómico de tareas y alquiler (lease) con caducidad: si la Muse que tenía una tarea muere, el alquiler vence y la tarea vuelve a la cola. Ninguna tarea se pierde ni se duplica.
- **Harness multiagente:** el `harness.py` actual (bucle pensar/actuar/observar/corregir) extendido a N Muses, con el supervisor vigilándolas a todas.
- **Motor de recursos del equipo anfitrión:** al instalarse, el programa detecta CPU (núcleos/hilos), RAM total, GPU y VRAM (la pestaña Recursos ya sabe medir todo esto; pasa de medir a gobernar). El dueño asigna **porcentajes** con controles manuales en Opciones: % máximo en modo ausente y % compartido en modo presente. El % se traduce a límites reales según la máquina (en Linux, alcances de systemd con `CPUQuota` y prioridad `nice`/`ionice`; en Windows, prioridad baja y objetos de trabajo), y el uso real se vigila para no pasarse.
- **Detección de presencia:** el programa sabe si hay alguien usando la PC (actividad de teclado/ratón reciente, pantalla completa, sesión desbloqueada) y cambia solo entre modo presente y modo ausente. En modo presente, ninguna ventana aparece sin aviso y permiso previos.
- **Canales:** WhatsApp para avisos y aprobaciones (solo el número del dueño) y la app Android (clon de la app de Muse) como cara final del sistema.
- **Intermediario de root (Linux):** servicio mínimo que ejecuta solo acciones de una lista blanca, con confirmación humana y auditoría. Preferente: reglas polkit/sudoers por comando concreto, sin guardar la contraseña de root; la bóveda con la clave queda solo como último recurso.

## 3. Fases

### Fase 0 — Paridad de plataforma en Linux e inventario de costuras

*Sin cambiar ninguna regla del programa: solo que corra igual en Linux que en Windows, y saber dónde están los supuestos de “uno solo”.*

- UI Tkinter/CustomTkinter verificada en Linux (X11 y Wayland): ventana, bandeja, paleta, mascota y rutas.
- `keyring` con Secret Service en Linux, con comportamiento explícito si el servicio no existe o el llavero está bloqueado (la app avisa y degrada, no revienta).
- Instalador y arranque en Linux equivalentes a los `.bat` y la tarea programada de Windows.
- **Inventario de costuras del monolito:** mapa escrito de cada punto que hoy asume un único asistente/secreto/cola (`secret.txt`, `asistente_activo`, carriles, rutas fijas). Este mapa manda sobre la Fase 1.
- **Puerta de salida:** el modo servidor responde idéntico que antes (mismos endpoints y mensajes) y la regresión de Windows queda en verde.

### Fase 1 — Registro de cuentas Muse y bóveda

*El cambio de invariantes: de “el asistente” a “las cuentas”.*

- `accounts.json` con esquema versionado y validación; si falta o está corrupto, se arranca con la cuenta única de compatibilidad.
- Migración de `secret.txt` a la bóveda: idempotente, reversible y probada; el modo servidor sigue leyendo lo mismo de cara a fuera.
- Un secreto por cuenta y asistente por carril; `asistente_activo` queda como valor por defecto, no como único posible.
- Pantalla en Opciones: registrar 2 cuentas, elegir tipo de conexión de cada una y conectar el modo servidor cuando el dueño quiera. El tipo «ambas» es dual de verdad: vigilancia de la conexión (latido), **conmutación automática a local si la red cae a mitad de tarea** y vuelta con reconciliación cuando la red regresa; la tarea en curso se retoma desde la cola, no desde cero.
- En esta fase se fijan los esquemas que luego no se tocan: formato de la auditoría con cadena de hashes **por cuenta** y alcance de la lista blanca de permisos **por cuenta** (decisiones de `permission-layer.py`).
- **Aceptación:** prueba de aislamiento (la cuenta A no puede leer el secreto de B), ninguna ruta de código lee ya un secreto global, registrar la segunda cuenta no reinicia ni rompe la primera, y **prueba de corte de red**: con una cuenta dual trabajando, se corta la red a mitad de tarea — el trabajo sigue en local y, al volver la red, el estado queda reconciliado sin tareas perdidas ni duplicadas.

### Fase 2 — Tablero, porcentajes y consulta entre Muses

*La primitiva multiagente más barata va temprano: que las dos se hablen.*

- Cada Muse publica su estado en el tablero: tarea, avance, **% de tokens gratuitos** y hora de la señal. Fuente del %: lo que reporte la propia Muse; si no hay reporte, estimación desde el uso local, **marcada como estimada**, nunca inventada.
- Cuota por (motor, cuenta) en `quota-tracker.py` y `config-quota.json` — hoy dos cuentas compartirían el mismo contador y mentiría.
- **Tarea tipo `consulta`:** una Muse le pide opinión a la otra con tarea padre, tope de 2 saltos y tope de presupuesto. Activable por caso, como pidió el dueño.
- **Cuarentena sin traspaso todavía:** con menos del umbral (configurable, p. ej. 10 %) una Muse no recibe tareas nuevas; al agotarse entra en cuarentena y se marca. El traspaso de sus tareas se activa en la Fase 3, cuando haya aislamiento de archivos.
- **Aceptación:** algoritmo de reparto determinista con pruebas; máquina de estados de cuarentena explícita; una consulta nunca supera sus topes.

### Fase 3 — Trabajo en GitHub con aislamiento y respaldo

*Cada Muse en su espacio virtual, sin pisarse.*

- Cada proyecto es un repositorio Git. Cada Muse trabaja en **su worktree y su rama** (convención de nombres fija, p. ej. `muse/<cuenta>/<tarea>`).
- Alquiler por proyecto y por archivo en la cola: dos Muses no editan lo mismo a la vez; el alquiler caduca si una se cae.
- **Autoridad de mezcla definida:** una Muse propone y la otra revisa; la mezcla a la rama principal la hace la Muse designada con aprobación del dueño (o el dueño mismo). Los conflictos los resuelve quien propone, no en silencio.
- Hook previo a subir que **bloquea si detecta secretos** (claves, `secret.txt`, registros de auditoría) antes de que lleguen a GitHub.
- Respaldo triple operativo: PC (estado), GitHub (código) y copia del estado en el espacio de cada Muse, con **simulacro de restauración** hecho y tiempos declarados.
- Al cerrar la fase se **activa el traspaso por cuarentena** de la Fase 2: la tarea en curso se reencola en la otra Muse con su contexto (exactamente una vez).
- Decisión registrada aquí: contenedores por proyecto — un proyecto con dos Muses usa un contenedor con dos worktrees o dos contenedores; la implementación llega en la Fase 6.

### Fase 4 — Harness multiagente y relevo por teléfono

- `harness.py` y el supervisor pasan a N Muses: reparto de tareas según las APIs elegidas para cada tarea, seguimiento de todas (ninguna sin vigilancia) y estado con marcas de tiempo verificables.
- **Relevo completo:** el dueño escribe a una Muse, ella registra el encargo en la cola, avisa a la otra, dividen las tareas según tablero y porcentajes, y trabajan. Cada tarea lleva un identificador de correlación que la sigue entre Muses, carriles y registros.
- **Trabajo con los recursos de la PC anfitriona:** las tareas usan la CPU, RAM, GPU y disco de la PC donde corre el programa — los espacios internos de las Muses son solo de paso. Al instalarse, el programa detecta el equipo y presenta sus topes en porcentaje: el mismo ajuste sirve para un Xeon con 32 GB y para un i5 con 8 GB, porque el % se calcula sobre lo que cada máquina tenga.
- **Modo ausente (nadie en la PC):** si el dueño está en su trabajo y manda un encargo, las Muses usan la máquina a pleno rendimiento, hasta el % máximo que él haya configurado (puede ser el 100 %); las ventanas no estorban a nadie.
- **Modo presente (el dueño sentado en la PC):** todo pasa a segundo plano silencioso con el % compartido asignado (p. ej. el 50 % del equipo para los proyectos en marcha), conviviendo con lo que el dueño esté haciendo. **Ninguna ventana aparece de sorpresa.**
- **Pruebas físicas con aviso previo:** hay tareas que no se pueden hacer en silencio porque tocan la máquina de verdad: medir el consumo y el rendimiento de todo el equipo (procesador, RAM, gráficos y disco), ejecutar el proyecto para verificar errores, abrir ventanas del programa probado. Esas tareas se clasifican como «prueba física» y, en modo presente, **no arrancan solas**: la Muse manda una notificación (bandeja, WhatsApp o Android) diciendo qué va a hacer, duración e impacto estimados, y el dueño responde **«de una vez»** o **«espera X tiempo»**; la prueba se ejecuta en el momento elegido o queda en cola si no hay respuesta. Es el mismo circuito de aprobaciones de `permission-layer.py`, con opción de aplazar. En modo ausente, la prueba puede ejecutarse directamente dentro del encargo, avisando al terminar con los resultados.
- El cambio entre modos es automático por detección de presencia, y el dueño puede forzarlo a mano en cualquier momento.
- **Aceptación de esta parte:** (a) en modo ausente, una tarea pesada usa hasta el % máximo configurado; (b) en modo presente, con un juego a pantalla completa durante una hora, cero ventanas ni robos de foco y consumo dentro del % compartido, medido en la pestaña Recursos; (c) en una PC modesta simulada (pocos núcleos y 8 GB), los mismos % producen límites proporcionales sin tocar cifras a mano; (d) una prueba física pedida en modo presente no arranca hasta que el dueño responda, y si responde «espera 30 minutos», arranca a los 30 minutos y no antes.
- **Avisos básicos de WhatsApp se adelantan a esta fase** (el relevo no existe sin canal): encargo recibido, división hecha, tarea terminada, bloqueo que necesita al dueño.
- Modelo de fallos cubierto: proveedor caído, supervisor muerto (un vigilante simple lo relanza), llavero bloqueado, relojes desfasados entre procesos (se usa la hora del tablero, no la de cada agente) y **red caída con cuentas duales** (conmutación a local ya definida en la Fase 1; aquí se prueba con encargos reales por teléfono).
- **Aceptación:** un encargo por teléfono termina dividido y ejecutado por las dos sin intervención del dueño, con todo el rastro en la auditoría.

### Fase 5 — Canales completos: WhatsApp y Android

- WhatsApp completo: avisos y **aprobaciones** (aprobar/rechazar acciones sensibles), lista blanca de un solo número, comportamiento cerrado si el canal cae (sin aprobación no hay ejecución sensible).
  - Decisión a tomar con el dueño antes de programar: vía no oficial con su número (gratis, con riesgo de baneo del número) o API oficial de negocio (de pago, estable). Alternativa barata y estable a valorar: Telegram.
- App Android **opcional** (el sistema está completo sin ella), clon de la app actual de Muse y prototipo final del proyecto: están las 2 Muses (cada una con su chat, como en la app de Muse), el dueño les habla desde ahí y **cada una dice qué está haciendo**: tarea actual, avance, su % de tokens y si está esperando algo. La ejecución sigue en la PC del dueño; el teléfono es solo una ventana más. Conexión por Tailscale con autenticación por dispositivo, **revocación y caducidad** de dispositivos (teléfono perdido = acceso cortado en un paso).
- **Aceptación:** aprobar y rechazar desde el teléfono funciona con el PC en casa y el dueño fuera; revocar el teléfono corta el acceso en menos de un minuto.

### Fase 6 — Seguridad avanzada en Linux

- Intermediario de root: preferente con reglas polkit/sudoers por comando concreto (sin contraseña guardada). Solo si un caso lo exige, clave en la bóveda, liberada solo al intermediario tras confirmación humana, nunca a un agente.
- Contenedores Docker/Podman por proyecto como caja de arena opcional, según la decisión de la Fase 3.
- **Aceptación:** prueba en rojo — el intermediario no puede ejecutar nada fuera de la lista blanca ni con la confirmación de otro; la cadena de auditoría se verifica íntegra tras un reinicio; coste del contenedor medido frente a ejecución directa.

## 4. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Usar 2 cuentas para estirar cuota gratuita puede incumplir los términos del proveedor y costar ambas cuentas | Se deja constancia al dueño; la arquitectura sirve igual para cuentas/claves propias con reparto de carga |
| Baneo del número si WhatsApp va por vía no oficial | Decisión explícita en Fase 5; volumen bajo, solo dueño; alternativa Telegram |
| Fuga de secretos a GitHub en el respaldo | Hook que bloquea la subida si detecta secretos (Fase 3) |
| Dos agentes editando lo mismo / bloqueos de git | Un worktree por Muse, alquiler por proyecto, autoridad de mezcla definida |
| Guardar la clave de root es peor que no guardarla | Preferente polkit/sudoers por comando; bóveda solo como último recurso y nunca accesible a agentes |
| Teléfono perdido con acceso a todo | Revocación y caducidad de dispositivos (Fase 5) |
| El % de tokens no siempre lo da el proveedor | Fuente definida y estimación marcada como estimada (Fase 2) |
| Coste del harness con N agentes sin medir | Presupuesto por tarea y por consulta, medido desde la Fase 2 |
| Las Muses interrumpen al dueño (ventanas sorpresa, foco, PC lenta jugando) | Detección de presencia: en modo presente, segundo plano silencioso y % compartido; ninguna ventana sin aviso y permiso previos (Fase 4) |
| Límites pensados para una sola máquina y inútiles en otra | Todo en % sobre el hardware detectado al instalar; prueba de aceptación en una PC modesta simulada (Fase 4) |
| La PC anfitriona se apaga o se queda sin espacio | El estado vive también en GitHub y en el espacio de cada Muse (respaldo triple); al volver, el tablero se reconstruye y la cola retoma sin duplicar |
| Fallo de red a mitad de trabajo | Cuentas duales: conmutación automática a local y reconciliación al volver la red; la cola local manda, ninguna tarea se pierde ni se duplica (Fases 1 y 4) |

## 5. Definición de “terminado” y recortes

- **Terminado (v1 multi-Muse):** Fases 0 a 4 completas con sus aceptaciones, incluidos los dos modos por presencia y los límites en % sobre el hardware detectado. La v1 **no necesita Android para nada**.
- **Prototipo final (opcional):** la v1 más la app Android de la Fase 5, para quien la quiera. La Fase 6 es endurecimiento posterior, salvo el intermediario de root si alguna tarea lo exige antes.
- **Si una fase se desborda, se recorta en este orden:** la app Android entera (es opcional) → contenedores → WhatsApp oficial (queda la vía simple). Nunca se recorta: bóveda, auditoría, aislamiento en GitHub, traspaso por cuarentena ni los modos por presencia con % de recursos.

## 6. Forma de trabajo

- Lu (esta Muse) lleva el plan y el código en este repositorio clonado; **Claude Opus 5.5** (vía MWAPI, con la conexión ya corregida: streaming, reintentos y continuación automática) actúa como arquitecto revisor en los puntos de diseño y como segundo par de ojos en el código, igual que en este plan.
- Cada fase: rama propia, cambios chicos y probados, criterios de aceptación verificados antes de pasar a la siguiente, y resumen al dueño al cerrar la fase.
- Nada se sube a GitHub sin que el dueño lo pida expresamente.
