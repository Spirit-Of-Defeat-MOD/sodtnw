"""Small vector scenes for the hidden theme animations (360 x 220 logical canvas)."""
import math


def crown(c, x, y, size=1, party=False):
    colour = '#f4c758' if not party else '#e76b8b'
    c.create_polygon(x-24*size,y+10*size,x-27*size,y-13*size,x-12*size,y-2*size,
        x,y-24*size,x+12*size,y-2*size,x+27*size,y-13*size,x+24*size,y+10*size,
        fill=colour,outline='#c99236',width=2)
    c.create_rectangle(x-23*size,y+6*size,x+23*size,y+15*size,fill='#e1a83b',outline='')


def duck(c, t):
    flap = math.sin(t*6)*6
    c.create_oval(100,115,245,181,fill='#ead9a6',outline='#bd9e65',width=2)
    c.create_oval(121,124+flap,195,160+flap,fill='#faf0ce',outline='#bd9e65')
    c.create_oval(208,65,268,134,fill='#f8ecca',outline='#bd9e65',width=2)
    c.create_polygon(258,97,291,111,260,120,fill='#e8a13f',outline='#ad6f2b')
    # Round spectacles, wild hair and a small pointed goatee.
    for x in (231,251):
        c.create_oval(x-8,89,x+7,105,outline='#2c2626',width=2)
        c.create_oval(x-1,94,x+2,99,fill='#252126',outline='')
    c.create_line(238,95,244,95,fill='#2c2626',width=2)
    c.create_polygon(220,70,217,57,232,64,239,49,245,63,262,57,265,75,fill='#eeeeeb',outline='#99948d')
    c.create_polygon(234,125,254,124,244,144,fill='#77716d',outline='')
    c.create_line(109,177,84,55,fill='#a98249',width=4)
    flag=[]
    for n in range(9):
        flag.extend((85+n*8,55+math.sin(t*5+n*.65)*5))
    for n in range(8,-1,-1):
        flag.extend((85+n*8,93+math.sin(t*5+n*.65)*5))
    c.create_polygon(flag,fill='#ac2636',outline='#e2b5a6')
    c.create_text(180,204,text='PERMANENT DUCK REVOLUTION',fill='#f0d990',font=('Segoe UI',11,'bold'))


