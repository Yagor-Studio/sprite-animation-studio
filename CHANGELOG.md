## v0.8.0 — Stabilità e gestione modifiche

### Aggiunto
- **Undo/Redo** (Ctrl+Z / Ctrl+Shift+Z) con profondità configurabile (default 10)
- **Dirty flag**: il titolo mostra un `*` quando ci sono modifiche non salvate
- **Prompt di chiusura** se ci sono modifiche non salvate (Salva / Non salvare / Annulla)
- **Autosave condizionale**: salva solo se ci sono modifiche pendenti
- **Indicatore di salvataggio** in basso a destra (💾 salvato, auto tra Ns, ⚠ fallito)
- Menu **File → Pulisci file orfani / Svuota cestino** (predisposizione, funzionalità attiva dalla 0.8.1)
- Impostazioni → Editor: profondità Undo configurabile

### Corretto
- **"Aggiorna libreria"** non svuota più silenziosamente: chiede conferma se la scansione è vuota o riduce i frame di oltre il 50%
- **Salvataggio fallito** ora segnalato visivamente (persistente) invece di dire "salvato"
- **Bridge Blender** fermato correttamente alla chiusura del progetto
- **"Salva con nome"** in una cartella diversa gestisce i percorsi relativi (Converti in assoluti / Copia / Annulla)
- **Ctrl+S** e scorciatoie ora usano un dispatcher unificato (fix di bug con Num Lock e tasti modificatori)
- **Timer autosave** aggiornato a caldo dalle Impostazioni (non serve più riavviare)
- **Undo/Redo** preserva l'espansione dei profili e la selezione corrente nell'albero
- Risoluzione minima finestra abbassata a 900×600

### Rimosso
- Print di debug in `timeline.py`, `ui_profile.py`, `ui_settings.py`, `ui_main.py`
- Codice morto (`load_frames`, `_go_to_welcome`)
- Variabili inutilizzate in `__init__`
### BLENDER ADDON sas_sprite_renderer.py 0.4.3 
- Risolto conflitto di movimento tra telecamere e bersaglio in caso di animazione e visualizzazione  da un frame differente dal primo in timeline. (Nella 0.4.2 è necessario registrare i keyframe della telecamera in Blender o premere "render all" visualizzando sempre il primo keyframe della timeline in Blender)
### Note
- Il comportamento di "eliminazione frame" resta non distruttivo: rimuove dal progetto, i PNG restano su disco. La pulizia file orfani arriverà in 0.8.1.
- Sto lavorando per inserire un tasto che renda tutte le telecamere un unico blocco per facilitarne il movimento fuori dai parametri presenti nella versione 0.4.4 di sas_sprite_renderer.py 