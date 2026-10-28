"""Prueba del mapa ampliado (ESTADO-MAPA-AMPLIADO.md): las 5 filas medidas de
verdad (directo y por el proxy del VPS), el router y el descargador leyendo
el mapa, el proxy caido simulado y la ventana sin congelarse.

  python pruebas/prueba_mapa_ampliado.py
"""
import importlib.util, json, os, shutil, sys, tempfile, time, tkinter as tk
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NUEVAS = ["ollama_registry", "huggingface", "github", "tailscale_ctrl", "cloudflare"]


def main():
    tmp = Path(tempfile.mkdtemp(prefix="growi-prueba-mapa-"))
    (tmp / "app").mkdir()
    for f in ("growi-bridge.py", "engines.json", "availability.json"):
        shutil.copy2(REPO / f, tmp / "app" / f)
    os.environ.update(GROWI_BRIDGE_SHARE=str(tmp / "share"), GROWI_BRIDGE_COLA=str(tmp / "cola.db"),
                      GROWI_BRIDGE_TOKEN_DIR=str(tmp / "tok"))
    spec = importlib.util.spec_from_file_location("gb_mapa", tmp / "app" / "growi-bridge.py")
    gb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gb)
    ev = {"proxy_guardado": bool(gb.proxy_url()), "umbral_lento_ms": gb.MAPA_LENTO_MS}
    # (d) la ventana no se congela: ticks cada 50 ms mientras el mapa mide en segundo plano
    root = tk.Tk()
    root.withdraw()
    gb._root = root
    huecos, ult = [], [time.perf_counter()]

    def tick():
        t = time.perf_counter()
        huecos.append(t - ult[0])
        ult[0] = t
        root.after(50, tick)
    root.after(50, tick)
    t0 = time.time()
    gb.start_availability(only=NUEVAS)
    while time.time() - t0 < 90 and (gb._AV["running"] or not all(r in gb._AV["rows"] for r in NUEVAS)):
        root.update()
        time.sleep(0.01)
    ev["d_mapa_en_segundo_plano"] = {"segundos_midiendo": round(time.time() - t0, 1),
                                     "hueco_maximo_de_la_ventana_ms": round(max(huecos) * 1000),
                                     "ticks": len(huecos)}
    # (a)+(b) las 5 filas, directo y por proxy
    ev["ab_filas"] = {r: {k: gb._AV["rows"][r].get(k) for k in ("estado", "frase", "ruta", "ms", "detalle")}
                      for r in NUEVAS if r in gb._AV["rows"]}
    t1 = time.time()
    gb.run_availability()  # el mapa entero, para saber cuanto tarda una vuelta completa
    ev["mapa_completo_segundos"] = round(time.time() - t1, 1)
    ev["mapa_completo"] = {r: (x.get("estado"), x.get("ruta"), x.get("ms")) for r, x in gb._AV["rows"].items()}
    ev["proxy_y_claude"] = {r: {k: (gb._AV["rows"].get(r) or {}).get(k) for k in ("estado", "frase", "ruta")}
                            for r in ("proxy", "claude")}
    # el descargador lee la fila de Hugging Face
    ev["descargador_ruta"] = gb.lib_route("NousResearch/Hermes-3-Llama-3.1-8B-GGUF")
    ev["router_claude_con_proxy_bien"] = gb._router_available("claude")
    # (c) proxy caido (simulado: el proxy apunta a un puerto cerrado)
    gb.proxy_url = lambda: "http://127.0.0.1:9"
    gb.run_availability(only=["proxy", "claude", "huggingface"])
    ev["c_proxy_caido"] = {r: {k: gb._AV["rows"][r].get(k) for k in ("estado", "frase", "ruta")}
                           for r in ("proxy", "claude", "huggingface")}
    ev["c_router_claude"] = gb._router_available("claude")
    try:
        ev["c_route_task"] = gb.route_task("Escribe una función en Python que sume dos números")
    except Exception as e:
        ev["c_route_task"] = f"{type(e).__name__}: {e}"
    out = REPO / "pruebas" / "evidencia" / "mapa-ampliado"
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidencia.json").write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(ev, ensure_ascii=False, indent=1, default=str), flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
