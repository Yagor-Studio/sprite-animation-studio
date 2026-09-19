# Sprite Animation Studio

## Cos'è
Stiamo cercando di costruire un sistema di gestione SPRITE/animazioni ma in realtà divento pazzo dietro questo progetto e dimentico di modificare le voci, vi voglio bene ma ho bisogno di dormire.

## Caratteristiche principali
- Gestione angoli 1–8 e HUD
- Import spritesheet con griglia, offset, padding
- Export con nomenclatura Doom
- Bridge Blender con render 8-camere
- Undo/Redo, autosave, salvataggio intelligente
- Shortcut personalizzabili

## Download
- **itch.io**: https://yagor-studio.itch.io/sprite-animation-studio
- **GitHub Releases**: https://github.com/Yagor-Studio/sprite-animation-studio

## Requisiti
- Windows 10/11
- (Per il codice sorgente) Python 3.10+, Pillow

## Installazione
### Utente finale
1. Scarica l'`.exe`
2. Esegui (nessuna installazione richiesta)

### Sviluppatore
```bat
git clone https://github.com/Yagor-Studio/sprite-animation-studio.git
cd sprite-animation-studio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m sprite_animation_studio.main

#### Tonno
Anche oggi è andata, stiamo lavorando sulla stabilità di Sprite Animation Studio ed errori di logica nel codice.
Ci vuole parecchia pazienza a provare, capire cosa non va, modificare, raffinare. Porca paletta sembrava stessimo andando veloci come il vento e ora è pieno di nodi. Ho passato ore a scrivere documenti come materiale da riversare in qualche AI per aiutarmi a trovare falle, è stato tipo un "cerca questo", cambia il ciclo, definisci una cosa, ricorda i dizionari, controlla se... 
Ho bumpato la 0.8.2 e finalmente si vola (a nanna)