# Sprite Animation Studio — Roadmap

**Stato attuale: v0.8.5** (26 settembre 2026)

Documento vivo. Le priorità sono guidate dall'uso reale del programma
sulla Doom Total Conversion in sviluppo parallelo: ogni feature di SAS
nasce da un'esigenza concreta del progetto.

---

## v0.8.3 — Rilasciata (20 settembre 2026)

Ultima release pubblica prima del ciclo di consolidamento.

---

## v0.8.4 — Rilasciata (25 settembre 2026)

**Obiettivo**: consolidamento sicurezza dati. Nessuna feature nuova
visibile, ma il programma smette di perdere lavoro silenziosamente.

- **Recupero da file corrotto** (C-09): un `.sas` illeggibile viene
  rinominato in `.sas.corrupt`, l'utente sceglie se caricare il backup,
  il ripristino è atomico.
- **Backup permanente su sovrascrittura** (C-08a/C-08a.1): quando si
  crea un nuovo progetto sopra uno esistente, il vecchio viene copiato
  con timestamp e mai più toccato.
- **Punto unico di caricamento animazione** (C-01 minima): durata,
  clona/specchia, elimina agiscono sempre sull'animazione mostrata.
- **Player non più bloccato** dopo svuotamento timeline (G-11).
- **Fix durata frame**: valore non si applica più al frame sbagliato
  quando si cambia contesto.
- **Spritesheet refactor** (C-11): la finestra non tiene più il
  progetto, usa callback. Niente più modifiche su progetti fantasma.
- **Rimozione scorciatoie** dalla lista Impostazioni (M3).
- **Prima suite pytest**: 102 test, 95 passanti, 7 xfail su bug noti.

Satellite: **grab_tool** — lettura/scrittura del chunk `grAb` nei PNG,
validato in SLADE 3. Integrabile in SAS a partire dalla 0.8.8.

---

## v0.8.5 — Rilasciata (26 settembre 2026)

**Obiettivo**: chiudere il ciclo di consolidamento e aprire l'editor
di esportazione.

- **Editor di esportazione** (G14): dialog a due righe con lista
  animazioni, timeline a blocchi, anteprima animata, lucchetti per
  blocco, scaling proporzionale.
- **Rotazione a due timeline indipendenti**: animazione che scorre,
  angoli che girano, durata X scelta dall'utente.
- **Export da libreria padre**: si può esportare spuntando una libreria
  intera, non solo un'animazione figlia.
- **Shortcut Ctrl+E** per aprire l'esportatore.
- **Fix C-04**: bridge Blender di nuovo importabile (bug presente dal
  primo commit).
- **Fix `_scan_folder`**: prefisso case-insensitive, angoli 0-8,
  mirror letter, no doppio jpeg.
- **Codici libreria ASCII-safe**: accenti ridotti con NFKD.
- **Manifest con duration non numerica** non crasha più.
- **Cleanup pyflakes**: zero warning residui.
- **Licenza MIT**.

---

## v0.8.6 — Inspector e timeline

**Obiettivo**: la prima vera aggiunta di UI dopo il consolidamento.

- **Inspector**: pannello laterale tra librerie e viewer che mostra le
  proprietà dell'elemento selezionato (libreria, animazione, frame).
  Scrive sui campi che già esistono nel modello (nome, codice, durata,
  loop, anchor).
- **Timeline refactor** (C-01 completo): TimelineModel diventa vista
  sull'AnimationData del progetto. Fine della doppia fonte di verità.
- **Riordino frame** nella timeline (drag & drop, regressione dalla
  0.7.6).
- **Redesign finestra Nuova animazione**: dialog unico con array visivo
  dei frame, anteprima, riordino.
- **Fix `TICK_MS`**: da 28 a 28.571 ms, con migrazione dei progetti
  esistenti.
- **C-08b**: backup configurabile (permanente / sessione / disattivato,
  formato timestamp personalizzabile).
- **Fix Invio** nello spinbox durata.

---

## v0.8.7 — Export spritesheet e multi-libreria

