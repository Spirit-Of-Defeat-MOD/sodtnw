"""Read-only mod-backed question banks for RR Games. No Tk work happens here."""
from collections import defaultdict
from dataclasses import dataclass,field
from functools import lru_cache
import hashlib
from pathlib import Path
import random
import re
import unicodedata

import numpy as np
from PIL import Image,ImageOps,ImageFilter

GAMES={
 'holy':('Holy Guesswork','Identify religions from their icons.',('Group hint + icon','Icon only','Silhouette only')),
 'shock':('Culture Shock','Place a culture and religion profile on the map.',('Guess the country','Guess the state','Cultures only: guess the state')),
 'minority':('Spot the Minority','Identify a minority culture in the highlighted state.',('Regional map + same-group choices','Regional map + all-culture choices','Regional map; state and country hidden')),
 'flags':('Flagrant Misidentification','Match flags before the time runs out.',('On-map tags','All tags, base flags','All flag variants')),
 'borders':('Borderline Genius','Identify a country from its map shape.',('On-map countries, multiple choice','Includes breakaways and formables, multiple choice','Brief glimpse, then type')),
 'passport':('Passport Please','Match political leaders to their countries.',('Startup leaders','All leaders','All leaders, type the country')),
 'ideology':('Guess That Ideology!','Identify a leader’s recorded ideology from their portrait.',('Main ideology','Sub-ideologies from all groups','Sub-ideologies from the correct main group')),
 'station':('Name That Station','Identify music from the installed RR radio mods.',('12-second clip, station choices','7-second clip, song choices','4-second clip, type the station with autocomplete')),
 'rrdle':('RRdle','One mystery RR country per UTC day.',('8 guesses, all hints and blurred flag','6 guesses and all hints','6 guesses, fewer hints; no suggestions')),
 'pinpoint':('Pinpoint','Click where the named state is on the world map.',('Capitals/populous states, no timer','Any named state, 20 seconds','All states, plain map, 10 seconds')),
}
LEVELS=('easy','medium','hard')


def normalise(value):
    value=re.sub(r'§.','',str(value))
    value=unicodedata.normalize('NFKD',value)
    return ''.join(c.lower() for c in value if c.isalnum() and not unicodedata.combining(c))


def flag_seconds(score):
    return max(5.,15.-score*.65)


def distinct_country_names(names,identifiers):
    """Qualify shared names globally; variants of one tag keep the same label."""
    groups=defaultdict(set);tags=defaultdict(set)
    for key,name in names.items():
        groups[normalise(name)].add(identifiers[key].upper());tags[normalise(identifiers[key])].add(identifiers[key].upper())
    return {key:f'{name} [{identifiers[key].upper()}]' if len(groups[normalise(name)])>1 or tags[normalise(name)]-{identifiers[key].upper()} else name
            for key,name in names.items()}


def border_country_id(key):
    if key.startswith(('breakaway:','cores:')):return key.split(':')[1]
    if key.startswith('formable:'):return key.rsplit(':',1)[-1]
    return key


@dataclass
class Question:
    key:str
    prompt:str
    detail:str
    answers:set
    labels:dict
    options:list=field(default_factory=list)
    aliases:set=field(default_factory=set)
    image:object=None
    typed:bool=False
    preview:float=0
    composition:object=None
    ambiguous:set=field(default_factory=set)
    audio:object=None

    def accepts(self,value,typed=False):
        return normalise(value) in self.aliases if typed else value in self.answers

    @property
    def answer_label(self):
        names=sorted({self.labels.get(key,key) for key in self.answers})
        return ' / '.join(names[:3])+(f' (+{len(names)-3} other matches)' if len(names)>3 else '')


@lru_cache(maxsize=192)
def read_image(path):
    if not path:return None
    try:
        with Image.open(path) as source:
            image=source.convert('RGBA')
        image.thumbnail((560,300),Image.Resampling.LANCZOS)
        return image
    except (OSError,ValueError,NotImplementedError):
        return None


