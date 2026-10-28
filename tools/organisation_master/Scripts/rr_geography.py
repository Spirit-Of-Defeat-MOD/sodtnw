"""Read-only geography and deterministic daily puzzle rules for RR Games."""
from collections import defaultdict
import datetime as dt
import hashlib
import math
import random
import re

import numpy as np
from PIL import Image

from rr_games_data import normalise

EPOCH=dt.date(2026,10,24)
GUESS_LIMITS={'easy':8,'medium':6,'hard':6}


def utc_day():return dt.datetime.now(dt.timezone.utc).date().isoformat()


def daily_number(day):return (dt.date.fromisoformat(day)-EPOCH).days+1


def daily_answer(day,level,candidates):
    pool=sorted(candidates)
    if not pool:raise ValueError('No countries are available for this difficulty.')
    # A cryptographic digest, rather than Python's process-randomised hash().
    seed=int.from_bytes(hashlib.sha256(f'rrdle:{day}:{level}'.encode()).digest(),'big')
    return random.Random(seed).choice(pool)


def daily_record(records,dev,day,level):
    rows=[r for r in records if r.get('game')=='rrdle' and r.get('dev')==dev and r.get('day')==day and r.get('difficulty')==level]
    return max(rows,key=lambda r:(len(r.get('guesses',[])),bool(r.get('finished')),r.get('updated','')),default=None)


def daily_board(records,level,today=None):
    today=dt.date.fromisoformat(today or utc_day());by_dev=defaultdict(dict)
    for r in records:
        if r.get('game')!='rrdle' or r.get('difficulty')!=level or not r.get('finished'):continue
        try:day=dt.date.fromisoformat(r['day'])
        except (KeyError,ValueError):continue
        if day>today:continue
        old=by_dev[r['dev']].get(day)
        if old is None or (len(r.get('guesses',[])),r.get('updated',''))>(len(old.get('guesses',[])),old.get('updated','')):by_dev[r['dev']][day]=r
    out=[]
    for dev,days in by_dev.items():
        wins=[(day,r) for day,r in sorted(days.items()) if r.get('completed')]
        best=run=0;previous=None
        for day,_ in wins:
            run=run+1 if previous and day-previous==dt.timedelta(days=1) else 1
            best=max(best,run);previous=day
        cursor=today
        if cursor not in days:cursor-=dt.timedelta(days=1)
        current=0
        while cursor in days and days[cursor].get('completed'):
            current+=1;cursor-=dt.timedelta(days=1)
        out.append(dict(dev=dev,current=current,best=best,win=100*len(wins)/len(days),
            average=sum(r.get('answered',0) for _,r in wins)/len(wins) if wins else None,played=len(days)))
    return sorted(out,key=lambda r:(-r['current'],-r['best'],-r['win'],r['average'] if r['average'] is not None else 99,r['dev'].lower()))


