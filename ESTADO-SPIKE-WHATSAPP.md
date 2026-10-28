# ESTADO — Spike WhatsApp (t-spike-whatsapp)

Rama `Claude`. Documento del spike: **`SPIKE-WHATSAPP.md`**. No hay código: es un spike. Datos consultados en
vivo el 28-oct-2026 en PyPI y en el registro de npm, y versiones de Node y Python de este PC.

## LISTO
- **(c) Recomendación escrita**:
  - **ganadora: Baileys como sidecar Node**, versión fijada en 6.7.24 (la estable; la 7.0.0 sigue en *rc*);
  - **reserva: pyaileys**;
  - **waeys descartada para empaquetar**: no declara licencia y todas sus versiones son del mismo día.

  Va con motivos (coste $0, Node ≥ 20 ya presente, MIT, qué se empaqueta y qué se exige instalar),
  la lista de lo que **NO** se promete (plantillas, botones, catálogos, WhatsApp Business), el riesgo de
  baneo con su mitigación y la Cloud API como fase posterior (de pago).
- **(d) Constancia**: el número personal de Leandro **no se vinculó**. No se generó ni escaneó ningún QR y no
  se instaló ninguna librería.
- Procedimiento escrito para la prueba en vivo y la medición de 2 h / 48 h (`SPIKE-WHATSAPP.md`, al final).
- Datos reales:
  - Node v24.20.0 / npm 11.19.0 y Python 3.12.10 en el PC;
  - Baileys `7.0.0-rc14` (latest) y `6.7.24` (legacy), MIT, `node >= 20`;
  - waeys `0.1.3` (sin licencia, solo `websockets`);
  - pyaileys `0.1.5` (MIT; `cryptography`, `protobuf`, `websockets`).

## FALTA
- **(a) Prueba en vivo de las tres vías** (instalar, conectar con QR, texto e imagen en los dos sentidos).
  **No se hizo** por dos motivos:
  1. en esta sesión no se autoriza instalar código externo (el mismo bloqueo que con OpenCode, spec 26); no
     se intentó saltarlo;
  2. **no hay número de pruebas**, y el personal no se vincula sin una decisión escrita de Leandro.

  La tabla de `SPIKE-WHATSAPP.md` deja cada casilla como FALTA con su motivo. No dice «no sirve».
- **(b) Estabilidad medida**: 0 h, porque ninguna vía conectó. El procedimiento para 2 h continuas y 48 h está
  escrito.
- Para seguir: un número de pruebas y la autorización para instalar en `%TEMP%\spike-wa\` (pasos en el
  documento).

## COMO PROBARLO
Leer `SPIKE-WHATSAPP.md` y seguir «Procedimiento para la prueba en vivo» con un número de pruebas.
