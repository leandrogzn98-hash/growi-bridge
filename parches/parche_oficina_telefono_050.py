"""Parche t-oficina-telefono-050 sobre oficina/protocolo/oficina_proto.py: el campo «Pedirle algo» pasa a ser
el TELEFONO al gerente (oficina/telefono/telefono.py): se abre con la tecla T o con el icono de la esquina,
una sola linea, sin historial; muestra el guardrail actual y el motor sugerido; la respuesta sale en un
bocadillo de Growi (una por mensaje) y Growi «lee» con el auricular mientras se crea la tarea real.
Sin Bridge, el encargo queda de borrador «pendiente de enviar» (lo del spec 5).

  python parche_oficina_telefono_050.py <oficina_proto.py>
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "t-oficina-telefono-050" in s:
    print("ya parcheado")
    sys.exit(0)


def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:80])
    s = s.replace(old, new)


rep('import estados as E  # noqa: E402  (t-oficina-estados-050: derivar_estado, transiciones, dormir)\n',
    'import estados as E  # noqa: E402  (t-oficina-estados-050: derivar_estado, transiciones, dormir)\n'
    'sys.path.insert(0, str(AQUI.parent / "telefono"))\n'
    'import telefono as TF  # noqa: E402  (t-oficina-telefono-050: el telefono al gerente)\n')
rep('MEM = E.Memoria(registro=metrica)\n',
    'MEM = E.Memoria(registro=metrica)\n'
    'TEL = TF.Telefono(cola=lambda: F["cola-live"].vista()["datos"] if "cola-live" in F else None, registro=metrica)\n'
    'tel_abierto = False\n'
    'tragar_t = False\n')
rep('''        elif e.type == pygame.TEXTINPUT and foco:
            entrada = (entrada + e.text)[:500]
''', '''        elif e.type == pygame.TEXTINPUT and foco:
            if tragar_t and e.text.lower() == "t":  # la T que abrio el telefono no se escribe
                tragar_t = False
                continue
            tragar_t = False
            entrada = (entrada + e.text)[:500]
''')
# T abre el telefono; Enter envia por el telefono (o borrador si no hay Bridge); Esc cuelga
rep('''            if e.key == pygame.K_TAB:
                foco = not foco
                (pygame.key.start_text_input if foco else pygame.key.stop_text_input)()''',
    '''            if e.key == pygame.K_t and not foco:
                tel_abierto, foco, tragar_t = True, True, True  # el telefono: tecla T
                pygame.key.start_text_input()
                continue
            if e.key == pygame.K_TAB:
                foco = not foco
                tel_abierto = tel_abierto or foco
                (pygame.key.start_text_input if foco else pygame.key.stop_text_input)()''')
rep('''            elif foco and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and entrada.strip():
                it = BOR.nuevo(entrada.strip())  # primero a disco: no se pierde aunque caiga todo
                log(f"encargo escrito: «{it['texto'][:60]}» -> " + (
                    "se envía" if _puede_enviar() else "borrador local, pendiente de enviar"))
                entrada = ""
                _enviar_pendientes()''',
    '''            elif foco and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and entrada.strip():
                if _puede_enviar():  # el telefono: el gerente lo clasifica y, si es tarea, la encola como la app
                    TEL.enc = ENC["mod"]
                    r_tel = TEL.enviar(entrada.strip())
                    log(f"telefono: «{entrada.strip()[:60]}» -> {r_tel}")
                else:
                    it = BOR.nuevo(entrada.strip())  # sin Bridge: borrador en disco, «pendiente de enviar»
                    log(f"encargo escrito sin Bridge: «{it['texto'][:60]}» -> borrador local, pendiente de enviar")
                entrada = ""''')
rep('''            elif e.key == pygame.K_ESCAPE:
                foco = False''', '''            elif e.key == pygame.K_ESCAPE:
                foco, tel_abierto = False, False''')
rep('''            foco = caja_in.collidepoint(e.pos)''', '''            if icono_tel.collidepoint(e.pos):
                tel_abierto = not tel_abierto
            foco = tel_abierto and caja_in.collidepoint(e.pos) or (tel_abierto and icono_tel.collidepoint(e.pos))''')
rep('caja_in = pygame.Rect(30, H - 46, 560, 30)\n',
    'caja_in = pygame.Rect(30, H - 46, 560, 30)\nicono_tel = pygame.Rect(W - 56, H - 56, 40, 40)\n')
# Growi lee con el auricular mientras el telefono trabaja
rep('''        if pid == "growi" and e_ in (E.SIN_TAREA, E.SIN_SENAL):''',
    '''        if pid == "growi" and TEL.estado != "colgado":
            ACTIVIDAD[pid] = "al teléfono"
        elif pid == "growi" and e_ in (E.SIN_TAREA, E.SIN_SENAL):''')
# el panel: sustituye la lista de borradores (historial) por el telefono de una linea
i = s.index('    texto("Pedirle algo (Tab para escribir, Enter para enviar). Nunca se finge enviado:", F12, C["suave"], 30, 540)\n')
j = s.index('    if cierre_t is not None:\n', i)
s = s[:i] + '''    # ---- telefono al gerente (t-oficina-telefono-050): una linea, sin historial
    pygame.draw.rect(pantalla, C["acento"] if tel_abierto else C["panel"], icono_tel, border_radius=10)
    pygame.draw.rect(pantalla, C["linea"], icono_tel, 1, border_radius=10)
    texto("T", F18, C["panel"] if tel_abierto else C["texto"], icono_tel.x + 14, icono_tel.y + 8)
    if tel_abierto:
        gr = ((V["cola-live"]["datos"] or {}).get("guardrail") if isinstance(V["cola-live"]["datos"], dict) else None)
        texto(f"Teléfono al gerente · guardrail: {gr or '—'} · motor sugerido: {TEL.motor_sugerido()}"
              f"{' · Growi está leyendo…' if TEL.estado != 'colgado' else ''}", F12, C["suave"], 30, 540, W - 120)
        pygame.draw.rect(pantalla, C["panel"], caja_in, border_radius=6)
        pygame.draw.rect(pantalla, C["acento"] if foco else C["linea"], caja_in, 1, border_radius=6)
        texto(entrada + ("|" if foco and int(t * 2) % 2 else ""), F13, C["texto"], caja_in.x + 8, caja_in.y + 5,
              caja_in.w - 16)
        texto("Enviar ⏎", F13, C["acento"], caja_in.right + 10, caja_in.y + 6)
    else:
        texto("Pulsa T (o el icono) para llamar al gerente.", F12, C["suave"], 30, H - 40)
    pend = BOR.pendientes()
    if pend:  # solo lo pendiente de enviar (sin Bridge), nunca un historial
        texto(f"{len(pend)} pendiente(s) de enviar: «{pend[-1]['texto'][:50]}»", F12, C["ambar"], 30, 556, W - 120)
    if TEL.bocadillo and time.time() - TEL.bocadillo[1] < 8:
        gx, gy = POS["growi"]
        caja_b = pygame.Rect(gx - 10, gy - 34, min(560, 12 + F12.size(TEL.bocadillo[0])[0]), 22)
        pygame.draw.rect(pantalla, C["panel"], caja_b, border_radius=8)
        pygame.draw.rect(pantalla, C["texto"], caja_b, 1, border_radius=8)
        texto(TEL.bocadillo[0], F12, C["texto"], caja_b.x + 6, caja_b.y + 3, 548)
    elif TEL.estado != "colgado":
        gx, gy = POS["growi"]
        texto("…", F18, C["texto"], gx + 8, gy - 26)
''' + s[j:]
out = s.replace("\n", "\r\n") if crlf else s
p.write_bytes(out.encode("utf-8"))
print(f"parcheado {p}; marca t-oficina-telefono-050")
