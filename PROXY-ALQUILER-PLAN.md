# Compartir el proxy con conocidos: lo que se haría (NO construido)

> **Bloqueado. No se construye nada hasta que se resuelvan los bloqueadores de abajo.** Este documento es el
> plan, para que cuando se resuelvan no haya que pensarlo de nuevo. El precio NO se publica en la app.

## Estado de los 4 bloqueadores (28-oct-2026)
| # | Bloqueador | Estado |
|---|---|---|
| 1 | **Túnel cifrado** (hoy el proxy usa BasicAuth: usuario:clave en base64 en cada petición, legible por cualquiera en el camino) | **NO resuelto**: no hay túnel SSH por inquilino |
| 2 | **Precio y tope** | **Decidido por Leandro (26-oct-2026)**: sin límite y sin precio por ahora; solo se comparte entre conocidos, sin venta. La **venta comercial** sigue bloqueada hasta fijar precio + tope + consulta legal |
| 3 | **Consulta legal/fiscal con Angelis** (reventa de servicios de telecom/internet, CONATEL, obligaciones fiscales) | **NO resuelto**. No se encontró una fuente clara; **no se afirma** que sea legal ni ilegal |
| 4 | **Plan exacto del VPS** (2.25.244.222, Hostinger): qué plan es y cuánto se paga hoy | **NO resuelto**: hay que mirarlo en el panel de Hostinger |

## Los números (para decidir el precio cuando toque)
- El VPS más barato renueva a **$11,99-$19,49/mes**. A $2,50/mes hacen falta 3 inquilinos para cubrir la
  promo ($6,49), 5 para la renovación ($11,99) y 8 para la renovación alta ($19,49): **no deja ganancia**, solo
  reparte el costo.
- Recomendación (hilo 7 §4): o $2,50/mes con **tope duro de 10** y «comparto mi proxy entre conocidos, sin
  soporte garantizado», o **$5/mes**: 2 cubren la promo, 3-4 la renovación, y queda margen para el soporte.
- El límite real es **el soporte**, no la máquina: con 1 persona de soporte, 5-10 inquilinos. El ancho de banda
  (4 TB/mes en el KVM 1) no limita: lo de Claude Code es texto.

## Lo que se construiría (cuando los bloqueadores estén resueltos)
1. **Túnel cifrado por inquilino**: SSH con `-D` (SOCKS) o un túnel SSH al puerto del proxy. El tráfico va
   cifrado hasta el VPS y solo hace falta `sshd`, que ya existe. Es la misma receta que el relay: una sola
   pieza resuelve las dos cosas. Descartados:
   - *tinyproxy detrás de TLS*: más piezas, y un certificado con dominio;
   - *WireGuard por inquilino*: más seguro, pero cada inquilino necesita cliente y clave, y eso es soporte por
     usuario.
2. **Script de alta / baja / revocación / vencimiento** (en el VPS):
   - **Alta**:
     - clave SSH **restringida** en `authorized_keys`, solo túnel y sin shell:
       `restrict,port-forwarding,permitopen="127.0.0.1:<puerto>",command="/bin/false"`;
     - fecha de pago y vencimiento en el registro;
     - credenciales + instrucciones listas para mandar por WhatsApp.
   - **Baja / revocación**: quitar la clave de `authorized_keys` y reiniciar tinyproxy; **menos de 1 minuto**,
     registrado (quién, cuándo, por qué).
   - **Vencimiento**: una tarea diaria (cron) corta solo a quien pasó su fecha sin pagar.
   - **Límites**: `MaxClients` global + tope de conexiones por usuario. `ConnectPort` solo **443 / 563 / 8443**,
     para que no sirva para otra cosa. Corte al primer abuso.
3. **Registro de inquilinos**: quién, desde cuándo, hasta cuándo, cuánto pagó, por qué vía (**Pago Móvil**
   recomendado, USDT por Binance Pay, Zinli; **no** Stripe, que no opera en Venezuela, ni tarjetas ni
   efectivo) y estado (activo / vencido / revocado). El pago se verifica **a mano**: con 5-10 inquilinos son
   5-10 verificaciones al mes.
4. **Lo que se alquila**: acceso a un proxy privado (infraestructura de red). **Cada inquilino usa SU cuenta de
   Claude/ChatGPT y SU clave**: compartir cuentas lo prohíben los proveedores.

## Riesgo para el VPS, dicho en voz alta
Si un inquilino usa el proxy para algo abusivo (spam, scraping masivo, ataques), **la IP del VPS puede quedar
bloqueada por los proveedores, y esa IP es también la de Leandro** (la que usa Growi Bridge). Mitigación: solo
inquilinos conocidos (nada de venta abierta), corte al primer abuso, `ConnectPort` restringido y tope de
conexiones. El script y la app lo dirán, no lo esconderán.

## Para desbloquear
1. Mirar en el panel de Hostinger qué plan es el VPS 2.25.244.222 y cuánto se paga.
2. Consultar con Angelis lo legal y lo fiscal (CONATEL, reventa, impuestos) y apuntar la respuesta.
3. Hacer el túnel SSH por inquilino (punto 1) **antes** de dar acceso a nadie: sin él, la clave viaja en claro.
4. Para vender (no solo compartir): fijar precio y tope.
