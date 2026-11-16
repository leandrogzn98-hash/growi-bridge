# -*- coding: utf-8 -*-
"""Escáner de secretos y hook pre-push (Growi Bridge, Fase 3).

Doble capa independiente (§6 del diseño de la Fase 3):

- **Capa A (la que detiene a una Muse):** `git_trabajo.subir` escanea con
  `escanear_objetos` EXACTAMENTE lo que el push va a enviar — los objetos
  alcanzables desde el sha que el remoto aún no tiene — y solo sube si no
  hay hallazgos. Las tareas corren además con el entorno git sin
  credenciales de escritura (§6.2 paso 0, en `git_trabajo`).
- **Capa B (la que protege al dueño en su terminal):** un hook `pre-push`
  fino que invoca a la COPIA ESTABLE de este mismo archivo desplegada en
  la carpeta compartida (`desplegar`). Por eso este módulo es
  AUTOCONTENIDO: solo importa la biblioteca estándar (la clave HMAC de
  los permitidos se lee de la clave de `permission-layer.py`, localizable
  por entorno o importando el módulo hermano cuando está al lado).

Se escanean OBJETOS, no diffs (corrección B11): un `.gitattributes` con
`-diff`/`binary`, un commit de mezcla, un archivo UTF-16 o un textconv
dejarían pasar un secreto por un escaneo de diffs sin hacer ruido. Un
blob que no se puede decodificar o que pasa de 16 MB es un hallazgo
`no_escaneable` (fail-closed), perdonable solo por la huella del blob
entero en la lista de permitidos (§6.4). La lista de bloqueo por NOMBRE
no admite permitidos jamás.

La evidencia de cada hallazgo va SIEMPRE redactada: el secreto literal
no aparece ni en resultados, ni en logs, ni en la auditoría.
"""
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MARCA_HOOK = "# growi-bridge: pre-push v1"
MAX_BLOB_ESCANEABLE = 16 * 1024 * 1024
CEROS = "0" * 40

