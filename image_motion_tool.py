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

APP_VERSION = "5.14"
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
        root.geometry("900x720")
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

    def build_ui(self):
        f=ttk.Frame(self.root,padding=12); f.pack(fill="both",expand=True)
        self.listbox=tk.Listbox(f,height=10); self.listbox.pack(fill="both",expand=True)
        b=ttk.Frame(f); b.pack(fill="x",pady=6)
        ttk.Button(b,text="Aggiungi immagini",command=self.add_images).pack(side="left")
        ttk.Button(b,text="Rimuovi",command=self.remove_selected).pack(side="left",padx=4)
        ttk.Button(b,text="Svuota",command=self.clear_images).pack(side="left")
        opts=ttk.LabelFrame(f,text="Impostazioni",padding=8); opts.pack(fill="x",pady=6)
        self.row(opts,"Movimento",ttk.Combobox(opts,textvariable=self.effect,values=EFFECTS,state="readonly",width=28),0)
        self.row(opts,"Preset",ttk.Combobox(opts,textvariable=self.preset,values=list(PRESETS),state="readonly",width=20),1)
        self.row(opts,"Durata (s)",ttk.Entry(opts,textvariable=self.duration,width=10),2)
        self.row(opts,"Risoluzione",ttk.Combobox(opts,textvariable=self.res,values=["1280x720","1920x1080","2560x1440","3840x2160"],state="readonly",width=16),3)
        self.row(opts,"FPS",ttk.Combobox(opts,textvariable=self.fps,values=["24","25","30","50","60"],state="readonly",width=10),4)
        self.row(opts,"Zoom %",ttk.Entry(opts,textvariable=self.zoom_strength,width=10),5)
        self.row(opts,"Pan/Tilt %",ttk.Entry(opts,textvariable=self.move_strength,width=10),6)
        self.row(opts,"Cartella output",ttk.Entry(opts,textvariable=self.output_dir,width=55),7)
        ttk.Button(opts,text="Sfoglia",command=self.choose_output).grid(row=7,column=2,padx=4)
        self.row(opts,"Nome singolo",ttk.Entry(opts,textvariable=self.filename,width=30),8)
        self.row(opts,"Prefisso batch",ttk.Entry(opts,textvariable=self.prefix,width=30),9)
        actions=ttk.Frame(f); actions.pack(fill="x",pady=8)
        ttk.Button(actions,text="ANTEPRIMA",command=self.preview).pack(side="left")
        ttk.Button(actions,text="ANNULLA",command=self.cancel).pack(side="left",padx=5)
        ttk.Button(actions,text="GENERA",command=self.generate).pack(side="left")
        ttk.Button(actions,text="AGGIORNAMENTI",command=self.check_update).pack(side="right")
        ttk.Progressbar(f,variable=self.progress,maximum=100).pack(fill="x")
        ttk.Label(f,textvariable=self.status).pack(anchor="w",pady=5)
        self.preset.trace_add("write",lambda *_:self.apply_preset())
    def row(self,p,label,widget,r):
        ttk.Label(p,text=label).grid(row=r,column=0,sticky="w",pady=3); widget.grid(row=r,column=1,sticky="w",pady=3)
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
                p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
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
        bat.write_text(chr(13).join(lines)+chr(13),encoding="utf-8")
        subprocess.Popen(["cmd","/c","start","",str(bat)],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        self.root.after(150,self.root.destroy)

if __name__=="__main__":
    root=tk.Tk(); App(root); root.mainloop()
