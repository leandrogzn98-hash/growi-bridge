---
name: prospectar
description: "Prospección comercial en borrador: filtra y prioriza prospectos de una lista CSV que el usuario deja en la carpeta, según nicho y ciudad, y escribe prospectos.csv con el motivo de cada uno. Sin raspar webs ni servicios de pago; nunca contacta a nadie."
version: 0.1.0
entradas:
  - "lista | ¿Qué archivo CSV de la carpeta uso como fuente? | lista.csv"
  - "nicho | ¿A qué nicho le vendemos?"
  - "ciudad | ¿En qué ciudad o zona? | cualquiera"
  - "cuantos | ¿Cuántos prospectos como máximo? | 10"
salidas:
  - prospectos.csv
---

# Prospectar (agente de Ventas, Growi Bridge)

Toma la lista CSV que indica la entrada `lista` (en la carpeta de la tarea) y escribe `prospectos.csv` con los mejores
`cuantos` para el `nicho` y la `ciudad` pedidos.

**Reglas**
1. **Única fuente: la lista.** No busques en internet, no raspes webs, no uses APIs de pago. Si la lista no existe o
   está vacía, escribe `prospectos.csv` solo con la cabecera y responde «sin lista: [PENDIENTE: lista de prospectos]».
2. **No inventes nada.** Si un prospecto no trae un dato (correo, teléfono, sector), queda vacío o
   `[PENDIENTE: dato]`. Nunca completes un contacto.
3. **No contactes a nadie.** Esta skill solo ordena una lista.

**Formato de `prospectos.csv`** (UTF-8, coma como separador): `nombre,empresa,ciudad,sector,contacto,prioridad,motivo`.
- `prioridad`: 1 (alta) a 3 (baja), según encaje con el nicho y la ciudad.
- `motivo`: una frase con el porqué, basada solo en lo que dice la lista.

Responde con una línea: cuántos prospectos elegiste de cuántos había en la lista.
