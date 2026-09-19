# Sprite Animation Studio — Roadmap

**Stato attuale: v0.8.0** (17 settembre 2026)

Documento vivo. Le priorità possono cambiare in base al feedback della
community e agli obiettivi del progetto (Doom Total Conversion in sviluppo
parallelo). Ogni versione è pensata per essere rilasciabile in autonomia.

---

## v0.8.1 — Gestione file

**Obiettivo**: chiudere la questione "eliminazione e file orfani" in modo
non distruttivo e reversibile.

- Cestino file orfani (`_trash/` accanto agli sprite)
- Manifest JSON con mappa file → origine, per il ripristino
- Menu `File → Pulisci file orfani…`
- Menu `File → Svuota cestino…`
- Ripristino file dal cestino (riporta i file alle posizioni originali)
- Impostazioni → Sezione "Pulizia":
  - Checkbox "Pulizia automatica"
  - Tendina trigger: *a ogni avvio* / *a ogni aggiornamento libreria* / *a ogni scrittura di nuovo frame*
  - Contatore: numero file, dimensione totale, data ultima pulizia
- Notifica non invasiva a fine pulizia

---

## v0.8.2 — Rifinitura editor

**Obiettivo**: limare i piccoli attriti quotidiani dell'editor.

- **Eliminazione granulare**: menu/sezione dedicata che permette di cancellare in modo selettivo:
  - Libreria intera
  - Animazione intera
  - Tutti i frame di un certo angolo
  - Solo i frame selezionati di un certo angolo
  - Tutti i frame di una certa lettera (es. tutte le A)
  - Solo i frame di una certa lettera, selezionati
- **UI compatta + geometria ricordata**:
  - Salvataggio geometria finestra in `CONFIG_DIR/window.json`
  - Ripristino all'avvio, con fallback se il monitor è cambiato
  - Sidebar collassabile
  - Timeline collassabile
  - Pulsante "Reset layout" in Strumenti
- **Scorciatoie duplicate**: controllo al salvataggio delle Impostazioni,
  avviso se due azioni puntano alla stessa combinazione
- **Report errori**: dialog a fine operazioni batch con lista dei file
  che hanno fallito e motivo

---

## v0.9.0 — Sistema Schemi Libreria

**Obiettivo**: trasformare SAS da "programma Doom" a "programma per sprite".
È il pezzo architetturale più grosso del progetto. Richiede attenzione
e tempo, ma è la feature che apre SAS a community diverse da quella Doom.

### Concetto
Uno **schema libreria** è un pacchetto riutilizzabile che risponde a tre domande:
1. Com'è fatto il nome dei file? (template con segnaposto)
2. Quante telecamere/angoli ha questa libreria?
3. Come si comportano gli angoli? (rotazioni, HUD, direzioni, singolo)

### Cosa comprende
- Modulo `library_schemas.py` con dataclass `LibrarySchema`
- Template di parsing a segnaposto: `[SPRITE]`, `[ANIM]`, `[LETTER]`, `[ANGLE]`, `[N]`, con separatori liberi
- Parser regex generato al volo dal template
- Schema predefiniti:
  - `8 CAM DOOM` (con angolo 0 HUD)
  - `8 CAM Standard` (senza angolo 0)
  - `4 CAM Base` (1–4)
  - `1 CAM Static`
  - `Pixel Art Custom` (da definire)
- Storage globale: `~/.sprite_studio/schemas.json` (condivisibile tra progetti)
- Editor schemi:
  - Creazione da zero
  - Duplicazione di uno esistente
  - Modifica con avviso se N profili lo usano
  - Esporta / Importa schema (JSON singolo)
- **Assistente "traduci cartella"**: apri una cartella, il sistema analizza i nomi, propone 2–3 template compatibili, tu scegli
- Integrazione in `CreateProfileDialog`: dropdown "Schema libreria"
- Selettore angoli dinamico: si disegnano solo gli angoli dello schema
- Etichette angolo personalizzabili dallo schema
- Blender Addon: tendina "Schema libreria" per determinare quante camere renderizzare
- Fallback automatico a `8 CAM DOOM` per `.sas` creati con versioni precedenti

### Dipendenze
- `models.py`: `ProfileData` guadagna `schema_name`
- `settings.py`: sezione `schemas` per la lista
- `ui_profile.py`, `ui_spritesheet.py`, `ui_main.py`: usano il parser centralizzato
- `blender_import.py`: accetta manifest con schema

### Rischi
- Parser troppo permissivo → accetta file che non dovrebbero passare
- Parser troppo rigido → utenti frustrati
- Migrazione `.sas` vecchi → deve essere trasparente e senza perdita

---

## v0.9.x — Blender & Live

**Obiettivo**: rendere il Bridge Blender un'esperienza fluida e bidirezionale.

- **Badge Live informativo** nel viewer:
  - `● live: AX` (allineato, verde)
  - `● live: BX (stai guardando AX)` (disallineato, arancione)
  - `● live off` (grigio)
