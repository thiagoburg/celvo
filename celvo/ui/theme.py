"""Dark ttk styling and Windows dark title-bar support."""

from __future__ import annotations

import ctypes
import sys


def apply_theme(root, style) -> None:
    """Apply Celvo's fixed dark palette to ttk widgets and the window surface."""
    bg, panel = "#202124", "#292a2d"
    fg, muted = "#e8eaed", "#bdc1c6"
    field, select = "#303134", "#375a7f"
    style.theme_use("clam")
    style.configure(".", background=bg, foreground=fg, fieldbackground=field)
    style.configure("TFrame", background=bg)
    style.configure("TLabelframe", background=bg, foreground=fg, bordercolor=muted)
    style.configure("TLabelframe.Label", background=bg, foreground=fg)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("TButton", background=panel, foreground=fg, bordercolor=muted, padding=(8, 4))
    style.map("TButton", background=[("active", select), ("disabled", bg)])
    style.configure("TCombobox", fieldbackground=field, background=panel, foreground=fg, arrowcolor=fg)
    style.map("TCombobox", fieldbackground=[("readonly", field)], foreground=[("readonly", fg)])
    style.configure(
        "Treeview", background=field, fieldbackground=field, foreground=fg,
        rowheight=25, bordercolor=muted
    )
    style.map("Treeview", background=[("selected", select)], foreground=[("selected", fg)])
    style.configure("Treeview.Heading", background=panel, foreground=fg, relief="flat")
    style.configure("Vertical.TScrollbar", background=panel, troughcolor=bg, arrowcolor=fg)
    root.configure(background=bg)


def apply_windows_dark_titlebar(root) -> bool:
    """Ask DWM to use the dark title-bar palette on Windows 11."""
    if sys.platform != "win32":
        return False
    try:
        hwnd = root.winfo_id()
        value = ctypes.c_int(1)
        dwmapi = ctypes.WinDLL("dwmapi")
        user32 = ctypes.WinDLL("user32")
        get_ancestor = user32.GetAncestor
        get_ancestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        get_ancestor.restype = ctypes.c_void_p
        hwnd = get_ancestor(ctypes.c_void_p(hwnd), 2) or hwnd  # GA_ROOT
        set_attribute = dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        set_attribute.restype = ctypes.c_long
        for attribute in (20, 19):  # Windows 11, then older Windows 10 SDK constant.
            result = set_attribute(
                ctypes.c_void_p(hwnd), attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result >= 0:
                return True
        return False
    except (AttributeError, OSError, RuntimeError, ctypes.ArgumentError):
        return False
