"""Small one-shot themed error-alert scenes, confined to the header illustration area."""
import math
from functools import lru_cache
import os
from PIL import Image,ImageTk
import paths

SCENES={
 "Revolution Realised":"Pipe repair", "Midnight":"Warning constellation", "Field Grey":"Bugle warning flag",
 "Arctic Station":"Freezing thermometer", "BurgSys":"Eyes in a classified folder", "Sons of Sorel":"Smouldering gear",
 "Stallonian Gambit":"Sandwich report", "Halloween":"Spider warning web", "Christmas":"Snow globe bug",
 "Vaporwave":"Glitching sunset", "Rising Sun":"Blossom warning", "Andorran Dream":"Spinning warning coin",
 "Classic":"Needs attention stamp"}
DURATION=5.0


def clamp(v):return max(0.,min(1.,v))
def ease(v):v=clamp(v);return v*v*(3-2*v)
def mix(a,b,k):
 k=clamp(k);aa=[int(a[i:i+2],16) for i in (1,3,5)];bb=[int(b[i:i+2],16) for i in (1,3,5)]
 return '#'+''.join(f'{round(x+(y-x)*k):02x}' for x,y in zip(aa,bb))


@lru_cache(maxsize=1)
def pipe_sheet():
 try:
  with Image.open(os.path.join(paths.TOOL,'secret_assets','error_alerts','pipe.png')) as im:return im.convert('RGBA')
 except OSError:return None


class Paint:
 def __init__(self,c,x,y,w,h,p):self.c=c;self.x=x;self.y=y;self.sx=w/240;self.sy=h/160;self.p=p;self.bg=p['header_background'];self.ac=p['copper'];self.fg=p['header_foreground']
 def coords(self,v):return [n*(self.sx if i%2==0 else self.sy)+(self.x if i%2==0 else self.y) for i,n in enumerate(v)]
 def line(self,v,color=None,width=2,**kw):return self.c.create_line(*self.coords(v),fill=color or self.ac,width=max(1,width*min(self.sx,self.sy)),**kw)
 def rect(self,v,fill=None,outline=None,width=1):return self.c.create_rectangle(*self.coords(v),fill=fill or '',outline=outline or self.ac,width=width)
 def oval(self,v,fill=None,outline=None,width=1):return self.c.create_oval(*self.coords(v),fill=fill or '',outline=outline or self.ac,width=width)
 def poly(self,v,fill=None,outline=None,width=1,**kw):return self.c.create_polygon(*self.coords(v),fill=fill or '',outline=outline or self.ac,width=width,**kw)
 def text(self,x,y,text,size=12,color=None,**kw):return self.c.create_text(*self.coords([x,y]),text=text,fill=color or self.fg,font=('Segoe UI',max(7,round(size*min(self.sx,self.sy))),'bold'),**kw)
 def star(self,x,y,r=4,color=None):self.line([x-r,y,x+r,y],color,1);self.line([x,y-r,x,y+r],color,1)
 def bug(self,x,y,r=13,color=None):
  color=color or self.p['age_red']
  for side in (-1,1):
   for dy in (-8,0,8):self.line([x+side*r*.5,y+dy*.6,x+side*(r+8),y+dy],color,1)
  self.oval([x-r*.65,y-r,x+r*.65,y+r],fill=mix(color,self.bg,.4),outline=color,width=2)
  self.line([x,y-r,x,y+r],color,1);self.oval([x-5,y-r-6,x+5,y-r+2],fill=color,outline=color)


def pipe(a,t):
 sheet=pipe_sheet()
 if sheet is None:a.bug(120,80);return
 frame=0 if t<.7 else (1,2)[int((t-.7)/.28)%2] if t<3.5 else 3
 size=round(156*min(a.sx,a.sy));key=('pipe',frame,size)
 cache=getattr(a.c,'_scene_images',None)
 if cache is None:cache={};a.c._scene_images=cache
 if key not in cache:
  cw,ch=sheet.width//2,sheet.height//2;x=frame%2*cw;y=frame//2*ch
  cache[key]=ImageTk.PhotoImage(sheet.crop((x,y,x+cw,y+ch)).resize((size,size),Image.Resampling.NEAREST),master=a.c)
 a.c.create_image(*a.coords([120,80]),image=cache[key])


