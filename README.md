## 📥 Download

Scarica l'ultima versione eseguibile dalla [pagina delle Release](https://github.com/yagor-studio/sprite-animation-studio/releases).
#
## 🚀 Avvio rapido
### Eseguibile in /dist
1. Scarica la repository
2. Apri /dist/SpriteAnimationStudio.exe

### Per sviluppatori (codice sorgente)
```bash
git clone https://github.com/TUO_USERNAME/sprite-animation-studio.git
cd sprite-animation-studio
pip install -r requirements.txt
python -m sprite_animation_studio.main


#####
##### Tonno, se hai problemi con il programma scrivimi
##### yagorstudio@gmail.com
#####
#####
##### Potresti anche supportarmi
#### itch.io # https://yagor-studio.itch.io/ <-[ in lavorazione ]
#### Ko-fi # https://ko-fi.com/yagorstudio
### E ricorda che la risorsa "welcome_bg" proviene da una collezione prodotta da ROGA, pastelli morbidi su carta.
##
## Sprite Animation Studio v0.7.3 ##
#
# Update della settimana:

Siamo arrivati di nuovo a sabato e mammina mia tonno, sono felicissimo dei risultati e spero di non bloccarmi ulteriormente in futuro.
Sono stato dietro alla gestione dei layout, per adesso ho creato due finestre principali [/Welcome per iniziare il programma] e [Editor] per interfacciarsi con il progetto.
Rispetto le versioni precedenti ho rimosso completamente il pannello di destra per dare priorità al lettore 2.5D che in futuro ritoccherò per una compatibilità "doppio lettore" (ne riparleremo quando gestiremo tutti gli angoli contemporaneamente).
Ho aggiornato un po' la toolbar, è una figata mettere bottoni e farci fare cose, anche tenerli bloccati... mi da un senso di onnipotenza :'D
Con l'aggiunta di /Spritesheet->/import\/export riesco a gestire una schermata extra senza impattare nel layout dell'editor, inoltre mantengo tutte le informazioni importanti senza sacrificare spazio.
E' stato un problema creare la logica di "Import" da spritesheet, ovviamente... per adesso mi tengo saldo al modello DoomEngine di nomenclatura quindi credo semplicemente un array dinamico con anteprima; selezioni tutti i dati parentali, da Libreria padre /AB, Libreria figlio /CD, Frame /A-Z, Angolo /0-1-8 e decidi in che ordine aggiornare la nomenclatura. 
In pratica seleziono uno Sprite "Doom Guy"con codice [DG], nomino una Animazione "Walking Animation" con codice [WA] e imposto 4 frame e 5 angoli con priorità agli angoli.
Il programma genera un numero kit di immagini nominati singolarmente secondo i dati inseriti in precedenza, quindi il programma potrà accederci direttamente senza ulteriori passaggi. [DGWAA1,DGWAA2,DGWAA3, DGWAA4, DGWAA5, DGWAB1, DGWAB2, e così via]
27 ore avanti al computer con qualche breve pausa per ricordarmi che sono morto solo dentro e si torna a lavoro, ho risolto un numero spropositato di errori con dnb e breakcore stile 2000s di sottofondo, tipo una folata di vento tra le dune di sabbia._._,---.__/'--._.
Ho aggiunto una ruota per orientare gli angoli così almeno capisci da dove stai guardando lo Sprite, dovrei implementare una regola che costringa i selettori "destra" e "sinistra" a passare solo tra quelli disponibili per agevolare le riproduzioni con meno angoli di base.
Risorse e Librerie ora funzionano bene insieme, è stato un vero e proprio inferno e spero si capisca come va usato, ti scriverò un tutorial entro la v1.0 e spero sarà un tonno a spigare le cose... sarà divertentissimo senza dubbio.
Rimosse le scritte dalle icone che andranno senza dubbio disegnate entro il rilascio ufficiale di SAS, se ci passi il cursore sopra (per almeno 0.4s) ti dicono cosa fanno!
La timeline sembra funzionare, anche angoli e lettori. I tasti tastano e la toolbar è sfiziosa. Non vedo l'ora di popolarla, specialmente "aiuto" e "impostazioni".
Mi fa troppo ridere "Aiuto", vorrei metterci un mano in pixel art per battere un cinque virtuale, non saprei cosa fare oltre questo, in impostazioni invece devo trovare cose importanti da metterci, devo segnarmi una lista di impostazioni e tasti rapidi.
AH c'è anche il salvataggio automatico e gli avvisi fastidiosi che rompono le scatole, poi li faccio piccolini e li metto sotto a tutto :P
Quindi niente, spero il programma ti piaccia.


#Yagor Studio, ROGA.