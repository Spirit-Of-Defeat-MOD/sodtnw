"""Lightweight, native Canvas artwork for the GFX brief deck."""
import math
import tkinter.font as tkfont

import ui


def blend(a, b, amount):
    a, b = (('#' + ''.join(ch * 2 for ch in c[1:])) if len(c) == 4 else c for c in (a, b))
    aa, bb = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (a, b))
    return '#' + ''.join(f'{round(x + (y - x) * amount):02x}' for x, y in zip(aa, bb))


def fitted_text(canvas, x, y, text, width, height, **kw):
    """Keep the full brief in Details; never paint through the card's footer."""
    if height < ui.px(15):
        return y
    ident = canvas.create_text(x, y, anchor='nw', text=text, width=width, **kw)
    if canvas.bbox(ident)[3] <= y + height:
        return canvas.bbox(ident)[3]
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        canvas.itemconfigure(ident, text=text[:mid].rstrip() + '…')
        if canvas.bbox(ident)[3] <= y + height:
            low = mid
        else:
            high = mid - 1
    canvas.itemconfigure(ident, text=text[:low].rstrip() + '…')
    return canvas.bbox(ident)[3]


def ornament(c, theme, x, y, size, ink, soft, bg):
    """A reserved header medallion: geometry stays clear of the title."""
    def line(points, **kw):
        return c.create_line(*[v for p in points for v in (x + p[0]*size, y + p[1]*size)], fill=ink, width=ui.px(2), **kw)
    def oval(a, b, d, e, **kw):
        return c.create_oval(x+a*size, y+b*size, x+d*size, y+e*size, **kw)
    def star(cx, cy, radius, points=5):
        coords=[]
        for i in range(points*2):
            a=-math.pi/2+i*math.pi/points
            r=radius*(1 if i%2==0 else .43)
            coords.extend((x+(cx+math.cos(a)*r)*size, y+(cy+math.sin(a)*r)*size))
        c.create_polygon(coords, fill=ink, outline='')
    if theme == 'Midnight':
        oval(.22,.1,.8,.68,fill=ink,outline='')
        oval(.38,.04,.87,.53,fill=bg,outline='')
        for a,b in ((.1,.25),(.84,.73),(.28,.85),(.91,.15)):
            star(a,b,.035,4)
        line([(.05,.79),(.24,.66),(.43,.82),(.67,.7)],dash=(2,4))
    elif theme == 'Arctic Station':
        for a in range(0,360,60):
            t=math.radians(a)
            end=(.5+.38*math.cos(t),.45+.38*math.sin(t))
            line([(.5,.45),end])
            for side in (-1,1):
                q=t+side*.8
                p=(.5+.26*math.cos(t),.45+.26*math.sin(t))
                line([p,(p[0]-.13*math.cos(q),p[1]-.13*math.sin(q))])
        line([(.05,.96),(.25,.77),(.4,.91),(.65,.72),(.94,.96)])
    elif theme == 'Halloween':
        for k in range(4):
            oval(.13+k*.13,.3,.49+k*.13,.85,fill=soft,outline=ink,width=ui.px(1))
        line([(.51,.31),(.56,.15),(.68,.13)])
        for cx in (.38,.66):
            c.create_polygon(x+(cx-.07)*size,y+.55*size,x+(cx+.05)*size,y+.55*size,x+cx*size,y+.43*size,fill=ink)
        line([(.3,.68),(.44,.74),(.53,.67),(.65,.74),(.77,.65)])
        line([(.02,.04),(.98,.04),(.98,.26)],dash=(2,3))
    elif theme == 'Christmas':
        line([(.05,.15),(.3,.28),(.55,.2),(.8,.3),(.98,.14)],smooth=True)
        for cx,cy in ((.25,.43),(.55,.57),(.83,.45)):
            line([(cx,.23),(cx,cy-.09)])
            oval(cx-.11,cy-.1,cx+.11,cy+.13,fill=soft,outline=ink,width=ui.px(2))
            star(cx,cy,.05,4)
        star(.52,.87,.09)
    elif theme == 'Vaporwave':
        oval(.18,.08,.82,.72,fill=ink,outline='')
        for j in range(5):
            yy=.4+j*.065
            c.create_rectangle(x+.15*size,y+yy*size,x+.85*size,y+(yy+.025)*size,fill=bg,outline='')
        for j in range(4):
            yy=.77+j*.07
            line([(.03,yy),(.97,yy)])
        for j in range(5):
            line([(.5,.72),(-.05+j*.27,1)])
    elif theme == 'Rising Sun':
        oval(.39,.1,.92,.63,fill=soft,outline=ink)
        line([(.03,.92),(.3,.61),(.48,.42),(.55,.19)])
        line([(.3,.61),(.16,.4)])
        for cx,cy in ((.18,.4),(.46,.43),(.55,.19)):
            for a in range(5):
                t=a*math.tau/5
                xx,yy=cx+math.cos(t)*.065,cy+math.sin(t)*.065
                oval(xx-.045,yy-.045,xx+.045,yy+.045,fill=ink,outline='')
            oval(cx-.025,cy-.025,cx+.025,cy+.025,fill=bg,outline='')
    elif theme == 'Soviet Terminal':
        line([(.3,.07),(.06,.07),(.06,.33)])
        line([(.7,.93),(.94,.93),(.94,.67)])
        oval(.25,.25,.75,.75,outline=ink,width=ui.px(2))
        line([(.5,.13),(.5,.87)]);line([(.13,.5),(.87,.5)])
        for j in range(4):
            line([(.1,.83+j*.035),(.33,.83+j*.035)])
    elif theme in ('Field Grey','Sons of Sorel'):
        oval(.19,.15,.81,.77,outline=ink,width=ui.px(3))
        if theme == 'Sons of Sorel':
            for a in range(12):
                t=a*math.tau/12
                line([(.5+.31*math.cos(t),.46+.31*math.sin(t)),(.5+.4*math.cos(t),.46+.4*math.sin(t))])
        star(.5,.46,.2)
        line([(.25,.8),(.5,.94),(.75,.8)])
        for xx in (.06,.94):
            oval(xx-.025,.03,xx+.025,.08,fill=ink,outline='')
    elif theme == 'BurgSys':
        line([(.12,.92),(.12,.4),(.5,.05),(.88,.4),(.88,.92)])
        line([(.26,.86),(.26,.46),(.5,.22),(.74,.46),(.74,.86)])
        line([(.5,.33),(.7,.59),(.5,.85),(.3,.59),(.5,.33)])
        star(.5,.59,.095,4)
    elif theme in ('Andorran Dream','Stallonian Gambit'):
        line([(.25,.4),(.18,.12),(.39,.28),(.5,.05),(.62,.28),(.83,.12),(.75,.4),(.25,.4)])
        if theme == 'Stallonian Gambit':
            line([(.08,.66),(.23,.76),(.4,.63),(.5,.67),(.6,.63),(.77,.76),(.92,.66)],smooth=True)
        else:
            for side in (-1,1):
                for j in range(4):
                    line([(.5,.5+j*.08),(.5+side*(.43-j*.07),.42+j*.12)])
        line([(.35,.87),(.5,.96),(.65,.87)])
    elif theme == 'Revolution Realised':
        for a in range(12):
            t=a*math.tau/12
            line([(.5+.3*math.cos(t),.5+.3*math.sin(t)),(.5+.47*math.cos(t),.5+.47*math.sin(t))])
        star(.5,.5,.27)
    else:
        oval(.15,.12,.85,.82,outline=ink,width=ui.px(2))
        oval(.21,.18,.79,.76,outline=ink)
        c.create_text(x+.5*size,y+.47*size,text='RR',font='om_head',fill=ink)
        line([(.32,.8),(.26,.98),(.5,.88),(.74,.98),(.68,.8)])


