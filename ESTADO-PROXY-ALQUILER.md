# ESTADO — Compartir / alquilar el proxy (t-proxy-alquiler)

Rama `Claude`. **No se construyó nada**: el propio spec lo manda mientras falte algún bloqueador. El plan
completo está en **`PROXY-ALQUILER-PLAN.md`**.

## Estado de los bloqueadores
| Bloqueador | Estado |
|---|---|
| Precio y tope | **Decidido** (Leandro, 26-oct-2026): sin límite y sin precio, solo entre conocidos; la venta sigue bloqueada |
| Túnel cifrado por inquilino | **FALTA**: hoy BasicAuth viaja en claro |
| Consulta legal/fiscal con Angelis | **FALTA** (no se afirma que sea legal ni ilegal) |
| Plan exacto del VPS (Hostinger, 2.25.244.222) | **FALTA**: hay que mirarlo en el panel |

## LISTO
- **(a) Documento de lo que se haría**: `PROXY-ALQUILER-PLAN.md`. Recoge:
  - los números (3-8 inquilinos solo para cubrir el VPS; recomendación $2,50 con tope 10, o $5);
  - el túnel SSH por inquilino, con las alternativas descartadas y por qué;
  - el script de alta/baja/revocación/vencimiento: clave SSH restringida, revocación en menos de 1 min,
    cron diario, `ConnectPort` 443/563/8443, `MaxClients`;
  - el registro de inquilinos y las vías de cobro (Pago Móvil, USDT, Zinli; no Stripe);
  - el **riesgo para la IP del VPS, que es también la de Leandro**, con su mitigación;
  - qué hace falta para desbloquear.

## FALTA
- **(b)-(e)** alta con túnel, revocación, vencimiento y registro: **no se construyen** hasta resolver el
  túnel, lo legal y el plan del VPS. Nada se publica en la app (ni precio ni oferta).

## COMO PROBARLO
Leer `PROXY-ALQUILER-PLAN.md`. Cuando estén los tres bloqueadores, se construye siguiendo esa lista.
