from PySide6.QtWidgets import QWidget

class Undoable:
    def undo(self):
        pass

    def redo(self):
        pass

class Undo:
    def __init__(self):
        self._undo_list = []
        self._redo_list = []
        self._limit = 500

    def push(self, *undoables: Undoable):
        if len(self._undo_list) == self._limit:
            self._undo_list.pop(0)

        self._undo_list.append(undoables)
        for r in undoables:
            r.redo()
        self._redo_list = []  # The redoable objects must be removed.

    def undo(self):
        if self._undo_list:
            undoable = self._undo_list.pop()
            for u in undoable:
                u.undo()
            self._redo_list.append(undoable)
            return
        print("No more undo available.")

    def redo(self):
        if self._redo_list:
            undoable = self._redo_list.pop()
            for r in undoable:
                r.redo()
            self._undo_list.append(undoable)
            return
        print("No more redo available.")

    def set_limit(self, limit: int):
        if limit >= 0:
            i = 0
            nb = len(self._undo_list) - limit
            while i < nb:
                self._undo_list.pop()
                i += 1
            self._limit = limit

    def clear_history(self):
        self._undo_list = []
        self._redo_list = []

class AddSceneItemCmd(Undoable):
    def __init__(self, obj, item):
        self.obj = obj
        self.item = item

    def undo(self):
        self.item.hide()
        self.obj.items.remove(self.item)

    def redo(self):
        self.item.show()
        self.obj.items.append(self.item)

    def merge(self, new_item):
        self.item = new_item

class ClearSceneCmd(Undoable):
    def __init__(self, obj):
        self.obj = obj
        self.old_items = None

    def undo(self):
        self.obj.items = [*self.old_items]
        for item in self.old_items:
            item.show()

    def redo(self):
        self.old_items = [*self.obj.items]
        self.obj.items.clear()
        for item in self.old_items:
            item.hide()

    def merge(self, new_item):
        self.item = new_item