def constellation(a,t):
 pts=[(111,23),(125,42),(115,62),(126,82),(118,102),(121,134)]
 q=ease(t/1.3)
 for i,(x,y) in enumerate(pts):
  x+=(1-q)*math.sin(i*7+t)*38;y+=(1-q)*math.cos(i*3+t)*14
  if i and t>1.1+i*.25:
   px,py=pts[i-1];a.line([px,py,x,y],mix(a.ac,a.fg,.3),1)
  a.star(x,y,4+math.sin(t*3+i)*(1-clamp(t/5)),a.fg)
  a.oval([x-6,y-6,x+6,y+6],outline=mix(a.ac,a.bg,.65))
 for i in range(13):a.star(20+(i*43)%200,12+(i*31)%138,1,a.p['muted'])


def bugle(a,t):
 gold='#d7b15a';dark='#856024';light='#f8df95'
 a.oval([35,77,128,130],outline=dark,width=9);a.oval([35,73,128,126],outline=gold,width=6)
 a.line([33,82,110,82,145,55],gold,9);a.line([33,79,108,79,143,52],light,2)
 a.poly([134,40,158,72,175,33,163,22],fill=gold,outline=dark,width=2)
 a.line([24,77,35,77],light,8)
 q=ease((t-.5)/2.7);top=105-88*q
 a.line([176,110,176,top],a.fg,2)
 if q>0:
  a.poly([178,top,216,top+6+math.sin(t*5)*(1-q)*4,211,top+31,178,top+27],fill=a.p['age_red'],outline=a.fg)
  a.text(194,top+15,'!',19,a.bg)
 if t<3.8:
  for i in range(3):
   f=(t*.55+i*.3)%1;a.text(50+i*24,65-f*35,'♪',13,mix(gold,a.bg,f))


def thermometer(a,t):
 q=ease(t/3.6);blue='#7bcfe8';glass=mix(a.fg,a.bg,.72);fluid=mix(a.p['age_red'],blue,q)
 a.oval([99,10,125,130],fill=glass,outline=a.fg,width=2)
 a.rect([101,24,123,124],fill=glass,outline=glass)
 a.oval([91,111,134,151],fill=glass,outline=a.fg,width=2)
 a.line([112,130,112,33+72*q],fluid,9);a.oval([101,120,123,143],fill=fluid,outline=fluid)
 for i in range(7):a.line([129,23+i*14,138+(i%2)*5,23+i*14],a.ac,1)
 a.text(170,70,f'{round(12-42*q)}°',20,a.fg)
 for x,y,dx,dy in [(15,8,1,1),(224,8,-1,1),(15,150,1,-1),(224,150,-1,-1)]:
  for i in range(5):
   r=(8+i*5)*q;a.line([x,y,x+dx*r*1.5,y+dy*r],blue,1)
   a.line([x+dx*r*.8,y+dy*r*.55,x+dx*r*.6,y+dy*(r*.55+8*q)],blue,1)


def folder(a,t):
 q=ease(t/2.8);paper=mix(a.ac,a.bg,.3);black=mix('#090812',a.bg,.12)
 a.poly([30,57,30,40,94,40,105,53,210,53,210,143,30,143],fill=paper,outline=a.ac,width=2)
 a.rect([39,62,202,131],fill=black,outline=a.p['border'])
 eye=mix(black,'#cf8bff',q)
 for x in (94,150):
  a.oval([x-18,87-5*q,x+18,87+5*q],fill=eye,outline=eye)
  a.oval([x-3,81,x+3,93],fill=black,outline=black)
  for n in range(3):a.oval([x-21-n*3,78-n*2,x+21+n*3,96+n*2],outline=mix(eye,black,.72+n*.08))
 top=57+63*q
 a.poly([22,top,199,top,210,145,30,145],fill=paper,outline=a.ac,width=2)
 a.text(115,top+(145-top)/2,'CLASSIFIED',11,a.bg)


def gear(a,t):
 q=ease(t/4);rotation=.5*(1-q)*t;heat=math.sin(min(1,t/4)*math.pi)
 color=mix(a.ac,'#f57836',heat*.85);pts=[]
 for i in range(64):
  angle=i*math.tau/64+rotation;r=51 if i%4 in (1,2) else 43
  pts.extend((120+math.cos(angle)*r,85+math.sin(angle)*r))
 a.poly(pts,fill=mix(a.p['surface'],color,.2),outline=color,width=2)
 a.oval([94,59,146,111],fill=a.bg,outline=color,width=3)
 a.oval([106,71,134,99],fill=mix(color,a.bg,.65),outline=a.fg)
 for i in range(5):
  f=clamp((t-.6-i*.15)/3.2)
  if 0<f<1:
   x=95+i*12+math.sin(f*7+i)*6;y=65-f*54;r=3+f*8
   a.oval([x-r,y-r,x+r,y+r],outline=mix(a.p['muted'],a.bg,f))
 for i in range(7):
  angle=i*math.tau/7;x=120+math.cos(angle)*39;y=85+math.sin(angle)*39
  a.oval([x-2,y-2,x+2,y+2],fill=mix('#e67b30',a.bg,.5*q),outline=a.bg)


