"""Parche t-skills-unidades-052 (0.5.2, componente 4 de 5) sobre growi-bridge.py: SKILLS COMO UNIDADES.
- Pedir una skill por su nombre: «skill» (texto o lista) en el .task.json, en un paso de workflow o en
  encolar_tarea(skill=...). Se activa siempre y primero; si no existe o no es valida, la tarea no se encola.
- Contrato opcional en el frontmatter: entradas ("nombre | pregunta | por_defecto") y salidas (archivos). Las
  entradas sin valor por defecto son obligatorias; las salidas se vuelven criterios (existe, o frase si llevan *).
- skills_estadisticas() (de los .result.json), skills_vista() y /gateway/skills con el token de siempre.

  python parche_skills_unidades_052.py <growi-bridge.py>
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
raw = p.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "t-skills-unidades-052" in s:
    print("ya parcheado")
    sys.exit(0)


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (s.count(old), old[:90])
    s = s.replace(old, new)


rep('_SKILL_CLAVES = {"name", "description", "version", "requires", "primaryEnv", "always", "borrador"}\n',
    '_SKILL_CLAVES = {"name", "description", "version", "requires", "primaryEnv", "always", "borrador",\n'
    '                 "entradas", "salidas"}  # entradas/salidas: contrato de la unidad (t-skills-unidades-052)\n')
rep('''        it["requires"] = req
''', '''        it["requires"] = req
        it["entradas"], it["salidas"], _pc = _skill_contrato(meta)  # t-skills-unidades-052
        prob += _pc
''')
rep('''def skills_indice():
    """El indice actual (lo construye la primera vez)."""''', '''def _skill_contrato(meta):
    """t-skills-unidades-052: (entradas, salidas, problemas) del frontmatter. Entradas: «nombre | pregunta |
    por_defecto» (sin valor por defecto = obligatoria). Salidas: archivos que la skill deja en la carpeta."""
    ent, sal, prob = [], [], []
    for x in meta.get("entradas") or []:
        if not isinstance(x, str) or not x.strip():
            prob.append("«entradas»: cada una es un texto «nombre | pregunta | por_defecto»")
            continue
        partes = [y.strip() for y in x.split("|")]
        if not re.match(r"^[a-z][a-z0-9_]{0,31}$", partes[0]):
            prob.append(f"«entradas»: «{partes[0][:30]}» no es un nombre válido (minúsculas, números y _)")
            continue
        ent.append({"nombre": partes[0], "pregunta": partes[1] if len(partes) > 1 and partes[1] else partes[0],
                    "por_defecto": partes[2] if len(partes) > 2 and partes[2] != "" else None})
    for x in meta.get("salidas") or []:
        if not isinstance(x, str) or not x.strip() or ".." in x or x.strip().startswith(("/", "\\\\")) or ":" in x:
            prob.append(f"«salidas»: «{str(x)[:40]}» tiene que ser un archivo relativo a la carpeta de la tarea")
            continue
        sal.append(x.strip())
    if not isinstance(meta.get("entradas") or [], list) or not isinstance(meta.get("salidas") or [], list):
        prob.append("«entradas» y «salidas» tienen que ser listas")
    return ent, sal, prob


def skill_por_nombre(nombre):
    """La skill del indice con ese nombre (sin distinguir mayusculas), o None."""
    n = str(nombre or "").strip().lower()
    return next((sk for sk in skills_indice()["skills"] if sk["name"].lower() == n), None)


def resolver_skills_pedidas(data):
    """t-skills-unidades-052: «skill» del task -> (nombres, entradas, criterios_extra, error). Una skill pedida
    que no existe, o una entrada obligatoria sin valor, es un error al encolar (no al correr)."""
    raw = data.get("skill")
    if raw in (None, "", []):
        return [], {}, [], None
    nombres = [raw] if isinstance(raw, str) else raw
    if not isinstance(nombres, list) or not all(isinstance(x, str) and x.strip() for x in nombres):
        return [], {}, [], "skill tiene que ser el nombre de una skill o una lista de nombres"
    if len(nombres) > SKILL_MAX_ACTIVAS:
        return [], {}, [], f"como mucho {SKILL_MAX_ACTIVAS} skills por tarea (pediste {len(nombres)})"
    dadas = data.get("entradas") or {}
    if not isinstance(dadas, dict):
        return [], {}, [], "entradas tiene que ser un objeto {nombre: valor}"
    out, entradas, crit = [], {}, []
    for n in nombres:
        sk = skill_por_nombre(n)
        if sk is None:
            hay = ", ".join(x["name"] for x in skills_indice()["skills"]) or "ninguna"
            return [], {}, [], f"la skill «{n}» no existe o no es válida en este PC (hay: {hay})"
        out.append(sk["name"])
        for e in sk.get("entradas") or []:
            v = dadas.get(e["nombre"], e["por_defecto"])
            if v is None or str(v).strip() == "":
                return [], {}, [], f"falta la entrada «{e['nombre']}» de la skill «{sk['name']}»: {e['pregunta']}"
            entradas[e["nombre"]] = str(v)[:2000]
        for f in sk.get("salidas") or []:
            crit.append(f"Hay al menos un archivo {f} en la carpeta de la tarea" if any(c in f for c in "*?[")
                        else {"tipo": "existe", "archivo": f})
    return out, entradas, crit, None


def skills_indice():
    """El indice actual (lo construye la primera vez)."""''')
# validate_task: resolver la skill pedida, sumar sus salidas como criterios y devolverla
rep('''    canal = data.get("canal")
    if canal is not None and (not isinstance(canal, str) or not _safe_id(canal)):
        return None, f"canal invalido: {canal}"
    return {''', '''    canal = data.get("canal")
    if canal is not None and (not isinstance(canal, str) or not _safe_id(canal)):
        return None, f"canal invalido: {canal}"
    skills_pedidas, entradas_skill, sk_crit, sk_err = resolver_skills_pedidas(data)  # t-skills-unidades-052
    if sk_err:
        return None, sk_err
    if sk_crit and not criterios_tipados:  # las salidas de la skill, salvo que el task traiga sus criterios tipados
        _cf, _ct, _ce = separar_criterios(sk_crit, cwd)
        if _ce:
            return None, f"las salidas de la skill no se pueden comprobar: {_ce}"
        criterios, criterios_tipados = criterios + [c for c in _cf if c not in criterios], _ct
    return {
        "skills_pedidas": skills_pedidas or None, "entradas_skill": entradas_skill or None,''')
# skills_bloque_prompt: las pedidas van primero y siempre; luego las elegidas por descripcion
rep('''        for sk, punt, comun in asis_skills_cands(task, skills_para_texto(task.get("prompt") or "")):''',
    '''        pedidas = [x for x in (skill_por_nombre(n) for n in (task.get("skills_pedidas") or [])) if x]
        _pn = {x["name"] for x in pedidas}
        reg["pedidas"] = sorted(_pn)
        cands = ([(x, "pedida", ["pedida por la tarea"]) for x in pedidas]
                 + [c for c in asis_skills_cands(task, skills_para_texto(task.get("prompt") or ""))
                    if c[0]["name"] not in _pn])[:max(len(pedidas), SKILL_MAX_ACTIVAS)]
        if task.get("entradas_skill"):
            partes.append("--- Entradas de la skill ---\\n" + "\\n".join(f"{k}: {v}" for k, v in task["entradas_skill"].items())
                          + "\\n--- Fin de las entradas ---")
        for sk, punt, comun in cands:''')
# plumbing de workflows: el paso puede llevar skill y entradas
rep('''        for k in ("acciones", "revisar", "allowed_tools", "permission_mode", "timeout_min"):
            if k in p:
                paso[k] = p[k]''', '''        for k in ("acciones", "revisar", "allowed_tools", "permission_mode", "timeout_min", "skill", "entradas"):
            if k in p:
                paso[k] = p[k]''')
rep('''                for k in ("acciones", "revisar"):
                    if k in p:
                        f[k] = p[k]''', '''                for k in ("acciones", "revisar", "skill", "entradas"):  # skill: t-skills-unidades-052
                    if k in p:
                        f[k] = p[k]''')
rep('''DAG_EXTRA = ("model", "acciones", "revisar", "titulo", "plantilla", "dinero", "allowed_tools", "permission_mode",
             "timeout_min")''', '''DAG_EXTRA = ("model", "acciones", "revisar", "titulo", "plantilla", "dinero", "allowed_tools", "permission_mode",
             "timeout_min", "skill", "entradas")''')
rep('''    for k in ("acciones", "revisar", "allowed_tools", "permission_mode", "timeout_min"):
        if k in extra:
            t[k] = extra[k]''', '''    for k in ("acciones", "revisar", "allowed_tools", "permission_mode", "timeout_min", "skill", "entradas"):
        if k in extra:
            t[k] = extra[k]''')
# encolar_tarea(skill=, entradas=)
rep('def encolar_tarea(prompt, criterios=None, model=None, engine=None, origen="app", urgente=False,\n'
    '                  despues_de=None):\n',
    'def encolar_tarea(prompt, criterios=None, model=None, engine=None, origen="app", urgente=False,\n'
    '                  despues_de=None, skill=None, entradas=None):\n')
rep('''    if despues_de:  # t-oficina-paseo-050: «después de esto», espera a que se resuelva esa aprobacion''',
    '''    if skill:  # t-skills-unidades-052: la skill pedida por su nombre (y sus entradas)
        data["skill"] = skill
        if entradas:
            data["entradas"] = dict(entradas)
    if despues_de:  # t-oficina-paseo-050: «después de esto», espera a que se resuelva esa aprobacion''')
# estadisticas, vista y gateway
rep('''def workflows_vista():''', '''def skills_estadisticas(dias=90):
    """t-skills-unidades-052: por skill, de los .result.json de los ultimos `dias`: usos (pedida / por
    descripcion), terminadas bien, costo mediano y ultima vez. Sin base nueva: sale de lo que ya se escribe."""
    corte = time.time() - dias * 86400
    st = {}
    for f in RESULTS.glob("*.result.json"):
        try:
            if f.stat().st_mtime < corte:
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        usadas = d.get("skills_activadas") or []
        pedidas = set(d.get("skills_pedidas") or [])
        for n in usadas:
            e = st.setdefault(n, {"usos": 0, "pedida": 0, "por_descripcion": 0, "ok": 0, "costos": [], "ultima": None})
            e["usos"] += 1
            e["pedida" if n in pedidas else "por_descripcion"] += 1
            e["ok"] += d.get("status") == "ok"
            if isinstance(d.get("cost_usd"), (int, float)):
                e["costos"].append(d["cost_usd"])
            fin = d.get("finished_at")
            if fin and (e["ultima"] is None or fin > e["ultima"]):
                e["ultima"] = fin
    for e in st.values():
        c = sorted(e.pop("costos"))
        e["costo_mediano"] = round(c[len(c) // 2], 4) if c else None
        e["tasa_ok"] = round(e["ok"] / e["usos"], 2) if e["usos"] else None
    return st


def skills_vista():
    """t-skills-unidades-052: cada skill como unidad: contrato, requisitos en este PC, estadisticas y validez."""
    est = skills_estadisticas()
    out = []
    for sk in skills_indice()["skills"]:
        out.append({"nombre": sk["name"], "version": sk.get("version"), "descripcion": sk.get("description"),
                    "origen": sk.get("origen_txt"), "entradas": sk.get("entradas") or [], "salidas": sk.get("salidas") or [],
                    "requisitos": skill_requisitos(sk), "estadisticas": est.get(sk["name"]),
                    "como_pedirla": {"skill": sk["name"], "entradas": {e["nombre"]: e["por_defecto"] or f"<{e['pregunta']}>"
                                                                        for e in sk.get("entradas") or []}}})
    return {"skills": out, "en_resultados_sin_skill_instalada": sorted(set(est) - {x["nombre"] for x in out})}


def workflows_vista():''')
rep('''        if u.path == "/gateway/workflows":  # los workflows con su costo estimado (t-workflows-052)''',
    '''        if u.path == "/gateway/skills":  # las skills como unidades (t-skills-unidades-052)
            try:
                return self._json(skills_vista())
            except Exception as e:
                log(f"gateway: /gateway/skills fallo ({type(e).__name__}: {e})")
                return self._json({"error": f"{type(e).__name__}: {e}"}, 500)
        if u.path == "/gateway/workflows":  # los workflows con su costo estimado (t-workflows-052)''')
# el resultado anota que skills pidio la tarea (para las estadisticas)
rep('''            result.setdefault("skills_activadas", [a["nombre"] for a in reg["activadas"]])''',
    '''            result.setdefault("skills_activadas", [a["nombre"] for a in reg["activadas"]])
            if reg.get("pedidas"):  # t-skills-unidades-052: para las estadisticas por skill
                result.setdefault("skills_pedidas", list(reg["pedidas"]))''')
out = s.replace("\n", "\r\n") if crlf else s
p.write_bytes(out.encode("utf-8"))
print(f"parcheado {p} (t-skills-unidades-052)")
