"""Láminas HTML/CSS a 1080x1350 con el brandbook de la marca. Sin gradientes, sin plantillas de tres columnas:
bloques de color sólido, asimetría deliberada y una idea por lámina.

Cada lámina lleva un script que (1) ajusta el tamaño de letra dentro de su caja fija sin bajar del mínimo legible y
(2) deja sus medidas en <html data-qc="..."> para el QC (Chrome --dump-dom). Con #sin-texto pinta el texto
transparente: el QC compara esa captura con la normal para medir el contraste real, también sobre fotos.
"""

import html
import re
import shutil
from pathlib import Path

from comun import ALTO, ANCHO, buscar_fuente

ROLES = ("gancho", "punto", "contraste", "lista", "cierre", "foto", "foto-gancho")

# Tamaños en px a 1080 de ancho: (máximo, mínimo legible). El ajuste nunca baja del mínimo: si no cabe, el QC rechaza.
TAM = {"titulo-gancho": (118, 66), "titulo": (96, 50), "titulo-cierre": (90, 58), "cuerpo": (44, 34),
       "items": (48, 32), "accion": (76, 52), "numeral": (230, 230)}

CSS = """
@font-face{font-family:"__TIT";src:url("fuentes/__TIT_ARCHIVO") format("truetype");font-weight:300 700;}
@font-face{font-family:"__CUE";src:url("fuentes/__CUE_REG") format("truetype");font-weight:400;}
@font-face{font-family:"__CUE";src:url("fuentes/__CUE_BOLD") format("truetype");font-weight:700;}
:root{--p:__PRINCIPAL;--a:__ACENTO;--f:__FONDO;--tc:__TXT_CLARO;--to:__TXT_OSCURO;}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;background:#000}
.lamina{position:relative;width:1080px;height:1350px;overflow:hidden;font-family:"__CUE",sans-serif;}
.oscura{background:var(--p);color:var(--tc)} .clara{background:var(--f);color:var(--to)}
.naranja{background:var(--a);color:var(--to)}
.caja{position:absolute;overflow:hidden;overflow-wrap:normal;word-break:normal;hyphens:manual}
.tit{font-family:"__TIT",sans-serif;font-weight:700;line-height:1.02;letter-spacing:-0.025em}
.cue{line-height:1.32;font-weight:400}
.res{color:var(--a)} .naranja .res{color:var(--p);text-decoration:underline;text-decoration-thickness:6px}
.meta{position:absolute;left:88px;right:88px;top:62px;display:flex;justify-content:space-between;
  font:700 26px/1.3 "__CUE",sans-serif;letter-spacing:.06em;text-transform:uppercase}
.meta span{padding:6px 0}
.meta.sobre-foto span{background:var(--p);color:var(--tc);padding:10px 16px}
.firma{position:absolute;left:88px;bottom:56px;font:700 26px/1.3 "__CUE",sans-serif;letter-spacing:.04em}
.barra{position:absolute;background:var(--a)}
.franja{position:absolute;right:0;top:0;width:30px;height:1350px;background:var(--p)}
.numeral{font-family:"__TIT",sans-serif;font-weight:700;line-height:.9;color:var(--a);letter-spacing:-0.05em}
.items{list-style:none;display:flex;flex-direction:column;gap:.7em}
.items li{display:flex;gap:.7em;align-items:flex-start;line-height:1.25}
.items li i{flex:0 0 auto;width:1.1em;height:1.1em;border:5px solid var(--p);margin-top:.08em}
.accion-caja{position:absolute;left:88px;top:780px;max-width:904px;background:var(--p);color:var(--tc);
  padding:34px 44px;overflow:hidden}
.foto{position:absolute;object-fit:cover;display:block}
.placa{position:absolute;background:var(--p)}
"""

