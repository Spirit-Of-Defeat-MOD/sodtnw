"""Mod-backed games, with developer leaderboards by difficulty."""
from concurrent.futures import Future
import datetime
from pathlib import Path
import queue
import threading
import textwrap
import time
import tkinter as tk
from tkinter import ttk
import uuid

from PIL import Image,ImageTk

import ui
from rr_games_style import GameBanner,ResultArtwork,result_band,stage,theme_game_tabs
from rr_games_data import GameData,QuestionFactory,GAMES,LEVELS,flag_seconds,normalise


def leaderboard(records,game,level):
    best={}
    for row in records:
        if row.get('game')!=game or row.get('difficulty')!=level or not row.get('dev'):continue
        rank=lambda r:(r.get('score',0),-float(r.get('duration',0))) if game=='pinpoint' else (r.get('score',0),bool(r.get('completed')), -float(r.get('duration',0)))
        old=best.get(row['dev'])
        if old is None or rank(row)>rank(old):best[row['dev']]=row
    if game=='pinpoint':return sorted(best.values(),key=lambda r:(-r.get('score',0),float(r.get('duration',0)),r['dev'].lower()))
    return sorted(best.values(),key=lambda r:(-r.get('score',0),not r.get('completed'),float(r.get('duration',0)),r['dev'].lower()))


class Worker:
    """Serial data work on a daemon; closing a loading game never delays app exit."""
    def __init__(self):
        self.tasks=queue.Queue();self.closed=False
        threading.Thread(target=self.run,name='rr-games-data',daemon=True).start()

    def submit(self,fn,*args):
        future=Future()
        if self.closed:future.cancel()
        else:self.tasks.put((future,fn,args))
        return future

    def run(self):
        while True:
            task=self.tasks.get()
            if task is None:return
            future,fn,args=task
            if not future.set_running_or_notify_cancel():continue
            try:future.set_result(fn(*args))
            except Exception as error:future.set_exception(error)

    def close(self):
        self.closed=True
        while True:
            try:task=self.tasks.get_nowait()
            except queue.Empty:break
            if task:task[0].cancel()
        self.tasks.put(None)


class GameService:
    def __init__(self,app):
        self.app=app;self.worker=Worker();self.messages=queue.Queue();self.factory=None
        cache=Path(app.tool_dir)/'.rr_games_cache'
        self.data_future=self.worker.submit(GameData,app.mod_root,str(cache),self.messages.put)
        self.geo=None
        self.music=None

    def geography(self):
        if self.geo is None:
            from rr_geography import Geography
            self.geo=Geography(self.data_future.result())
        return self.geo

    def question(self,game,level,seen):
        if game=='station':
            if self.music is None:
                from rr_music_game import MusicQuestions
                self.music=MusicQuestions(Path(self.app.mod_root).parent)
            return self.music.question(level,seen)
        if self.factory is None:self.factory=QuestionFactory(self.data_future.result())
        return self.factory.question(game,level,seen)

    def close(self):self.worker.close()


def show(app):
    window=getattr(app,'rr_games_window',None)
    if window is not None and window.winfo_exists():window.deiconify();window.lift();return window
    if getattr(app,'rr_games_service',None) is None:app.rr_games_service=GameService(app)
    app.rr_games_window=GamesWindow(app,app.rr_games_service)
    return app.rr_games_window