def sunset(c, t, vapor=False, palms=None):
    dusk=min(1,max(0,t/5.8))
    def shade(day,night):return tuple(round(a+(b-a)*dusk) for a,b in zip(day,night))
    def colour(rgb):return '#%02x%02x%02x'%rgb
    # One-pixel sky rows, then clipped circular bands. Gaps reveal the actual sky;
    # no rectangular stripe is painted over the edges of the sun.
    for y in range(20,184):
        p=(y-20)/164
        rgb=shade((38+130*p,24+45*p,84+15*p),(10+20*p,9+10*p,32+24*p))
        c.create_rectangle(20,y,340,y+1,fill=colour(rgb),outline='',tags='sunset_sky')
    cy=92+133*dusk;radius=39
    sections=((-39,0),(3,9),(13,19),(24,30),(35,39)) if vapor else ((-39,39),)
    for lo,hi in sections:
        top=max(20,cy+lo);bottom=min(184,cy+hi)
        if top>=bottom:continue
        rows=[top]+list(range(math.ceil(top),math.floor(bottom)+1))+[bottom]
        edge=[(180-math.sqrt(max(0,radius**2-(y-cy)**2)),y) for y in rows]
        edge += [(360-x,y) for x,y in reversed(edge)]
        c.create_polygon([v for point in edge for v in point],
            fill=colour(shade((246,180,108),(208,98,110))),outline='',tags='sunset_sun')
    c.create_polygon(20,165,65,126,109,160,157,142,210,168,263,132,340,170,340,186,20,186,
        fill='#15233d',outline='')
    c.create_line(20,185,340,185,fill='#df8eb8' if vapor else '#e3ae86',width=2)
    if vapor:
        if palms:
            c.create_image(66,184,image=palms['left'],anchor='s')
            c.create_image(295,184,image=palms['right'],anchor='s')
        else:
            for x,sign in ((64,1),(295,-1)):
                c.create_line(x,184,x-7*sign,143,x+6*sign,100,fill='#110e29',width=5,smooth=True)
                for dx,dy in ((-38,16),(-31,-11),(-7,-29),(24,-19),(39,9)):
                    c.create_line(x+6*sign,100,x+dx*.6,97+dy*.5,x+dx,100+dy,fill='#110e29',width=3,smooth=True)
                    for n in range(1,7):
                        p=n/7;px=x+6*sign+(dx-6*sign)*p;py=100+dy*p
                        c.create_line(px,py,px+sign*5,py+12*(1-p)+3,fill='#110e29',width=1)
        cassette=palms.get('cassette') if palms else None
        if cassette:
            c.create_image(180,228,image=cassette,tags='sunset_cassette')
            # Subtle reel motion stays inside the printed reel windows.
            for x in (157,203):
                for spoke in range(3):
                    angle=t*3+spoke*math.tau/3
                    c.create_line(x,227,x+4*math.cos(angle),227+4*math.sin(angle),
                                  fill='#ba88dd',width=1,tags='sunset_cassette')
            c.create_text(180,211,text='ZHGYV',fill='#452068',font=('Consolas',6,'bold'),tags='sunset_cassette')
        else:
            c.create_rectangle(130,198,230,258,fill='#3a185e',outline='#66d9e6',tags='sunset_cassette')
            c.create_rectangle(136,202,224,216,fill='#c6a2e7',outline='',tags='sunset_cassette')
            for x in (157,203):c.create_oval(x-9,218,x+9,236,outline='#e487db',width=2,tags='sunset_cassette')
    for n in range(11):
        x=35+(n*27)%300;y=32+(n*19)%65
        if dusk>.45+n*.035:
            c.create_oval(x,y,x+1.5,y+1.5,fill='#c9c3e8',outline='',tags='sunset_stars')



def penguin(c, t):
    bounce=math.sin(t*7)*5
    c.create_oval(118,175,247,188,fill='#9cc8d9',outline='')
    c.create_oval(135,41+bounce,226,177+bounce,fill='#172c40',outline='#557b8e',width=2)
    c.create_oval(149,87+bounce,214,166+bounce,fill='#f2f7ed',outline='')
    for x in (165,195):
        c.create_oval(x-7,64+bounce,x+7,84+bounce,fill='#fbfbef',outline='')
        c.create_oval(x-2,71+bounce,x+2,78+bounce,fill='#142132',outline='')
    c.create_polygon(171,88+bounce,191,88+bounce,181,103+bounce,fill='#eda64f',outline='')
    for x in (156,204):
        c.create_oval(x-17,169+bounce,x+16,184+bounce,fill='#e9a752',outline='')
    c.create_line(135,108+bounce,111,135+bounce+math.sin(t*9)*13,fill='#172c40',width=12)
    c.create_line(223,108+bounce,250,132+bounce-math.sin(t*9)*13,fill='#172c40',width=12)
    for n in range(6):
        x=65-(t*40+n*17)%55;y=130+n*9
        c.create_line(x,y,x+19,y,fill='#b4e0ee',width=2)


def forbidden(c, t):
    strength=(math.sin(t*3)+1)/2
    c.create_polygon(180,15,316,174,42,174,180,15,fill='#1c0a15',outline='#8e1836',width=2)
    c.create_oval(95,30,265,200,outline='#a82e51',width=2)
    for n in range(7):
        a=t*.15+n*math.tau/7;x=180+90*math.cos(a);y=113+90*math.sin(a)
        c.create_text(x,y,text=('†','∴','◇')[n%3],fill='#b34566',font=('Segoe UI',15))
    for dx,dy in ((-2,0),(2,0),(0,2),(0,-2)):
        c.create_text(180+dx,111+dy,text='Himmler was Added',fill='#6f1732',font=('Georgia',21,'bold'))
    c.create_text(180,111,text='Himmler was Added',fill=f'#{int(205+45*strength):02x}8a86',font=('Georgia',21,'bold'))