JS = r"""
(function(){
 var SIN = location.hash === '#sin-texto';
 if (SIN) { var s = document.createElement('style');
   s.textContent = '.t,.t *{color:transparent!important;text-decoration-color:transparent!important}';
   document.head.appendChild(s); }
 function cabe(el){ return el.scrollHeight <= el.clientHeight + 1 && el.scrollWidth <= el.clientWidth + 1; }
 function ajustar(){
   document.querySelectorAll('[data-max]').forEach(function(el){
     var t = +el.dataset.max, min = +el.dataset.min; el.style.fontSize = t + 'px';
     while (!cabe(el) && t > min) { t -= 2; el.style.fontSize = t + 'px'; }
     el.dataset.final = t;
   });
 }
 function caja(r){ return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; }
 function lineas(el){
   var out = [], w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
   while (w.nextNode()) { var n = w.currentNode; if (!n.textContent.trim()) continue;
     var par = n.parentElement; if (par !== el && par.closest('.t') !== el) continue;
     var rg = document.createRange(); rg.selectNodeContents(n);
     Array.prototype.forEach.call(rg.getClientRects(), function(r){ if (r.width > 1 && r.height > 1) out.push(caja(r)); });
   }
   return out;
 }
 function recortes(el){
   var r = el.getBoundingClientRect(), p = el.parentElement, out = [], cs0 = getComputedStyle(el);
   // un resalte en línea pinta su caja de fuente un poco por fuera de la línea: tolerancia del 30 % del cuerpo
   var tol = cs0.display === 'inline' ? Math.max(2, parseFloat(cs0.fontSize) * 0.3) : 1;
   while (p) { var cs = getComputedStyle(p);
     if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') { var q = p.getBoundingClientRect();
       if (r.left < q.left - tol || r.top < q.top - tol || r.right > q.right + tol || r.bottom > q.bottom + tol)
         out.push((p.className || p.tagName) + ' ' + caja(q).join(','));
     }
     p = p.parentElement; }
   return out;
 }
 function medir(){
   var m = {ancho: innerWidth, alto: innerHeight, fuentes: {}, elementos: [], gradientes: [], imagenes: [],
            acciones: document.querySelectorAll('.accion').length};
   var caras = Array.from(document.fonts);
   function cargada(fam){ return caras.some(function(f){ return f.family.replace(/"/g, '') === fam && f.status === 'loaded'; }); }
   m.fuentes.titulares = cargada('__TIT');
   m.fuentes.cuerpo = cargada('__CUE');
   m.fuentes.estado = caras.map(function(f){ return f.family + ' ' + f.weight + ': ' + f.status; });
   document.querySelectorAll('.t').forEach(function(el, i){
     var cs = getComputedStyle(el), r = el.getBoundingClientRect();
     m.elementos.push({i: i, clase: el.className, texto: el.innerText.replace(/\s+/g, ' ').trim(),
       caja: caja(r), lineas: lineas(el), scrollH: el.scrollHeight, clientH: el.clientHeight,
       scrollW: el.scrollWidth, clientW: el.clientWidth, color: cs.color, tam: parseFloat(cs.fontSize),
       peso: cs.fontWeight, fuente: cs.fontFamily, visible: cs.visibility !== 'hidden' && cs.display !== 'none' && r.width > 0 && r.height > 0,
       ajuste: el.dataset.final ? [+el.dataset.max, +el.dataset.min, +el.dataset.final] : null,
       recortes: recortes(el)});
   });
   document.querySelectorAll('*').forEach(function(el){
     var bi = getComputedStyle(el).backgroundImage; if (bi && bi.indexOf('gradient') >= 0) m.gradientes.push(el.className || el.tagName);
   });
   document.querySelectorAll('img').forEach(function(im){
     var r = im.getBoundingClientRect(), cs = getComputedStyle(im);
     m.imagenes.push({src: im.getAttribute('src'), natural: [im.naturalWidth, im.naturalHeight], caja: caja(r),
       objectFit: cs.objectFit, cargada: im.complete && im.naturalWidth > 0});
   });
   document.documentElement.setAttribute('data-qc', JSON.stringify(m));
 }
 document.fonts.ready.then(function(){
   var imgs = Array.prototype.map.call(document.images, function(im){
     return im.complete ? Promise.resolve() : new Promise(function(ok){ im.onload = im.onerror = ok; }); });
   Promise.all(imgs).then(function(){ ajustar(); medir(); });
 });
})();
"""