def icon_mask(image):
    alpha=image.getchannel('A')
    if alpha.getextrema()[0]>240:
        # Some DDS icons have opaque black padding rather than an alpha channel.
        array=np.asarray(image)
        corners=np.array([array[0,0,:3],array[0,-1,:3],array[-1,0,:3],array[-1,-1,:3]])
        background=np.median(corners,axis=0)
        distance=np.max(np.abs(array[...,:3].astype(float)-background),axis=2)
        alpha=Image.fromarray(np.where(distance>24,255,0).astype('uint8'))
    else:alpha=alpha.point(lambda a:255 if a>60 else 0)
    return alpha


def silhouette_icon(image):
    alpha=icon_mask(image);box=alpha.getbbox()
    if not box:return None
    out=Image.new('RGBA',image.size,'#e8e4dc');out.putalpha(alpha)
    return out.crop(box)


class GameData:
    def __init__(self,root,cache_dir=None,progress=None):
        self.root=Path(root);self.cache=Path(cache_dir or self.root/'tools/organisation_master/.rr_games_cache')
        self.progress=progress or (lambda text:None)
        self.countries={};self.states={};self.cultures={};self.religions={};self.leaders=[];self.flags=[];self.flag_labels={}
        self.errors={};self.map=None;self.state_raster=None;self.shapes={};self.image_keys={};self.holy_index={}
        self.progress('Reading country data…')
        from cm_data import CountryData,find_game
        self.country_data=CountryData(str(self.root),find_game(str(self.root)),cache_dir=str(self.cache/'countries'),progress=self.progress)
        self._countries()
        self.progress('Reading cultures and religions…')
        self._cultures()
        self.progress('Indexing leaders and flags…')
        self._leaders()
        self._borders()
        self._country_names()
        self.progress('RR Games is ready.')

    def _country_names(self):
        names={};identifiers={};rows={}
        for tag,country in self.countries.items():
            key='country:'+tag;names[key]=country['name'];identifiers[key]=tag;rows[key]=country
            if country.get('base_name'):
                key='base:'+tag;names[key]=country['base_name'];identifiers[key]=tag
        for key,profile in self.border_profiles.items():
            record='border:'+key;names[record]=profile['name'];identifiers[record]=border_country_id(key);rows[record]=profile
        for tag,name in self.flag_labels.items():
            key='flag:'+tag;names[key]=name;identifiers[key]=tag.removeprefix('cosmetic:')
        labels=distinct_country_names(names,identifiers);self.country_alias_owners=defaultdict(set)
        for key,name in names.items():
            identity=identifiers[key].upper();aliases={normalise(name),normalise(labels[key]),normalise(identity)}
            if key in rows:
                row=rows[key];row['name']=labels[key];row['aliases'].add(normalise(labels[key]));aliases |= row['aliases']
            elif key.startswith('base:'):self.countries[key[5:]]['base_name']=labels[key]
            else:self.flag_labels[key[5:]]=labels[key]
            for alias in aliases:self.country_alias_owners[alias].add(identity)
        # Current qualified names and literal tags outrank another country's
        # historical/ideological aliases (e.g. an old alias "Egypt").
        for key,label in labels.items():self.country_alias_owners[normalise(label)]={identifiers[key].upper()}
        for identity in identifiers.values():self.country_alias_owners[normalise(identity)]={identity.upper()}

    def typed_country_aliases(self,identifiers):
        allowed={identifier.upper() for identifier in identifiers}
        aliases={alias for alias,owners in self.country_alias_owners.items() if owners<=allowed}
        ambiguous={alias for alias,owners in self.country_alias_owners.items() if len(owners)>1 and not owners<=allowed}
        return aliases,ambiguous

    def _countries(self):
        data=self.country_data
        for tag,country in data.countries.items():
            politics=country.get('set_politics')
            ruling=next((entry.value for entry in politics if entry.key=='ruling_party'),None) if isinstance(politics,list) else None
            name=data.name(tag,ideology=ruling)
            aliases={tag,name,data.name(tag,raw=True)}
            aliases.update(data.label(tag+'_'+main,'') for main in data.mains)
            self.countries[tag]=dict(id=tag,name=name,base_name=data.name(tag,raw=True),aliases={normalise(n) for n in aliases if n},
                states=sorted(country.states),on_map=bool(country.states),flag=data.flag_path(tag,ideology=ruling),base_flag=data.flag_map.get(tag.lower()+'.tga'))
        self.flag_labels={tag:c['name'] for tag,c in self.countries.items()}
        stems={stem.lower():stem for stem in data.flag_stems}
        for filename,path in sorted(data.flag_map.items()):
            if Path(filename).suffix.lower()!='.tga':continue
            stem=Path(filename).stem;tag=stem[:3].upper()
            if tag not in self.countries or (len(stem)>3 and stem[3]!='_'):
                # Formable/cosmetic nations can have names rather than three-letter
                # tags. Include their variants in Hard without inventing map tags.
                base=stem
                for ideology in sorted(data.all_mains,key=len,reverse=True):
                    if base.endswith('_'+ideology.lower()):base=base[:-len(ideology)-1];break
                tag='cosmetic:'+base
                source=stems.get(base,base)
                name=data.name(source,raw=True)
                self.flag_labels[tag]=name if name!=source else source.replace('_',' ').title()
            self.flags.append(dict(id=stem,tag=tag,path=path,base='_' not in stem))

    def _cultures(self):
        import culture_master as cm
        self.culture_data=data=cm.ModData(str(self.root),progress=self.progress)
        sprites={}
        for rel in (cm.F_GFX,cm.F_REL_GFX):sprites.update(data.read_sprites(cm.TextFile(data.path(rel)).lines))
        for kind,storage in (('sub',self.cultures),('religion',self.religions)):
            for token,node in data.nodes[kind].items():
                ancestor=node
                while ancestor.parent:ancestor=ancestor.parent
                path=self.root/sprites.get(cm.sprite_name(node),cm.ModData.icon_path(node))
                storage[token]=dict(id=token,name=node.label(),group=ancestor.token,
                    group_name=ancestor.label(),parent=node.parent.label() if node.parent else '',icon=str(path) if path.is_file() else None)
        for sid,comp in data.comps['culture'].items():
            if not comp.majority or comp.majority not in self.cultures:continue
            religion=data.comps['religion'].get(sid)
            self.states[sid]=dict(id=str(sid),name=self.country_data.state_names.get(sid,data.loc.get(f'STATE_{sid}',f'State {sid}')),
                owner=self.country_data.state_owner.get(sid),majority=comp.majority,
                cultures=tuple(sorted((t,n) for t,n in comp.strengths.items() if t in self.cultures)),
                religions=tuple(sorted((t,n) for t,n in religion.strengths.items() if t in self.religions)) if religion else (),
                religion_majority=religion.majority if religion else None,low_population=sid in data.low_pop)

    def _leaders(self):
        data=self.country_data;owners=defaultdict(set);startup=set()
        for tag,country in data.countries.items():
            for cid in country.characters:owners[cid].add(tag)
            politics=country.get('set_politics')
            ruling=next((e.value for e in politics if e.key=='ruling_party'),None) if isinstance(politics,list) else None
            leader=data.leader_for(tag,ruling) if ruling else None
            if leader and country.states:startup.add((tag,leader.id))
            for cid in country.dual.values():
                if country.states:startup.add((tag,cid))
        for cid,ch in data.characters.items():
            if not ch.leaders():continue
            tag=getattr(ch,'tag',None)
            if tag in self.countries:owners[cid].add(tag)
            stem=Path(ch.rel).stem
            for value in (cid,stem):
                match=re.match(r'^([A-Z][A-Z0-9]{2})(?:_|\s|-|$)',value)
                if match and match[1] in self.countries:owners[cid].add(match[1])
            portrait=next((data.portrait_path(value) for _,size,value in ch.portrait_slots if size=='large' and data.portrait_path(value)),None)
            if not portrait:continue
            for tag in sorted(owners[cid]):
                name=data.label(ch.name_key,'') or ''
                if name==cid or name.startswith(tag+'_'):name='Political leader'
                ideologies=tuple(dict.fromkeys(sub for sub,_,_ in ch.leaders() if sub in data.sub_ideology or sub in data.ideologies))
                self.leaders.append(dict(id=cid+':'+tag,country=tag,name=name,path=portrait,startup=(tag,cid) in startup,ideologies=ideologies))

    def describe(self,state,culture_only=False,majority_only=False):
        rows=[]
        for token,strength in state['cultures']:
            if majority_only and token!=state['majority']:continue
            node=self.cultures[token];role='majority' if token==state['majority'] else 'minority'
            rows.append(f"{node['name']} — {role}, presence {strength}")
        if not culture_only and state['religions']:
            rows.append('Religions: '+', '.join(self.religions[t]['name'] for t,_ in state['religions']))
        return '\n'.join(rows)

    def fingerprint(self,path,mask=False):
        key=(path,mask)
        if key not in self.image_keys:
            image=read_image(path)
            if image is None:self.image_keys[key]=None
            else:
                if mask:
                    image=silhouette_icon(image)
                    if image is not None:image=icon_mask(image).resize((64,64))
                self.image_keys[key]=hashlib.sha256(image.tobytes()).hexdigest() if image is not None else None
        return self.image_keys[key]

    def _borders(self):
        """Country Master's starting borders, scripted breakaways and formable footprints."""
        data=self.country_data;self.border_profiles={};seen=set()
        def add(key,name,states,kind,aliases=()):
            states=tuple(sorted(set(states)&set(data.state_owner)))
            identity=(normalise(name),states)
            if not states or identity in seen:return
            seen.add(identity)
            self.border_profiles[key]=dict(name=name,states=states,kind=kind,
                aliases={normalise(n) for n in (name,*aliases) if n})
        for tag,country in self.countries.items():
            if country['on_map']:add(tag,country['name'],country['states'],'startup',country['aliases'])
        scripted=set()
        for decision in data.decisions:
            by_tag=defaultdict(list)
            for sid,tag in data.simulate([decision]).items():
                if tag in self.countries and not self.countries[tag]['on_map']:by_tag[tag].append(sid)
            for tag,states in by_tag.items():
                country=self.countries[tag];scripted.add(tag)
                digest=hashlib.sha1(str(sorted(states)).encode()).hexdigest()[:12]
                add('breakaway:'+tag+':'+digest,country['name'],states,'breakaway',country['aliases'])
        for tag,country in data.countries.items():
            if not country.states and tag not in scripted:
                add('cores:'+tag,self.countries[tag]['name'],country.cores,'breakaway',self.countries[tag]['aliases'])
        for formable in data.formables:
            states=set(formable.required)|set(formable.cores)
            for _,result in formable.results:
                name=data.name(result,raw=True)
                if name==result:name=data.formable_name(formable)
                add('formable:'+formable.key+':'+result,name,states,'formable',(result,))

    def load_map(self):
        if self.map is None:
            self.progress('Preparing the game maps…')
            from country_master import LayeredMap
            source=LayeredMap(self.country_data,str(self.cache/'map'),self.progress)
            self.state_raster=source.stmap
            image=Image.fromarray(source.stmap.astype(np.uint16))
            image.thumbnail((2048,1024),Image.Resampling.NEAREST)
            self.map=np.asarray(image).copy()

    def state_map(self,sid):
        """A square, unlabeled local map with the quiz state clearly highlighted."""
        self.load_map();raster=self.state_raster;sid=int(sid)
        selected=raster==sid
        ys=np.flatnonzero(selected.any(axis=1));xs=np.flatnonzero(selected.any(axis=0))
        if not len(xs):raise ValueError('This state has no map pixels.')
        height,width=raster.shape
        gaps=np.diff(np.r_[xs,xs[0]+width]);cut=int(gaps.argmax())
        start=int(xs[(cut+1)%len(xs)]);span=int((xs[cut]-start)%width)+1
        side=min(height,width,max(160,round(max(span,len(ys),int(ys[-1]-ys[0]+1))*1.8)))
        left=start+(span-side)//2;top=max(0,min(height-side,int((ys[0]+ys[-1]-side)//2)))
        crop=raster[top:top+side,(np.arange(side)+left)%width]
        crop=np.asarray(Image.fromarray(crop.astype(np.uint16)).resize((420,420),Image.Resampling.NEAREST))
        if not np.any(crop==sid):raise ValueError('This state is too small for a clear map question.')
        rgb=np.empty((*crop.shape,3),dtype=np.uint8);rgb[:]=(37,54,72)
        land=(crop>0)&(crop<65535)
        rgb[land]=(104,126,111)
        rgb[land&(crop%2==0)]=(115,137,121)
        edge=np.zeros(crop.shape,dtype=bool)
        edge[1:] |= crop[1:]!=crop[:-1];edge[:,1:] |= crop[:,1:]!=crop[:,:-1]
        rgb[edge&land]=(58,79,73)
        active=crop==sid
        outline=np.asarray(Image.fromarray((active*255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5)))>0
        rgb[outline]=(255,236,180);rgb[active]=(232,155,63)
        return Image.fromarray(rgb).convert('RGBA')

    def silhouette(self,tag):
        if tag in self.shapes:return self.shapes[tag]
        self.load_map()
        mask=np.isin(self.map,self.border_profiles[tag]['states'])
        ys=np.flatnonzero(mask.any(axis=1));xs=np.flatnonzero(mask.any(axis=0))
        if len(xs)<2 or mask.sum()<8:return None
        width=mask.shape[1];gaps=np.diff(np.r_[xs,xs[0]+width]);cut=int(gaps.argmax())
        start=int(xs[(cut+1)%len(xs)]);span=int((xs[cut]-start)%width)+1
        crop=mask[ys[0]:ys[-1]+1,(np.arange(span)+start)%width]
        alpha=Image.fromarray((crop*255).astype('uint8'))
        out=Image.new('RGBA',alpha.size,'#e8e4dc');out.putalpha(alpha)
        out.thumbnail((500,270),Image.Resampling.LANCZOS)
        # Pad the shape rather than stretching it; small islands stay visible.
        out=ImageOps.expand(out,border=12,fill=(0,0,0,0));self.shapes[tag]=out
        return out

    def availability(self):
        return dict(holy=sum(bool(r['icon']) for r in self.religions.values()),shock=len(self.states),
            minority=sum(len(s['cultures'])>1 for s in self.states.values()),flags=len(self.flags),
            borders=sum(c['on_map'] for c in self.countries.values()),passport=len(self.leaders),
            ideology=sum(bool(row.get('ideologies')) for row in self.leaders))