def burned(c, t):
    # The flames consume the panel, then subside into embers and charred cracks.
    intensity=max(0,1-t/4)
    for n in range(30):
        x=8+n*12
        height=(45+110*(.5+.5*math.sin(n*1.9+t*8)))*intensity
        for shrink,colour in ((1,'#b72d14'),(.72,'#ed681c'),(.38,'#ffc458')):
            c.create_polygon(x-11,220,x-7,220-height*.4*shrink,
                x+math.sin(t*7+n)*12,220-height*shrink,x+9,220-height*.25*shrink,x+15,220,
                fill=colour,outline='',smooth=True)
    for n in range(24):
        x=25+(n*53)%310;y=205-((t*55+n*13)%180)
        c.create_oval(x,y,x+3,y+3,fill='#dc7437' if n%2 else '#9b4733',outline='')
    for x in (45,115,235,310):
        c.create_line(x,35,x-8,60,x+13,81,x-3,118,fill='#51453e',width=3)
    c.create_text(180,117,text='THE FIRES HAVE GONE OUT.',fill='#c1aba0',font=('Segoe UI',15,'bold'))
    c.create_text(180,145,text='Double-click the gear to restore.',fill='#aa755a',font=('Segoe UI',10))


def portrait(c, t, pointer, photo):
    if photo:c.create_image(180,121,image=photo)
    else:c.create_oval(109,52,251,193,fill='#b88a69',outline='#e0bb8c',width=3)
    crown(c,180,40+math.sin(t*2)*2,.85)
    # The badge is square; these eye sockets sit over the portrait's own eyes.
    dx=max(-4,min(4,pointer[0]*8));dy=max(-2,min(2,pointer[1]*5))
    for x,y in ((171,100),(196,96)):
        c.create_oval(x-8,y-4,x+8,y+4,fill='#f3e8df',outline='#573d39')
        c.create_oval(x-3+dx,y-3+dy,x+3+dx,y+3+dy,fill='#292438',outline='')


def skeleton(c, t):
    wristx=180+math.sin(t*4)*14
    c.create_line(wristx,192,178,139,fill='#d8d0bc',width=10)
    c.create_oval(159,103,202,149,fill='#e9dfc7',outline='#8b806b',width=2)
    for n in range(5):
        x=161+n*10;y=75-16*math.sin(n*.7)
        c.create_line(174+n*3,117,x+math.sin(t*5+n)*5,y,x-4+math.sin(t*5+n)*8,y-24,
                      fill='#f4e7c9',width=6,smooth=True)
        c.create_oval(x-6,y-28,x+1,y-21,fill='#f4e7c9',outline='')
    c.create_text(180,211,text='A HAND WITH THE BACKLOG?',fill='#e6af68',font=('Segoe UI',11,'bold'))


def sleigh(c, t):
    bob=math.sin(t*5)*5
    c.create_polygon(90,119+bob,225,119+bob,230,160+bob,115,160+bob,fill='#a52e48',outline='#edc56a',width=3)
    c.create_line(98,168+bob,236,168+bob,252,156+bob,fill='#e8ce89',width=4,smooth=True)
    for x,colour in ((130,'#43866b'),(167,'#ca769b'),(202,'#d0a855')):
        c.create_rectangle(x-14,95+bob,x+12,127+bob,fill=colour,outline='#f8dfaa')
        c.create_line(x,95+bob,x,127+bob,fill='#f3dfa4',width=3)
    c.create_oval(251,91+bob,300,117+bob,fill='#917052',outline='')
    c.create_line(223,131+bob,260,112+bob,fill='#bfa572',width=2)
    for x in (261,286):c.create_line(x,110+bob,x+6,141+bob,fill='#917052',width=4)
    c.create_line(295,98+bob,316,73+bob,317,55+bob,fill='#917052',width=5)
    c.create_line(316,73+bob,331,62+bob,fill='#917052',width=4)
    c.create_oval(309,65+bob,334,83+bob,fill='#917052',outline='')
    c.create_oval(330,73+bob,338,81+bob,fill='#e14352',outline='')


