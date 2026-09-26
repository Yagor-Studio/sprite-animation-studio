# Sprite Animation Studio

Editor desktop per organizzare, modificare ed esportare sprite 2.5D
compatibili con Doom. Sviluppato in Python con Tkinter.

**Stato attuale: v0.8.5** (26 settembre 2026)

---

## Cos'è SAS

SAS è uno strumento per modder di Doom. Prende sprite renderizzati da
Blender (8 angoli, n frame per animazione), li organizza in librerie e
animazioni, e li prepara per l'uso in GZDoom tramite SLADE o UDB.

È pensato per chi lavora su total conversion o mod complesse, dove la
gestione manuale di centinaia di sprite diventa ingestibile.

---

## Caratteristiche principali

- **Import da Blender** tramite addon dedicato (`sas_sprite_renderer.py`),
  con bridge in tempo reale durante la sessione di modellazione.
- **Import da spritesheet** con griglia configurabile, offset, padding.
- **Gestione angoli 1–8** e sprite HUD a rotazione singola.
- **Nomenclatura Doom** compatibile con SLADE/UDB.
- **Undo/Redo, autosave, salvataggio atomico con backup**.
- **Editor di esportazione APNG/GIF** con timeline a blocchi, anteprima
  animata e rotazione a due timeline indipendenti.
- **Scorciatoie personalizzabili**.
- **Recupero automatico da file corrotti** con ripristino dal backup.

---

## Download

- **itch.io**: https://yagor-studio.itch.io/sprite-animation-studio
- **GitHub Releases**: https://github.com/Yagor-Studio/sprite-animation-studio/releases

---

## Requisiti

- **Windows 10/11** (versione binaria)
- **Python 3.10+** con Pillow (per eseguire da sorgente)

---

## Installazione

### Utente finale

1. Scarica `SpriteAnimationStudio.exe` dall'ultima release.
2. Eseguilo. Nessuna installazione richiesta.

### Sviluppatore

```bat
git clone https://github.com/Yagor-Studio/sprite-animation-studio.git
cd sprite-animation-studio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m sprite_animation_studio.main


#### Tonno ricorda sempre: 
####
####		All'amore devoti,
####			dall'amore mai vinti!