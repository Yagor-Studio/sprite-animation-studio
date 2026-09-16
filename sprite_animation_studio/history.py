# sprite_animation_studio/history.py
"""Gestione Undo/Redo basata su snapshot completi del progetto.

Uno snapshot è semplicemente il dict prodotto da ProjectData.to_dict().
Non serve nessuna logica di diff: il progetto intero viene serializzato,
e il ripristino avviene ricostruendo un ProjectData da quello snapshot.

Limite noto: il Dirty flag non torna a "pulito" dopo un undo che riporta
il progetto a uno stato identico a quello salvato. Questo è accettato
per la v0.8 e documentato in ROADMAP.
"""


class ProjectHistory:
    def __init__(self, max_depth=10):
        self._undo_stack = []
        self._redo_stack = []
        self.max_depth = max(1, int(max_depth))

    def push(self, snapshot):
        """Salva uno snapshot PRIMA di una modifica. Svuota la pila redo."""
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()
        while len(self._undo_stack) > self.max_depth:
            self._undo_stack.pop(0)

    def undo(self, current_snapshot):
        """Ritorna lo snapshot precedente, o None se non c'è. Sposta
        current_snapshot nella pila redo."""
        if not self._undo_stack:
            return None
        self._redo_stack.append(current_snapshot)
        while len(self._redo_stack) > self.max_depth:
            self._redo_stack.pop(0)
        return self._undo_stack.pop()

    def redo(self, current_snapshot):
        """Ritorna lo snapshot successivo, o None se non c'è. Sposta
        current_snapshot nella pila undo."""
        if not self._redo_stack:
            return None
        self._undo_stack.append(current_snapshot)
        while len(self._undo_stack) > self.max_depth:
            self._undo_stack.pop(0)
        return self._redo_stack.pop()

    def can_undo(self):
        return bool(self._undo_stack)

    def can_redo(self):
        return bool(self._redo_stack)

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    def depth(self):
        """Quanti snapshot sono attualmente disponibili per l'undo."""
        return len(self._undo_stack)