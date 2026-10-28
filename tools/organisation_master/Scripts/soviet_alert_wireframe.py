"""Flat 1980s terminal-vector alert animation: no camera, projection or 3D mesh."""
import math
from error_alert_scenes import clamp,ease,mix

PROFILE=[(-87,0),(-83,-15),(-68,-25),(-51,-25),(-42,-37),(-21,-41),(0,-45),(23,-40),(42,-36),(52,-25),(70,-24),(83,-12),(87,1),(74,12),(51,17),(29,15),(19,27),(14,50),(25,71),(-24,71),(-14,50),(-19,27),(-29,15),(-51,17),(-75,12),(-87,0)]


def cloud_profile(progress):
    grow=.12+.88*ease(progress)
    return [(380+x*grow,149+(y-71)*grow) for x,y in PROFILE]


def draw_soviet(canvas,elapsed,width,height,p,scene):
    sx=width/520;sy=height/176;phase,q=scene
    bg=p['header_background'];green=p['copper'];bright=p['header_foreground']
    def line(points,intensity=1,smooth=False):
        coords=[]
        for x,y in points:coords.extend((x*sx,y*sy))
        canvas.create_line(*coords,fill=mix(bg,green,.12*intensity),width=max(2,3*min(sx,sy)),smooth=smooth)
        canvas.create_line(*coords,fill=mix(bg,green,intensity),width=max(1,min(sx,sy)),smooth=smooth)
    def label(x,y,text,font,color):canvas.create_text(x*sx,y*sy,text=text,anchor='w',font=font,fill=color)
    def pulse(radius,intensity):
        # Flat outward energy arcs, not rings lying on a perspective floor.
        canvas.create_arc((380-radius)*sx,(149-radius)*sy,(380+radius)*sx,(149+radius)*sy,
                          start=0,extent=180,style='arc',outline=mix(bg,green,intensity),width=max(1,min(sx,sy)))
    label(14,20,'INCOMING TRANSMISSION','om_bold',bright)
    label(14,47,'ERROR SIGNAL DETECTED','om_small',p['foreground'])
    label(14,70,'Review • respond • resolve','om_small',p['muted'])
    label(14,137,'ACTION REQUIRED','om_small_bold',p['age_red'])
    # Faint CRT raster confined to the illustration, plus a simple flat horizon.
    for y in range(10,163,5):line([(271,y),(506,y)],.045)
    line([(273,150),(506,150)],.28)
    if phase=='fall':
        y=-36+180*q*q
        line([(371,y-36),(371,y-8),(380,y+5),(389,y-8),(389,y-36),(371,y-36)],.95)
        line([(371,y-30),(361,y-43),(363,y-22),(371,y-19)],.8)
        line([(389,y-30),(399,y-43),(397,y-22),(389,y-19)],.8)
        line([(371,y-23),(389,y-23)],.5)
        line([(380,y-36),(380,y+5)],.45)
        for n in range(3):line([(380,y-48-n*13),(380,y-54-n*13)],.45-n*.1)
        line([(365,143),(365,150),(372,150)],.5)
        line([(395,143),(395,150),(388,150)],.5)
        return
    if phase=='blast':
        radius=9+76*ease(q)
        for n in range(3):pulse(max(2,radius-n*15),max(.1,.9-n*.25))
        for n in range(7):
            angle=math.pi*n/6
            line([(380-math.cos(angle)*radius*.3,149-math.sin(angle)*radius*.3),
                  (380-math.cos(angle)*radius,149-math.sin(angle)*radius)],.8*(1-q))
        return
    grow=min(1,q*1.3) if phase=='cloud' else 1
    line(cloud_profile(grow),.95,smooth=True)
    factor=.12+.88*ease(grow)
    def local(points,intensity=.65):line([(380+x*factor,149+(y-71)*factor) for x,y in points],intensity,smooth=True)
    # A handful of flat hand-drawn billow contours; deliberately no latitude/longitude cage.
    local([(-69,0),(-58,-10),(-42,-9),(-31,-19),(-12,-20),(1,-15),(13,-22),(32,-18),(43,-8),(59,-9),(69,1)],.6)
    local([(-59,10),(-37,8),(-18,13),(0,10),(18,14),(39,8),(59,10)],.45)
    local([(-9,24),(-5,44),(-12,62)],.55)
    local([(9,24),(5,44),(12,62)],.55)
    local([(-24,71),(-8,66),(0,69),(9,66),(25,71)],.6)
    if phase=='cloud' and q<.75:pulse(36+q*70,.35*(1-q/.75))
