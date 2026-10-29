"""Captura de la ventana de la app SIN mostrarla al usuario ni robarle el foco (t-auditoria-045).

La ventana se muestra 100 % transparente (alpha 0), que deja pasar los clics (WS_EX_TRANSPARENT), al fondo del orden
Z, como ventana de herramienta (sin botón en la barra de tareas) y sin activarse (ShowWindowAsync SW_SHOWNOACTIVATE, nunca
deiconify de Tk, que activa). Fuera de pantalla no sirve: GDI recorta lo que Tk dibuja y quedan huecos en blanco. Se
lee con PrintWindow (PW_RENDERFULLCONTENT), que da el contenido sin la transparencia, y se vuelve a ocultar. Antes y
después se apunta la ventana en primer plano: si cambiara, la captura lo dice.

Las llamadas que mueven o muestran la ventana corren en un hilo aparte mientras el hilo de Tk bombea mensajes: desde
el hilo de Tk, los mensajes que mandan disparan enlaces de Python (<Configure>, <Map>) sin el GIL y el intérprete se
cae. PrintWindow, al revés, va en el hilo de Tk: solo pinta, y desde otro hilo a veces se interbloquea con él.
"""

import ctypes
import threading
from ctypes import wintypes

u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32
GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_APPWINDOW, WS_EX_NOACTIVATE = -20, 0x80, 0x40000, 0x08000000
WS_EX_TRANSPARENT, HWND_BOTTOM = 0x20, 1
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
SWP_NOACTIVATE, SWP_NOZORDER, SWP_FRAMECHANGED = 0x10, 0x4, 0x20
PW_RENDERFULLCONTENT = 2
u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
u32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
u32.SetWindowPos.argtypes = [wintypes.HWND, ctypes.c_void_p] + [ctypes.c_int] * 4 + [wintypes.UINT]
u32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
u32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
u32.GetDC.argtypes = [wintypes.HWND]
u32.GetDC.restype = wintypes.HDC
u32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
g32.CreateCompatibleDC.argtypes = [wintypes.HDC]
g32.CreateCompatibleDC.restype = wintypes.HDC
g32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
g32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
g32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
g32.SelectObject.restype = wintypes.HGDIOBJ
g32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
g32.DeleteDC.argtypes = [wintypes.HDC]
g32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                          ctypes.c_void_p, wintypes.UINT]


def _marco(root):
    return int(root.wm_frame(), 16)


def _en_hilo(fn, bombear):
    res = {}

    def corre():
        try:
            res["v"] = fn()
        except Exception as e:  # noqa: BLE001
            res["e"] = e
    t = threading.Thread(target=corre, daemon=True)
    t.start()
    while t.is_alive():
        bombear(0.05)
    if "e" in res:
        raise res["e"]
    return res.get("v")


def preparar(root, ancho, alto, bombear):
    """Deja la ventana lista para capturas: fuera de pantalla, sin barra de tareas, sin activarse."""
    hwnd = _marco(root)
    root.attributes("-alpha", 0.0)  # invisible antes de mostrarse nunca
    root.geometry(f"{ancho}x{alto}+0+0")  # Tk sabe el tamaño; la ventana sigue sin mostrarse
    bombear(0.3)

    def fn():
        ex = u32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        u32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, (ex | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT)
                              & ~WS_EX_APPWINDOW)
        u32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOACTIVATE | SWP_FRAMECHANGED | 0x1 | 0x2)
    _en_hilo(fn, bombear)
    return hwnd


def capturar(root, ruta, bombear, durante=None):
    """PNG de la ventana entera. durante(): se llama con la ventana mostrada (para medir lo que se ve).
    Devuelve {"ruta", "ancho", "alto", "printwindow", "foco_igual", "foco_nuestro"}."""
    hwnd = _marco(root)
    antes = u32.GetForegroundWindow()
    _en_hilo(lambda: u32.ShowWindowAsync(hwnd, SW_SHOWNOACTIVATE), bombear)  # ShowWindow síncrona a veces se cuelga
    bombear(2.0)  # sin RedrawWindow(UPDATENOW): desde otro hilo puede quedarse esperando al de Tk
    out = _leer(hwnd, ruta)  # en el hilo de Tk: PrintWindow desde otro hilo se interbloquea con el de Tk
    if durante is not None:
        out["medido"] = durante()
    _en_hilo(lambda: u32.ShowWindowAsync(hwnd, SW_HIDE), bombear)
    bombear(0.3)
    despues = u32.GetForegroundWindow()
    out["foco_igual"] = antes == despues
    # lo que de verdad importa: que la ventana activa nunca sea la nuestra (si cambió, fue otra ventana del usuario)
    out["foco_nuestro"] = despues == hwnd or antes == hwnd
    return out


def _leer(hwnd, ruta):
    from PIL import Image
    r = wintypes.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = u32.GetDC(hwnd)
    mdc = g32.CreateCompatibleDC(hdc)
    bmp = g32.CreateCompatibleBitmap(hdc, w, h)
    viejo = g32.SelectObject(mdc, bmp)
    ok = u32.PrintWindow(hwnd, mdc, PW_RENDERFULLCONTENT)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]
    bih = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
    g32.SelectObject(mdc, viejo)
    g32.DeleteObject(bmp)
    g32.DeleteDC(mdc)
    u32.ReleaseDC(hwnd, hdc)
    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(ruta)
    return {"ruta": str(ruta), "ancho": w, "alto": h, "printwindow": bool(ok)}
