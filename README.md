# Image Motion Tool

Applicazione desktop Python/Tkinter per generare video da immagini tramite FFmpeg.

## Build automatica Windows

Il workflow `Build Windows executable` parte a ogni push su `main`, nelle pull
request verso `main` e manualmente da **Actions → Build Windows executable → Run workflow**.
Usa Windows Server 2022 x64, Python 3.12 e PyInstaller con dipendenze fissate.

Al termine scaricare l'artifact **ImageMotionTool-Windows-x64** dalla pagina del run
e decomprimerlo. `ImageMotionTool.exe` contiene Python, Tkinter e `ffmpeg.exe`:
non richiede installazioni di Python o FFmpeg sul PC Windows x64 di destinazione.
La modalità `onefile` estrae i componenti in una cartella temporanea all'avvio.
Il codice dell'applicazione individua già FFmpeg tramite `sys._MEIPASS`.

La CI avvia l'eseguibile da una cartella vuota, verifica la creazione della finestra
Tkinter e usa il FFmpeg estratto per codificare un breve MP4 con `libx264`.
Questo controllo non sostituisce una prova manuale degli effetti di rendering.

## Riprodurre la build su Windows

Da PowerShell, nella radice del repository, con Python 3.12 x64 installato:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe scripts/prepare_ffmpeg.py
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name ImageMotionTool --add-binary "ffmpeg.exe;." image_motion_tool.py
.\.venv\Scripts\python.exe scripts/smoke_windows.py
```

Output: `dist/ImageMotionTool.exe`. Per avviare direttamente il sorgente usare
`.\.venv\Scripts\python.exe image_motion_tool.py` dopo il download di FFmpeg.

## FFmpeg e distribuzione

`scripts/prepare_ffmpeg.py` scarica la build statica Windows x64 GPL di
[BtbN/FFmpeg-Builds](https://github.com/BtbN/FFmpeg-Builds) e controlla l'archivio
contro il checksum SHA-256 pubblicato nella stessa release. La release `latest`
è aggiornata upstream: FFmpeg può cambiare tra due build. Una mancata corrispondenza
del checksum interrompe la build. URL e hash effettivi sono salvati in
`dist/FFmpeg-notices/BUILD-SOURCE.txt`, insieme alla licenza upstream
e al README upstream, quando presente nell'archivio.

Conservare gli avvisi e rispettare gli obblighi GPL e di disponibilità dei sorgenti
quando si redistribuisce FFmpeg, anche se incluso nell'eseguibile.

Il workflow produce artifact, non pubblica GitHub Releases e non modifica
`version.json`: l'URL dell'aggiornamento resta quello esistente. L'eseguibile
generato non è firmato digitalmente.