- **Finestra export spritesheet dedicata**, separata da quella di
  import.
- **Multi-libreria sprite**: l'albero a sinistra dell'esportatore
  diventa libreria → animazioni, con checkbox di libreria padre.
- **Import APNG** (chiude il cerchio con l'export già esistente).
- **Shortcut personalizzabili** in Impostazioni, con test dei conflitti.

---

## v0.8.8 — Export `.pk3` e `grAb`

**Obiettivo**: SAS produce un artefatto caricabile in GZDoom.

- **Export `.pk3`** con struttura corretta per SLADE/UDB.
- **Integrazione `grab_tool`**: al momento dell'export, scrive il chunk
  `grAb` nei PNG con l'offset coerente su tutti gli angoli.
- **Chunk metadati SAS** dentro i PNG (F2 dei documenti formati).
- **Schema unico naming Doom** (parser centralizzato).

---

## v0.8.9 — Import e modifica `.pk3`

- **Aprire `.pk3` esistente**, vedere il contenuto in albero.
- **Audio e codice ZScript** visibili e modificabili.
- **Mappe** importate come file opachi (non interpretate).
- **`anchor`** integrato: CLI + webapp Streamlit.

---

## v0.9.0 — Pipeline Doom completa

**Obiettivo**: fare una TC senza uscire da SAS, tranne le mappe.

- **Template ZScript**: generatore da configurazione JSON (GameBox
  embrionale).
- **Preview embedded**: mini-mappa 2D con telemetria via log GZDoom.
- **Pannello Inspector esteso** ad audio, codice, entità.
- **Lock ZScript/JSON** per progetto (modalità formato).

---

## v1.0.0 — Release stabile

**Obiettivo**: SAS è pronto per essere consigliato a chiunque.


- **TC Backrooms** come campo di prova della pipeline completa.


### Architettura
- Refactor `ui_main.py` in moduli (`viewer_widget`, `timeline_widget`,
  `library_tree`, `bridge_controller`).
- `MainWindow` diventa thin controller.

### Robustezza
- Test per ogni modulo refactorato.
- Fallback puliti su file mancanti/corrotti.
- Gestione multi-monitor e scaling.

### Internazionalizzazione
- Sistema `tr()` con `it.json` / `en.json`.
- Migrazione progressiva di tutta la UI.
- Regola: ogni nuova stringa passa da `tr()`.

### Distribuzione
- Workflow GitHub Actions per build automatica.
- Release firmata.

### Documentazione
- Manuale utente navigabile.
- Tutorial pipeline Blender → SAS → SLADE/UDB.
- Wiki del repository.

---

## Satelliti Yagor Studio

Progetti paralleli a SAS, indipendenti, in tempi morti. Nati per
risolvere problemi reali del progetto.

- **`anchor`** — CLI + webapp per il chunk `grAb`. Integrabile in SAS
  dalla 0.8.8. Potenziale rilascio pubblico indipendente (webapp
  Streamlit).
- **`lex`** — tool i18n git-native con repo pubblica delle traduzioni.
  Da usare per SAS e per altri progetti Python.
- **`eco-mem`** — gestione memoria di Yagor Studio (task, bivii,
  decisioni, sessioni). Strumento interno.
- **`mini_doom`** — esperimento: motore 2.5D in Tkinter. Prototipo per
  la GameBox.
- **GameBox** — visione a lungo termine: SAS diventa strumento unico
  per creare TC in GZDoom con dipendenza minima da altri software.

---

## Backlog

### Editor
- Manipolazione sprite (nudge, resize, chroma key, ritaglio bordi)
- Copy / paste frame tra animazioni
- Multi-selezione con operazioni batch
- Ricerca e filtri nell'albero
- Confronto side-by-side di due angoli
- Sistema temi con file JSON esterni

### Export & integrazione
- Bundle `.sas` come archivio autonomo
- PNG di progetto condivisibile
- JSON di definizione animazioni per motori custom

### Distribuzione
- Sistema di plugin per importatori/esportatori

---

*Ultimo aggiornamento: 26 settembre 2026*