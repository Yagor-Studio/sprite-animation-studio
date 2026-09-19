## Blender Addon - sas_sprite_renderer.py
### v0.4.3 — Stabilità render batch

# Fix: le telecamere non vengono più ricreate ad ogni "Render All",
  risolvendo il disallineamento dell'inquadratura quando il playhead
  era spostato rispetto al primo frame.
# Fix: "Render All" ferma automaticamente la Live Mode se attiva,
  evitando che i PNG batch vengano sovrascritti da render live in
  bassa qualità.
# Nuova opzione "Insegui target durante il render" (default OFF).


## [0.8.2] — 2026-09-19

### Sicurezza dati
- **C1** — Creare un progetto con un nome già esistente non lo sovrascrive
  più silenziosamente. Appare un dialog a 3 scelte:
  *Apri il progetto esistente / Crea nuovo (sovrascrive) / Annulla*.
  In caso di sovrascrittura, il `.sas` precedente viene conservato come `.bak`.
- **C2** — Salvataggio atomico: scrittura su file temporaneo, sostituzione
  solo a scrittura completata, copia di sicurezza `.bak` della versione
  precedente. Se il `.sas` principale è illeggibile, si tenta il caricamento
  dal `.bak` e lo si ripristina.
- **C3** — Le modifiche alla durata dei frame entrano nello storico undo e
  marcato lo stato "modificato".

### Correttezza
- **G4** — La riproduzione usa la durata del frame mostrato, non di quello
  successivo. Le durate variabili (es. 8-2-2-8 tic) ora si sentono.
- **G5** — Il campo durata agisce **solo sul frame selezionato**. Nuovo
  pulsante "→ tutti" per applicare la durata a tutta l'animazione con
  conferma esplicita.
- **G8** — "Salva con nome" azzera lo stato modificato e registra il progetto
  tra i recenti.
- **G10** — "Aggiorna libreria" usa la cartella associata al profilo, non
  l'ultima cartella aperta in Risorse.

### UI / UX
- **R9** — DPI awareness: interfaccia nitida su schermi con scaling al 125%
  o 150%, senza più sfuocatura.
- **R9b** — Pulsante di chiusura della schermata iniziale ancorato all'angolo.
- **G7** — Timeline con scrollbar orizzontale, rotellina del mouse e
  auto-scroll: il frame selezionato e quello in riproduzione restano
  sempre visibili.
- **M1** — Lo Stop riporta l'indicatore al primo frame.
- **M2** — Durante la riproduzione il rettangolo rosso segue il frame
  corrente nella timeline.