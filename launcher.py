# launcher.py
import sys
from pathlib import Path

# Aggiungi la cartella corrente al path
sys.path.insert(0, str(Path(__file__).parent))

# Importa ed esegui l'app
from sprite_studio.main import main

if __name__ == "__main__":
    main()