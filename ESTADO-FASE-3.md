# Estado de la fase 3: 0.4.0 fase B (en curso)

Orden de la lista de Leandro. Cada spec terminado tiene su `ESTADO-*.md` en la
raíz y su commit.

| # | Spec | Estado | Commit / motivo |
|---|---|---|---|
| 01 | t-ajustes-reorg | **LISTO** (FALTA: densidad, reducir movimiento, 4 avisos y borrar datos, que no existían) | `fab58af`, `ESTADO-AJUSTES-REORG.md` |
| 02 | t-autocalibracion-vram | **SALTADO (bloqueo de hardware)** | La verificación pide cargar un modelo real. La GPU (RTX 3060 6 GB) tiene 4,2 GB ocupados por el llama-server de Ollama del usuario: cargar Hermes 8B (5 GB) aquí fallaría o le quitaría memoria. Además, el log real de llama-server (`llama\llama-server.log`, nivel por defecto) **no trae** los «buffer size = X MiB»: solo `n_ctx_slot`. Hace falta `-v` o medir con nvidia-smi. Retomar con la GPU libre |
| 03 | t-automations | **LISTO** | `2490f08`, `ESTADO-AUTOMATIONS.md` |
| 04 | t-blender-herramienta | **LISTO** (Blender 5.2.2 real, tornamesa y QC) | `50cd345`, `ESTADO-BLENDER-HERRAMIENTA.md` |
| 05 | t-byos-visible | **LISTO** (Max y ChatGPT conectadas, detectadas en vivo) | `478265f`, `ESTADO-BYOS-VISIBLE.md` |
| 06 | t-calculadora-paleta | **LISTO** | `e8f3ed7`, `ESTADO-CALCULADORA-PALETA.md` |
| 07 | t-carga-300ms | **LISTO** (FALTA: esqueleto en Tareas, Carpetas y Registro, que hoy cargan en síncrono y no esperan) | `24cdec9`, `ESTADO-CARGA-300MS.md` |
| 08 | t-catalogo-030 | **SALTADO (bloqueo)** | Pide leer en Hugging Face los tamaños y sha256 reales, descargar ~10 GB (Qwen2.5-Coder-7B, Gemma 3 4B, Qwen3-Embedding) y hacer la carga de prueba en llama-server. La GPU está ocupada por el Ollama del usuario (4,2 de 6 GB) y descargar a la carpeta de la app instalada no está permitido. **También quedan bloqueados los que dependen de él:** 12 t-embeddings-8081, 14 t-evaluar-hermes4 y 41 t-vision-gemma3-4b |
| 09 | t-comandos-script | **LISTO** | `2fc2345` + `c1735fc` (arreglo de mypy que marcó el gate), `ESTADO-COMANDOS-SCRIPT.md` |
| 10 | t-dag-fases-030 | **LISTO** | `3f40082`, `ESTADO-DAG-FASES.md` |
| 11 | t-detector-avast | **LISTO** (lo que faltaba tras t-ip-estable: Tailscale en «Starting…» y las caídas consultables) | `567ed68`, `ESTADO-DETECTOR-AVAST.md` |
| 12 | t-embeddings-8081 | **SALTADO (depende del 08)** | Necesita Qwen3-Embedding instalado por t-catalogo-030 y la GPU libre |
| 13 | t-estimado-gasto-030 | **LISTO** (FALTA: aplicar el umbral por plan) | `7d6d1c5`, `ESTADO-ESTIMADO-GASTO.md` |
| 14 | t-evaluar-hermes4 | **SALTADO (depende del 08 + GPU)** | Pide A/B con 10 tareas en local con Hermes 4 descargado; la GPU está ocupada y el catálogo (08) no se pudo instalar |
| 15 | t-gasto-pronostico | **LISTO** (FALTA P2: ahorro por usar local) | `566fbaa`, `ESTADO-GASTO-PRONOSTICO.md` |
| 16 | t-interruptor-motor | **LISTO** | `ebed8ec`, `ESTADO-INTERRUPTOR-MOTOR.md` |
| 17 | t-lote-conectividad-040 | **LISTO** (parte 1 = spec 11; parte 2 = mapa ampliado) | `5e02dcc`, `ESTADO-LOTE-CONECTIVIDAD-040.md`, `ESTADO-MAPA-AMPLIADO.md` |
| 18 | t-lote-evaluar-modelos-040 | **SALTADO (GPU + modelos)** | Junta t-vision-gemma3-4b y t-evaluar-hermes4: hacen falta Gemma 3 4B + mmproj y Hermes 4 descargados y la GPU libre (la ocupa el Ollama del usuario). Con él quedan también 14 y 41 |
| 19 | t-lote-mascota-040 | **LISTO** (incluye 21 t-mascota-estados y 22 t-mascota-memoria-minima; FALTA: arte definitivo y la semana de validación) | `13574d1`, `ESTADO-LOTE-MASCOTA-040.md` |
| 20 | t-mapa-ampliado | **LISTO** (dentro del 17) | `ESTADO-MAPA-AMPLIADO.md` |
| 21-22 | t-mascota-estados, t-mascota-memoria-minima | **LISTO** (dentro del 19) | `ESTADO-LOTE-MASCOTA-040.md` |
| 23 | t-matriz-estados | **SALTADO (dependencia)** | Depende de t-estados-vacios y t-estados-error (fase A), que **no se han hecho**: no están en el código ni en la cadena enviada (CADENA-ESTADO.json). Es una auditoría que usa esos componentes |
| 24 | t-memoria-buscable | **LISTO** | `c7e8625`, `ESTADO-MEMORIA-BUSCABLE.md` |
| 25 | t-modelo-por-superficie-auto | **LISTO** | `1d21404`, `ESTADO-MODELO-POR-SUPERFICIE.md` |
| 26 | t-motor-opencode | **SALTADO (permiso)** | El spec pide **instalar OpenCode** (`npm install -g opencode-ai`, vía oficial). El clasificador de permisos de esta sesión **denegó** instalar código externo, y sin el binario no se puede verificar en vivo ni su nombre, ni su sintaxis, ni su salida, ni la prueba corta (el spec prohíbe inventar el descriptor). Para retomar: que Leandro autorice la instalación |
| 27 | t-movimiento-contraste | **LISTO** (FALTA: la sesión real en Night Sky, con el procedimiento) | `deac949`, `ESTADO-MOVIMIENTO-CONTRASTE.md` |
| 28 | t-notas-obsidian-030 | **LISTO** (FALTA: Muse Link como espejo, que necesita endpoint y credencial; la configuración guiada) | `6c24061`, `ESTADO-NOTAS-OBSIDIAN.md` |
| 29 | t-onboarding-fallos | **LISTO** (FALTA: cronometrar la «primera victoria < 2 min» con un modelo real) | `abb5df6`, `ESTADO-ONBOARDING-FALLOS.md` |
| 30 | t-panel-estado-gateway | **LISTO** (el registro de cambios de motor es en memoria; el router con fallbacks es el spec 35) | `3ef8d12`, `ESTADO-PANEL-ESTADO-GATEWAY.md` |
| 31 | t-pedir-cosecha | **LISTO** (FALTA: cosecha real — sin TIKTOK_MS_TOKEN y gasta créditos; el lado de la VM es contrato; tarifa de Instagram sin dato) | `197ec62`, `ESTADO-PEDIR-COSECHA.md` |
| 32 | t-perfil-sobre-mi | **LISTO** (FALTA: (c) con Hermes 8B solo a medias — rellena el tono con las reglas de estilo; probar con Claude gasta cuota) | `fa5c984`, `ESTADO-PERFIL-SOBRE-MI.md` |
| 33 | t-politicas-persistentes-030 | **LISTO** (FALTA: aprobación remota por WhatsApp — no existe; pasos dentro de una corrida del CLI no se interceptan) | `f1e313f`, `ESTADO-POLITICAS-PERSISTENTES.md` |
| 34 | t-prueba-corte | **LISTO** (FALTA: la primera prueba real — la provoca Leandro; propuesta sáb 7-nov-2026 10:00) | `9ae0bd8`, `ESTADO-PRUEBA-CORTE.md` |

**Prerrequisito general:** la fase A (opus-tasks-030) no está completa en la
cadena: 24 de 28 enviados, parada en `t-temas-oscuro-sistema`. Cada spec
construye sobre lo que sí existe en el código.

**Observación (arranque, medida):** `build_gui` tarda **15-16 s con el código de la base** (4a88d34) y 17-18 s ahora. El perfil (cProfile) da **`tema_seccion` → `_KitCtk.option` (CTkOptionMenu) ~11 s** (fase A, temas; `t-temas-oscuro-sistema` sigue a medias en su cadena, por eso no se tocó). Antes se apuntó: la app tarda 11-13 s en abrir el puente (lo ve el smoke del gate). Compilar `growi-bridge.py` en una carpeta nueva tarda ~9 s, pero un lanzador con `.pyc` en caché **no** bajó el tiempo medido en la app real, así que se descartó. Queda para un fix aparte: perfilar `build_gui` (antes se vio `_gw_poll_loop` y la carga de imágenes).
