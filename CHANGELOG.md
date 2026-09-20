# Changelog

Tutte le modifiche notevoli di **Sprite Animation Studio**.
Formato basato su [Keep a Changelog](https://keepachangelog.com/it/1.1.0/),
versionamento [SemVer](https://semver.org/lang/it/).

---

## Blender Addon — `sas_sprite_renderer.py`

### [0.4.3] — 2026-09-19

- **Fix**: le telecamere non vengono più ricreate ad ogni "Render All",
  risolvendo il disallineamento dell'inquadratura quando il playhead
  era spostato rispetto al primo frame.
- **Fix**: "Render All" ferma automaticamente la Live Mode se attiva,
  evitando che i PNG batch vengano sovrascritti da render live in
  bassa qualità.
- **Nuovo**: opzione "Insegui target durante il render" (default OFF).

---

## [0.8.3] — 2026-09-20

### Diagnostica
- Sistema di **logging centralizzato** con rotazione automatica
  (3 file da 1 MB in `~/.sprite_studio/sprite_studio.log`).
- **Crash handler globale**: cattura eccezioni anche prima dell'avvio
  di Tkinter e scrive il traceback completo nel log.
- Nuova voce **Aiuto → Apri cartella log**.

### Correttezza
- **Dispatchere scorciatoie**: sostituito `bind_all` con `bind` sul root
  e referenziato il `funcid` per `unbind` corretto. Niente più handler
  orfani quando si cambia progetto.
- **G12** — Spritesheet: apertura singola istanza. Se la finestra è
  già aperta, viene portata in primo piano invece di crearne una seconda.
- **G13** — Validazione lettere oltre la Z. Se `lettera iniziale + numero frame`
  supera Z, l'export viene bloccato con messaggio contestuale che indica
  il massimo consentito.
- **M3** — Escape annulla la cattura delle scorciatoie. Aggiunto pulsante
  "Annulla" esplicito. Risolto anche il race tra `_confirm` e `_cancel`.
- **M8** — Chiusura esplicita dei file immagine in `_create_mirrored_png`
  e `_build_background`, evitando "file in uso" su Windows.
- **M11** — Encoding UTF-8 esplicito in `settings.py` e `project_manager.py`.
- **M12** — Validazione dei settings al caricamento: valori fuori range
  vengono clampati, evitando loop di autosave.
- **M4** — Rimossa voce duplicata nel dizionario scorciatoie.
- **M7** — Rimossa `_set_controls_state`, inefficace perché scorreva solo
  i figli diretti. L'overlay nero copre e intercetta già i click.

### Distribuzione
- **R4** — Icona dell'applicazione nell'`.exe`.

### Rimosso
- Codice morto relativo al vecchio sistema di disabilitazione controlli.

---

## [0.8.2] — 2026-09-19

### Sicurezza dati
- **C1** — Creare un progetto con un nome già esistente non lo sovrascrive
  più silenziosamente. Dialog a 3 scelte: *Apri il progetto esistente /
  Crea nuovo (sovrascrive) / Annulla*. In caso di sovrascrittura, il `.sas`
  precedente è conservato come `.bak`.
- **C2** — Salvataggio atomico: scrittura su file temporaneo, sostituzione
  solo a scrittura completata, copia di sicurezza `.bak`. Se il `.sas`
  principale è illeggibile, si tenta il ripristino dal `.bak`.
- **C3** — Le modifiche alla durata dei frame entrano nello storico undo
  e marcano lo stato "modificato".

### Correttezza
- **G4** — La riproduzione usa la durata del frame mostrato, non di quello
  successivo.
- **G5** — Il campo durata agisce **solo sul frame selezionato**. Nuovo
  pulsante "→ tutti" con conferma esplicita.
- **G8** — "Salva con nome" azzera lo stato modificato e registra il
  progetto nei recenti.
- **G10** — "Aggiorna libreria" usa la cartella associata al profilo,
  non l'ultima cartella aperta in Risorse.

### UI / UX
- **R9** — DPI awareness: interfaccia nitida su schermi con scaling al
  125% o 150%.
- **R9b** — Pulsante di chiusura della schermata iniziale ancorato all'angolo.
- **G7** — Timeline con scrollbar orizzontale, rotellina del mouse e
  auto-scroll.
- **M1** — Lo Stop riporta l'indicatore al primo frame.
- **M2** — Durante la riproduzione il rettangolo rosso segue il frame
  corrente nella timeline.

---

## [0.8.0] — 2026-09-17

### Aggiunto
- **Undo / Redo** con profondità configurabile (default 10).
  Scorciatoie `Ctrl+Z` e `Ctrl+Shift+Z`. Preserva espansione dei profili
  e selezione nell'albero.
- **Dirty flag**: asterisco nel titolo quando ci sono modifiche non salvate.
  Prompt di chiusura con 3 opzioni.
- **Autosave condizionale**: salva solo se ci sono modifiche pendenti.
- **Indicatore di salvataggio**: 💾 salvato / auto tra Ns / ⚠ salvataggio fallito.
- **Blender Addon** incluso nel repository.
- **Bridge Blender**: menu Strumenti → Blender Bridge.

### Corretto
- "Aggiorna libreria" non svuota più silenziosamente: chiede conferma
  se la scansione è vuota o riduce i frame di oltre il 50%.
- "Salvato" riflette l'esito reale del salvataggio.
- Bridge fermato correttamente alla chiusura del progetto.
- "Salva con nome" gestisce i percorsi relativi con dialog a 3 scelte.
- Ctrl+S e scorciatoie usano un dispatcher unificato.
- Timer autosave aggiornato a caldo dalle Impostazioni.
- Risoluzione minima finestra a 900×600.

### Rimosso
- Print di debug e codice morto.

---

## [0.7.3] — 2026-09-12

Release iniziale pubblica su GitHub / itch.io. Formato `.sas`, lettore
2.5D con angoli 1–8, timeline, clona-specchia, importazione spritesheet,
esportazione con nomenclatura Doom, selettore angoli a cerchio, sfondi
viewer.