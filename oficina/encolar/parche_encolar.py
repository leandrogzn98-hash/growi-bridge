"""Parche t-oficina-encolar-externa-050: saca de _send_ask (UI) la parte que
construye y escribe el .task.json a encolar_tarea() (sin ventana), y _send_ask
la llama. Se aplica por separado a cada copia (no se copian entre si).
Uso: python parche_encolar.py <growi-bridge.py> [...]"""
import shutil
import sys
from pathlib import Path

OLD = '''def _send_ask():
    """Manda la tarea escrita en la pagina Tareas al runner (Claude u
    Ollama local, segun el motor elegido)."""
    w = _widgets
    text = w.get("ask_text")
    if text is None:
        return
    prompt = text.get("1.0", "end").strip()
    if not prompt:
        return
    if mem_comando_ui(prompt, "chat de Tareas"):  # «/nuevo» y «recuerda esto»: memoria, no tarea
        text.delete("1.0", "end")
        return
    engine = "Claude Sonnet"
    try:
        engine = w["ask_engine"].get() or engine
    except Exception:
        pass
    model = _ASK_ENGINES.get(engine, "sonnet")
    if model.startswith("ollama:") and not valid_model_name(model.split(":", 1)[1]):
        model = "sonnet"
    model, fell = local_fallback_model(model)
    if fell:
        engine = "el modelo local (sin nube, calidad menor)"
    crit_box = w.get("ask_criterios")
    criterios = []
    if crit_box is not None:
        for c in crit_box.get("1.0", "end").splitlines():
            c = c.strip(" -•\\t")
            if c.startswith("{"):
                try:
                    d = json.loads(c)
                    if isinstance(d, dict):  # criterio tipado; el runner lo valida al encolar
                        criterios.append(d)
                        continue
                except ValueError:
                    pass
            if c:
                criterios.append(c)
    TASKS.mkdir(parents=True, exist_ok=True)
    base = "t-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    task_id = base
    i = 1
    while (TASKS / f"{task_id}.task.json").exists():
        task_id = f"{base}-{i}"
        i += 1
    data = {"id": task_id, "prompt": prompt, "cwd": asis_cwd_envio(), "model": model,
            "timeout_min": 30, "allowed_tools": "Read,Write,Edit,Bash",
            "permission_mode": "acceptEdits"}
    _asis = asis_activo()
    if _asis is not None:
        data["asistente"] = _asis["id"]  # la tarea queda con el asistente con el que se mando
    if model == "motor:auto":
        # Elige el runner; los permisos quedan por si elige Claude.
        data.pop("model")
        data["motor"] = AUTO
    elif model.startswith("motor:"):
        data.pop("model")
        data["motor"] = model.split(":", 1)[1]
        _e = get_engine(data["motor"]) or {}
        # Lo que el descriptor dice que puede: herramientas de Growi y permisos.
        if not _cap(_e, "habilidades_growi"):
            data.pop("allowed_tools")
        if not _cap(_e, "herramientas"):
            data.pop("permission_mode")
    if criterios:
        data["criterios"] = criterios
    (TASKS / f"{task_id}.task.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"tareas: '{task_id}' enviado al runner ({engine})")
    text.delete("1.0", "end")
    if crit_box is not None:
        crit_box.delete("1.0", "end")
    if w.get("ask_status") is not None:
        w["ask_status"].config(text=f"✓ Enviado al runner ({engine})")
        _ask_spinner(task_id, engine)
'''

