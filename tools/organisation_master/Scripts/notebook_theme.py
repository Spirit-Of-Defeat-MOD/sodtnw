"""Shared palette for notebook navigation in the masters."""
from tkinter import ttk
import ui


def theme_notebook(root, name):
    """Notebook tabs need their own palette; button styles do not reach them."""
    p=ui.P;style=ttk.Style(root)
    style.configure(name,background=p['background'],bordercolor=p['border'])
    style.configure(name+'.Tab',background=p['button_background'],foreground=p['button_foreground'],
                    bordercolor=p['border'],lightcolor=p['surface'],darkcolor=p['border'],
                    padding=(ui.px(14),ui.px(7)),font='om_bold',focuscolor=p['copper'])
    style.map(name+'.Tab',
              background=[('disabled',p['surface']),('selected',p['header_background']),('active',p['button_active'])],
              foreground=[('disabled',p['muted']),('selected',p['header_foreground']),('active',p['button_foreground'])],
              lightcolor=[('selected',p['border'])])