def sandwich(a,t):
 q=ease((t-.4)/3.0);bread='#dba45c';edge='#99612d';lettuce='#72a856'
 a.oval([32,113,208,151],fill=bread,outline=edge,width=2)
 a.poly([35,112,55,103,75,110,96,102,119,110,144,101,170,109,198,104,207,121],fill=lettuce,outline='#45743d')
 a.poly([43,112,202,112,185,128,158,115,124,128,95,116,70,126],fill='#f4d77d',outline='#c79443')
 py=111-55*q
 a.rect([85,py,161,min(py+51,121)],fill=mix('#fff0c9',a.bg,.1),outline=a.fg)
 a.text(123,py+24,'ERROR',12,a.p['age_red'])
 top=88-68*q
 a.oval([31,top,209,top+43],fill=bread,outline=edge,width=2)
 for x,y in ((65,10),(90,17),(126,8),(151,20),(177,12)):a.line([x,top+y,x+4,top+y-2],'#f9e1a2',2)


def spider(a,t):
 silk=mix(a.fg,a.bg,.25);center=(42,16)
 endpoints=[(225,20),(219,70),(218,141),(150,150),(80,149),(23,150)]
 for x,y in endpoints:a.line([*center,x,y],mix(silk,a.bg,.5),1)
 for f in (.3,.55,.8):
  pts=[]
  for x,y in endpoints:pts.extend((center[0]+(x-center[0])*f,center[1]+(y-center[1])*f))
  a.line(pts,mix(silk,a.bg,.55),1)
 path=[(116,34),(130,34),(130,102),(116,102),(116,34),(123,127),(123,140),(136,140),(136,127),(123,127),(184,122)]
 progress=ease(t/4)*10;index=min(9,int(progress));fraction=progress-index
 pts=[]
 for x,y in path[:index+1]:pts.extend((x,y))
 x0,y0=path[index];x1,y1=path[index+1];x=x0+(x1-x0)*fraction;y=y0+(y1-y0)*fraction
 pts.extend((x,y))
 if len(pts)>=4:a.line(pts,silk,2)
 body=a.p['age_red']
 for side in (-1,1):
  for dy in (-8,-3,3,8):a.line([x+side*4,y+dy*.3,x+side*12,y+dy],body,1)
 a.oval([x-6,y-7,x+6,y+7],fill=body,outline=silk)


def snowglobe(a,t):
 q=ease(t/4);dx=math.sin(t*19)*(1-q)*7
 cx=120+dx;cy=73;r=61
 glass=mix(a.fg,a.bg,.8);a.oval([cx-r,cy-r,cx+r,cy+r],fill=glass,outline=a.fg,width=2)
 a.oval([cx-r+7,cy-r+6,cx-r+25,cy-13],outline=mix(a.fg,a.bg,.4),width=2)
 a.bug(cx,cy+7,17,mix(glass,a.p['age_red'],clamp((t-1.2)/2)))
 for i in range(29):
  angle=i*2.399+t*(1-q)*4;rr=8+(i*13)%47
  x=cx+math.cos(angle)*rr*(1-q)+(i%7-3)*8*q
  y=cy+math.sin(angle)*rr*(1-q)+(45+(i%3)*3)*q
  a.oval([x-1.5,y-1.5,x+1.5,y+1.5],fill=a.fg,outline=a.fg)
 a.poly([76+dx,127,164+dx,127,181+dx,153,60+dx,153],fill=mix(a.ac,a.bg,.25),outline=a.ac,width=2)
 a.line([72+dx,143,168+dx,143],a.fg,1)


def sunset(a,t):
 q=ease((t-1)/3);pink='#ed65bc';cyan='#6ee4ed'
 for offset in (-110,-65,-30,0,30,65,110):a.line([120,111,120+offset,157],mix(cyan,a.bg,.45),1)
 for y in (114,123,136,155):a.line([9,y,230,y],mix(pink,a.bg,.5),1)
 for i in range(14):
  yy=-45+i*7;half=math.sqrt(max(0,45**2-(yy+3)**2))
  glitch=math.sin(t*24+i*3)*12*math.sin(q*math.pi)
  color=mix(mix('#f9b26d',pink,i/13),a.bg,q)
  a.rect([120-half+glitch,61+yy,120+half+glitch,66+yy],fill=color,outline=color)
 if q>0:
  color=mix(a.bg,cyan,q);a.poly([120,22,176,118,64,118],outline=color,width=2)
  a.text(120,83,'!',38,color)


