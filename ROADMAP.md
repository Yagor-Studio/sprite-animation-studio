
---

## ROADMAP.md (aggiornata)

```markdown
# Sprite Animation Studio — Roadmap

**Stato attuale: v0.8.3** (20 settembre 2026)

Documento vivo. Le priorità sono guidate dall'uso reale del programma
sulla Doom Total Conversion in sviluppo parallelo: ogni feature di SAS
nasce da un'esigenza concreta del progetto.

---

## v0.8.4 — Rifinitura editor e gestione file

**Obiettivo**: chiudere i problemi quotidiani dell'editor e introdurre
il cestino/file orfani.

- **G1/G2/G3 — Refactor dispatcher scorciatoie**:
  - Dispatcher context-aware: niente attivazione mentre si scrive
  - Handler unico referenziato, dismissione corretta alla chiusura progetto
  - Rimozione completa della finestra precedente
- **G9 — Codici libreria/animazione univoci**: verifica all'atto della
  creazione, proposta automatica di alternativa (terza lettera o
  incremento), possibilità di modificarli a mano
- **Cestino file orfani** (`_trash/` accanto agli sprite):
  - Manifest JSON con mappa file → origine
  - Menu `File → Pulisci file orfani / Svuota cestino`
  - Ripristino dal cestino
  - Impostazioni → sezione "Pulizia" con trigger automatico e statistiche

---

## v0.8.5 — Sistema Schemi Libreria (parte 1)

**Obiettivo**: il motore del parsing dinamico.

- Modulo `library_schemas.py` con dataclass `LibrarySchema`
- Template a segnaposto: `[SPRITE]`, `[ANIM]`, `[LETTER]`, `[ANGLE]`, `[N]`
  con separatori liberi
- Parser regex generato al volo dal template
- Modulo `naming.py`: punto unico di lettura/scrittura dei nomi
- Sostituzione dei 4 punti di parsing sparsi (`ui_profile`, `ui_main`,
  `ui_spritesheet`, `blender_import`)
- Fallback automatico a `8 CAM DOOM` per `.sas` pre-0.8.5

---

## v0.8.6 — Sistema Schemi Libreria (parte 2)

**Obiettivo**: UI per gli schemi e integrazione.

- Storage globale `~/.sprite_studio/schemas.json`
- Editor schemi: crea, duplica, modifica, esporta, importa
- **Assistente "traduci cartella"**: analizza una cartella, propone
  2–3 template compatibili
- Dropdown "Schema libreria" in `CreateProfileDialog`
- Selettore angoli dinamico: pallini disegnati solo per gli angoli dello schema
- Etichette angolo personalizzabili dallo schema
- Blender Addon: tendina "Schema libreria" nel pannello SAS

---

## v0.8.7 — Export + presentazione

**Obiettivo**: chiudere la 0.8.x con contenuto visibile.

- **G14** — Collegare all'interfaccia l'export **APNG / GIF** già scritto
  in `sprite_utils.py`
- **Test critici** (blocco 4 della checklist 1.0):
  - `get_initials`, parser nomi, round-trip `ProjectData`,
    manifest → modelli, timeline model, history undo
  - Framework: pytest
- **R3** — README e struttura allineati alla versione reale
- **R5** — Licenza (MIT o CC BY-NC-SA, da decidere)
- **R8** — Versione derivata dal tag Git al build

---

## v0.9.0 — Pipeline Doom

**Obiettivo**: export `.pk3` e integrazione con SLADE / UDB.
È il traguardo che rende SAS utilizzabile per un progetto Doom completo.

- Export `.pk3` con struttura `sprites/DGWA A1.png` corretta
- Export `.wad` (bonus)
- Preset di export salvabili
- Mappatura completa nomenclatura SAS → nomenclatura Doom
- Template `DECORATE` / `ZSCRIPT` vuoto generato con l'export
- Test end-to-end: SAS → SLADE → UDB
- Documentazione della pipeline

---

## v0.9.x — Bridge Blender avanzato

- **Badge Live informativo** nel viewer
- **Checkbox "Sincronizza lettore"** per seguire i frame live
- **Menu Bridge separato** dalla sezione Strumenti
- **Animation Library panel in Blender** per gestire `bpy.data.actions`
- **Bridge bidirezionale**: `command.json` per pilotare Blender da SAS
- **Lock camere con `Child Of` constraint** (rimandato da 0.8.3)

---

## v1.0.0 — Release stabile

**Obiettivo**: SAS è pronto per essere consigliato a chiunque, non solo
a chi sa arrangiarsi.

### Test e refactor
- Refactor `ui_main.py` in moduli:
  - `viewer_widget.py`, `timeline_widget.py`, `library_tree.py`,
    `bridge_controller.py`
  - `MainWindow` diventa thin controller
- Refactor `ui_profile.py`, `ui_spritesheet.py` sul parser centralizzato

### Robustezza
- Tutti gli `except:` nudi sostituiti da `except Exception:`
- Fallback puliti su file mancanti/corrotti
- Gestione multi-monitor e scaling

### Distribuzione
- Release GitHub automatizzata via workflow
- Installer MSI (opzionale)
- Portable mode (opzionale)

### Documentazione
- Manuale utente HTML navigabile
- Tutorial: pipeline Blender → SAS → Slade/UDB
- Wiki del repository

---

## Backlog

### Editor
- Manipolazione sprite (nudge, resize, chroma key, ritaglio bordi)
- Copy / Paste frame tra animazioni
- Riordino drag & drop nella timeline
- Multi-selezione con operazioni batch
- Ricerca e filtri nell'albero
- Vista spritesheet integrata (griglia frame × angoli)
- Confronto side-by-side di due angoli
- Sistema temi con file JSON esterni
- Icone SVG al posto delle emoji

### Export & integrazione
- Import da APNG con durate
- Import da manifest esterni
- Chunk PNG `grAb` (offset Doom) e metadati SAS nei PNG
- Bundle `.sas` come archivio autonomo
- JSON di definizione animazioni per motori custom

### Distribuzione
- Sistema di plugin per importatori/esportatori
- Internazionalizzazione IT / EN

---

*Ultimo aggiornamento: 20 settembre 2026*