class Geography:
    def __init__(self,game):
        self.game=game;self.data=game.country_data
        game.load_map();self.raster=game.state_raster;self.height,self.width=self.raster.shape
        self.km_per_pixel=40075/self.width;self.edges={};self.positions={};self.countries={}
        self._positions();self._countries();self._images()

    def _positions(self):
        # Accumulate full-resolution centroids in bounded strips, retaining even
        # one-pixel islands. Circular longitude avoids dateline centroids at Greenwich.
        size=65536;counts=np.zeros(size);sx=np.zeros(size);cx=np.zeros(size);sy=np.zeros(size)
        angle=np.arange(self.width)*2*math.pi/self.width
        for top in range(0,self.height,128):
            block=self.raster[top:top+128].astype(np.int32);flat=block.ravel()
            counts+=np.bincount(flat,minlength=size)[:size]
            sx+=np.bincount(flat,weights=np.broadcast_to(np.sin(angle),block.shape).ravel(),minlength=size)[:size]
            cx+=np.bincount(flat,weights=np.broadcast_to(np.cos(angle),block.shape).ravel(),minlength=size)[:size]
            sy+=np.bincount(flat,weights=np.broadcast_to(np.arange(top,top+len(block))[:,None],block.shape).ravel(),minlength=size)[:size]
        for sid in self.data.state_names:
            if 0<sid<65535 and counts[sid]:
                x=(math.atan2(sx[sid],cx[sid])%(2*math.pi))*self.width/(2*math.pi)
                self.positions[sid]=(x,float(sy[sid]/counts[sid]))

    def _countries(self):
        d=self.data;g=self.game
        border_of={}
        for key,p in g.border_profiles.items():
            if p['kind']=='startup':border_of[key]=key
            elif key.startswith(('breakaway:','cores:')):border_of.setdefault(key.split(':')[1],key)
        for tag,c in d.countries.items():
            states=sorted(c.states);capital=c.get('capital');cap=int(capital) if str(capital).isdigit() else None
            politics=c.get('set_politics');main=next((e.value for e in politics if e.key=='ruling_party' and not e.block),None) if isinstance(politics,list) else None
            entry=d.main_entries.get(main);side=entry.get('side') if entry else None
            cultures={g.states[s]['majority'] for s in states if s in g.states}
            self.countries[tag]=dict(id=tag,name=g.countries[tag]['name'],aliases=set(g.countries[tag]['aliases']),
                states=states,capital=cap,position=self.positions.get(cap),continent=d.continent(tag,d.state_owner) or None,
                ideology=main,ideology_name=d.label(main,main) if main else None,side=side if isinstance(side,str) else None,
                population=sum(d.state_pop.get(s,0) for s in states) if all(s in d.state_pop for s in states) else None,
                cultures=cultures,groups={g.cultures[t]['group'] for t in cultures},
                flag=g.countries[tag]['flag'],border=border_of.get(tag),on_map=bool(states))
        for key,p in g.border_profiles.items():
            if p['kind']!='formable':continue
            result=key.rsplit(':',1)[-1]
            if result in self.countries:continue
            states=list(p['states']);cultures={g.states[s]['majority'] for s in states if s in g.states}
            self.countries[result]=dict(id=result,name=p['name'],aliases=p['aliases']|{normalise(result)},states=states,
                capital=None,position=None,continent=None,ideology=None,ideology_name=None,side=None,
                population=sum(d.state_pop[s] for s in states) if all(s in d.state_pop for s in states) else None,
                cultures=cultures,groups={g.cultures[t]['group'] for t in cultures},flag=d.cosmetic_flag(result),border=key,on_map=False)
        self.lookup=defaultdict(set)
        for tag,c in self.countries.items():
            for name in c['aliases']|{normalise(c['name']),normalise(tag)}:self.lookup[name].add(tag)

    def _images(self):
        image=Image.fromarray(self.raster.astype(np.uint16));image.thumbnail((2048,1024),Image.Resampling.NEAREST)
        self.small=np.asarray(image);land=(self.small>0)&(self.small<65535)
        plain=np.empty((*self.small.shape,3),dtype=np.uint8);plain[:]=(34,53,70);plain[land]=(135,151,133)
        palette=np.tile(np.array([135,151,133],dtype=np.uint8),(65536,1));palette[0]=palette[65535]=(34,53,70)
        for sid,tag in self.data.state_owner.items():
            if 0<sid<65535:palette[sid]=self.data.map_rgb(tag) or (135,151,133)
        self.palette=palette
        political=palette[self.small].copy()
        edge=np.zeros(self.small.shape,dtype=bool);edge[1:] |= self.small[1:]!=self.small[:-1];edge[:,1:] |= self.small[:,1:]!=self.small[:,:-1]
        political[edge&land]=(45,50,55)
        self.plain=Image.fromarray(plain);self.political=Image.fromarray(political)

    def region(self,bounds,level,owner=None,selected=None):
        left,top,right,bottom=bounds;raster=self.raster[top:bottom,left:right]
        land=(raster>0)&(raster<65535)
        if level=='hard':
            rgb=np.empty((*raster.shape,3),dtype=np.uint8);rgb[:]=(34,53,70);rgb[land]=(135,151,133)
        else:
            rgb=self.palette[raster].copy()
            edge=np.zeros(raster.shape,dtype=bool);edge[1:] |= raster[1:]!=raster[:-1];edge[:,1:] |= raster[:,1:]!=raster[:,:-1]
            rgb[edge&land]=(45,50,55)
        if owner and level=='easy':
            mask=np.isin(raster,[s for s,t in self.data.state_owner.items() if t==owner])
            rgb[mask]=(rgb[mask].astype(float)*.72+np.array([255,235,135])*.28).astype('uint8')
        if selected is not None:rgb[raster==selected]=(255,220,75)
        return Image.fromarray(rgb)

    def pool(self,level):
        return sorted(tag for tag,c in self.countries.items()
            if (level=='hard' and any(c[k] for k in ('continent','ideology','cultures','position')))
            or (level!='hard' and c['on_map'] and (level!='easy' or len(c['states'])>=3)))

    def state_pool(self,level):
        ids=sorted(self.positions);d=self.data
        if level=='hard':return ids
        ids=[s for s in ids if not re.fullmatch(r'(?:State[ _]?|STATE_)?\d+',d.state_names.get(s,''),re.I)]
        if level=='medium':return ids
        capitals={c['capital'] for c in self.countries.values() if c['on_map']}
        average=sum(d.state_pop.get(s,0) for s in self.positions)/max(1,len(self.positions))
        return [s for s in ids if s in capitals or d.state_pop.get(s,0)>average]

    def resolve(self,text,allowed):
        allowed=set(allowed)
        direct=[tag for tag in allowed if tag.casefold()==text.strip().casefold()]
        if len(direct)==1:return direct[0]
        direct=[tag for tag in allowed if normalise(self.countries[tag]['name'])==normalise(text)]
        if len(direct)==1:return direct[0]
        matches=self.lookup.get(normalise(text),set())&allowed
        if len(matches)==1:return next(iter(matches))
        return None

    def suggestions(self,text,allowed):
        needle=normalise(text)
        if not needle:return []
        matches=[tag for tag in allowed if any(needle in alias for alias in self.countries[tag]['aliases']|{normalise(tag),normalise(self.countries[tag]['name'])})]
        return sorted(matches,key=lambda t:(not normalise(self.countries[t]['name']).startswith(needle),self.countries[t]['name']))[:8]

    def distance(self,a,b):
        dx=(b[0]-a[0]+self.width/2)%self.width-self.width/2;dy=b[1]-a[1]
        km=math.hypot(dx,dy)*self.km_per_pixel
        compass=('→','↘','↓','↙','←','↖','↑','↗')
        arrow=compass[round(math.atan2(dy,dx)/(math.pi/4))%8] if km else '●'
        return km,arrow,max(0,100*(1-km/(40075/2)))

    def hints(self,guess,answer,level):
        g=self.countries[guess];a=self.countries[answer];out=[]
        def tile(title,value,color):out.append((title,str(value),color))
        if a['continent']:tile('Continent',g['continent'] or 'Unavailable','green' if g['continent']==a['continent'] else 'black')
        if a['ideology']:
            color='green' if g['ideology']==a['ideology'] else 'yellow' if a['side'] and g['side']==a['side'] else 'black'
            tile('Ruling ideology',g['ideology_name'] or 'Unavailable',color)
        if level!='hard':
            n=len(g['states']);target=len(a['states']);tile('States',str(n)+(' ✓' if n==target else ' ↑' if n<target else ' ↓'),'green' if n==target else 'black')
            if a['population'] is not None:
                n=g['population'];target=a['population'];same=n is not None and abs(n-target)<=target*.1
                tile('Population','Unavailable' if n is None else f'{n:,}'+(' ✓' if same else ' ↑' if n<target else ' ↓'),'green' if same else 'black')
        if a['cultures']:
            exact=bool(g['cultures']&a['cultures']);group=bool(g['groups']&a['groups'])
            tile('Shared culture','Shared culture' if exact else 'Shared group' if group else 'None','green' if exact else 'yellow' if group else 'black')
        if a['position']:
            if g['position']:
                km,arrow,close=self.distance(g['position'],a['position']);tile('Capital distance',f'{km:,.0f} km '+(arrow if level!='hard' else '')+f'\n{close:.0f}% close','green' if km<1 else 'yellow' if close>=75 else 'black')
            else:tile('Capital distance','Unavailable','black')
        return out

    def nearest(self,sid,point):
        x,y=point;x=x%self.width;y=max(0,min(self.height-1,y))
        if int(self.raster[int(y),int(x)])==sid:return 0.,(x,y),True
        if sid not in self.edges:
            mask=self.raster==sid
            inside=mask.copy();inside[1:] &= mask[:-1];inside[:-1] &= mask[1:];inside &= np.roll(mask,1,axis=1)&np.roll(mask,-1,axis=1)
            inside[0]=False;inside[-1]=False
            yy,xx=np.nonzero(mask&~inside);self.edges[sid]=(xx,yy)
            if len(self.edges)>12:self.edges.pop(next(iter(self.edges)))
        xx,yy=self.edges[sid]
        if not len(xx):raise ValueError('State boundary unavailable.')
        dx=(xx-x+self.width/2)%self.width-self.width/2;dist=dx*dx+(yy-y)**2
        index=int(dist.argmin());return math.sqrt(float(dist[index]))*self.km_per_pixel,(float(xx[index]),float(yy[index])),False

    def pinpoint_score(self,sid,point):
        if point is None:return dict(points=0,km=None,click=None,target=self.positions[sid],inside=False,sid=sid)
        km,target,inside=self.nearest(sid,point)
        return dict(points=1000 if inside else max(0,round(1000-km/2)),km=round(km,2),click=tuple(point),target=target,inside=inside,sid=sid)

    def reveal(self,tag):
        country=self.countries[tag]
        if country['border']:return self.game.silhouette(country['border'])
        if country['capital'] in self.positions:return self.game.state_map(country['capital'])
        return None