- **Checkbox "Sincronizza lettore"**: se attiva, al ricevimento di un aggiornamento
  live salta automaticamente al frame corrispondente
- **Menu Bridge separato** dalla sezione Strumenti (prepara il terreno a bridge futuri:
  Krita, Aseprite, Pixelorama)
- **Icona di stato bridge** nella barra in alto, colorata in base allo stato
- **Animation Library panel in Blender**:
  - Lista delle `bpy.data.actions` dell'armatura selezionata
  - Operatori: assegna action attiva, crea nuova, duplica, rinomina, elimina
  - Nome action → nome animazione → codice SAS automatico
  - Protezione doppia conferma per eliminazioni con users > 0
- **Bridge bidirezionale** (da progettare):
  - `command.json` pollato da Blender
  - SAS → Blender: "apri progetto X", "vai al frame Y", "renderizza frame corrente"
  - Gestione priorità e concorrenza comandi

---

## v1.0.0 — Release stabile

**Obiettivo**: base solida, pronta per essere consigliata a chiunque.
Prima della 1.0, i seguenti punti vanno chiusi per considerare il
programma "affidabile al 100%".

### Test e refactor
- **Test critici** (prima del refactor):
  - `get_initials` — 1, 2, 3+ parole, vuoto, accenti, caratteri speciali
  - `manifest_to_models` — manifest valido, incompleto, malformato
  - `apply_manifest_to_project` — full vs live, merge, conflitti
  - Round-trip `ProjectData.to_dict / from_dict`
  - Parser naming — casi validi e casi limite
  - `_resolve_file_field` — path assoluto, relativo, mancante
  - Framework: **pytest**
- **Refactor `ui_main.py`**: estrazione in moduli
  - `viewer_widget.py` (canvas, zoom, sfondi)
  - `timeline_widget.py` (timeline, player)
  - `library_tree.py` (albero, risorse)
  - `bridge_controller.py` (logica bridge)
  - `MainWindow` diventa thin controller
- **Refactor `ui_profile.py`, `ui_spritesheet.py`**: allineamento al parser centralizzato

### Robustezza
- Sistema di logging centralizzato con livelli (DEBUG/INFO/WARNING/ERROR)
- Pulsante "Apri cartella log" in Aiuto
- Gestione errori: tutti gli `except:` nudi sostituiti da `except Exception:`
- Fallback puliti in caso di file mancanti/corrotti

### Distribuzione
- **Release GitHub automatizzata**: workflow pubblica anche su GitHub Releases
  con `.exe` allegato (oggi solo itch.io via butler)
- **Versione da tag Git**: `APP_VERSION` deriva dal tag di release, non più
  costante manuale
- **Sincronizzazione tag/versione**: check nel workflow, blocca se mismatch

### Documentazione
- `README.md` completo con screenshot, workflow d'uso, esempi
- `CHANGELOG.md` retroattivo fino a 0.7.x
- `LICENSE` (MIT o CC BY-NC-SA, da decidere)
- Manuale utente HTML navigabile
- Tutorial brevi per i workflow comuni:
  - Importare sprite da Blender
  - Importare spritesheet e convertirli in libreria
  - Esportare per Slade / UDB

---

## Backlog (senza versione assegnata)

### Editor
- **Copy / Paste frame**: copiare un frame (con tutti gli angoli) e incollarlo altrove, anche tra animazioni diverse
- **Riordino drag & drop nella timeline**: trascinare thumbnail per riordinare
- **Multi-selezione nell'albero**: operazioni batch (rinomina, sposta, esporta)
- **Ricerca e filtri**: filtro nell'albero per nome/codice, highlight dei frame mancanti
- **Vista spritesheet integrata**: griglia frame × angoli alternativa alla timeline lineare
- **Confronto side-by-side**: due angoli affiancati nel viewer
- **Sistema shortcut**: supporto a combinazioni triple (es. Ctrl+Alt+Shift+K), preset caricabili

### Export & integrazione
- **Export WAD / PK3**: pacchetto con struttura cartelle corretta per Slade
- **Preset di export salvabili**: risoluzione, formato, naming, cartella
- **JSON di definizione animazioni**: per motori custom
- **Import da Slade / UDB**: reverse del flusso di export

### Internazionalizzazione
- **Italiano / Inglese**
- Stringhe centralizzate in `strings.py` o file JSON per lingua

### Distribuzione
- Installer MSI (Windows)
- Portable mode (cartella `data/` accanto all'`.exe`)

### Sistema plugin
- API per importatori / esportatori custom
- Richiede stabilizzazione dell'architettura interna
- Sarebbe la feature che apre SAS a *qualsiasi* motore 2.5D

---

## Progetti satellite

### Blender Addon — `sas_sprite_renderer.py`
- Vedi sezione v0.9.x
- Documentazione interna nel pannello Help del plugin

### Pipeline completa (visione a lungo termine)