class GamesWindow(tk.Toplevel):
    def __init__(self,app,service):
        super().__init__(app.root)
        self.app,self.service=app,service;self._om_nonmodal=True
        self.title('RR Games');self.transient(app.root)
        self.geometry(f"1000x{min(800,self.winfo_screenheight()-90)}");self.minsize(760,580)
        self.closed=False;self.data_ready=False;self.active=False;self.busy=False;self.current=None;self.future=None;self.future_round=None
        self.timer_job=self.poll_job=self.feedback_job=self.board_job=None
        self.last_tick=time.monotonic();self.had_focus=False;self.hidden=False;self.preview_left=0
        self.clip_player=None;self.clip_job=None;self.audio_ready=False
        self.game_names={meta[0]:key for key,meta in GAMES.items()}
        body=ttk.Frame(self,padding=12);body.pack(fill='both',expand=True)
        self.banner=GameBanner(body);self.banner.pack(fill='x')
        self.round_review=[];self.pending_end=False;self.last_summary=None
        self.tabs=ttk.Notebook(body,style="RRGame.TNotebook");self.tabs.pack(fill='both',expand=True,pady=(8,0))
        self.play_page=ttk.Frame(self.tabs,padding=10);self.board_page=ttk.Frame(self.tabs,padding=10)
        self.tabs.add(self.play_page,text='Play');self.tabs.add(self.board_page,text='Leaderboards')
        controls=ttk.Frame(self.play_page);controls.pack(fill='x')
        self.game_var=tk.StringVar(value=next(iter(self.game_names)))
        self.game_combo=ttk.Combobox(controls,textvariable=self.game_var,values=list(self.game_names),state='readonly',width=31)
        self.game_combo.grid(row=0,column=0,sticky='ew',padx=(0,8));controls.columnconfigure(0,weight=1)
        self.level_var=tk.StringVar(value='Easy')
        self.level_combo=ttk.Combobox(controls,textvariable=self.level_var,values=('Easy','Medium','Hard'),state='readonly',width=12)
        self.level_combo.grid(row=0,column=1,padx=(0,8))
        self.start_button=ttk.Button(controls,text='Start round',command=self.start,state='disabled');self.start_button.grid(row=0,column=2)
        self.end_button=ttk.Button(controls,text='End round',command=self.end,state='disabled');self.end_button.grid(row=0,column=3,padx=(8,0))
        self.practice_button=ttk.Button(controls,text='Practice',command=lambda:self.start(practice=True),state='disabled')
        self.game_combo.bind('<<ComboboxSelected>>',self.game_changed);self.level_combo.bind('<<ComboboxSelected>>',self.game_changed)
        self.description=ttk.Label(self.play_page,wraplength=900,style='Muted.TLabel');self.description.pack(anchor='w',pady=(8,4))
        self.loading=ttk.Progressbar(self.play_page,mode='indeterminate');self.loading.pack(fill='x',pady=(2,4));self.loading.start(18)
        self.load_status=ttk.Label(self.play_page,text='Loading game data…',style='Muted.TLabel');self.load_status.pack(anchor='w')
        line=self.score_line=ttk.Frame(self.play_page);line.pack(fill='x',pady=(10,4))
        self.score_label=ttk.Label(line,text='Choose a game and difficulty.',font='om_bold');self.score_label.pack(side='left')
        self.clock_label=ttk.Label(line,font='om_bold');self.clock_label.pack(side='right')
        self.timer=ttk.Progressbar(self.play_page,mode='determinate');self.timer.pack(fill='x')
        self.prompt=ttk.Label(self.play_page,text='Ten games. Three difficulties. One very competitive dev team.',font='om_bold',wraplength=900)
        self.prompt.pack(anchor='w',pady=(8,4))
        self.image_canvas=tk.Canvas(self.play_page,height=245,highlightthickness=0,borderwidth=0);self.image_canvas.pack(fill='both',expand=True)
        self.image_canvas.bind('<Configure>',lambda e:self.render_image())
        self.composition_frame=ttk.Frame(self.play_page)
        self.composition_tables={};self.composition_panels={}
        for index,(key,title) in enumerate((('cultures','Cultures'),('religions','Religions'))):
            panel=ttk.LabelFrame(self.composition_frame,text=title,padding=4)
            panel.grid(row=0,column=index,sticky='nsew',padx=(0,5) if index==0 else (5,0))
            self.composition_frame.columnconfigure(index,weight=1,uniform='composition')
            tree=ttk.Treeview(panel,columns=('name','presence','role'),show='headings',height=8,selectmode='none')
            for column,label,width in (('name',title[:-1] if key=='cultures' else 'Religion',150),('presence','Presence',90),('role','Role',75)):
                tree.heading(column,text=label);tree.column(column,width=width,minwidth=40 if column=='role' else 60,stretch=True)
            scroll=ttk.Scrollbar(panel,orient='vertical',command=tree.yview)
            scroll.pack(side='right',fill='y');tree.pack(fill='both',expand=True);tree.configure(yscrollcommand=scroll.set)
            self.composition_tables[key]=tree;self.composition_panels[key]=panel
        self.composition_frame.rowconfigure(0,weight=1)
        self.detail_frame=ttk.Frame(self.play_page)
        self.detail=tk.Text(self.detail_frame,height=2,wrap='word',borderwidth=0,highlightthickness=0,state='disabled',font='om_small')
        self.detail.pack(side='left',fill='x',expand=True)
        detail_scroll=ttk.Scrollbar(self.detail_frame,orient='vertical',command=self.detail.yview);detail_scroll.pack(side='right',fill='y');self.detail.configure(yscrollcommand=detail_scroll.set)
        self.answers=ttk.Frame(self.play_page);self.answers.pack(fill='x')
        self.choice_buttons=[]
        for n in range(4):
            button=ttk.Button(self.answers,text='',width=1,command=lambda index=n:self.choose(index))
            button.grid(row=n//2,column=n%2,sticky='ew',padx=(0,4) if n%2==0 else (4,0),pady=3)
            self.choice_buttons.append(button)
        for n in (0,1):self.answers.columnconfigure(n,weight=1)
        self.typed_frame=ttk.Frame(self.play_page)
        self.answer_var=tk.StringVar();self.entry=ttk.Combobox(self.typed_frame,textvariable=self.answer_var)
        self.entry.pack(side='left',fill='x',expand=True);self.entry.bind('<Return>',lambda e:self.answer())
        self.entry.bind('<KeyRelease>',self.station_autocomplete)
        self.submit=ttk.Button(self.typed_frame,text='Submit',command=self.answer);self.submit.pack(side='left',padx=(8,0))
        self.audio_controls=ttk.Frame(self.play_page)
        ttk.Button(self.audio_controls,text='▶ Replay clip',command=self.play_clip).pack(side='left',padx=(0,8))
        ttk.Button(self.audio_controls,text='■ Stop',command=self.stop_clip).pack(side='left')
        self.audio_status=ttk.Label(self.audio_controls,style='Muted.TLabel');self.audio_status.pack(side='left',padx=10)
        self.clip_volume=tk.DoubleVar(value=.6)
        ttk.Scale(self.audio_controls,from_=0,to=1,variable=self.clip_volume,command=self.set_clip_volume,length=110).pack(side='right')
        ttk.Label(self.audio_controls,text='Volume').pack(side='right',padx=6)
        self.feedback=ttk.Label(self.play_page,wraplength=900,font='om_bold');self.feedback.pack(anchor='w',pady=(8,0))
        self.footer=ttk.Label(self.play_page,text='Questions use the saved mod data. Quiz rounds have 10 questions.',style='Muted.TLabel',wraplength=900)
        self.footer.pack(side='bottom',fill='x',before=self.image_canvas,pady=(6,0))
        self.feedback.pack(fill='x',after=self.prompt,pady=(4,6))
        self.detail_frame.pack(side='bottom',fill='x',before=self.image_canvas,pady=(4,6))
        from rr_extended_games import ExtendedGames
        self.extra=ExtendedGames(self)
        selectors=ttk.Frame(self.board_page);selectors.pack(fill='x')
        self.board_game=tk.StringVar(value=self.game_var.get());self.board_level=tk.StringVar(value='Easy')
        a=ttk.Combobox(selectors,textvariable=self.board_game,values=list(self.game_names),state='readonly',width=33);a.pack(side='left',fill='x',expand=True)
        b=self.board_level_combo=ttk.Combobox(selectors,textvariable=self.board_level,values=('Easy','Medium','Hard'),state='readonly',width=14);b.pack(side='left',padx=8)
        for combo in (a,b):combo.bind('<<ComboboxSelected>>',lambda e:self.fill_board())
        self.board=ttk.Treeview(self.board_page,columns=('rank','dev','score','accuracy','time','date'),show='headings',height=16)
        for key,title,width in (('rank','#',40),('dev','Developer',150),('score','Best score',90),('accuracy','Correct / answered',135),('time','Time',85),('date','Achieved',150)):
            self.board.heading(key,text=title);self.board.column(key,width=width,anchor='w' if key in ('dev','date') else 'center',stretch=key in ('dev','date'))
        self.board.pack(fill='both',expand=True,pady=(12,8))
        self.board_note=ttk.Label(self.board_page,text='Best run per developer and difficulty. Score first; faster time breaks ties.',style='Muted.TLabel',wraplength=850);self.board_note.pack(anchor='w')
        self.result_page=ttk.Frame(self.tabs,padding=16)
        result_heading=ttk.Frame(self.result_page);result_heading.pack(fill='x',pady=(0,12))
        self.result_art=ResultArtwork(result_heading);self.result_art.pack(side='right')
        result_words=ttk.Frame(result_heading);result_words.pack(side='left',fill='both',expand=True)
        self.result_title=ttk.Label(result_words,text='Round complete',font='om_title');self.result_title.pack(anchor='w')
        self.result_score=ttk.Label(result_words,font='om_big');self.result_score.pack(anchor='w',pady=(10,4))
        self.result_detail=ttk.Label(result_words,wraplength=650,font='om_body');self.result_detail.pack(anchor='w')
        actions=ttk.Frame(self.result_page);actions.pack(fill='x',pady=(0,12))
        self.again_button=ttk.Button(actions,text='▶ Play Again',command=self.play_again);self.again_button.pack(side='left',ipadx=16,ipady=5)
        ttk.Button(actions,text='Review round / map',command=lambda:self.tabs.select(self.play_page)).pack(side='left',padx=8)
        ttk.Button(actions,text='Leaderboards',command=lambda:self.tabs.select(self.board_page)).pack(side='left')
        review_frame=ttk.Frame(self.result_page);review_frame.pack(fill='both',expand=True)
        self.review=ttk.Treeview(review_frame,columns=('question','chosen','answer','result'),show='headings',height=10)
        for key,label,width in (('question','Question',240),('chosen','Your answer',200),('answer','Correct answer',220),('result','Result',90)):
            self.review.heading(key,text=label);self.review.column(key,width=width,minwidth=65,stretch=True)
        scroll=ttk.Scrollbar(review_frame,command=self.review.yview);scroll.pack(side='right',fill='y')
        horizontal=ttk.Scrollbar(review_frame,orient='horizontal',command=self.review.xview);horizontal.pack(side='bottom',fill='x')
        self.review.configure(yscrollcommand=scroll.set,xscrollcommand=horizontal.set);self.review.pack(fill='both',expand=True)
        self.review.bind('<Double-Button-1>',self.review_answer)
        self.review.bind('<<TreeviewSelect>>',self.review_selection)
        self.review_note=ttk.Label(self.result_page,wraplength=850,font='om_bold');self.review_note.pack(fill='x',before=review_frame,pady=(6,8))
        ttk.Label(self.result_page,text='Double-click a row to read its full answer.',style='Muted.TLabel').pack(anchor='w',before=review_frame,pady=5)
        bottom=ttk.Frame(body);bottom.pack(side='bottom',fill='x',before=self.tabs,pady=(8,0))
        ttk.Button(bottom,text='Close games',command=self.close).pack(side='left')
        self.next_button=ttk.Button(bottom,text='Next question →',command=lambda:self.after_answer(self.pending_end))
        self.next_button.pack(side='right');self.next_button.pack_forget()
        self.reveal=ttk.Label(body,wraplength=900,font='om_bold',padding=(12,8))
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.bind('<Destroy>',self.destroyed,add='+')
        self.bind('<Configure>',self.resize_text,add='+')
        ui.THEME_HOOKS.append(self.retheme);self.retheme();self.game_changed()
        self.answers.pack_forget();self.poll_job=self.after(100,self.poll);self.timer_job=self.after(100,self.tick);self.refresh_board()

    def resize_text(self,event):
        if event.widget is not self:return
        width=max(300,self.winfo_width()-60)
        for label in (self.description,self.prompt,self.feedback,self.footer):label.configure(wraplength=width)
        self.extra.status.configure(wraplength=max(200,width-120))
        self.result_detail.configure(wraplength=max(200,width-ui.px(170)))
        self.reveal.configure(wraplength=width-ui.px(24))
        self.review_note.configure(wraplength=width-ui.px(24))

    def set_detail(self,text):
        self.detail.configure(state='normal');self.detail.delete('1.0','end');self.detail.insert('1.0',text);self.detail.configure(state='disabled');self.detail.yview_moveto(0)

    def game_changed(self,event=None):
        game=self.game_names[self.game_var.get()];level=self.level_combo.current()
        if level<0:level=0
        self.level_combo.configure(values=('Easy','Normal','Hard') if game in ('passport','ideology','station') else ('Easy','Medium','Hard'))
        self.level_combo.current(level)
        self.description.configure(text=GAMES[game][1])
        if not self.active:self.description.pack(anchor='w',before=self.score_line,pady=(6,4))
        self.banner.set_game(game,GAMES[game][0],self.level_var.get()+' · '+GAMES[game][2][level])
        if game=='rrdle':
            self.practice_button.grid(row=0,column=4,padx=(8,0))
            self.practice_button.configure(state='normal' if self.data_ready and not self.active else 'disabled')
        else:self.practice_button.grid_remove()
        if not self.active and hasattr(self,'extra') and self.extra.mode and self.extra.mode!=game:
            self.extra.hide();self.detail_frame.pack(side='bottom',fill='x',before=self.feedback,pady=(4,6));self.show_composition(None)
        self.board_game.set(self.game_var.get());self.board_level.set(('Easy','Medium','Hard')[level]);self.fill_board()

    def start(self,practice=False):
        if self.active or not self.service.data_future.done():return
        try:self.service.data_future.result()
        except Exception as error:self.load_status.configure(text='Game data could not load: '+str(error));return
        todo=self.app.todo_page();player=todo.me.get()
        if not any(d.get('name')==player for d in todo.data.get('devs',[])):
            self.feedback.configure(text='Choose your developer name in the main tool before starting.');return
        self.player=player;self.round_id=uuid.uuid4().hex
        self.round_review=[];self.next_button.pack_forget();self.reveal.pack_forget();self.description.pack_forget();self.result_art.stop()
        if str(self.result_page) in self.tabs.tabs():self.tabs.hide(self.result_page)
        self.session_game=self.game_names[self.game_var.get()];self.session_level=LEVELS[self.level_combo.current()]
        self.correct=self.answered=0;self.duration=0.;self.seen=set();self.active=True;self.last_tick=time.monotonic()
        self.game_combo.configure(state='disabled');self.level_combo.configure(state='disabled');self.start_button.configure(state='disabled');self.end_button.configure(state='normal')
        self.practice_button.configure(state='disabled')
        self.tabs.select(self.play_page);self.feedback.configure(text='');self.next_question()

        if self.session_game in ('rrdle','pinpoint'):
            self.extra.start(self.session_game,self.session_level,practice)

    def next_question(self):
        if not self.active:return
        self.stop_clip();self.audio_controls.pack_forget();self.next_button.pack_forget();self.reveal.pack_forget()
        if self.session_game in ('rrdle','pinpoint'):
            self.current=None;self.busy=True;self.answers.pack_forget();self.typed_frame.pack_forget()
            self.image_canvas.pack_forget();self.composition_frame.pack_forget();self.set_detail('');self.detail.configure(height=1)
            self.future=None
            return
        self.extra.hide();self.footer.configure(text='Questions use the saved mod data. Quiz rounds have 10 questions.')
        self.timer.pack(fill='x',before=self.prompt)
        self.detail_frame.pack(side='bottom',fill='x',before=self.feedback,pady=(4,6))
        self.current=None;self.busy=True;self.hidden=False;self.preview_left=0
        self.answers.pack_forget();self.typed_frame.pack_forget();self.image_canvas.delete('all')
        self.load_status.pack(anchor='w',before=self.score_line)
        self.loading.pack(fill='x',before=self.load_status,pady=(2,4));self.loading.start(18)
        self.prompt.configure(text='Preparing your next question…');self.set_detail('');self.answer_var.set('')
        self.future_round=self.round_id
        self.future=self.service.worker.submit(self.service.question,self.session_game,self.session_level,set(self.seen))
        self.update_score()

    def poll(self):
        self.poll_job=None
        if self.closed:return
        message=None
        while True:
            try:message=self.service.messages.get_nowait()
            except queue.Empty:break
        if message:self.load_status.configure(text=message)
        if self.service.data_future.done() and not self.data_ready:
            self.data_ready=True;self.loading.stop();self.loading.pack_forget()
            try:
                data=self.service.data_future.result()
                if not self.active:self.start_button.configure(state='normal')
                if not self.active and self.game_names[self.game_var.get()]=='rrdle':self.practice_button.configure(state='normal')
                if message is None and not self.active:self.load_status.configure(text=f"Ready · {len(data.religions)} religions · {len(data.states)} states · {len(data.leaders)} leaders")
            except Exception as error:self.load_status.configure(text='Unable to load questions: '+str(error))
        if self.future is not None and self.future.done():
            future,self.future=self.future,None
            if self.active and self.future_round==self.round_id:
                try:self.show_question(future.result())
                except Exception as error:
                    self.feedback.configure(text='Question unavailable: '+str(error));self.finish(False)
        self.poll_job=self.after(100,self.poll)

    def show_question(self,question):
        self.loading.stop();self.loading.pack_forget();self.load_status.configure(text='Ready')
        self.current=question;self.seen.add(question.key);self.busy=False;self.hidden=False
        self.load_status.pack_forget()
        self.preview_left=question.preview;self.budget=flag_seconds(self.correct);self.remaining=self.budget
        self.prompt.configure(text=question.prompt);self.set_detail(question.detail);self.feedback.configure(text='')
        self.show_composition(question.composition)
        self.audio_ready=False
        self.entry.configure(values=sorted(set(question.labels.values())) if question.audio and question.typed else ())
        if question.audio:self.audio_controls.pack(side='bottom',fill='x',before=self.detail_frame,pady=4)
        if question.typed:
            self.typed_frame.pack(side='bottom',fill='x',before=self.prompt)
            self.entry.configure(state='disabled' if self.preview_left else 'normal');self.submit.configure(state='disabled' if self.preview_left else 'normal')
            if not self.preview_left:self.entry.focus_set()
        else:
            self.answers.pack(side='bottom',fill='x',before=self.prompt)
            for n,button in enumerate(self.choice_buttons):
                if n<len(question.options):button.configure(text=textwrap.fill(question.options[n][1],width=38),state='normal');button.grid()
                else:button.grid_remove()
        self.last_tick=time.monotonic();self.update_score();self.render_image()
        if question.audio:self.play_clip()

    def station_autocomplete(self,event):
        q=self.current
        if not q or not q.audio or not q.typed or not self.active or self.busy:return
        value=self.answer_var.get()
        matches=sorted({label for label in q.labels.values() if normalise(value) in normalise(label)})
        self.entry.configure(values=matches)
        if event.keysym in ('BackSpace','Delete','Left','Right','Up','Down','Home','End','Return','Escape','Tab'):return
        prefix=[label for label in matches if value and label.casefold().startswith(value.casefold())]
        if prefix:
            self.answer_var.set(prefix[0]);self.entry.selection_range(len(value),'end');self.entry.icursor(len(value))

    def play_clip(self):
        if not self.current or not self.current.audio or not self.active or self.busy:return
        self.stop_clip();clip=self.current.audio
        try:
            if self.clip_player is None:
                from music_master import Player
                self.clip_player=Player()
            self.clip_player.play(clip['path'],clip['volume']*self.clip_volume.get(),start=clip['start'],length=clip['duration'])
            self.audio_ready=True;self.audio_status.configure(text=f'Playing {clip["seconds"]:g}s clip')
            self.clip_job=self.after(round(clip['seconds']*1000),self.stop_clip)
        except Exception as error:
            self.audio_status.configure(text='Audio unavailable');self.feedback.configure(text='Unable to play clip: '+str(error))

    def stop_clip(self):
        if self.clip_job is not None:
            try:self.after_cancel(self.clip_job)
            except tk.TclError:pass
            self.clip_job=None
        if self.clip_player is not None:self.clip_player.stop()
        if hasattr(self,'audio_status'):self.audio_status.configure(text='Clip stopped')

    def set_clip_volume(self,value):
        if self.clip_player is not None and self.current and self.current.audio:
            self.clip_player.set_volume(float(value)*self.current.audio['volume'])

    def show_composition(self,composition):
        self.detail.configure(height=1 if composition is not None else 2)
        if composition is None:
            self.composition_frame.pack_forget()
            self.image_canvas.pack(fill='both',expand=True,after=self.detail_frame)
            return
        self.image_canvas.pack_forget();self.detail_frame.pack_forget()
        self.composition_frame.pack(fill='both',expand=True,after=self.prompt,pady=(4,8))
        for key,tree in self.composition_tables.items():
            tree.delete(*tree.get_children())
            panel=self.composition_panels[key]
            if key not in composition:
                panel.grid_remove();self.composition_frame.columnconfigure(1,weight=0,minsize=0,uniform='')
                continue
            panel.grid();self.composition_frame.columnconfigure(1,weight=1,uniform='composition')
            for row in composition[key]:tree.insert('','end',values=row)
            if not composition[key]:tree.insert('','end',values=('None recorded','—','—'))

    def choose(self,index):
        if not self.current or index>=len(self.current.options):return
        self.answer(self.current.options[index][0])

    def answer(self,value=None,timeout=False):
        if not self.active or self.busy or self.current is None or self.preview_left>0:return
        typed=self.current.typed
        if typed and value is None:value=self.answer_var.get()
        if typed and not value and not timeout:return
        if typed and normalise(value) in self.current.ambiguous and not timeout:
            self.feedback.configure(text='That station name is shared. Select its full name from the suggestions.' if self.current.audio else 'That country name is shared. Add its tag, for example Name [TAG], or enter the tag alone.');return
        if self.current.audio and not self.audio_ready:
            self.feedback.configure(text='Play the clip before answering. Check your audio device, then use Replay clip.');return
        self.stop_clip()
        good=False if timeout else self.current.accepts(value,typed)
        self.answered+=1;self.correct+=int(good);self.busy=True
        for button in self.choice_buttons:button.configure(state='disabled')
        self.submit.configure(state='disabled');self.entry.configure(state='disabled')
        self.feedback.configure(text=('Correct!  '+self.current.answer_label) if good else ('Time ran out.  ' if timeout else 'Not quite.  ')+'Answer: '+self.current.answer_label,
            foreground=ui.P['age_green'] if good else ui.P['age_red'])
        self.reveal.configure(text=self.feedback.cget('text'),foreground=ui.P['age_green'] if good else ui.P['age_red'],background=ui._mix(ui.P['surface'],ui.P['header_background'],.4))
        self.feedback.configure(text='');self.reveal.pack(side='bottom',fill='x',before=self.tabs,pady=(4,0))
        self.update_score()
        self.round_review.append((self.current.detail or self.current.prompt,
            'Time ran out' if timeout else str(value) if typed else self.current.labels.get(value,str(value)),
            self.current.answer_label,'✓ Correct' if good else '✕ Incorrect'))
        self.pending_end=(self.session_game=='flags' and not good) or (self.session_game!='flags' and self.answered>=10)
        self.next_button.configure(text='See round results →' if self.pending_end else 'Next question →')
        self.next_button.pack(side='right');self.next_button.focus_set()
        self.hidden=False;self.render_image()

    def after_answer(self,end):
        self.feedback_job=None
        self.next_button.pack_forget()
        if not self.active or not self.busy:return
        if end:self.finish(True)
        else:self.next_question()

    def update_score(self):
        if not self.active:return
        text=f'Streak: {self.correct}' if self.session_game=='flags' else f'Question {min(10,len(self.seen)+int(self.current is None))} / 10 · Score {self.correct}'
        self.score_label.configure(text=text)

    def render_image(self):
        if self.closed:return
        canvas=self.image_canvas;canvas.delete('all');stage(canvas)
        if self.current is None:return
        w=max(100,canvas.winfo_width());h=max(100,canvas.winfo_height())
        if self.hidden:
            canvas.create_text(w/2,h/2,text='Map hidden — type the country name.',fill=ui.P['foreground'],font='om_bold');return
        image=self.current.image
        if image is None:
            photo=self.banner.artwork(self.session_game,112)
            if photo:canvas.create_image(w/2,h/2,image=photo)
            else:canvas.create_text(w/2,h/2,text='♫' if self.current.audio else '✦',fill=ui.P['copper'],font=('Segoe UI',54))
            return
        image=image.copy()
        if self.session_game=='borders' or (self.session_game=='holy' and self.session_level=='hard'):
            alpha=image.getchannel('A');image=Image.new('RGBA',image.size,ui.P['input_foreground']);image.putalpha(alpha)
        factor=min((w-24)/image.width,(h-16)/image.height,5)
        image=image.resize((max(1,round(image.width*factor)),max(1,round(image.height*factor))),Image.Resampling.LANCZOS)
        self.photo=ImageTk.PhotoImage(image,master=self);canvas.create_image(w/2,h/2,image=self.photo)

    def tick(self):
        self.timer_job=None
        if self.closed:return
        now=time.monotonic();dt=min(.5,now-self.last_tick);self.last_tick=now
        if self.active and self.session_game in ('rrdle','pinpoint'):
            try:focus=self.focus_displayof()
            except (KeyError,tk.TclError):focus=None
            if focus is not None and focus.winfo_toplevel() is self:self.had_focus=True
            paused=self.state() not in ('normal','zoomed') or (self.had_focus and (focus is None or focus.winfo_toplevel() is not self))
            self.extra.tick(dt,paused)
        elif self.active and not self.busy and self.current is not None:
            try:focus=self.focus_displayof()
            except (KeyError,tk.TclError):focus=None
            if focus is not None and focus.winfo_toplevel() is self:self.had_focus=True
            paused=self.state() not in ('normal','zoomed') or (self.had_focus and (focus is None or focus.winfo_toplevel() is not self))
            if paused:
                self.clock_label.configure(text='Paused')
                if self.current.audio:self.stop_clip()
            else:
                self.duration+=dt
                if self.preview_left>0:
                    self.preview_left=max(0,self.preview_left-dt);self.clock_label.configure(text=f'Map visible: {self.preview_left:.1f}s')
                    self.timer.configure(maximum=self.current.preview,value=self.preview_left)
                    if self.preview_left==0:
                        self.hidden=True;self.render_image();self.entry.configure(state='normal');self.submit.configure(state='normal');self.entry.focus_set()
                elif self.session_game=='flags':
                    self.remaining=max(0,self.remaining-dt);self.clock_label.configure(text=f'{self.remaining:.1f}s')
                    self.timer.configure(maximum=self.budget,value=self.remaining)
                    if self.remaining==0:self.answer(timeout=True)
                else:self.clock_label.configure(text=f'{int(self.duration)//60}:{int(self.duration)%60:02d}');self.timer.configure(value=0)
        self.timer_job=self.after(80,self.tick)

    def end(self):
        if self.active:self.finish(False)

    def finish(self,completed,show_board=True):
        if not self.active:return
        self.stop_clip()
        if self.session_game in ('rrdle','pinpoint'):self.extra.end();return
        self.active=False;self.busy=False
        self.next_button.pack_forget()
        self.loading.stop();self.loading.pack_forget()
        if self.feedback_job is not None:self.after_cancel(self.feedback_job);self.feedback_job=None
        if self.answered:
            record=dict(id=self.round_id,game=self.session_game,difficulty=self.session_level,dev=self.player,
                score=self.correct,answered=self.answered,duration=round(self.duration,2),completed=completed,
                when=datetime.datetime.now(datetime.timezone.utc).isoformat())
            todo=self.app.todo_page();scores=todo.data.setdefault('rr_game_scores',[])
            if not any(row.get('id')==record['id'] for row in scores):scores.append(record)
            todo.save(undoable=False,feedback=False)
        self.start_button.configure(state='normal');self.end_button.configure(state='disabled')
        self.game_combo.configure(state='readonly');self.level_combo.configure(state='readonly')
        self.answers.pack_forget();self.typed_frame.pack_forget()
        self.score_label.configure(text=f'Round complete · {self.correct} correct from {self.answered}')
        self.clock_label.configure(text='');self.timer.configure(value=0)
        self.board_game.set(GAMES[self.session_game][0]);self.board_level.set(self.session_level.title());self.fill_board()
        if show_board:
            self.show_round_result(str(self.correct)+(" streak" if self.session_game=='flags' else f' / {self.answered} correct'),
                f'{self.answered} answered · {self.correct/self.answered:.0%} accuracy' if self.answered else 'No answers submitted.', self.round_review,completed=completed)

    def show_round_result(self,score,detail,rows=(),completed=True,daily=False,paused=False,reaction=None):
        self.last_summary=(score,detail,list(rows))
        self.result_title.configure(text='Daily paused' if paused else 'Round complete' if completed else 'Round ended')
        self.result_score.configure(text=score)
        seconds=int(getattr(self.extra,'duration',self.duration) if self.session_game in ('rrdle','pinpoint') else self.duration)
        self.reveal.pack_forget()
        self.result_art.play(self.session_game,'paused' if paused else reaction or result_band(self.session_game,self.correct))
        self.result_detail.configure(text=f'{GAMES[self.session_game][0]} · {self.level_var.get()} · {seconds//60}:{seconds%60:02d}\n{detail}')
        self.again_button.configure(text='Resume daily' if paused else '▶ Play practice' if daily else '▶ Play Again')
        self.result_daily,self.result_paused=daily,paused
        self.review.delete(*self.review.get_children())
        for row in rows:self.review.insert('','end',values=row)
        if not rows:self.review.insert('','end',values=('No answers submitted.','','',''))
        self.review_note.configure(text='')
        if rows:self.review.selection_set(self.review.get_children()[0])
        self.tabs.add(self.result_page,text='Round results');self.tabs.select(self.result_page)
        self.again_button.focus_set()

    def paint_result(self):
        self.result_art.draw()

    def play_again(self):
        if self.active:return
        self.game_var.set(GAMES[self.session_game][0]);self.level_combo.current(LEVELS.index(self.session_level));self.game_changed()
        self.start(practice=self.session_game=='rrdle' and not self.result_paused)

    def review_selection(self,event=None):
        selected=self.review.selection()
        if not selected:return
        _,chosen,answer,_=self.review.item(selected[0],'values')
        self.review_note.configure(text=f'Correct answer: {answer}\nYour answer: {chosen}' if answer else '')

    def review_answer(self,event=None):
        from tkinter import messagebox
        selected=self.review.selection()
        if selected:
            question,chosen,answer,result=self.review.item(selected[0],'values')
            messagebox.showinfo('Round review',f'{question}\n\nYour answer: {chosen}\nCorrect answer: {answer}\n\n{result}',parent=self)

    def fill_board(self):
        if not hasattr(self,'board'):return
        game=self.game_names[self.board_game.get()];level=self.board_level.get().lower()
        if level=='normal':level='medium'
        normal=game in ('passport','ideology','station')
        self.board_level_combo.configure(values=('Easy','Normal','Hard') if normal else ('Easy','Medium','Hard'))
        self.board_level.set('Normal' if normal and level=='medium' else level.title())
        if game=='rrdle':
            from rr_geography import daily_board
            columns=('Rank','Developer','Current streak','Best streak','Win %','Avg guesses (wins)')
            for key,title in zip(self.board['columns'],columns):self.board.heading(key,text=title)
            rows=daily_board(self.app.todo_page().data.get('rr_game_scores',[]),level)
            self.board.delete(*self.board.get_children())
            for n,row in enumerate(rows,1):self.board.insert('','end',values=(n,row['dev'],row['current'],row['best'],f'{row["win"]:.1f}%',f'{row["average"]:.2f}' if row['average'] is not None else '—'))
            self.board_note.configure(text='Daily games only. Streaks use consecutive UTC dates; average guesses counts wins. Practice is unscored.')
            return
        for key,title in zip(self.board['columns'],('#','Developer','Best score','States played' if game=='pinpoint' else 'Correct / answered','Time','Achieved')):self.board.heading(key,text=title)
        self.board_note.configure(text='Best run per developer and difficulty. Score first; faster time breaks ties.')
        rows=leaderboard(self.app.todo_page().data.get('rr_game_scores',[]),game,level)
        self.board.delete(*self.board.get_children())
        for n,row in enumerate(rows,1):
            seconds=int(row.get('duration',0));date=str(row.get('when',''))[:10]
            score=str(row.get('score',0)) if game=='flags' else str(row.get('score',0))+('/10,000' if game=='pinpoint' else '/10')
            accuracy=f"{row.get('answered',0)} / 10" if game=='pinpoint' else f"{row.get('score',0)} / {row.get('answered',0)}"
            self.board.insert('','end',values=(n,row['dev'],score,accuracy,f'{seconds//60}:{seconds%60:02d}',date))

    def refresh_board(self):
        self.board_job=None
        if self.closed:return
        if self.game_names[self.game_var.get()]=='rrdle' and self.extra.mode=='rrdle' and self.extra.geo and not self.extra.waiting:self.extra.check_daily()
        self.fill_board();self.board_job=self.after(1500,self.refresh_board)

    def retheme(self):
        if self.closed:return
        theme_game_tabs(self);ui.theme_all(self);self.banner.draw();self.render_image()
        if hasattr(self,'session_game'):self.paint_result()
        if hasattr(self,'reveal'):
            self.reveal.configure(background=ui._mix(ui.P['surface'],ui.P['header_background'],.4),
                foreground=ui.P['age_green'] if self.round_review and self.round_review[-1][3].startswith('✓') else ui.P['age_red'])
        if hasattr(self,'extra'):self.extra.draw_tiles();self.extra.map.render()

    def destroyed(self,event):
        if event.widget is self and not self.closed:self.close(destroy=False)

    def close(self,destroy=True):
        if self.closed:return
        if self.active:self.finish(False,show_board=False)
        self.stop_clip()
        self.result_art.stop()
        self.extra.hide()
        self.closed=True
        for job in (self.poll_job,self.timer_job,self.feedback_job,self.board_job):
            if job is not None:
                try:self.after_cancel(job)
                except tk.TclError:pass
        if self.retheme in ui.THEME_HOOKS:ui.THEME_HOOKS.remove(self.retheme)
        if destroy:self.destroy()
