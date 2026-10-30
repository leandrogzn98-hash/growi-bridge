# ESTADO — Departamento Diseño y Audiovisuales (0.5.0, t-oficina-depto-diseno-050)

Rama `Claude`, 29-oct-2026. Pedido: un quinto departamento en la oficina virtual, con la Directora y dos empleados
(el Editor y Motion), que opere la skill de edición de vídeo con IA.

No se tocó `VERSION` ni ninguno de los 4 departamentos existentes.

## Lo primero: las dependencias no están, así que la integración es FALTA

El spec dice que solo se integra si los specs 7 (plano), 10 (paper doll, `skin.json` y `validate_skins.py`) y
11 (empleados) están LISTO. **Ninguno se ha ejecutado:**

- `specs/opus-tasks-050/CADENA-ESTADO-050.json` dice `"fase": "espera-fase-b"`, con el historial vacío y sin
  ningún spec enviado. De la 0.5.0 solo se corrió el spec 1 (mediciones, commit 28e9dbc).
- No existe ningún `plano.json`, `skin.json` ni `validate_skins.py` en el repo ni en `C:\Users\forte`
  (búsqueda por nombre). Tampoco hay `ESTADO-t-oficina-plano/skins/empleados-050` en `share\outbox\` ni sus
  results en `runner-results\`.
- Tampoco está `PALETA-Y-SKINS.md` completo. En el PC solo está su §15 (tintes); falta el §1, la paleta de 24 colores.

Por eso **no se inventó** ni el plano, ni el `skin.json`, ni el validador, ni los sprites. Se hizo lo que es
propio de este spec y no depende de ellos, en un formato que se integra copiando cuando existan.

## LISTO

- **Identidad del departamento.** `oficina/departamentos/diseno-audiovisuales.json`: nombre «Diseño y
  Audiovisuales», id `diseno-audiovisuales`, corbata **frambuesa #C2185B (propuesta)**. El área se define por
  requisitos: mesa de edición con monitor de timeline, mesa de motion con vista previa 9:16, mesa de la Directora
  y tablón de estilos con las 3 tarjetas del catálogo más la marca activa. Lleva las reglas que tiene que cumplir
  su sitio en el plano (sin solapes con los 4 departamentos ni con café, ventana, baño, planta y pasillo;
  alcanzable por BFS).
- **Los 3 personajes, como fichas con los campos que el spec 10 fija para `skin.json`** (id, nombre,
  departamento, plataforma, rol, capas, colores, animaciones, notas). Cada uno tiene las 8 animaciones del sistema:
  idle, escribir, caminar, cafe, telefono, vagancia, celebrar y dormir.
  - **La Directora**: líder, con corbata frambuesa y claqueta bajo el brazo (la única con claqueta).
  - **El Editor**: sin corbata, con un rollo de película al hombro.
  - **Motion**: sin corbata, con gorro de pompón y lápiz óptico. No lleva tableta, porque la única con tableta es
    Runa.
  Con ellos el roster pasaría de 14 a 17.
- **Contexto de fortalezas**: los 5 servicios (QC automático del render, edición por lotes nocturna, costos
  transparentes por vídeo, memoria de marca y repurposing), cada uno apuntando a su script real de la skill. El
  pipeline: Whisper transcribe, Claude dirige, Gemini mira y Remotion renderiza.
- **Conexión con la skill** (sección `skill` del JSON y abajo).
- **Validador del departamento**: `python oficina/departamentos/validar_departamento.py` da **8 OK, 0 FALLA,
  4 FALTA**:
  - 3 personajes y 1 líder; la corbata solo en la líder; las 8 animaciones en los 3; identificadores únicos.
  - Corbata distinta de todo lo ocupado: lo más cercano es el tinte rojo #FF6363, con ΔE 31,8, por encima del
    mínimo de 20; después la corbata de Claude, con ΔE 44,2.
  - Los 5 servicios con su script existente, el pipeline de 4 pasos y la skill existente.
  - Las 4 FALTA son las dependencias: paleta de 24, `plano.json`, `skin.json` y `validate_skins.py`.
- `py_compile` del validador sin errores.

## Cómo opera la skill el departamento

- **Invocación**: una tarea del runner con `"motor": "claude"` cuyo prompt pide la skill `edicion-video` con
  crudo, estilo, marca, director y salida. El formato exacto de la tarea y del resultado está en
  `skills/edicion-video/SKILL.md`, sección «Modo Bridge». El runner activa la skill por su descripción.
- **Bocadillo con progreso**: lo saca de `<salida>\reporte.json → eventos`, que se reescribe en cada paso.
  Textos de 140 caracteres como máximo: «Transcribiendo…», «Lista de cortes: 8 cortes», «Costo estimado: $0»,
  «Renderizando…», «QC OK». Quién habla en cada momento:
  - el Editor, hasta «corte y audio»;
  - la Directora, en «lista de cortes»;
  - Motion, desde «render: inicio» hasta «QC».
- **Toast al terminar**: uno solo cuando `estado` pasa a listo, rechazado por QC o error. Por ejemplo «Reel listo
  (23,4 s, QC OK, $0)» o «Reel rechazado por QC: subtítulos fuera de pantalla».
- **Animaciones**: escribir mientras su paso está en curso; celebrar (golpe de claqueta) cuando pasa el QC.

## FALTA

| Qué | Por qué | Qué hacer cuando se pueda |
|---|---|---|
| Departamento en `plano.json` con mesas, sillas y posiciones sin solapes | El spec 7 no se ejecutó: no hay plano | Tras el spec 7, añadir los 4 elementos de `area.elementos` donde quepan respetando `area.reglas_de_plano`, y pasar su validador de solapes y BFS |
| Los 3 en `skin.json` y `validate_skins.py` en verde | El spec 10 no se ejecutó | Copiar las 3 fichas a `skin.json` (mismos campos) y correr `validate_skins.py` |
| Sprites 32x48 a 8 FPS en Pixelorama, y que rendericen en el visor del spec 9 | No hay pipeline validado (spec 9) ni visor: dibujarlos ahora sería hacerlo sin el esqueleto común ni la paleta | Tras los specs 9 y 10, dibujarlos sobre el esqueleto común, con retoque a mano píxel a píxel |
| Corbata dentro de la paleta de 24 | `PALETA-Y-SKINS.md` §1 no está en el PC | Comprobar #C2185B; si no está, tomar el magenta más cercano de la paleta y volver a pasar el validador |
| Colores de pelo, ropa y piel de los 3 | Salen de la paleta de 24 | Igual que la fila anterior |
| Formato definitivo del contexto de fortalezas | Lo fija el spec 11 | Pasar `fortalezas` al formato del spec 11 (el contenido ya está) |
| Bocadillos y toasts implementados | Los specs 8 (estados) y 16 (bocadillos) no existen todavía | Leer `reporte.json` como se describe arriba |

## CÓMO PROBARLO

```
cd C:\Users\forte\source\growi-bridge
python oficina\departamentos\validar_departamento.py
```

Hoy sale 8 OK, 0 FALLA, 4 FALTA. Cuando existan `plano.json`, `skin.json` y `validate_skins.py`, el mismo
validador comprueba si el departamento ya está dentro, y las FALTA pasan a OK o a FALLA.

La skill que opera el departamento se prueba con `ESTADO-SKILL-EDICION-VIDEO-060.md`.