NEW = '''# ---------------------------------------------------------------- encolar (sin ventana)
# t-oficina-encolar-externa-050: lo que hace «Pedirle algo» (Tareas y Ctrl+K ->
# «Pedirle algo a Claude») ya no vive solo en la ventana. encolar_tarea() arma y
# escribe el MISMO .task.json en runner-tasks/; _send_ask (la ventana) la llama, y
# otro proceso (la oficina: oficina\\encolar\\encolar.py) la importa y la llama igual.
# Lo que pasa despues es del runner, no de quien encola: lo apunta en cola.db
# (cola_registrar via _cola_ver, ANTES de recogerlo) y le aplica el guardrail
# (_approval_needed -> _park_for_approval -> «esperando_aprobacion»). Esta
# funcion NUNCA escribe cola.db, runner-live.json, runner-status.json,
# .revision.json, .orquestacion.json ni settings.json (settings solo se lee).
def criterios_de_texto(texto):
    """Una frase por linea (sin viñetas); una linea {...} es un criterio tipado."""
    criterios = []
    for c in str(texto or "").splitlines():
        c = c.strip(" -•\\t")
        if c.startswith("{"):
            try:
                d = json.loads(c)
                if isinstance(d, dict):  # criterio tipado; el runner lo valida al encolar
                    criterios.append(d)
                    continue
            except ValueError:
                pass
        if c:
            criterios.append(c)
    return criterios


def _modelo_por_defecto():
    """El model del task que la ventana pone por defecto (Ajustes)."""
    try:
        return _ASK_ENGINES.get(_default_engine_label(engine_choices()), "sonnet")
    except Exception:
        return "sonnet"


def encolar_tarea(prompt, criterios=None, model=None, engine=None, origen="app"):
    """Encola una tarea como «Pedirle algo». -> {"ok", "id", "archivo", "engine",
    "data", "error"}. model = el «model» del task que da el desplegable («sonnet»,
    «opus», «haiku», «motor:auto», «motor:llama», «ollama:<nombre>»...); sin model
    va el de por defecto de Ajustes. criterios = lista (frases o dicts tipados) o
    texto con una frase por linea. origen solo va al Registro: el .task.json es
    identico venga de la ventana o de otro proceso."""
    prompt = str(prompt or "").strip()
    if not prompt:
        return {"ok": False, "error": "el encargo está vacío"}
    if re.match(r"^\\s*/nuevo\\b", prompt, re.I) or _MEM_RECUERDA_RE.match(prompt):
        return {"ok": False, "error": "«/nuevo» y «recuerda esto» son de la memoria, no una tarea"}
    if isinstance(criterios, str):
        criterios = criterios_de_texto(criterios)
    criterios = [c if isinstance(c, dict) else str(c).strip(" -•\\t") for c in (criterios or [])]
    criterios = [c for c in criterios if isinstance(c, dict) or c]
    if not model:
        model = _modelo_por_defecto()
    model = str(model).strip()
    if engine is None:
        engine = next((l for l, m in _ASK_ENGINES.items() if m == model), model)
    if model.startswith("ollama:") and not valid_model_name(model.split(":", 1)[1]):
        model = "sonnet"
    model, fell = local_fallback_model(model)
    if fell:
        engine = "el modelo local (sin nube, calidad menor)"
    TASKS.mkdir(parents=True, exist_ok=True)
    base = "t-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    data = {"id": base, "prompt": prompt, "cwd": asis_cwd_envio(), "model": model,
            "timeout_min": 30, "allowed_tools": "Read,Write,Edit,Bash",
            "permission_mode": "acceptEdits"}
    _asis = asis_activo()
    if _asis is not None:
        data["asistente"] = _asis["id"]  # la tarea queda con el asistente con el que se mando
    if model == "motor:auto":
        # Elige el runner; los permisos quedan por si elige Claude.
        data.pop("model")
        data["motor"] = AUTO
    elif model.startswith("motor:"):
        data.pop("model")
        data["motor"] = model.split(":", 1)[1]
        _e = get_engine(data["motor"]) or {}
        # Lo que el descriptor dice que puede: herramientas de Growi y permisos.
        if not _cap(_e, "habilidades_growi"):
            data.pop("allowed_tools")
        if not _cap(_e, "herramientas"):
            data.pop("permission_mode")
    if criterios:
        data["criterios"] = criterios
    # Escritura atomica y exclusiva: se escribe aparte (.tmp, que el runner no
    # mira: solo busca *.task.json) y se renombra; en Windows os.rename falla si
    # el nombre ya existe, asi que dos procesos que encolan en el mismo segundo
    # nunca se pisan (el segundo toma el sufijo -1, -2...).
    tmp = TASKS / f".{base}-{os.getpid()}-{threading.get_ident()}.tmp"
    i = 0
    try:
        while True:
            tid = base if i == 0 else f"{base}-{i}"
            i += 1
            dest = TASKS / f"{tid}.task.json"
            if dest.exists() or any((d / f"{tid}.task.json").exists()
                                    for d in (PROCESSING, DONE, WAITING)):
                continue
            data["id"] = tid
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                os.rename(tmp, dest)
                break
            except FileExistsError:
                continue
    except OSError as e:
        try:
            tmp.unlink()
        except OSError:
            pass
        return {"ok": False, "error": f"no se pudo escribir en {TASKS} ({type(e).__name__}: {e})"}
    log(f"tareas: '{tid}' enviado al runner ({engine})"
        + ("" if origen == "app" else f"; pedido desde {str(origen)[:40]}"))
    return {"ok": True, "id": tid, "archivo": str(dest), "engine": engine, "data": data, "error": None}


def _send_ask():
    """Manda la tarea escrita en la pagina Tareas al runner (Claude u
    Ollama local, segun el motor elegido). El encargo lo arma y lo escribe
    encolar_tarea(); aqui solo se lee la ventana y se pinta el resultado."""
    w = _widgets
    text = w.get("ask_text")
    if text is None:
        return
    prompt = text.get("1.0", "end").strip()
    if not prompt:
        return
    if mem_comando_ui(prompt, "chat de Tareas"):  # «/nuevo» y «recuerda esto»: memoria, no tarea
        text.delete("1.0", "end")
        return
    engine = "Claude Sonnet"
    try:
        engine = w["ask_engine"].get() or engine
    except Exception:
        pass
    model = _ASK_ENGINES.get(engine, "sonnet")
    crit_box = w.get("ask_criterios")
    criterios = criterios_de_texto(crit_box.get("1.0", "end")) if crit_box is not None else []
    r = encolar_tarea(prompt, criterios, model=model, engine=engine, origen="app")
    if not r["ok"]:
        log(f"tareas: no se pudo enviar ({r['error']})")
        if w.get("ask_status") is not None:
            w["ask_status"].config(text=f"No se pudo enviar: {r['error']}", fg=THEME["orange_text"])
        return
    task_id, engine = r["id"], r["engine"]
    text.delete("1.0", "end")
    if crit_box is not None:
        crit_box.delete("1.0", "end")
    if w.get("ask_status") is not None:
        w["ask_status"].config(text=f"✓ Enviado al runner ({engine})", fg=THEME["green_text"])
        _ask_spinner(task_id, engine)
'''

for f in sys.argv[1:]:
    p = Path(f)
    raw = p.read_bytes()
    crlf = raw.count(b"\r\n") == raw.count(b"\n")
    src = raw.decode("utf-8").replace("\r\n", "\n")
    if "def encolar_tarea(" in src:
        print("ya parcheado:", p)
        continue
    assert src.count(OLD) == 1, f"no encuentro _send_ask exacto en {p}"
    bak = p.with_name(p.name + ".pre-encolar-externa.bak")
    assert not bak.exists(), bak
    shutil.copy2(p, bak)
    out = src.replace(OLD, NEW)
    if crlf:
        out = out.replace("\n", "\r\n")
    p.write_bytes(out.encode("utf-8"))
    print("parcheado:", p, "| bak:", bak, "| CRLF:", crlf)
