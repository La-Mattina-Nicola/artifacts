from prompt_toolkit.completion import Completer, Completion


class GameCompleter(Completer):
    def __init__(self, heroes, items_manager, world_map):
        self.heroes = heroes
        self.items_manager = items_manager
        self.world_map = world_map

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.strip()
        parts = text.split()

        if len(parts) == 0:
            for h in self.heroes:
                yield Completion(h.name, start_position=0)
            return

        if len(parts) == 1:
            for h in self.heroes:
                if h.name.lower().startswith(parts[0].lower()):
                    yield Completion(h.name, start_position=-len(parts[0]))
            return

        if len(parts) == 2:
            actions = ["fight", "gather", "craft", "task"]
            for a in actions:
                if a.startswith(parts[1].lower()):
                    yield Completion(a, start_position=-len(parts[1]))
            return

        hero, action, prefix = parts[0], parts[1], parts[2]

        if action == "fight" and self.world_map:
            for code in (self.world_map.monsters or {}).keys():
                if code.startswith(prefix):
                    yield Completion(code, start_position=-len(prefix))

        elif action == "gather" and self.items_manager:
            for code, item in (self.items_manager.items or {}).items():
                if item.subtype in ("mining", "woodcutting", "fishing", "alchemy"):
                    if code.startswith(prefix):
                        yield Completion(code, start_position=-len(prefix))

        elif action == "craft" and self.items_manager:
            for code in (self.items_manager.items or {}).keys():
                if code.startswith(prefix):
                    yield Completion(code, start_position=-len(prefix))

        elif action == "task":
            for kind in ("items", "monsters"):
                if kind.startswith(prefix):
                    yield Completion(kind, start_position=-len(prefix))
