# Estado de la fase 4: 0.4.5, rediseño de interfaz (en curso)

Se sigue el orden de `specs/opus-tasks-045/INDICE-045.md`. Cada spec terminado tiene su `ESTADO-*.md` en la raíz
y su commit. El 150 % de DPI es simulado (`GROWI_BRIDGE_DPI=144`), como en el piloto.

| # | Spec | Estado | Commit / motivo |
|---|---|---|---|
| 1 | t-tokens-raycast-045 | **LISTO**. Texto `#F5F5F6` y error `#E64C51`, por la tabla de colores y el contraste AA. FALTA: fuente por columna y color por celda, que ttk no permite | `ESTADO-TOKENS-RAYCAST.md` |
| 2 | t-estado-banner-nube-045 | **LISTO**. Probe por runner-status.json, alarma confirmada y estados informativos. FALTA: la barra lateral sigue con el sondeo (#19) | `ESTADO-ESTADO-BANNER-NUBE.md` |
| 3 | t-estado-mapa-045 | **LISTO**. Scroll a la posición real, resalte de 3 s o hasta el siguiente clic, y arreglo de los cortes a ventana mínima. FALTA: el 150 % real | `ESTADO-ESTADO-MAPA.md` |