def stocking(c, t):
    offset=max(0,1-min(1,t/1.5))*80
    c.create_line(173,117+offset,173,32+offset,186,22+offset,202,31+offset,202,53+offset,
        fill='#f8e3cf',width=13,smooth=True)
    for y in (40,65,90):c.create_line(166,y+offset,181,y-10+offset,fill='#c84859',width=5)
    c.create_polygon(133,52,202,52,202,139,238,149,244,174,222,188,154,188,133,166,
        fill='#aa334c',outline='#edcda2',width=2)
    c.create_rectangle(126,51,209,77,fill='#f1e4cd',outline='')
    c.create_text(180,209,text='ONE SWEET LITTLE DISCOVERY',fill='#f3c983',font=('Segoe UI',10,'bold'))


def cat(c, t):
    stretch=math.sin(min(1,t/3)*math.pi/2)*24
    c.create_oval(83-stretch,135,246+stretch,179,fill='#352c40',outline='#9e769a',width=2)
    c.create_oval(223+stretch,105,280+stretch,155,fill='#352c40',outline='#9e769a',width=2)
    c.create_polygon(227+stretch,117,229+stretch,87,247+stretch,108,fill='#352c40',outline='#9e769a')
    c.create_polygon(257+stretch,108,277+stretch,88,280+stretch,122,fill='#352c40',outline='#9e769a')
    c.create_line(242+stretch,126,249+stretch,130,fill='#e5c7cd',width=2)
    c.create_line(260+stretch,129,267+stretch,125,fill='#e5c7cd',width=2)
    c.create_line(94-stretch,149,64-stretch,117,82-stretch,97,fill='#352c40',width=13,smooth=True)
    for n in range(7):
        x=40+(n*47+t*17)%280;y=25+(n*31+t*19)%130
        c.create_oval(x,y,x+7,y+4,fill='#e9a4bd',outline='')


def eagle(c, t):
    c.create_oval(144,96,216,177,fill='#b9903a',outline='#f1d27c',width=2)
    for sign in (-1,1):
        c.create_polygon(180,129,180+sign*91,70,180+sign*123,94,180+sign*101,137,180+sign*39,163,
            fill='#9a752d',outline='#d5af58',width=2)
        x=180+sign*35
        c.create_line(180+sign*15,119,x,77,fill='#c69c45',width=19)
        c.create_oval(x-18,56,x+18,86,fill='#d4ad55',outline='#f3d684')
        c.create_polygon(x+sign*13,65,x+sign*37,75,x+sign*14,80,fill='#e4bb67',outline='')
        c.create_polygon(x-17,58,x+math.sin(t*3)*3,19,x+17,58,fill='#c9749d' if sign<0 else '#6baab4',outline='#f5df9d')
        c.create_oval(x-4,15,x+4,23,fill='#f5df9d',outline='')
    for n in range(15):
        x=30+(n*29)%300;y=(t*31+n*23)%200
        c.create_rectangle(x,y,x+4,y+7,fill=('#d8b553','#b66793','#729aa7')[n%3],outline='')


def draw(c, kind, t, pointer=(0,0), photo=None, scale=1):
    c.delete('all')
    if kind=='duck':duck(c,t)
    elif kind in ('sunset','vapor'):sunset(c,t,kind=='vapor',photo)
    elif kind=='penguin':penguin(c,t)
    elif kind=='forbidden':forbidden(c,t)
    elif kind=='burned':burned(c,t)
    elif kind=='portrait':portrait(c,t,pointer,photo)
    elif kind=='skeleton':skeleton(c,t)
    elif kind=='sleigh':sleigh(c,t)
    elif kind=='stocking':stocking(c,t)
    elif kind=='cat':cat(c,t)
    elif kind=='eagle':eagle(c,t)
    elif kind=='logo':
        if photo:c.create_image(180,110,image=photo)
        else:c.create_text(180,110,text='RR',fill='#bca260',font=('Segoe UI',70,'bold'))
    c.scale('all',0,0,scale,scale)
    if scale != 1:
        for item in c.find_all():
            if c.type(item)=='text':
                parts=c.tk.splitlist(c.itemcget(item,'font'))
                c.itemconfigure(item,font=(parts[0],max(7,round(int(parts[1])*scale)),*parts[2:]))