# ---------------------------------------------------------------- patrones
# Superconjunto de la tabla `_SECRETO_RES` del monolito (esa no se toca):
# las suyas primero y las nuevas de la Fase 3 (§6.1) después.
PATRONES = (
    ("clave tipo sk-", re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9][A-Za-z0-9_-]{5,}")),
    ("token de GitHub (gh*_)", re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{8,}")),
    ("token de GitHub (github_pat_)", re.compile(r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{8,}")),
    ("token de Slack (xox?-)", re.compile(r"(?<![A-Za-z0-9_])xox[baprs]-[A-Za-z0-9-]{6,}")),
    ("clave de Google (AIza)", re.compile(r"(?<![A-Za-z0-9_])AIza[0-9A-Za-z_-]{10,}")),
    ("clave privada (BEGIN ... PRIVATE KEY)", re.compile(r"-----BEGIN[A-Z0-9 ]*PRIVATE KEY-----")),
    ("clave de Tripo (tsk_)", re.compile(r"(?<![A-Za-z0-9_])tsk_[A-Za-z0-9_-]{8,}")),
    ("clave AWS (AKIA)", re.compile(r"(?<![A-Za-z0-9_])AKIA[0-9A-Z]{16}(?![0-9A-Z])")),
)

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_ASIG_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_.\-]*(?:SECRET|TOKEN|PASSWORD|PASSWD|API_KEY|APIKEY|PRIVATE_KEY)"
    r"[A-Za-z0-9_.\-]*)\s*[:=]\s*[\"']?([^\s\"']{12,})")


def _es_marcador(valor):
    """Un valor obvio de plantilla no es un secreto (`...`, `xxx`,
    `changeme`, `${...}`, `<...>`, o un solo carácter repetido)."""
    v = valor.strip().strip("\"'")
    if not v:
        return True
    if v.startswith("${") or (v.startswith("<") and v.endswith(">")):
        return True
    if re.fullmatch(r"\.{3,}|x{3,}|changeme|change-me|placeholder|ejemplo|example", v, re.I):
        return True
    return len(set(v)) == 1


def _redactar(texto):
    """La evidencia segura: nunca el secreto entero."""
    t = str(texto)
    if len(t) <= 4:
        return "••••"
    return f"{t[:3]}•••({len(t)} caracteres)"


def _huella_linea(linea):
    return hashlib.sha256(linea.rstrip("\r\n").encode("utf-8")).hexdigest()


def escanear_linea(linea, ruta="", nlinea=None, commit=None):
    """Hallazgos de contenido en UNA línea (sin los de nombre de archivo)."""
    out = []
    for tipo, rx in PATRONES:
        for m in rx.finditer(linea):
            out.append({"commit": commit, "archivo": ruta, "linea": nlinea,
                        "tipo": tipo, "evidencia": _redactar(m.group(0)),
                        "huella": _huella_linea(linea)})
    if "=" in linea or ":" in linea:  # el JWT solo «en asignación» (§6.1)
        for m in _JWT_RE.finditer(linea):
            if len(m.group(0)) >= 40:
                out.append({"commit": commit, "archivo": ruta, "linea": nlinea,
                            "tipo": "JWT en asignación",
                            "evidencia": _redactar(m.group(0)),
                            "huella": _huella_linea(linea)})
    for m in _ASIG_RE.finditer(linea):
        if not _es_marcador(m.group(2)):
            out.append({"commit": commit, "archivo": ruta, "linea": nlinea,
                        "tipo": f"asignación con pinta de secreto ({m.group(1)})",
                        "evidencia": _redactar(m.group(2)),
                        "huella": _huella_linea(linea)})
    return out


def escanear_texto(texto, ruta="", commit=None):
    """Hallazgos de contenido en un texto completo, línea a línea."""
    out = []
    for i, linea in enumerate(str(texto).splitlines(), 1):
        out.extend(escanear_linea(linea, ruta=ruta, nlinea=i, commit=commit))
    return out


# ------------------------------------------------------- bloqueo por nombre
_NOMBRES_EXACTOS = {
    "secret.txt", "credenciales.dpapi.json", "consultas-uso.json",
    "tablero.json", "alquileres.json", "traspasos.json", "propuestas.json",
    "accounts.json", "settings.json", "manifiesto.json",
    "cola.db", "cola.db-wal", "cola.db-shm",
}
_COMPONENTES_BLOQUEADOS = {"respaldo", "respaldo-estado", ".growi"}
_ENV_PERMITIDOS_POR_NOMBRE = {".env.example", ".env.sample"}


def nombre_bloqueado(ruta):
    """El motivo si la ruta no puede subir NUNCA por su nombre; None si pasa.

    Comparación por nombre base en minúsculas (§6.1 + I12): ni `.ENV` ni
    `Secret.txt` se cuelan en Windows. La lista de nombres NO admite
    permitidos (§6.4)."""
    partes = [p for p in str(ruta).replace("\\", "/").split("/") if p not in ("", ".")]
    if not partes:
        return None
    if any(p.lower() in _COMPONENTES_BLOQUEADOS for p in partes[:-1]):
        return "ruta dentro de una carpeta de estado de Growi (respaldo/…)"
    base = partes[-1].lower()
    if base in _NOMBRES_EXACTOS:
        return f"archivo de estado o credenciales de Growi ({base})"
    if base == ".env" or (base.startswith(".env.") and base not in _ENV_PERMITIDOS_POR_NOMBRE):
        return "archivo .env (los secretos no viven en el repo)"
    if base.startswith("audit-log") and base.endswith(".json"):
        return "registro de auditoría de Growi"
    if base.startswith("audit-indice") and base.endswith(".json"):
        return "ancla de auditoría de Growi"
    if base.endswith(".pem") or base.endswith(".key"):
        return "clave privada por extensión (.pem/.key)"
    if base.endswith(".dpapi.json"):
        return "credenciales protegidas de Growi (.dpapi.json)"
    if base.startswith("id_rsa") or base.startswith("id_ed25519"):
        return "clave SSH por nombre (id_rsa*/id_ed25519*)"
    return None


# ---------------------------------------------------------------- git real

class ErrorSecretos(Exception):
    """Fallo operativo del escáner (el llamador decide: fail-closed)."""


def correr_git_real(args, cwd=None, timeout=120, entrada=None):
    """Ejecutor git por defecto: (rc, stdout, stderr) en texto.

    Sin prompt interactivo jamás (GIT_TERMINAL_PROMPT=0); timeout con
    muerte del proceso. Los módulos que necesitan otro ejecutor lo
    inyectan; este es el que usa el hook."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        p = subprocess.run(["git", *[str(a) for a in args]],
                           cwd=str(cwd) if cwd else None, env=env,
                           input=entrada, capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise ErrorSecretos("git no está en el PATH")
    except subprocess.TimeoutExpired:
        raise ErrorSecretos(f"git {' '.join(str(a) for a in args[:2])} tardó más de {timeout} s")
    return (p.returncode,
            p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def leer_blob_real(repo, oid):
    """El contenido EXACTO (bytes) de un blob, por subprocess directo.

    Los blobs no pueden pasar por el ejecutor de texto: un binario o un
    UTF-16 llegarían mutilados y el escaneo mentiría."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        p = subprocess.run(["git", "cat-file", "blob", str(oid)],
                           cwd=str(repo), env=env, capture_output=True, timeout=120)
    except FileNotFoundError:
        raise ErrorSecretos("git no está en el PATH")
    except subprocess.TimeoutExpired:
        raise ErrorSecretos("cat-file tardó demasiado")
    if p.returncode != 0:
        raise ErrorSecretos(f"cat-file blob {str(oid)[:8]} falló")
    return p.stdout


