import os
import sys
import random
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_VERSION = "5.18"
VERSION_URL = "https://raw.githubusercontent.com/interforever90/image-motion-tool/main/version.json"

EFFECTS = [
    "Automatico","Zoom In","Zoom Out","Pan sinistra → destra","Pan destra → sinistra",
    "Tilt basso → alto","Tilt alto → basso","Pan + Zoom In","Pan + Zoom Out"
]
MANUAL_EFFECTS = EFFECTS[1:]
PRESETS = {"Delicato":(5.0,7.0),"Cinematico":(8.0,12.0),"Dinamico":(14.0,20.0),"Personalizzato":None}

class App:
    def __init__(self, root):
        self.root=root
        root.title(f"Image Motion Tool {APP_VERSION} — Auto Updater")
        width=min(1080,max(960,root.winfo_screenwidth()-64))
        height=min(780,max(640,root.winfo_screenheight()-96))
        root.geometry(f"{width}x{height}")
        root.minsize(960,640)
        self.images=[]
        self.current_process=None
        self.cancel_event=threading.Event()
        self.duration=tk.StringVar(value="7.0")
        self.effect=tk.StringVar(value="Automatico")
        self.res=tk.StringVar(value="1920x1080")
        self.fps=tk.StringVar(value="30")
        self.zoom_strength=tk.StringVar(value="8")
        self.move_strength=tk.StringVar(value="12")
        self.preset=tk.StringVar(value="Cinematico")
        self.output_dir=tk.StringVar(value=str(Path.home()/"Videos"))
        self.filename=tk.StringVar(value="")
        self.prefix=tk.StringVar(value="")
        self.status=tk.StringVar(value="Pronto")
        self.progress=tk.DoubleVar(value=0)
        self.build_ui()

    def configure_styles(self):
        bg, card, field = "#0b1220", "#141e30", "#0d1728"
        text, muted, accent = "#e9eff9", "#a5b2c8", "#5eead4"
        self.root.configure(background=bg)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=card, foreground=text)
        style.configure("Page.TFrame", background=bg)
        style.configure("Card.TFrame", background=card)
        style.configure("Page.TLabel", background=bg, foreground=text)
        style.configure("Title.TLabel", background=bg, foreground=text, font=("Segoe UI", 23, "bold"))
        style.configure("Subtitle.TLabel", background=bg, foreground=muted)
        style.configure("Card.TLabel", background=card, foreground=text)
        style.configure("Hint.TLabel", background=card, foreground=muted, font=("Segoe UI", 9))
        style.configure("Version.TLabel", background="#183339", foreground=accent, padding=(12, 6))
        style.configure("Card.TLabelframe", background=card, bordercolor="#28354b", relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=card, foreground=text, font=("Segoe UI", 11, "bold"))
        style.configure("TEntry", fieldbackground=field, foreground=text, insertcolor=text,
                        bordercolor="#34445f", lightcolor=field, darkcolor=field, padding=6)
        style.configure("TCombobox", fieldbackground=field, background="#24334b", foreground=text,
                        arrowcolor=accent, bordercolor="#34445f", padding=6)
        style.map("TCombobox", fieldbackground=[("readonly", field)],
                  foreground=[("readonly", text)], selectbackground=[("readonly", field)],
                  selectforeground=[("readonly", text)])
        style.configure("TButton", background="#24334b", foreground=text, borderwidth=0,
                        padding=(13, 8), focusthickness=2, focuscolor=accent)
        style.map("TButton", background=[("pressed", "#344762"), ("active", "#30425e")])
        style.configure("Primary.TButton", background=accent, foreground="#072c29",
                        font=("Segoe UI", 11, "bold"), padding=(22, 10))
        style.map("Primary.TButton", background=[("pressed", "#2dd4bf"), ("active", "#99f6e4")])
        style.configure("Cancel.TButton", foreground="#fda4af")
        style.configure("TScrollbar", background="#34445f", troughcolor=field, borderwidth=0, arrowcolor=muted)
        style.configure("TProgressbar", background=accent, troughcolor=field, borderwidth=0, thickness=7)
        self.root.option_add("*TCombobox*Listbox.background", field)
        self.root.option_add("*TCombobox*Listbox.foreground", text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#234d57")
        self.root.option_add("*TCombobox*Listbox.selectForeground", text)

    def build_ui(self):
        self.configure_styles()
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        header=ttk.Frame(self.root,style="Page.TFrame",padding=(24,18,24,14))
        header.grid(row=0,column=0,sticky="ew")
        header.columnconfigure(0,weight=1)
        ttk.Label(header,text="Image Motion Tool",style="Title.TLabel").grid(row=0,column=0,sticky="w")
        ttk.Label(header,text="Trasforma le tue immagini in movimento.",style="Subtitle.TLabel").grid(row=1,column=0,sticky="w",pady=(3,0))
        ttk.Label(header,text=f"V{APP_VERSION}",style="Version.TLabel").grid(row=0,column=1,padx=(12,14))
        ttk.Button(header,text="Aggiornamenti",command=self.check_update).grid(row=0,column=2)

        content=ttk.Frame(self.root,style="Page.TFrame",padding=(24,0,24,0))
        content.grid(row=1,column=0,sticky="nsew")
        content.columnconfigure(0,weight=5,uniform="panels")
        content.columnconfigure(1,weight=6,uniform="panels")
        content.rowconfigure(0,weight=1)
        images=ttk.LabelFrame(content,text="  Immagini  ",style="Card.TLabelframe",padding=16)
        images.grid(row=0,column=0,sticky="nsew",padx=(0,16))
        images.columnconfigure(0,weight=1)
        images.rowconfigure(1,weight=1)
        ttk.Label(images,text="Aggiungi le immagini nell’ordine desiderato.",style="Hint.TLabel").grid(row=0,column=0,columnspan=2,sticky="w",pady=(0,12))
        self.listbox=tk.Listbox(images,height=10,background="#0d1728",foreground="#e9eff9",
                               selectbackground="#234d57",selectforeground="#ffffff",font=("Segoe UI",10),
                               highlightthickness=1,highlightbackground="#28354b",highlightcolor="#5eead4",
                               relief="flat",borderwidth=0,activestyle="none")
        self.listbox.grid(row=1,column=0,sticky="nsew")
        scroll=ttk.Scrollbar(images,orient="vertical",command=self.listbox.yview)
        scroll.grid(row=1,column=1,sticky="ns")
        self.listbox.configure(yscrollcommand=scroll.set)
        image_actions=ttk.Frame(images,style="Card.TFrame")
        image_actions.grid(row=2,column=0,columnspan=2,sticky="ew",pady=(12,0))
        ttk.Button(image_actions,text="+ Aggiungi immagini",command=self.add_images).pack(fill="x")
        edit=ttk.Frame(images,style="Card.TFrame")
        edit.grid(row=3,column=0,columnspan=2,sticky="ew",pady=(8,0))
        edit.columnconfigure((0,1),weight=1)
        ttk.Button(edit,text="Rimuovi selezione",command=self.remove_selected).grid(row=0,column=0,sticky="ew",padx=(0,4))
        ttk.Button(edit,text="Svuota elenco",command=self.clear_images).grid(row=0,column=1,sticky="ew",padx=(4,0))

        settings_view=ttk.Frame(content,style="Page.TFrame")
        settings_view.grid(row=0,column=1,sticky="nsew")
        settings_view.columnconfigure(0,weight=1)
        settings_view.rowconfigure(0,weight=1)
        self.settings_canvas=tk.Canvas(settings_view,background="#0b1220",highlightthickness=0,width=1,height=1)
        self.settings_canvas.grid(row=0,column=0,sticky="nsew")
        settings_scroll=ttk.Scrollbar(settings_view,orient="vertical",command=self.settings_canvas.yview)
        settings_scroll.grid(row=0,column=1,sticky="ns",padx=(8,0))
        self.settings_canvas.configure(yscrollcommand=settings_scroll.set)
        settings=ttk.Frame(self.settings_canvas,style="Page.TFrame")
        settings_window=self.settings_canvas.create_window((0,0),window=settings,anchor="nw")
        settings.bind("<Configure>",lambda _:self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all")))
        self.settings_canvas.bind("<Configure>",lambda event:self.settings_canvas.itemconfigure(settings_window,width=event.width))
        settings.columnconfigure(0,weight=1)
        movement=ttk.LabelFrame(settings,text="  Movimento e intensità  ",style="Card.TLabelframe",padding=(14,8))
        movement.grid(row=0,column=0,sticky="ew",pady=(0,12))
        movement.columnconfigure(1,weight=1)
        self.row(movement,"Effetto",ttk.Combobox(movement,textvariable=self.effect,values=EFFECTS,state="readonly",width=25),0)
        self.row(movement,"Preset",ttk.Combobox(movement,textvariable=self.preset,values=list(PRESETS),state="readonly"),1)
        self.row(movement,"Zoom (%)",ttk.Entry(movement,textvariable=self.zoom_strength),2)
        self.row(movement,"Pan / Tilt (%)",ttk.Entry(movement,textvariable=self.move_strength),3)
        video=ttk.LabelFrame(settings,text="  Video  ",style="Card.TLabelframe",padding=(14,8))
        video.grid(row=1,column=0,sticky="ew",pady=(0,12))
        video.columnconfigure(1,weight=1)
        self.row(video,"Durata (secondi)",ttk.Combobox(video,textvariable=self.duration,values=["7","10","15","30","60","120"],state="normal"),0)
        self.row(video,"Risoluzione",ttk.Combobox(video,textvariable=self.res,values=["1280x720","1920x1080","2560x1440","3840x2160"],state="readonly"),1)
        self.row(video,"FPS",ttk.Combobox(video,textvariable=self.fps,values=["24","25","30","50","60"],state="readonly"),2)
        ttk.Label(video,text="Durata libera, anche oltre 120 s. Anteprima: massimo 5 s.",style="Hint.TLabel").grid(row=3,column=0,columnspan=2,sticky="w",pady=(6,2))
        export=ttk.LabelFrame(settings,text="  Esportazione  ",style="Card.TLabelframe",padding=(14,8))
        export.grid(row=2,column=0,sticky="ew")
        export.columnconfigure(1,weight=1)
        self.row(export,"Cartella",ttk.Entry(export,textvariable=self.output_dir,width=20),0)
        ttk.Button(export,text="Sfoglia",command=self.choose_output).grid(row=0,column=2,padx=(8,0))
        self.row(export,"Nome singolo",ttk.Entry(export,textvariable=self.filename),1)
        self.row(export,"Prefisso batch",ttk.Entry(export,textvariable=self.prefix),2)

        footer=ttk.Frame(self.root,style="Page.TFrame",padding=(24,16,24,18))
        footer.grid(row=2,column=0,sticky="ew")
        footer.columnconfigure(0,weight=1)
        actions=ttk.Frame(footer,style="Page.TFrame")
        actions.grid(row=0,column=0,sticky="ew",pady=(0,12))
        ttk.Button(actions,text="Anteprima",command=self.preview).pack(side="left")
        ttk.Button(actions,text="Annulla",style="Cancel.TButton",command=self.cancel).pack(side="left",padx=8)
        ttk.Button(actions,text="Genera video",style="Primary.TButton",command=self.generate).pack(side="right")
        ttk.Progressbar(footer,variable=self.progress,maximum=100).grid(row=1,column=0,sticky="ew")
        ttk.Label(footer,textvariable=self.status,style="Subtitle.TLabel").grid(row=2,column=0,sticky="w",pady=(7,0))
        self.preset.trace_add("write",lambda *_:self.apply_preset())

    def row(self,p,label,widget,r):
        ttk.Label(p,text=label,style="Card.TLabel").grid(row=r,column=0,sticky="w",padx=(0,12),pady=4)
        widget.grid(row=r,column=1,sticky="ew",pady=4)
    def add_images(self):
        fs=filedialog.askopenfilenames(filetypes=[("Immagini","*.jpg *.jpeg *.png *.webp *.bmp")])
        for x in fs:
            if x not in self.images:self.images.append(x); self.listbox.insert("end",x)
    def remove_selected(self):
        for i in reversed(self.listbox.curselection()): self.listbox.delete(i); self.images.pop(i)
    def clear_images(self): self.images.clear(); self.listbox.delete(0,"end")
    def choose_output(self):
        d=filedialog.askdirectory(initialdir=self.output_dir.get())
        if d:self.output_dir.set(d)
    def apply_preset(self):
        v=PRESETS.get(self.preset.get())
        if v:self.zoom_strength.set(str(v[0])); self.move_strength.set(str(v[1]))
    @staticmethod
    def even(n): return max(2,int(n)//2*2)
    def factors(self,effect):
        if effect in ("Pan sinistra → destra","Pan destra → sinistra"): return 4,2
        if effect in ("Tilt basso → alto","Tilt alto → basso"): return 2,4
        return 4,4
    def filter(self,effect):
        w,h=map(int,self.res.get().split("x")); fps=int(self.fps.get()); frames=max(2,int(round(float(self.duration.get())*fps)))
        zs=max(.01,float(self.zoom_strength.get())/100); ms=max(.01,float(self.move_strength.get())/100)
        fx,fy=self.factors(effect); rw=self.even(w*fx); rh=self.even(h*fy)
        reserve=1+max(zs,ms)+.12; sw=self.even(rw*reserve); sh=self.even(rh*reserve)
        t=f"min(1,on/{frames-1})"; e=f"(({t})^3*(10-15*({t})+6*({t})^2))"
        if effect=="Zoom In": z=f"1+{zs}*{e}"
        elif effect=="Zoom Out": z=f"1+{zs}*(1-{e})"
        elif effect=="Pan + Zoom In": z=f"1+{zs*.75}*{e}"
        elif effect=="Pan + Zoom Out": z=f"1+{zs*.75}*(1-{e})"
        else: z=f"1+{max(.035,zs*.45)}"
        ax="max(0,iw-iw/zoom)"; ay="max(0,ih-ih/zoom)"
        px=f"min({ax},{rw*ms})"; py=f"min({ay},{rh*ms})"; cx=f"({ax})/2"; cy=f"({ay})/2"
        if effect in ("Pan sinistra → destra","Pan + Zoom In","Pan + Zoom Out"): x=f"{cx}-({px})/2+({px})*{e}"
        elif effect=="Pan destra → sinistra": x=f"{cx}+({px})/2-({px})*{e}"
        else:x=cx
        if effect=="Tilt basso → alto": y=f"{cy}+({py})/2-({py})*{e}"
        elif effect=="Tilt alto → basso": y=f"{cy}-({py})/2+({py})*{e}"
        else:y=cy
        if fx!=fy: pre=f"scale={sw}:{sh}:flags=fast_bilinear,"
        else: pre=f"scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos,crop={sw}:{sh},"
        return pre+f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={rw}x{rh}:fps={fps},scale={w}:{h}:flags=lanczos,setsar=1,format=yuv420p"
    def ffmpeg(self):
        base=Path(getattr(sys,"_MEIPASS",Path(__file__).parent))
        return str(base/"ffmpeg.exe")
    def outname(self,src,index,total):
        out=Path(self.output_dir.get()); out.mkdir(parents=True,exist_ok=True)
        if total==1 and self.filename.get().strip(): stem=self.filename.get().strip()
        else: stem=(self.prefix.get().strip()+"_" if self.prefix.get().strip() else "")+Path(src).stem
        p=out/(stem+".mp4"); n=2
        while p.exists():p=out/f"{stem}_{n}.mp4";n+=1
        return p
    def run_one(self,src,out,effect,preview=False):
        dur=min(float(self.duration.get()),5) if preview else float(self.duration.get())
        olddur=self.duration.get(); oldres=self.res.get(); oldfps=self.fps.get()
        if preview:self.duration.set(str(dur));self.res.set("1280x720");self.fps.set("24")
        vf=self.filter(effect)
        if preview:self.duration.set(olddur);self.res.set(oldres);self.fps.set(oldfps)
        cmd=[self.ffmpeg(),"-y","-loop","1","-i",src,"-vf",vf,"-t",str(dur),"-c:v","libx264","-preset","ultrafast" if preview else "veryfast","-crf","25" if preview else "17","-pix_fmt","yuv420p","-movflags","+faststart","-progress","pipe:1","-nostats",str(out)]
        log=tempfile.NamedTemporaryFile(delete=False,suffix=".log"); log.close()
        try:
            with open(log.name,"wb") as err:
                p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                self.current_process=p
                for line in p.stdout:
                    if self.cancel_event.is_set():
                        p.terminate(); break
                rc=p.wait()
            if rc and not self.cancel_event.is_set(): raise RuntimeError(Path(log.name).read_text(errors="ignore")[-4000:])
        finally:
            self.current_process=None
            try:os.unlink(log.name)
            except:pass
    def generate(self):
        if not self.images:return messagebox.showwarning("Attenzione","Aggiungi almeno un'immagine.")
        self.cancel_event.clear(); threading.Thread(target=self._generate_worker,daemon=True).start()
    def _generate_worker(self):
        start=time.time(); total=len(self.images)
        try:
            for i,src in enumerate(list(self.images),1):
                if self.cancel_event.is_set():break
                effect=random.choice(MANUAL_EFFECTS[:-2]) if self.effect.get()=="Automatico" else self.effect.get()
                out=self.outname(src,i,total); t0=time.time()
                self.root.after(0,lambda i=i,effect=effect:self.status.set(f"Video {i}/{total}: {effect}"))
                self.run_one(src,out,effect)
                elapsed=time.time()-t0
                self.root.after(0,lambda i=i,elapsed=elapsed:self.progress.set(i/total*100))
            elapsed=time.time()-start
            self.root.after(0,lambda:self.status.set("Annullato" if self.cancel_event.is_set() else f"Completato in {elapsed:.1f} s"))
        except Exception as ex:self.root.after(0,lambda ex=ex:messagebox.showerror("Errore",str(ex)))
    def preview(self):
        if not self.images:return messagebox.showwarning("Attenzione","Aggiungi almeno un'immagine.")
        def w():
            p=Path(tempfile.gettempdir())/"ImageMotionTool_preview.mp4"
            effect=random.choice(MANUAL_EFFECTS[:-2]) if self.effect.get()=="Automatico" else self.effect.get()
            try:self.run_one(self.images[0],p,effect,True); os.startfile(p)
            except Exception as ex:self.root.after(0,lambda:messagebox.showerror("Errore anteprima",str(ex)))
        threading.Thread(target=w,daemon=True).start()
    def cancel(self):
        self.cancel_event.set()
        if self.current_process:
            try:self.current_process.terminate()
            except:pass
    @staticmethod
    def _version_tuple(v):
        return tuple(int(x) for x in str(v).strip().lstrip("vV").split("."))
    def check_update(self):
        def worker():
            try:
                req=urllib.request.Request(VERSION_URL,headers={"User-Agent":f"ImageMotionTool/{APP_VERSION}"})
                import json
                with urllib.request.urlopen(req,timeout=15) as r:data=json.load(r)
                if self._version_tuple(data["version"])<=self._version_tuple(APP_VERSION):
                    self.root.after(0,lambda:messagebox.showinfo("Aggiornamenti","Hai già la versione più recente."));return
                url=data.get("download_url",""); notes=data.get("notes","")
                if not url:raise RuntimeError("URL di download non disponibile.")
                if not messagebox.askyesno("Aggiornamento disponibile",f"Disponibile V{data['version']}.\n\n{notes}\n\nScaricarla?"):return
                d=Path(tempfile.gettempdir())/"ImageMotionToolUpdater"; d.mkdir(exist_ok=True)
                new=d/"ImageMotionTool_NEW.exe"
                urllib.request.urlretrieve(url,new)
                if new.stat().st_size<1_000_000:raise RuntimeError("Il file scaricato non sembra un eseguibile valido.")
                self.root.after(0,lambda:self.apply_update(new))
            except Exception as ex:self.root.after(0,lambda:messagebox.showerror("Aggiornamenti",str(ex)))
        threading.Thread(target=worker,daemon=True).start()
    def apply_update(self,new):
        if not messagebox.askyesno("Aggiornamento pronto","Download completato. Chiudere il programma, sostituire la versione corrente e riavviare automaticamente?"):return
        old=Path(sys.executable).resolve()
        bat=Path(tempfile.gettempdir())/"ImageMotionTool_apply_update.bat"
        lines=["@echo off","setlocal","set /a tries=0",":retry","timeout /t 1 /nobreak >nul",f'move /y "{new}" "{old}" >nul 2>&1',"if %errorlevel%==0 goto done","set /a tries+=1","if %tries% LSS 30 goto retry","exit /b 1",":done",f'start "" "{old}"','del "%~f0"']
        bat.write_text("\r\n".join(lines)+"\r\n",encoding="utf-8",newline="")
        # A restarted onefile EXE needs its own extraction directory after we exit.
        env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1")
        subprocess.Popen(["cmd","/c","start","",str(bat)],env=env,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        self.root.after(150,self.root.destroy)

if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()