def blossoms(a,t):
 q=ease(t/3.8);pink='#e999b2'
 a.line([18,151,46,113,76,92],mix(a.ac,a.bg,.15),3)
 a.line([42,119,31,83],a.ac,2)
 targets=[(122+(i%2)*4,30+i*6) for i in range(12)]+[(119,131),(126,128),(131,135),(123,139)]
 for i,(tx,ty) in enumerate(targets):
  x=(16+(i*47)%210)*(1-q)+tx*q+math.sin(t*3+i)*(1-q)*12
  y=(-25-(i*29)%100)*(1-q)+ty*q
  for n in range(5):
   angle=n*math.tau/5+i*.5;px=x+math.cos(angle)*3;py=y+math.sin(angle)*3
   a.oval([px-2,py-3,px+2,py+3],fill=pink,outline=pink)
  a.oval([x-1,y-1,x+1,y+1],fill='#f5d29b',outline='#f5d29b')


def coin(a,t):
 q=ease(t/3.5);width=abs(math.cos(t*7))*(1-q)*53+53*q
 gold='#dab04b';dark='#8d6020';light='#f6e1a1'
 a.oval([123-width,24,129+width,141],fill=dark,outline=dark,width=2)
 a.oval([117-width,20,123+width,137],fill=gold,outline=light,width=2)
 a.oval([123-width*.8,31,117+width*.8,126],outline=dark)
 if q>.55:a.text(120,78,'!',int(20+28*q),dark)
 else:
  a.line([120,49,120,106],light,2)
 for i in range(5):
  if .3<t<3.8:
   angle=i*math.tau/5+t;x=120+math.cos(angle)*80;y=80+math.sin(angle)*62
   a.star(x,y,3,mix(light,a.bg,q))


def stamp(a,t):
 paper=mix(a.fg,a.bg,.8);a.rect([42,35,202,147],fill=paper,outline=a.ac,width=2)
 for y in (55,66,77,126,135):a.line([55,y,184,y],mix(a.ac,paper,.5),1)
 down=ease(t/1.5);up=ease((t-2)/1.5);y=-55+112*down-100*up
 a.rect([83,y+33,169,y+58],fill=a.p['age_red'],outline=a.ac,width=2)
 a.poly([105,y+36,105,y+15,99,y+9,99,y-4,151,y-4,151,y+9,145,y+15,145,y+36],fill=mix(a.ac,a.bg,.3),outline=a.fg,width=2)
 if t>1.45:
  a.rect([60,83,186,116],outline=a.p['age_red'],width=2)
  a.text(123,99,'NEEDS ATTENTION',10,a.p['age_red'])


DRAWERS={'Revolution Realised':pipe,'Midnight':constellation,'Field Grey':bugle,'Arctic Station':thermometer,
 'BurgSys':folder,'Sons of Sorel':gear,'Stallonian Gambit':sandwich,'Halloween':spider,'Christmas':snowglobe,
 'Vaporwave':sunset,'Rising Sun':blossoms,'Andorran Dream':coin,'Classic':stamp}


ASSETS={'Revolution Realised':'pipe','Midnight':'constellation','Field Grey':'bugle','Arctic Station':'thermometer',
 'BurgSys':'folder','Sons of Sorel':'gear','Stallonian Gambit':'sandwich','Halloween':'web','Christmas':'snowglobe',
 'Vaporwave':'sunset','Rising Sun':'blossoms','Andorran Dream':'coin','Classic':'stamp'}


@lru_cache(maxsize=16)
def scene_sheet(key):
 try:
  with Image.open(os.path.join(paths.TOOL,'secret_assets','error_alerts',key+'.png')) as image:return image.convert('RGBA')
 except OSError:return None


def sprite_frame(key,elapsed):
 t=max(0,elapsed)
 if key=='pipe':return 0 if t<.7 else (1,2)[int((t-.7)/.23)%2] if t<3.5 else 3
 if key=='coin':return 0 if t<2.5 else min(7,4+int((t-2.5)/.45))
 if key=='gear':return min(4,int(t*2.5)) if t<2 else (5,6)[int((t-2)*4)%2] if t<4 else 7
 return min(7,int(t*2))