class QuestionFactory:
    def __init__(self,data,rng=None):self.data=data;self.rng=rng or random.Random()

    def options(self,answers,labels):
        correct=self.rng.choice(sorted(answers));wrong=[key for key in labels if key not in answers and labels[key] not in {labels[a] for a in answers if a in labels}]
        self.rng.shuffle(wrong)
        distinct=[];seen=set()
        for key in wrong:
            name=normalise(labels[key])
            if name not in seen:distinct.append(key);seen.add(name)
        selected=[correct]+distinct[:3];self.rng.shuffle(selected)
        if len(selected)<2:raise ValueError('There are not enough distinct answer choices for this difficulty.')
        return [(key,labels[key]) for key in selected]

    def country_labels(self,level='medium'):
        return {tag:self.rng.choice((c['name'],c.get('base_name',c['name']))) if level=='hard' else c['name'] for tag,c in self.data.countries.items()}

    def country_question(self,key,prompt,detail,answers,image,typed=False,preview=0,eligible=None,level='medium'):
        names=self.country_labels(level)
        labels={tag:names[tag] for tag,c in self.data.countries.items() if eligible is None or tag in eligible}
        aliases,ambiguous=self.data.typed_country_aliases(answers)
        return Question(key,prompt,detail,set(answers),labels,[] if typed else self.options(answers,labels),aliases,image,typed,preview,ambiguous=ambiguous)

    def question(self,game,level,seen=None):
        if game not in GAMES or level not in LEVELS:raise ValueError('Choose a valid game and difficulty.')
        if not self.data.availability().get(game):raise ValueError('No usable saved mod data is available for this game.')
        seen=seen or set();last=None
        for _ in range(100):
            try:question=getattr(self,'make_'+game)(level)
            except (LookupError,ValueError) as error:last=error;continue
            if question and (question.key not in seen or len(seen)>100):return question
        raise ValueError(str(last) if last else 'No new usable questions are available. Try another difficulty or start a new round.')

    def make_holy(self,level):
        d=self.data;pool=[r for r in d.religions.values() if r['icon']]
        row=self.rng.choice(pool);image=read_image(row['icon'])
        if image is None:raise ValueError('Religion icon is unavailable.')
        mask=level=='hard';key=d.fingerprint(row['icon'],mask)
        if not key:raise ValueError('This icon has no usable silhouette.')
        answers={r['id'] for r in pool if r['icon']==row['icon'] and (level!='easy' or r['group']==row['group'])}
        labels={r['id']:r['name'] for r in pool}
        candidates=[r for r in pool if r['id'] not in answers];self.rng.shuffle(candidates)
        wrong=[];used={normalise(labels[token]) for token in answers}
        for candidate in candidates:
            name=normalise(candidate['name'])
            if name in used or d.fingerprint(candidate['icon'],mask)==key:continue
            wrong.append(candidate['id']);used.add(name)
            if len(wrong)==3:break
        if not wrong:raise ValueError('Not enough distinct religion icons.')
        selected=[self.rng.choice(sorted(answers))]+wrong;self.rng.shuffle(selected)
        detail='Religion group: '+row['group_name'] if level=='easy' else ('Silhouette only.' if mask else 'Identify this religion.')
        if mask:image=silhouette_icon(image)
        return Question('holy:'+key,'Which religion is this?',detail,answers,labels,[(token,labels[token]) for token in selected],image=image)

    def make_shock(self,level):
        d=self.data;pool=[s for s in d.states.values() if s['owner'] in d.countries]
        state=self.rng.choice(pool);culture_only=level=='hard'
        signature=lambda s:(s['majority'],s['cultures'],() if culture_only else (s.get('religion_majority'),s['religions']))
        matches=[s for s in pool if signature(s)==signature(state)]
        from culture_master import STRENGTH_LABELS
        def rows(kind,nodes,majority):
            return [(nodes[t]['name'],'Absolute (low population)' if state.get('low_population') and n==1 else STRENGTH_LABELS.get(n,str(n)),
                     'Majority' if t==majority else 'Minority')
                    for t,n in sorted(state[kind],key=lambda item:(item[0]!=majority,-item[1],nodes[item[0]]['name']))]
        composition={'cultures':rows('cultures',d.cultures,state['majority'])}
        if not culture_only:composition['religions']=rows('religions',d.religions,state.get('religion_majority'))
        detail='Identify the location from its saved composition.'
        if level=='easy':question=self.country_question('shock:'+str(signature(state)),'Which country contains this state?',detail,{s['owner'] for s in matches},None,level=level)
        else:
            answers={s['id'] for s in matches};labels={s['id']:s['name'] for s in pool}
            question=Question('shock:'+str(signature(state)),'Which state has this composition?',detail,answers,labels,self.options(answers,labels))
        question.composition=composition
        return question

    def make_minority(self,level):
        d=self.data;pool=[s for s in d.states.values() if len(s['cultures'])>1]
        state=self.rng.choice(pool);present={t for t,_ in state['cultures']};answers=present-{state['majority']}
        correct=self.rng.choice(sorted(answers));node=d.cultures[correct]
        candidates=d.cultures
        if level=='easy':candidates={t:n for t,n in candidates.items() if n['group']==node['group']};answers &= set(candidates)
        labels={t:n['name'] for t,n in candidates.items() if t not in present or t in answers}
        image=d.state_map(state['id'])
        detail='The orange area is the state to identify.'
        if level!='hard':detail=state['name']+' · '+d.countries.get(state['owner'],{}).get('name','Unowned')+'\n'+detail
        if level=='easy':detail+='\nChoices from '+node['group_name']
        return Question('minority:'+str(state['id']),'Which minority culture lives in the highlighted state?',detail,answers,labels,self.options(answers,labels),image=image)

    def make_flags(self,level):
        d=self.data
        if level=='easy':
            pool=[dict(id=tag,tag=tag,path=c['flag']) for tag,c in d.countries.items() if c['on_map'] and c['flag']]
        elif level=='medium':
            pool=[]
            for tag,c in d.countries.items():
                path=(c['flag'] if c['on_map'] else None) or c['base_flag']
                if path:pool.append(dict(id=tag,tag=tag,path=path))
        else:pool=d.flags
        names=dict(d.flag_labels);names.update(self.country_labels(level))
        row=self.rng.choice(pool);image=read_image(row['path'])
        if image is None:raise ValueError('Flag image is unavailable.')
        key=d.fingerprint(row['path'])
        by_tag=defaultdict(list)
        for flag in pool:by_tag[flag['tag']].append(flag['path'])
        candidates=[tag for tag in by_tag if tag!=row['tag']];self.rng.shuffle(candidates)
        # Only inspect the few potential distractors, not thousands of flags on
        # every first question. Identical flags never appear as wrong choices.
        wrong=[];seen_labels={normalise(names[row['tag']])}
        for tag in candidates:
            name=normalise(names[tag])
            if name in seen_labels:continue
            if any(d.fingerprint(path)==key for path in by_tag[tag]):continue
            wrong.append(tag);seen_labels.add(name)
            if len(wrong)==3:break
        if not wrong:raise ValueError('Not enough distinct flags for this difficulty.')
        options=[row['tag']]+wrong;self.rng.shuffle(options)
        labels={tag:names[tag] for tag in by_tag}
        return Question('flags:'+key,'Which country flies this flag?',
            'Match the country before the timer runs out.',{row['tag']},labels,[(tag,labels[tag]) for tag in options],image=image)

    def make_borders(self,level):
        d=self.data;pool={key:p for key,p in d.border_profiles.items() if level!='easy' or p['kind']=='startup'}
        key=self.rng.choice(list(pool));profile=pool[key]
        image=d.silhouette(key)
        if image is None:raise ValueError('This country is too small to form a clear silhouette.')
        answers={k for k,p in pool.items() if p['states']==profile['states']}
        names=self.country_labels(level)
        labels={k:names.get(border_country_id(k),p['name']) if p['kind']!='formable' else p['name'] for k,p in pool.items()};typed=level=='hard'
        aliases,ambiguous=d.typed_country_aliases({border_country_id(k) for k in answers})
        return Question('borders:'+str(profile['states']),'Which country is this?',
            'Remember the map: it disappears after 4 seconds.' if typed else 'Identify the country from its silhouette.',
            answers,labels,[] if typed else self.options(answers,labels),aliases,image,typed,4 if typed else 0,ambiguous=ambiguous)

    def make_passport(self,level):
        d=self.data;pool=[r for r in d.leaders if level!='easy' or r['startup']]
        row=self.rng.choice(pool);image=read_image(row['path'])
        if image is None:raise ValueError('Leader portrait is unavailable.')
        key=d.fingerprint(row['path'])
        related=[r for r in pool if r['path'].lower()==row['path'].lower() or r['id'].split(':')[0]==row['id'].split(':')[0]]
        answers={r['country'] for r in related}
        return self.country_question('passport:'+key,'Which country does this leader belong to?',row['name'],answers,image,typed=level=='hard',eligible={r['country'] for r in pool},level=level)

    def make_ideology(self,level):
        d=self.data;source=d.country_data
        pool=[r for r in d.leaders if any(level=='easy' or sub in source.sub_ideology for sub in r.get('ideologies',()))]
        row=self.rng.choice(pool);image=read_image(row['path'])
        if image is None:raise ValueError('Leader portrait is unavailable.')
        # Some portraits/names are reused by several records. Every recorded
        # valid role for the visible person must be accepted, never guessed
        # from their country's ruling party.
        related=[r for r in pool if r['id'].rsplit(':',1)[0]==row['id'].rsplit(':',1)[0]
            or (r['path'].lower()==row['path'].lower() and normalise(r['name'])==normalise(row['name']))]
        subs={sub for r in related for sub in r.get('ideologies',())}
        mains={source.sub_ideology.get(sub,sub) for sub in subs}
        detail=row['name'] or 'Identify this leader.'
        if level=='easy':
            answers=mains
            labels={main:source.label(main,main.replace('_',' ').title()) for main in source.ideologies}
            prompt='What is this leader’s main ideology?'
        else:
            answers=subs&set(source.sub_ideology)
            if not answers:raise ValueError('No recorded sub-ideology is available for this leader.')
            if level=='hard':
                main=self.rng.choice(sorted({source.sub_ideology[sub] for sub in answers}))
                answers={sub for sub in answers if source.sub_ideology[sub]==main}
                tokens={sub for sub,parent in source.sub_ideology.items() if parent==main}
                detail+='\nMain ideology: '+source.label(main,main.replace('_',' ').title())
            else:tokens=set(source.sub_ideology)
            labels={sub:source.label(sub,sub.replace('_',' ').title()) for sub in tokens}
            labels=distinct_country_names(labels,{sub:sub for sub in labels})
            prompt='What is this leader’s sub-ideology?'
        return Question('ideology:'+row['id'].rsplit(':',1)[0],prompt,detail,answers,labels,self.options(answers,labels),image=image)
