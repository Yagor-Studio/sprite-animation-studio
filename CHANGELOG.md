## v0.8.5 — 26 settembre 2026

Release di consolidamento. Fix critici, prima suite di test, editor di esportazione.

### Sicurezza dati
- Recupero da file corrotto con dialog (C-09)
- Backup permanente su sovrascrittura progetto (C-08a)
- Conservazione .bak su progetto corrotto (C-08a.1)

### Editor e timeline
- Punto unico di caricamento animazione (C-01 minima)
- Player non si blocca su svuotamento timeline (G-11)
- Fix durata: valore non si applica più al frame sbagliato
- Scorciatoie: rimozione dalla lista Impostazioni (M3)

### Export
- Nuovo editor di esportazione con timeline a blocchi (G14)
- Esportazione APNG/GIF con scaling proporzionale
- Preview animata, lucchetti per blocco, shortcut Ctrl+E
- Export da libreria padre, non solo da animazione figlia

### Blender
- Fix bridge Blender rotto da settimane (C-04)
- Manifest con duration non numerica non crasha più

### Spritesheet
- Finestra Spritesheet non tiene più il progetto (C-11)
- 4 bug in _scan_folder (prefisso, angoli, mirror, jpeg)

### Test
- Prima suite pytest (102 test, funzioni pure)
- grab_tool: 35 test, chunk grAb validato in SLADE

### Altro
- Codici libreria ASCII-safe (accenti ridotti con NFKD)
- __pycache__ in .gitignore