def sprite_scene(a,key,t):
 sheet=scene_sheet(key)
 if sheet is None:return False
 frame=sprite_frame(key,t);columns=2 if key=='pipe' else 4;rows=2
 cw,ch=sheet.width//columns,sheet.height//rows
 size=max(1,round(158*min(a.sx,a.sy)))
 angle=round(t*55*(1-ease(t/2))/5)*5 if key=='gear' and t<2 else 0
 width=size
 if key=='coin' and t<2.5:width=max(12,round(size*(.12+.88*abs(math.cos(t*7)))))
 cache=getattr(a.c,'_scene_images',None)
 if cache is None:cache={};a.c._scene_images=cache
 signature=('art',key,frame,size,width,angle)
 if signature not in cache:
  x=frame%columns*cw;y=frame//columns*ch
  image=sheet.crop((x,y,x+cw,y+ch)).resize((width,size),Image.Resampling.NEAREST)
  if angle:image=image.rotate(angle,resample=Image.Resampling.NEAREST,expand=True)
  cache[signature]=ImageTk.PhotoImage(image,master=a.c)
 dx=math.sin(t*19)*(1-ease(t/3))*3 if key=='snowglobe' else 0
 a.c.create_image(*a.coords([120+dx,80]),image=cache[signature])
 effects(a,key,t)
 return True


def effects(a,key,t):
 fade=1-ease((t-2.6)/2.2)
 if t>=DURATION:return
 if key in ('constellation','coin'):
  for i in range(6):
   angle=i*math.tau/6+t*.8;x=120+math.cos(angle)*85;y=80+math.sin(angle)*65
   a.star(x,y,2+math.sin(t*4+i),mix(a.ac,a.bg,1-fade))
 elif key=='bugle':
  for i in range(3):
   q=(t*.55+i*.3)%1;a.text(22+i*17,100-q*70,'♪',10,mix(a.ac,a.bg,max(1-fade,q)))
 elif key=='thermometer':
  q=ease(t/3.8);ice='#8edbf2'
  for x,y,dx,dy in ((8,8,1,1),(231,8,-1,1),(8,151,1,-1),(231,151,-1,-1)):
   for j in range(1,5):
    k=j*6*q;a.line([x,y,x+dx*k*1.5,y+dy*k],ice,1)
    a.line([x+dx*k,y+dy*k*.6,x+dx*(k+3),y+dy*(k*.6+8*q)],ice,1)
 elif key in ('gear','folder'):
  color='#eea461' if key=='gear' else '#c594ee'
  for i in range(5):
   q=clamp((t-.5-i*.2)/3.8);x=45+i*35+math.sin(q*8+i)*6;y=125-q*105
   if 0<q<1:a.oval([x-2-q*3,y-2-q*4,x+2+q*3,y+2+q*4],outline=mix(color,a.bg,q))
 elif key=='sunset' and 1<t<3.8:
  intensity=math.sin((t-1)/2.8*math.pi)
  for i in range(7):
   yy=25+i*16;xx=120+math.sin(t*25+i)*22*intensity
   a.line([xx-15,yy,xx+15,yy],mix('#6ee4ed' if i%2 else '#ed65bc',a.bg,1-intensity),1)
 elif key=='blossoms' and t<3.5:
  for i in range(8):
   q=(t*.4+i*.13)%1;x=20+i*26+math.sin(q*6+i)*8;y=-10+q*167
   a.oval([x-2,y-3,x+2,y+3],fill=mix('#efabc1',a.bg,1-fade),outline=a.bg)
 elif key=='stamp' and 1.4<t<2.1:
  q=(t-1.4)/.7
  for i in range(8):
   angle=i*math.tau/8;x=120+math.cos(angle)*(22+q*44);y=106+math.sin(angle)*(8+q*15)
   a.oval([x-1,y-1,x+1,y+1],fill=mix(a.p['age_red'],a.bg,q),outline=a.bg)
 elif key=='pipe' and .7<t<3.3:
  for i in range(5):
   q=(t*2+i*.2)%1;x=178+q*45;y=72+q*q*46+i*3
   a.line([x,y,x+2,y+4],mix('#4bbce8',a.bg,q),2)


def draw_scene(canvas,name,elapsed,x,y,width,height,palette):
    drawer=DRAWERS.get(name)
    if not drawer:return
    a=Paint(canvas,x,y,width,height,palette);t=min(DURATION,max(0,elapsed))
    if not sprite_scene(a,ASSETS[name],t):drawer(a,t)
