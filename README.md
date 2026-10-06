# Image Motion Tool

Applicazione desktop Python/Tkinter per generare video da immagini tramite FFmpeg.

## Build automatica Windows

Il workflow `Build Windows executable` parte a ogni push su `main`, nelle pull
request verso `main`, al push di tag `v*` e manualmente da
**Actions → Build Windows executable → Run workflow**.
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

L'eseguibile generato non è firmato digitalmente.

## Pubblicare una versione

1. Aggiornare `APP_VERSION` nel sorgente e aggiungere le note in
   `release-notes/<versione>.md`, ad esempio `release-notes/5.15.md`.
2. Fare commit e push su `main`, poi creare e inviare il tag corrispondente:
   `git tag v5.15` e `git push origin v5.15`.
3. Il workflow compila e verifica l'eseguibile del tag, pubblica una GitHub Release
   con `ImageMotionTool.exe` e `FFmpeg-notices.zip`, poi aggiorna `version.json`
   su `main` con versione, note e URL della release pubblicata.

Il job di pubblicazione usa `GITHUB_TOKEN` con `contents: write`; gli altri job
hanno soltanto permessi di lettura. Eventuali protezioni di `main` devono consentire
il commit del manifest dal bot. Se il push del manifest è bloccato, la release
può esistere ma l'app non riceve ancora l'aggiornamento: il workflow segnala errore.
La pubblicazione può essere ripetuta senza sostituire gli asset di una release
già pubblicata. La versione del tag deve corrispondere ad `APP_VERSION` su `main`.

Per il tag `v5.15` viene eseguito anche un controllo Windows dell'aggiornamento:
parte l'EXE pubblico V5.14 e i metodi updater estratti dall'eseguibile originale
leggono il manifest pubblico, scaricano la V5.15 ed eseguono il vecchio BAT
senza modificarlo. In caso di errore viene provato anche il BAT CRLF con il
metodo estratto dall'EXE V5.15, verificando sostituzione e riavvio. Il test conferma
automaticamente le finestre di dialogo e simula la chiusura della vecchia GUI;
non automatizza i click nella V5.14 già installata sul PC dell'utente.
Per ripetere solo il controllo della compatibilità dopo una modifica alla pipeline,
un commit su `main` con `[verify-updater]` nel messaggio abilita nuovamente il job
dopo la build. I dettagli diagnostici sono disponibili nel riepilogo del job.

Il controllo ha confermato un difetto nella V5.14 pubblicata: il suo BAT con soli
CR non sostituisce l'EXE, pur riuscendo a scaricare la V5.15. Il controllo
comparativo dell'updater CRLF della V5.15 passa: sostituzione e riavvio verificati.
Il job di compatibilità segnala quindi errore; i job di build e pubblicazione
sono riusciti. Per passare dalla V5.14 serve una sola sostituzione manuale iniziale
dell'EXE con quello della V5.15. Il codice della vecchia copia già installata non
può essere corretto dal repository.

Per correggere le note di una release già pubblicata, aggiornare il relativo
file `release-notes/<versione>.md` e inviare su `main` un commit con
`[sync-release-notes]` nel messaggio. Il workflow sincronizza le note della release
e quelle di `version.json` senza sostituire gli asset pubblicati. Il tag e
`APP_VERSION` devono ancora corrispondere alla versione interessata.

Non modificare `version.json` prima della disponibilità dell'eseguibile: la V5.14
legge questo file per proporre e scaricare l'aggiornamento. Il nome dell'asset
rimane stabile (`ImageMotionTool.exe`), mentre la versione è interna all'app.