def esc(t):
    """Escapa HTML; **así** resalta en el color de acento (sigue siendo texto medido por el QC)."""
    t = html.escape(str(t or ""))
    return re.sub(r"\*\*(.+?)\*\*", r'<span class="t res">\1</span>', t)


def caja(clase, x, y, w, h, contenido, tam, extra="", estilo=""):
    mx, mn = TAM[tam]
    return (f'<div class="caja t {clase}" data-max="{mx}" data-min="{mn}" '
            f'style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;{estilo}" {extra}>{contenido}</div>')


def preparar_fuentes(marca, destino):
    """Copia los archivos de fuente del brandbook a <destino>/fuentes. -> (archivos, avisos)"""
    carpeta = Path(destino) / "fuentes"
    carpeta.mkdir(parents=True, exist_ok=True)
    avisos, archivos = [], {}
    pedidos = {"tit": (marca["fuentes"]["titulares"], 700), "cue_reg": (marca["fuentes"]["cuerpo"], 400),
               "cue_bold": (marca["fuentes"]["cuerpo"], 700)}
    for k, (familia, peso) in pedidos.items():
        f = buscar_fuente(familia, peso)
        if not f:
            avisos.append(f"No encontré la fuente «{familia}» {peso} en este PC: instálala (el QC rechazará las láminas).")
            archivos[k] = "falta.ttf"
            continue
        shutil.copyfile(f, carpeta / f.name)
        archivos[k] = f.name
    return archivos, avisos


def _meta(marca, n, total, sobre_foto=False):
    return (f'<div class="meta{" sobre-foto" if sobre_foto else ""}"><span class="t">{esc(marca["nombre"])}</span>'
            f'<span class="t">{n:02d} / {total:02d}</span></div>')


def _firma(marca, l):
    """Firma de la marca; en la última lámina, además, los datos que la marca pide ahí (p. ej. el RIF)."""
    texto = "   ".join(x for x in [marca.get("firma") or "", l.get("_pie") or ""] if x)
    return f'<div class="firma t">{esc(texto)}</div>' if texto else ""


