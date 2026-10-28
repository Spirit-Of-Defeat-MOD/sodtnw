"""RRdle and Pinpoint play panels. All mod/map preparation uses the games worker."""
import datetime as dt
import random
import tkinter as tk
from tkinter import ttk

from PIL import Image,ImageTk,ImageFilter

import ui
from rr_games_data import read_image,GAMES
from rr_geography import GUESS_LIMITS,utc_day,daily_answer,daily_number,daily_record
from rr_game_map import GameMap
from rr_games_style import result_band


class ExtendedGames(ttk.Frame):
    def __init__(self,window):
        super().__init__(window.play_page)
        self.w=window;self.geo=None;self.running=False;self.waiting=False;self.job=None;self.flash_job=None;self.token=0
        self.future=None;self.mode=None;self.daily_tag=None;self.chosen=None
        self.banner=ttk.Frame(self);self.banner.pack(fill='x')
        self.flag_label=ttk.Label(self.banner);self.flag_label.pack(side='left',padx=(0,10))
        self.status=ttk.Label(self.banner,wraplength=800,font='om_bold');self.status.pack(side='left',fill='x',expand=True)
        self.daily_frame=ttk.Frame(self)
        self.input_row=ttk.Frame(self.daily_frame);self.input_row.pack(fill='x',pady=(6,4))
        ttk.Label(self.input_row,text='Country:').pack(side='left',padx=(0,8))
        self.text=tk.StringVar();self.entry=ttk.Entry(self.input_row,textvariable=self.text)
        self.entry.pack(side='left',fill='x',expand=True)
        self.guess_button=ttk.Button(self.input_row,text='Guess',command=self.guess);self.guess_button.pack(side='left',padx=(8,0))
        self.entry.bind('<KeyRelease>',self.suggest);self.entry.bind('<Return>',lambda e:self.guess())
        self.suggestion_frame=ttk.Frame(self.daily_frame)
        self.suggestions=tk.Listbox(self.suggestion_frame,height=3,exportselection=False,font='om_small')
        self.suggestions.pack(fill='x');self.suggestions.bind('<<ListboxSelect>>',self.pick_suggestion)
        tiles_frame=ttk.Frame(self.daily_frame);tiles_frame.pack(fill='both',expand=True,pady=4)
        self.tiles=tk.Canvas(tiles_frame,width=1,height=200,highlightthickness=0)
        scroll=ttk.Scrollbar(tiles_frame,orient='vertical',command=self.tiles.yview);scroll.pack(side='right',fill='y')
        self.tiles.pack(fill='both',expand=True);self.tiles.configure(yscrollcommand=scroll.set)
        self.tiles.bind('<Configure>',lambda e:self.draw_tiles())
        self.tiles.bind('<MouseWheel>',lambda e:self.tiles.yview_scroll(-1 if e.delta>0 else 1,'units'))
        self.reveal_label=ttk.Label(self.daily_frame);self.reveal_label.pack(anchor='center')
        self.share_button=ttk.Button(self.daily_frame,text='Share',command=self.share)
        self.map_frame=ttk.Frame(self)
        map_controls=ttk.Frame(self.map_frame);map_controls.pack(fill='x',pady=4)
        ttk.Label(map_controls,text='Click to guess · drag to pan · wheel to zoom',style='Muted.TLabel').pack(side='left')
        ttk.Button(map_controls,text='Fit map',command=lambda:self.map.reset()).pack(side='right')
        self.map=GameMap(self.map_frame,self.map_click);self.map.pack(fill='both',expand=True)
        self.next_button=ttk.Button(self.map_frame,text='Next state',command=self.next_state)
        self.bind('<Destroy>',self.destroyed,add='+')

    def start(self,game,level,practice=False):
        self.cancel_jobs();self.token+=1;self.mode=game;self.level=level;self.practice=practice
        self.running=False;self.waiting=True;self.duration=0.;self.results=[];self.guesses=[];self.hint_rows=[]
        self.suggestion_frame.pack_forget();self.share_button.pack_forget();self.next_button.pack_forget()
        self.daily_frame.pack_forget();self.map_frame.pack_forget();self.reveal_label.configure(image='');self.flag_label.configure(image='')
        self.status.configure(text='Preparing geography…');self.w.prompt.configure(text=GAMES[game][0])
        if game=='rrdle' or level=='easy':self.w.timer.pack_forget()
        else:self.w.timer.pack(fill='x',before=self.w.prompt)
        self.w.footer.configure(text='Daily puzzles use UTC. Practice is unscored.' if game=='rrdle' else 'Ten states · 1,000 points each · map distances use 40,075 km per world width.')
        self.w.detail_frame.pack_forget();self.pack_forget();self.pack(fill='both',expand=True,pady=4)
        self.async_call(self.w.service.geography,self.ready)

    def async_call(self,fn,callback,*args):
        self.waiting=True;self.future=self.w.service.worker.submit(fn,*args);token=self.token
        self.w.load_status.pack(anchor='w',before=self.w.score_line)
        self.w.loading.pack(fill='x',before=self.w.load_status);self.w.loading.start(18)
        def poll():
            self.job=None
            if self.w.closed or token!=self.token:return
            if not self.future.done():self.job=self.after(80,poll);return
            self.w.loading.stop();self.w.loading.pack_forget();self.waiting=False
            try:callback(self.future.result())
            except Exception as error:
                self.running=False;self.status.configure(text='Unable to prepare game: '+str(error));self.unlock()
        self.job=self.after(80,poll)

    def ready(self,geo):
        self.geo=geo;self.running=True
        self.w.load_status.configure(text=f'Ready · {len(geo.countries)} countries · {len(geo.positions)} states')
        if self.mode=='rrdle':self.start_daily()
        else:
            pool=geo.state_pool(self.level)
            if len(pool)<10:raise ValueError('Fewer than ten usable states are available.')
            self.states=random.sample(pool,10);self.map_frame.pack(fill='both',expand=True)
            self.next_state()

    def start_daily(self):
        self.day=utc_day();self.limit=GUESS_LIMITS[self.level];self.pool=self.geo.pool(self.level)
        self.guesses=[];todo=self.w.app.todo_page();records=todo.data.get('rr_game_scores',[])
        if self.practice:
            self.answer=random.choice(self.pool);self.record=None
        else:
            shared=todo.data.setdefault('rr_daily',{}).setdefault(self.day,{})
            if self.level not in shared:
                shared[self.level]=daily_answer(self.day,self.level,self.pool);todo.save(undoable=False,feedback=False)
            self.answer=shared[self.level]
            self.record=daily_record(records,self.w.player,self.day,self.level)
        if self.answer not in self.geo.countries:
            raise ValueError('The shared daily country is absent from these mod files. Pull the latest mod files, or use Practice.')
        if self.record:
            self.guesses=list(self.record.get('guesses',[]));self.duration=self.record.get('duration',0.)
            self.run_id=self.record['id']
        else:self.run_id='rrdle:'+self.day+':'+self.level+':'+self.w.player
        self.daily_frame.pack(fill='both',expand=True);self.text.set('');self.chosen=None
        self.entry.configure(state='normal');self.guess_button.configure(state='normal');self.entry.focus_set()
        if not self.practice and self.record is None:self.save_daily(False,False)
        self.refresh_daily()
        solved=self.answer in self.guesses;finished=solved or len(self.guesses)>=self.limit
        if finished:self.finish_daily(solved,save=False)
        elif self.record and self.record.get('finished'):self.save_daily(False,False)

    def suggest(self,event=None):
        if event is not None and event.keysym in ('Return','Up','Down'):return
        self.chosen=None
        if self.level=='hard' or not self.running:return
        self.matches=self.geo.suggestions(self.text.get(),self.geo.countries)
        self.suggestions.delete(0,'end')
        for tag in self.matches:
            name=self.geo.countries[tag]['name'];suffix=' ['+tag.upper()+']'
            self.suggestions.insert('end',name if name.casefold().endswith(suffix.casefold()) else name+suffix)
        if self.matches:self.suggestion_frame.pack(fill='x',after=self.input_row)
        else:self.suggestion_frame.pack_forget()

    def pick_suggestion(self,event=None):
        selected=self.suggestions.curselection()
        if not selected:return
        self.chosen=self.matches[selected[0]];self.text.set(self.geo.countries[self.chosen]['name'])
        self.entry.focus_set()

    def guess(self):
        if not self.running or self.waiting or self.mode!='rrdle':return
        self.check_daily()
        if not self.running:return
        tag=self.chosen if self.chosen and self.text.get()==self.geo.countries[self.chosen]['name'] else self.geo.resolve(self.text.get(),self.geo.countries)
        if tag is None:self.status.configure(text='Choose a recognised country name or tag. Ambiguous names need a tag.');return
        if tag in self.guesses:self.status.configure(text='You already guessed that country.');return
        self.guesses.append(tag);self.text.set('');self.chosen=None;self.suggestion_frame.pack_forget()
        self.refresh_daily();solved=tag==self.answer
        if solved or len(self.guesses)>=self.limit:self.finish_daily(solved)
        elif not self.practice:self.save_daily(False,False)

    def refresh_daily(self):
        self.hint_rows=[(tag,self.geo.hints(tag,self.answer,self.level)) for tag in self.guesses if tag in self.geo.countries]
        self.draw_tiles();self.tiles.yview_moveto(1)
        title='Practice' if self.practice else f'RRdle #{daily_number(self.day)} · {self.day} UTC'
        self.w.score_label.configure(text=f'{title} · {len(self.guesses)} / {self.limit} guesses')
        self.status.configure(text='Name the mystery country. Arrows point towards the answer; grey tiles mean no match.' if self.level!='hard' else 'Name the mystery country. No suggestions, size, population or direction hints.')
        self.show_flag(blur=max(0,10-len(self.guesses)*1.5) if self.level=='easy' else None)

    def draw_tiles(self):
        self.tiles.configure(background=ui.P['input_background']);self.tiles.delete('all')
        if self.mode!='rrdle':return
        width=max(200,self.tiles.winfo_width());y=6
        colors={'green':'#28613d','yellow':'#806520','black':'#292d36'}
        for index,(tag,hints) in enumerate(getattr(self,'hint_rows',[]),1):
            self.tiles.create_text(6,y,text=f'{index}. '+self.geo.countries[tag]['name'],fill=ui.P['foreground'],font='om_bold',anchor='nw')
            y+=25;cell=(width-6)/max(1,len(hints))
            for n,(title,value,color) in enumerate(hints):
                x=3+n*cell
                self.tiles.create_rectangle(x,y,x+cell-5,y+80,fill=colors[color],outline=ui.P['border'])
                self.tiles.create_text(x+cell/2,y+12,text=title,fill='#ffffff',font='om_tiny',width=cell-12)
                self.tiles.create_text(x+cell/2,y+47,text=value,fill='#ffffff',font='om_small_bold',width=cell-12)
            y+=90
        self.tiles.configure(scrollregion=(0,0,width,y))

    def show_flag(self,blur=None):
        path=self.geo.countries[self.answer]['flag'];image=read_image(path) if path else None
        if image is None or blur is None:self.flag_label.configure(image='');return
        image=image.copy();image.thumbnail((92,55),Image.Resampling.LANCZOS)
        if blur:image=image.filter(ImageFilter.GaussianBlur(blur))
        self.flag_photo=ImageTk.PhotoImage(image,master=self);self.flag_label.configure(image=self.flag_photo)

    def save_daily(self,solved,finished):
        if self.practice:return
        todo=self.w.app.todo_page();now=dt.datetime.now(dt.timezone.utc).isoformat()
        record=dict(id=self.run_id,game='rrdle',difficulty=self.level,dev=self.w.player,day=self.day,guesses=list(self.guesses),
            score=self.limit-len(self.guesses)+1 if solved else 0,answered=len(self.guesses),completed=solved,finished=finished,
            duration=round(self.duration,2),when=(self.record or {}).get('when',now),updated=now)
        records=todo.data.setdefault('rr_game_scores',[])
        for index,row in enumerate(records):
            if row.get('id')==self.run_id:records[index]=record;break
        else:records.append(record)
        self.record=record;todo.save(undoable=False,feedback=False)

    def finish_daily(self,solved,save=True):
        self.running=False;self.entry.configure(state='disabled');self.guess_button.configure(state='disabled')
        self.suggestion_frame.pack_forget();self.show_flag(0)
        self.status.configure(text=('Solved! ' if solved else 'The answer was ')+self.geo.countries[self.answer]['name'])
        if save:self.save_daily(solved,True)
        self.share_button.pack(anchor='e',pady=4);self.async_call(lambda:self.geo.reveal(self.answer),self.show_reveal)
        self.unlock()
        answer=self.geo.countries[self.answer]['name']
        rows=[(f'Guess {n}',self.geo.countries[tag]['name'],answer,'✓ Solved' if tag==self.answer else 'Clues given') for n,tag in enumerate(self.guesses,1)]
        self.w.show_round_result(f'{self.limit-len(self.guesses)+1} points · {len(self.guesses)} / {self.limit} guesses' if solved else f'0 points · X / {self.limit}',
            ('Solved! ' if solved else 'The answer was ')+answer+(' · Practice (unscored)' if self.practice else ' · Daily puzzle'),rows,daily=True,reaction=result_band('rrdle',solved=solved))

    def show_reveal(self,image):
        if image is None:return
        image=image.copy();image.thumbnail((220,100),Image.Resampling.LANCZOS)
        self.reveal_photo=ImageTk.PhotoImage(image,master=self);self.reveal_label.configure(image=self.reveal_photo)

    def share(self):
        solved=self.answer in self.guesses;count=str(len(self.guesses)) if solved else 'X'
        title='RRdle Practice' if self.practice else f'RRdle #{daily_number(self.day)}'
        rows=[f'{title} ({self.level.title()}) {count}/{self.limit}']
        symbols={'green':'🟩','yellow':'🟨','black':'⬛'}
        rows.extend(''.join(symbols[color] for _,_,color in hints) for _,hints in self.hint_rows)
        self.clipboard_clear();self.clipboard_append('\n'.join(rows));self.status.configure(text='Copied result to clipboard.')

    def check_daily(self):
        if self.mode!='rrdle' or self.practice or not self.geo:return
        shared=self.w.app.todo_page().data.get('rr_daily',{}).get(self.day,{}).get(self.level)
        if shared and shared!=self.answer:
            if shared not in self.geo.countries:
                self.running=False;self.status.configure(text='The shared answer needs newer mod files. Pull the mod to resume this daily.');self.unlock();return
            self.answer=shared;self.refresh_daily()
            solved=shared in self.guesses;finished=solved or len(self.guesses)>=self.limit
            self.save_daily(solved,finished)
            if finished:self.finish_daily(solved,save=False)
            elif not self.running:self.status.configure(text='Shared daily updated. Start to resume your saved guesses.')

    def next_state(self):
        if not self.running or self.waiting:return
        if len(self.results)>=10:self.finish_pinpoint();return
        if self.flash_job:self.after_cancel(self.flash_job);self.flash_job=None
        self.sid=self.states[len(self.results)];self.next_button.pack_forget();self.map.enabled=True
        owner=self.geo.data.state_owner.get(self.sid);self.map.set_world(self.geo,self.level,owner)
        name=self.geo.data.state_names.get(self.sid,f'State {self.sid}')
        text=name
        if self.level!='hard':text+=' · '+self.geo.countries.get(owner,{}).get('name','Unowned')
        if self.level=='easy':text+=' · '+self.geo.data.state_continent.get(self.sid,'')
        self.w.prompt.configure(text=text);self.w.score_label.configure(text=f'State {len(self.results)+1} / 10 · {sum(r["points"] for r in self.results):,} points')
        self.status.configure(text='Click inside the target state for 1,000 points.');self.flag_label.configure(image='')
        if self.level=='easy' and owner in self.geo.countries:
            path=self.geo.countries[owner]['flag'];image=read_image(path) if path else None
            if image:
                image=image.copy();image.thumbnail((72,44));self.flag_photo=ImageTk.PhotoImage(image,master=self);self.flag_label.configure(image=self.flag_photo)
        self.remaining={'easy':None,'medium':20.,'hard':10.}[self.level]
        self.w.timer.configure(value=0)

    def map_click(self,point):
        if not self.running or self.waiting or not self.map.enabled:return
        self.map.enabled=False
        self.async_call(self.geo.pinpoint_score,self.show_pinpoint_result,self.sid,point)

    def show_pinpoint_result(self,result):
        self.results.append(result);self.map.results=[result];self.map.selected=self.sid;self.map.flash=True;self.map.render()
        self.w.score_label.configure(text=f'State {len(self.results)} / 10 · {sum(r["points"] for r in self.results):,} points')
        km=result['km'];text='Time ran out — 0 points.' if km is None else 'Inside the state! 1,000 points.' if result['inside'] else f'{km:,.0f} km off · {result["points"]:,} points'
        self.status.configure(text=text);self.w.clock_label.configure(text='')
        self.next_button.configure(text='Show results' if len(self.results)==10 else 'Next state');self.next_button.pack(anchor='e',pady=4)
        self.flash_count=0;self.flash_state()

    def flash_state(self):
        self.flash_job=None
        if not self.running:return
        self.flash_count+=1;self.map.flash=self.flash_count%2==0 or self.flash_count>=6;self.map.render()
        if self.flash_count<6:self.flash_job=self.after(180,self.flash_state)

    def finish_pinpoint(self):
        self.running=False;score=sum(r['points'] for r in self.results)
        if self.results:
            record=dict(id=self.w.round_id,game='pinpoint',difficulty=self.level,dev=self.w.player,score=score,answered=len(self.results),
                completed=len(self.results)==10,duration=round(self.duration,2),when=dt.datetime.now(dt.timezone.utc).isoformat(),
                hits=sum(r['inside'] for r in self.results),clicks=self.results)
            todo=self.w.app.todo_page();records=todo.data.setdefault('rr_game_scores',[])
            if not any(r.get('id')==record['id'] for r in records):records.append(record);todo.save(undoable=False,feedback=False)
        self.map.set_world(self.geo,self.level);self.map.results=list(self.results);self.map.enabled=False;self.map.render()
        self.next_button.pack_forget();self.status.configure(text=f'{score:,} / 10,000 points · {sum(r["inside"] for r in self.results)} exact hits · {len(self.results)} states played')
        self.w.score_label.configure(text='Pinpoint · round results');self.unlock()
        rows=[(self.geo.data.state_names.get(r['sid'],f"State {r['sid']}"),
            'Time ran out' if r['km'] is None else 'Inside target' if r['inside'] else f"{r['km']:,.0f} km off",
            self.geo.data.state_names.get(r['sid'],f"State {r['sid']}"),f"{r['points']:,} pts") for r in self.results]
        self.w.show_round_result(f'{score:,} / 10,000 points',
            f"{sum(r['inside'] for r in self.results)} exact hits · {len(self.results)} states played. Review round / map shows every guess and target.",rows,completed=len(self.results)==10,reaction=result_band('pinpoint',score))

    def tick(self,seconds,paused):
        if not self.running or self.waiting:return
        if self.mode=='pinpoint' and not self.map.enabled:return
        if paused:self.w.clock_label.configure(text='Paused');return
        self.duration+=seconds
        if self.mode=='pinpoint' and self.remaining is not None:
            self.remaining=max(0,self.remaining-seconds);self.w.clock_label.configure(text=f'{self.remaining:.1f}s')
            self.w.timer.configure(maximum=20 if self.level=='medium' else 10,value=self.remaining)
            if not self.remaining:self.map_click(None)
        else:self.w.clock_label.configure(text=f'{int(self.duration)//60}:{int(self.duration)%60:02d}')

    def end(self):
        if self.waiting:
            self.token+=1;self.cancel_jobs();self.waiting=False;self.running=False
            if self.mode=='pinpoint' and self.geo:self.finish_pinpoint()
            else:self.unlock()
            return
        if self.mode=='rrdle':
            if self.running:self.save_daily(False,False)
            self.running=False;self.entry.configure(state='disabled');self.guess_button.configure(state='disabled')
            self.status.configure(text='Practice ended.' if self.practice else 'Daily paused. Start again to resume your guesses.');self.unlock()
            self.w.show_round_result(f'{len(self.guesses)} / {self.limit} guesses used',
                'Practice ended.' if self.practice else 'Your daily guesses are saved. Resume to continue; the answer remains hidden.',
                [(f'Guess {n}',self.geo.countries[tag]['name'],'Not revealed','Paused') for n,tag in enumerate(self.guesses,1)],
                completed=False,daily=True,paused=not self.practice)
        elif self.geo:self.finish_pinpoint()

    def unlock(self):
        self.w.active=False;self.w.busy=False;self.w.start_button.configure(state='normal');self.w.end_button.configure(state='disabled')
        self.w.game_combo.configure(state='readonly');self.w.level_combo.configure(state='readonly');self.w.practice_button.configure(state='normal')
        self.w.loading.stop();self.w.loading.pack_forget();self.w.timer.configure(value=0);self.w.clock_label.configure(text='')
        self.w.board_game.set(GAMES[self.mode][0]);self.w.board_level.set(self.level.title());self.w.fill_board()

    def cancel_jobs(self):
        for job in (self.job,self.flash_job):
            if job:
                try:self.after_cancel(job)
                except tk.TclError:pass
        self.job=self.flash_job=None

    def hide(self):
        self.token+=1;self.cancel_jobs();self.running=False;self.pack_forget()

    def destroyed(self,event):
        if event.widget is self:self.token+=1;self.cancel_jobs()
