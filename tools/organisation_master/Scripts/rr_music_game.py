"""Read-only music questions from the same installed RR stations as the sidebar radio."""
from collections import defaultdict
import os
from pathlib import Path
import random

from rr_games_data import Question,normalise


class MusicQuestions:
    def __init__(self,mod_dir,rng=None,stations=None):
        from radio import stations_in
        self.rng=rng or random.Random();self.durations={};self.stations={};self.tracks={};self.song_stations=defaultdict(set)
        if stations is None:stations,_=stations_in(str(mod_dir))
        for key,(title,tracks,_missing) in stations.items():
            usable=[t for t in tracks if not t.ad and not t.jingle and t.volume>0 and Path(t.path).is_file()]
            if not usable:continue
            self.stations[key]=title
            for track in usable:
                path=os.path.normcase(os.path.abspath(track.path))
                row=self.tracks.setdefault(path,dict(path=track.path,name=track.name,volume=track.volume,stations=set()))
                row['stations'].add(key)
        if not self.tracks:raise ValueError('No playable RR radio songs are installed. Pull the RR music mods and try again.')
        for row in self.tracks.values():self.song_stations[normalise(row['name'])].update(row['stations'])
        names=defaultdict(list)
        for key,title in self.stations.items():names[normalise(title)].append(key)
        for keys in names.values():
            if len(keys)>1:
                for key in keys:
                    root,token=key.rsplit('|',1)
                    self.stations[key]+=f' [{Path(root).name}/{token}]'

    def question(self,level,seen=None):
        from music_master import ogg_info
        seen=seen or set();seconds={'easy':12.,'medium':7.,'hard':4.}[level]
        for _ in range(100):
            path=self.rng.choice(list(self.tracks));row=self.tracks[path];key='station:'+path
            if key in seen:continue
            if path not in self.durations:self.durations[path]=ogg_info(row['path'])[0]
            duration=self.durations[path]
            if duration is None or duration<4:continue
            length=min(seconds,duration-.1);max_start=max(0,duration-length-.1)
            start=self.rng.uniform(min(max_start,duration*.1),max_start)
            if level=='medium':
                labels={p:t['name'] for p,t in self.tracks.items()}
                answers={p for p,t in self.tracks.items() if normalise(t['name'])==normalise(row['name'])}
                prompt='Which song is this?'
            else:
                labels=dict(self.stations);answers=set(self.song_stations[normalise(row['name'])]);prompt='Which station plays this song?'
            aliases=set();ambiguous=set()
            if level=='hard':
                # Full labels always work. Short station titles/tokens work only
                # when they identify an accepted station without ambiguity.
                owners=defaultdict(set)
                for station,label in labels.items():
                    for alias in (label,label.split(' · ')[0],station.rsplit('|',1)[-1]):owners[normalise(alias)].add(station)
                aliases={a for a,ids in owners.items() if ids<=answers}
                ambiguous={a for a,ids in owners.items() if len(ids)>1 and not ids<=answers}
                options=[]
            else:
                correct=self.rng.choice(sorted(answers));used={normalise(labels[k]) for k in answers}
                wrong=[p for p in labels if p not in answers];self.rng.shuffle(wrong);choices=[correct]
                for candidate in wrong:
                    label=normalise(labels[candidate])
                    if label in used:continue
                    choices.append(candidate);used.add(label)
                    if len(choices)==(3 if level=='easy' else 4):break
                if len(choices)<2:continue
                self.rng.shuffle(choices);options=[(p,labels[p]) for p in choices]
            return Question(key,prompt,f'Listen to the {length:g}-second clip. Replay is available.',answers,labels,options,aliases,
                typed=level=='hard',ambiguous=ambiguous,audio=dict(path=row['path'],start=start,seconds=length,duration=duration,volume=row['volume']))
        raise ValueError('Not enough distinct playable tracks or answer choices. Install more RR radio songs or start a new round.')