def cuerpo_lamina(l, marca, n, total, orden_punto):
    rol = l["rol"]
    tit, txt = esc(l.get("titulo")), esc(l.get("texto"))
    foto = l.get("_foto_rel")
    enc = html.escape(l.get("encuadre") or "center 40%")
    if rol == "gancho":
        partes = [_meta(marca, n, total), '<div class="barra" style="left:88px;top:300px;width:132px;height:18px"></div>',
                  caja("tit", 88, 352, 860, 640, tit, "titulo-gancho")]
        if txt:
            partes.append(caja("cue", 88, 1018, 780, 190, txt, "cuerpo"))
        return "oscura", partes + [_firma(marca, l)]
    if rol == "punto":
        partes = ['<div class="franja"></div>', _meta(marca, n, total),
                  caja("numeral", 72, 150, 520, 260, f"{orden_punto:02d}", "numeral"),
                  caja("tit", 88, 452, 860, 350, tit, "titulo")]
        if txt:
            partes.append(caja("cue", 88, 830, 800, 360, txt, "cuerpo"))
        return "clara", partes + [_firma(marca, l)]
    if rol == "contraste":
        partes = ['<div class="placa" style="left:0;top:0;width:1080px;height:700px"></div>',
                  _meta(marca, n, total, sobre_foto=False).replace('class="meta"', 'class="meta" style="color:var(--tc)"'),
                  caja("tit", 88, 190, 880, 460, tit, "titulo", estilo="color:var(--tc)"),
                  '<div class="barra" style="left:88px;top:680px;width:40px;height:40px"></div>']
        if txt:
            partes.append(caja("cue", 88, 770, 840, 420, txt, "cuerpo"))
        return "clara", partes + [_firma(marca, l)]
    if rol == "lista":
        items = "".join(f'<li><i></i><span class="t">{esc(it)}</span></li>' for it in l.get("items") or [])
        mx, mn = TAM["items"]
        partes = [_meta(marca, n, total), caja("tit", 88, 170, 880, 230, tit, "titulo"),
                  f'<ul class="caja items cue" data-max="{mx}" data-min="{mn}" '
                  f'style="left:88px;top:430px;width:880px;height:780px">{items}</ul>']
        return "clara", partes + [_firma(marca, l)]
    if rol == "cierre":
        acc = esc(l.get("accion") or "")
        palabra = (marca.get("cta") or {}).get("palabra")
        if palabra:
            acc = acc.replace(html.escape(palabra), f"<b>{html.escape(palabra)}</b>")
        mx, mn = TAM["accion"]
        partes = [_meta(marca, n, total), caja("tit", 88, 230, 880, 500, tit, "titulo-cierre"),
                  f'<div class="accion-caja"><div class="t accion tit" data-max="{mx}" data-min="{mn}" '
                  f'style="max-height:220px;overflow:hidden;line-height:1.2">{acc}</div></div>']
        if txt:
            partes.append(caja("cue", 88, 1030, 820, 170, txt, "cuerpo"))
        return "naranja", partes + [_firma(marca, l)]
    if rol == "foto":
        partes = [f'<img class="foto" src="{html.escape(foto)}" style="left:0;top:0;width:1080px;height:790px;object-position:{enc}">',
                  '<div class="placa" style="left:0;top:790px;width:1080px;height:560px"></div>',
                  _meta(marca, n, total, sobre_foto=True),
                  caja("tit", 88, 840, 900, 250, tit, "titulo", estilo="color:var(--tc)")]
        if txt:
            partes.append(caja("cue", 88, 1105, 860, 150, txt, "cuerpo", estilo="color:var(--tc)"))
        return "oscura", partes
    if rol == "foto-gancho":
        partes = [f'<img class="foto" src="{html.escape(foto)}" style="left:0;top:0;width:1080px;height:1350px;object-position:{enc}">',
                  _meta(marca, n, total, sobre_foto=True),
                  '<div class="placa" style="left:0;top:700px;width:960px;height:560px"></div>',
                  '<div class="barra" style="left:88px;top:748px;width:132px;height:18px"></div>',
                  caja("tit", 88, 796, 820, 330, tit, "titulo", estilo="color:var(--tc)")]
        if txt:
            partes.append(caja("cue", 88, 1140, 800, 100, txt, "cuerpo", estilo="color:var(--tc)"))
        return "oscura", partes
    raise ValueError(f"rol desconocido «{rol}» (válidos: {', '.join(ROLES)})")


def html_lamina(l, marca, fuentes, n, total, orden_punto):
    fondo, partes = cuerpo_lamina(l, marca, n, total, orden_punto)
    c = marca["colores"]
    css = (CSS.replace("__TIT_ARCHIVO", fuentes["tit"]).replace("__CUE_REG", fuentes["cue_reg"])
           .replace("__CUE_BOLD", fuentes["cue_bold"]).replace("__TIT", "Tit").replace("__CUE", "Cue")
           .replace("__PRINCIPAL", c["principal"]).replace("__ACENTO", c["acento"]).replace("__FONDO", c["fondo"])
           .replace("__TXT_CLARO", c["texto_sobre_oscuro"]).replace("__TXT_OSCURO", c["texto_sobre_claro"]))
    js = JS.replace("__TIT", "Tit").replace("__CUE", "Cue")
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Lámina {n:02d}</title>'
            f'<meta name="viewport" content="width={ANCHO},height={ALTO}"><style>{css}</style></head>'
            f'<body><div class="lamina {fondo}" data-rol="{l["rol"]}">{"".join(partes)}</div>'
            f'<script>{js}</script></body></html>')
