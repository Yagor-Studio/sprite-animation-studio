## v0.8.4 — 25 settembre 2026

Consolidamento sicurezza dati. Nessuna feature nuova visibile, ma il programma non perde più lavoro silenziosamente.

### Recupero da file corrotto
- Un .sas illeggibile viene rinominato in .sas.corrupt prima di qualsiasi operazione. Il file corrotto non viene mai distrutto.
- Se esiste un .bak valido, l'utente sceglie con un dialog se caricarlo. Il backup viene ripristinato con scrittura atomica (tmp + replace).
- Il dialog "Progetto corrotto" compare sia dalla welcome sia da File → Apri progetto.
- Tutti gli eventi (corrotto rinominato, backup usato, annullamento) finiscono nel log.

### Durata dei frame
- La modifica della durata non si applica più alla frame sbagliata quando si cambia contesto (animazione, eliminazione, undo) con un debounce pendente.
- Il campo della durata si aggiorna correttamente al cambio frame.
- Il click fuori dallo spinbox libera il focus e applica il valore.

### Timeline e player
- Il player non resta bloccato dopo che la timeline viene svuotata o sostituita.
- Un unico punto di caricamento dell'animazione nella timeline. Le operazioni su durata, clona e specchia, elimina, agiscono sempre sull'animazione mostrata.

### Scorciatoie
- Rimozione di una scorciatoia dalla lista delle Impostazioni, con conferma.
- Il dialog di cattura non accumula più pulsanti "Annulla" a ogni tasto premuto.

### Spritesheet
- La finestra Spritesheet non conserva più un riferimento al progetto. L'import passa da callback: il progetto corrente non viene mai mutato dalla finestra, e le modifiche non si perdono più dopo un undo.

### Altro
- .gitignore aggiornato per __pycache__/.
- CLAUDE.md: load_project aggiunto tra i file sensibili.