def shell(c, x, y, width, height, item, section_colour, kind):
    p=ui.P
    theme=ui.THEME['t']['name']
    body=p['surface']; fg=p['foreground']; muted=p['muted']; accent=p['copper']
    header=p['header_background']; ink=p['header_foreground']
    # Keep each theme's signature colour in the print, without replacing section identity.
    special={'Christmas':('#54202d','#f8dea4'), 'Halloween':('#35203d','#ffae62'),
             'Vaporwave':('#342553','#70eee6'), 'Andorran Dream':('#30250e','#e3bb52'),
             'Soviet Terminal':('#081e15','#8be7a7')}
    header,ink=special.get(theme,(header,ink))
    pad=ui.px(18); right=x+width; bottom=y+height
    title_width=max(ui.px(80),width-ui.px(142))
    title_font=tkfont.nametofont('om_title')
    # Reserve up to three title lines, increasing the header for long names.
    lines=min(3,max(1,math.ceil(title_font.measure(item['name'])/title_width)))
    hh=ui.px(63)+lines*title_font.metrics('linespace')
    hh=max(ui.px(110), min(hh,ui.px(150)))
    c.create_rectangle(x+ui.px(5),y+ui.px(6),right+ui.px(5),bottom+ui.px(6),fill=blend(p['background'],'#000000',.3),outline='')
    c.create_rectangle(x,y,right,bottom,fill=body,outline=p['border'],width=ui.px(1))
    for i in range(24):
        c.create_rectangle(x+1,y+hh*i/24,right-1,y+hh*(i+1)/24+1,
                           fill=blend(header,blend(header,accent,.16),i/23),outline='')
    c.create_line(x,y+hh,right,y+hh,fill=accent,width=ui.px(2))
    c.create_text(x+pad,y+ui.px(12),anchor='nw',text='G F X  /  A R T W O R K  B R I E F',font='om_small',fill=ink)
    fitted_text(c,x+pad,y+ui.px(34),item['name'],title_width,hh-ui.px(42),font='om_title',fill=ink)
    ornament(c,theme,right-ui.px(102),y+ui.px(13),ui.px(81),ink,blend(header,accent,.25),blend(header,accent,.12))
    # Thin inner rules give the header a printed frame, rather than a plain stripe.
    c.create_line(x+pad,y+ui.px(7),right-pad,y+ui.px(7),fill=blend(header,ink,.35))
    yy=y+hh+ui.px(12)
    c.create_rectangle(x+pad,yy,x+pad+ui.px(4),yy+ui.px(17),fill=section_colour,outline='')
    c.create_text(x+pad+ui.px(12),yy,anchor='nw',text=kind,font='om_small',fill=fg,width=width-pad*2-ui.px(12))
    footer=bottom-ui.px(55)
    c.create_rectangle(x+1,footer,right-1,bottom-1,fill=blend(body,header,.3),outline='')
    c.create_line(x+pad,footer,right-pad,footer,fill=p['border'])
    c.create_text(x+pad,footer+ui.px(8),anchor='nw',text='OUTPUT FILE',font='om_small',fill=muted)
    fitted_text(c,x+pad,footer+ui.px(25),item.get('file') or '?',width-pad*2,ui.px(25),font='om_small',fill=fg)
    return yy+ui.px(29),footer-ui.px(12),fg,muted,blend(fg,accent,.4)
