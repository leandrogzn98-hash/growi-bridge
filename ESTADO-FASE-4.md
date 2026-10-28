# Estado de la fase 4: 0.4.5, rediseño de interfaz (en curso)

Se sigue el orden de `specs/opus-tasks-045/INDICE-045.md`. Cada spec terminado tiene su `ESTADO-*.md` en la raíz
y su commit. El 150 % de DPI es simulado (`GROWI_BRIDGE_DPI=144`), como en el piloto.

| # | Spec | Estado | Commit / motivo |
|---|---|---|---|
| 1 | t-tokens-raycast-045 | **LISTO**. Texto `#F5F5F6` y error `#E64C51`, por la tabla de colores y el contraste AA. FALTA: fuente por columna y color por celda, que ttk no permite | `ESTADO-TOKENS-RAYCAST.md` |
| 2 | t-estado-banner-nube-045 | **LISTO**. Probe por runner-status.json, alarma confirmada y estados informativos. FALTA: la barra lateral sigue con el sondeo (#19) | `ESTADO-ESTADO-BANNER-NUBE.md` |
| 3 | t-estado-mapa-045 | **LISTO**. Scroll a la posición real, resalte de 3 s o hasta el siguiente clic, y arreglo de los cortes a ventana mínima. FALTA: el 150 % real | `ESTADO-ESTADO-MAPA.md` |
| 4 | t-tareas-estadisticas-045 | **LISTO**. 3 estadísticas reales, píldoras con contadores que cuadran, fijada en vivo. FALTA: la tabla es más ancha que la ventana a 150 % (#10) | `ESTADO-TAREAS-ESTADISTICAS.md` |
| 5 | t-barra-lateral-045 | **LISTO**. 232 px, contadores reales (Estado = fallos del mapa), Consumo hoy real sin sumar el equivalente, tarjeta del guardrail → Permisos, interruptor CTk con clásico de respaldo, cabe a la altura mínima. Pruebas ocultas desde aquí. FALTA: nav en Tk (por regla), 150 % real | `ESTADO-BARRA-LATERAL.md` |
| 6 | t-carpetas-ctk-045 | **LISTO**. Una fila CTk por carpeta (ruta real, Abrir, Quitar) + Añadir/Restablecer; respaldo clásico en las 4 condiciones; arranque igual (página 11 ms). FALTA: capturas (a pedido: no se abren ventanas) | `ESTADO-CARPETAS-CTK.md` |
| 7 | t-apis-tarjetas-045 | **LISTO**. «Conexiones»: tarjeta CTk por proveedor con estado real (sin clave / sin probar / conectada / error / ninguna activa) y su acción; respaldo clásico. Probado con claves falsas contra 127.0.0.1. FALTA: capturas (a pedido) | `ESTADO-APIS-TARJETAS.md` |
| 8 | t-modelos-tarjetas-045 | **LISTO**. Las 4 tarjetas en CTk; «Quién responde» como tarjetas por motor con Automático primero y ✓, estado con punto y coste real (tarifa de lista, medido, $0 local o «sin datos»); respaldo clásico por tarjeta; lo pesado se dibuja al abrir Modelos (dibujarlo al arrancar costaba +2,4 s). FALTA: capturas (a pedido) | `ESTADO-MODELOS-TARJETAS.md` |