def leer_staged_real(repo, ruta):
    """El contenido EXACTO (bytes) de un archivo tal como está en el índice."""
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        p = subprocess.run(["git", "show", f":{ruta}"],
                           cwd=str(repo), env=env, capture_output=True, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise ErrorSecretos(f"show :{ruta} falló ({type(e).__name__})")
    if p.returncode != 0:
        raise ErrorSecretos(f"show :{ruta} falló")
    return p.stdout


def _decodificar(datos):
    """Texto de un blob: UTF-8, o UTF-16 si trae BOM. None si no se puede."""
    if datos.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return datos.decode("utf-16")
        except UnicodeDecodeError:
            return None
    if datos.startswith(b"\xef\xbb\xbf"):
        try:
            return datos.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError:
        return None


# ------------------------------------------------------------- permitidos

def _clave_hmac():
    """La clave del circuito de confirmaciones de permission-layer.py.

    Orden: la ruta de GROWI_PERM_SECRET (la conoce el hook), el módulo
    hermano si está al lado (uso dentro de la app). None si no hay clave:
    sin clave ningún permitido valida (fail-closed)."""
    ruta = os.environ.get("GROWI_PERM_SECRET")
    if ruta and os.path.isfile(ruta):
        with open(ruta, "rb") as f:
            return f.read()
    try:
        import importlib.util
        vecino = Path(__file__).with_name("permission-layer.py")
        if vecino.is_file():
            spec = importlib.util.spec_from_file_location("permission_layer", str(vecino))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod._secreto()
    except Exception:
        pass
    return None


def _firma_permitido(clave, repo_id, ruta, huella, tipo):
    msg = f"{repo_id}|{ruta}|{huella}|{tipo}".encode("utf-8")
    return hmac.new(clave, msg, hashlib.sha256).hexdigest()


def _ruta_permitidos(base_dir, repo_id):
    return Path(base_dir) / f"permitidos-{repo_id}.json"


def cargar_permitidos(base_dir, repo_id):
    try:
        d = json.loads(_ruta_permitidos(base_dir, repo_id).read_text(encoding="utf-8"))
        if isinstance(d, list):
            return d
    except (OSError, ValueError):
        pass
    return []


def permitido_cubre(base_dir, repo_id, ruta, huella, tipo):
    """True SOLO si hay una entrada con firma HMAC válida para ese
    hallazgo exacto (corrección B12: los permitidos viven fuera del repo
    y los firma el dueño; una entrada sin firma válida no existe)."""
    if not base_dir or not repo_id or not huella:
        return False
    clave = _clave_hmac()
    if clave is None:
        return False
    for e in cargar_permitidos(base_dir, repo_id):
        if not isinstance(e, dict):
            continue
        if (e.get("ruta") == ruta and e.get("huella") == huella
                and e.get("tipo") == tipo):
            esperada = _firma_permitido(clave, repo_id, ruta, huella, tipo)
            if hmac.compare_digest(str(e.get("firma", "")), esperada):
                return True
    return False


def agregar_permitido(base_dir, repo_id, ruta, huella, tipo, reloj=None):
    """Crea una entrada firmada. Lo llama SOLO el CLI tras la confirmación
    humana (§6.4); el secreto nunca entra en la entrada, solo su huella."""
    clave = _clave_hmac()
    if clave is None:
        raise ErrorSecretos("no hay clave de confirmaciones para firmar el permitido")
    entrada = {"ruta": ruta, "huella": huella, "tipo": tipo,
               "creada_ts": (reloj or time.time)(),
               "firma": _firma_permitido(clave, repo_id, ruta, huella, tipo)}
    lista = cargar_permitidos(base_dir, repo_id)
    lista.append(entrada)
    path = _ruta_permitidos(base_dir, repo_id)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(lista, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return entrada


# -------------------------------------------------------- escaneo de objetos

def _tipos_objetos(repo, oids, correr_git):
    """{oid: tipo} con un solo cat-file --batch-check."""
    if not oids:
        return {}
    entrada = ("\n".join(oids) + "\n").encode("utf-8")
    rc, out, _ = correr_git(["cat-file", "--batch-check=%(objectname) %(objecttype)"],
                            cwd=repo, entrada=entrada)
    if rc != 0:
        raise ErrorSecretos("cat-file --batch-check falló")
    tipos = {}
    for linea in out.splitlines():
        partes = linea.split(" ", 1)
        if len(partes) == 2:
            tipos[partes[0]] = partes[1]
    return tipos


def escanear_objetos(repo, sha, remoto="origin", correr_git=None, base_dir=None,
                     repo_id=None, leer_blob=None):
    """Escanea los objetos que un push de `sha` enviaría y el remoto no
    tiene (correcciones B10/B11). Devuelve la lista de hallazgos
    {commit, archivo, linea, tipo, evidencia, huella} (vacía = limpio).

    Lanza ErrorSecretos si git falla: el llamador trata eso como
    bloqueo (fail-closed), nunca como «sin hallazgos»."""
    correr = correr_git or correr_git_real
    repo = str(repo)
    # ¿Hay referencia remota contra la que recortar? Sin remoto, se
    # escanea todo lo alcanzable (fail-closed, aunque sea más lento).
    rc, _, _ = correr(["rev-parse", "--verify", "--quiet",
                       f"refs/remotes/{remoto}/HEAD"], cwd=repo)
    rango = [sha, "--not", f"--remotes={remoto}"] if rc == 0 else [sha]
    rc, out, err = correr(["rev-list", "--objects", *rango], cwd=repo)
    if rc != 0:
        raise ErrorSecretos(f"rev-list falló: {err.strip()[:200]}")
    objetos = {}   # oid -> ruta (solo los que traen ruta)
    for linea in out.splitlines():
        if not linea.strip():
            continue
        oid, _, ruta = linea.partition(" ")
        if ruta:
            objetos[oid] = ruta
    rc, out, _ = correr(["rev-list", *rango], cwd=repo)
    commits = [l.strip() for l in out.splitlines() if l.strip()] if rc == 0 else []
    tipos = _tipos_objetos(repo, list(objetos), correr)
    blobs = {oid: ruta for oid, ruta in objetos.items() if tipos.get(oid) == "blob"}

    # Atribución blob -> commit que lo introdujo (el más antiguo del rango
    # que lo contiene): recorremos los commits de más viejo a más nuevo.
    atrib = {}
    for commit in reversed(commits):
        rc, out, _ = correr(["ls-tree", "-r", commit], cwd=repo)
        if rc != 0:
            continue
        for linea in out.splitlines():
            # «100644 blob <oid>\t<ruta>»
            meta, _, _ruta = linea.partition("\t")
            partes = meta.split(" ")
            if len(partes) >= 3 and partes[1] == "blob":
                atrib.setdefault(partes[2], commit)

    hallazgos = []

    def anadir(h):
        # Permitidos (B12): solo contenido y no_escaneable, con firma.
        if h["tipo"] != "nombre_bloqueado" and base_dir and repo_id:
            if permitido_cubre(base_dir, repo_id, h["archivo"], h["huella"], h["tipo"]):
                return
        hallazgos.append(h)

    # LFS declarado en el .gitattributes de la punta: sus objetos viajan
    # como punteros y su contenido real no pasa por este escaneo (§6.1).
    rc, out, _ = correr(["cat-file", "-p", f"{sha}:.gitattributes"], cwd=repo)
    if rc == 0 and "filter=lfs" in out:
        anadir({"commit": sha, "archivo": ".gitattributes", "linea": None,
                "tipo": "git_lfs", "huella": None,
                "evidencia": "el repo declara Git LFS: su contenido no se puede escanear"})

    for oid, ruta in sorted(blobs.items(), key=lambda kv: kv[1]):
        commit = atrib.get(oid, sha)
        motivo = nombre_bloqueado(ruta)
        if motivo:
            hallazgos.append({"commit": commit, "archivo": ruta, "linea": None,
                              "tipo": "nombre_bloqueado", "huella": None,
                              "evidencia": motivo})
            continue
        datos = (leer_blob or leer_blob_real)(repo, oid)
        if datos.startswith(b"version https://git-lfs.github.com/spec/v1"):
            anadir({"commit": commit, "archivo": ruta, "linea": None,
                    "tipo": "git_lfs", "huella": None,
                    "evidencia": "puntero de Git LFS: el contenido real no se escaneó"})
            continue
        if len(datos) > MAX_BLOB_ESCANEABLE:
            anadir({"commit": commit, "archivo": ruta, "linea": None,
                    "tipo": "no_escaneable",
                    "huella": hashlib.sha256(datos).hexdigest(),
                    "evidencia": f"blob de {len(datos)} bytes: pasa del máximo escaneable"})
            continue
        texto = _decodificar(datos)
        if texto is None:
            anadir({"commit": commit, "archivo": ruta, "linea": None,
                    "tipo": "no_escaneable",
                    "huella": hashlib.sha256(datos).hexdigest(),
                    "evidencia": "blob no decodificable como texto (binario)"})
            continue
        for h in escanear_texto(texto, ruta=ruta, commit=commit):
            anadir(h)
    return hallazgos


def escanear_staged(repo, correr_git=None, leer_staged=None):
    """Escanea lo que hay en el índice (para el commit de rescate del
    traspaso, §8.3 paso 2): nombres bloqueados y contenido de cada blob
    staged. Devuelve hallazgos."""
    correr = correr_git or correr_git_real
    rc, out, err = correr(["diff", "--cached", "--name-only", "-z"], cwd=str(repo))
    if rc != 0:
        raise ErrorSecretos(f"diff --cached falló: {err.strip()[:200]}")
    hallazgos = []
    for ruta in [r for r in out.split("\0") if r]:
        motivo = nombre_bloqueado(ruta)
        if motivo:
            hallazgos.append({"commit": None, "archivo": ruta, "linea": None,
                              "tipo": "nombre_bloqueado", "huella": None,
                              "evidencia": motivo})
            continue
        try:
            datos = (leer_staged or leer_staged_real)(repo, ruta)
        except ErrorSecretos:
            continue
        texto = _decodificar(datos)
        if texto is None:
            hallazgos.append({"commit": None, "archivo": ruta, "linea": None,
                              "tipo": "no_escaneable",
                              "huella": hashlib.sha256(datos).hexdigest(),
                              "evidencia": "blob staged no decodificable"})
            continue
        hallazgos.extend(escanear_texto(texto, ruta=ruta))
    return hallazgos


# ------------------------------------------------------------------- hook

def desplegar(base_dir):
    """Copia estable del escáner en la carpeta compartida (§6.3): el hook
    la invoca desde ahí, así mover o actualizar una copia de la app no lo
    rompe. Se refresca si el hash difiere. Devuelve la ruta desplegada."""
    destino = Path(base_dir) / "secretos.py"
    origen = Path(__file__).read_bytes()
    try:
        if destino.is_file() and destino.read_bytes() == origen:
            return destino
    except OSError:
        pass
    tmp = destino.with_suffix(".py.tmp")
    tmp.write_bytes(origen)
    os.replace(tmp, destino)
    return destino


def texto_hook(python_exe, ruta_escaner, base_dir, ruta_secreto=None):
    """El script del hook pre-push (fino): por cada línea de stdin que no
    sea un borrado, escanea el sha local; cualquier fallo (hallazgos,
    escáner ausente, intérprete caído) sale ≠ 0 y git aborta el push."""
    py = str(python_exe).replace("\\", "/")
    esc = str(ruta_escaner).replace("\\", "/")
    base = str(base_dir).replace("\\", "/")
    env_sec = f'GROWI_PERM_SECRET="{str(ruta_secreto).replace(chr(92), "/")}" ' if ruta_secreto else ""
    return f"""#!/bin/sh
{MARCA_HOOK}
# Lo instala Growi Bridge al registrar el proyecto: bloquea la subida si
# el escaneo de objetos encuentra secretos. Borrar este archivo es la
# forma manual y visible de desactivarlo.
remoto="$1"
[ -z "$remoto" ] && remoto=origin
if [ ! -f "{esc}" ]; then
  echo "growi-bridge: falta el escáner ({esc}); subida bloqueada" >&2
  exit 1
fi
while read -r ref_local sha_local ref_remota sha_remoto; do
  if [ "$sha_local" = "{CEROS}" ]; then
    continue
  fi
  {env_sec}"{py}" "{esc}" --escanear-push "$sha_local" "$remoto" --base "{base}" || exit 1
done
exit 0
"""


# -------------------------------------------------------------------- CLI

def _base_defecto():
    """La carpeta compartida por usuario (la misma regla que el monolito
    para _token_dir, sin depender de él: el hook corre solo)."""
    env = os.environ.get("GROWI_BRIDGE_TOKEN_DIR")
    if env:
        return Path(env)
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA")
                    or (Path.home() / "AppData" / "Local")) / "GrowiBridge"
    return Path(os.environ.get("XDG_DATA_HOME")
                or (Path.home() / ".local" / "share")) / "GrowiBridge"


def _repo_id_de_ruta(ruta):
    """Primeros 16 hex del SHA-256 de la ruta canónica (como en §2)."""
    canon = os.path.normcase(str(Path(ruta).resolve()))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def _raiz_repo(cwd):
    rc, out, _ = correr_git_real(["rev-parse", "--show-toplevel"], cwd=cwd)
    return out.strip() if rc == 0 else None


def _main(argv):
    if "--escanear-push" in argv:
        i = argv.index("--escanear-push")
        sha = argv[i + 1] if i + 1 < len(argv) else ""
        remoto = argv[i + 2] if i + 2 < len(argv) and not argv[i + 2].startswith("--") else "origin"
        base = _base_defecto()
        if "--base" in argv:
            base = Path(argv[argv.index("--base") + 1])
        raiz = _raiz_repo(os.getcwd())
        if not raiz or not sha:
            print("growi-bridge: no se pudo determinar el repo o el sha; subida bloqueada",
                  file=sys.stderr)
            return 2
        try:
            hallazgos = escanear_objetos(raiz, sha, remoto, base_dir=base,
                                         repo_id=_repo_id_de_ruta(raiz))
        except ErrorSecretos as e:
            print(f"growi-bridge: el escáner falló ({e}); subida bloqueada", file=sys.stderr)
            return 2
        if hallazgos:
            print("growi-bridge: SUBIDA BLOQUEADA, secretos detectados:", file=sys.stderr)
            for h in hallazgos:
                donde = h["archivo"] + (f":{h['linea']}" if h.get("linea") else "")
                print(f"  - {donde}: {h['tipo']} ({h['evidencia']})", file=sys.stderr)
            return 1
        return 0
    if "--permitir" in argv:
        i = argv.index("--permitir")
        try:
            repo, archivo, linea = argv[i + 1], argv[i + 2], int(argv[i + 3])
        except (IndexError, ValueError):
            print("uso: secretos.py --permitir <repo> <archivo> <linea>", file=sys.stderr)
            return 2
        base = _base_defecto()
        if "--base" in argv:
            base = Path(argv[argv.index("--base") + 1])
        if not sys.stdin.isatty():
            print("El permitido lo firma una persona desde una terminal interactiva.",
                  file=sys.stderr)
            return 2
        raiz = _raiz_repo(repo) or str(Path(repo).resolve())
        ruta_archivo = Path(raiz) / archivo
        try:
            lineas = ruta_archivo.read_text(encoding="utf-8").splitlines()
            texto_linea = lineas[linea - 1]
        except (OSError, IndexError) as e:
            print(f"no se pudo leer {archivo}:{linea} ({e})", file=sys.stderr)
            return 2
        hall = escanear_linea(texto_linea, ruta=archivo, nlinea=linea)
        if not hall:
            print(f"en {archivo}:{linea} no hay ningún hallazgo que permitir",
                  file=sys.stderr)
            return 2
        h = hall[0]
        print(f"Hallazgo: {h['tipo']} en {archivo}:{linea} ({h['evidencia']})")
        print("Esto permite ESE hallazgo exacto en el futuro. Escribe SI para firmar:")
        if input("> ").strip() != "SI":
            print("Cancelado.")
            return 1
        entrada = agregar_permitido(base, _repo_id_de_ruta(raiz), archivo,
                                    h["huella"], h["tipo"])
        print(f"Permitido firmado y guardado en {_ruta_permitidos(base, _repo_id_de_ruta(raiz))}")
        return 0
    print("uso: secretos.py --escanear-push <sha> [remoto] [--base <dir>] | "
          "--permitir <repo> <archivo> <linea>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
