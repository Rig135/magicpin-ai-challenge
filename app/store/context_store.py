class ContextStore:
    def __init__(self):
        # (scope, context_id) -> {"version": int, "payload": dict}
        self.store = {}
    
    def put(self, scope: str, context_id: str, version: int, payload: dict) -> tuple[bool, int]:
        key = (scope, context_id)
        if key in self.store:
            current_version = self.store[key]["version"]
            if current_version >= version:
                return False, current_version
        
        self.store[key] = {"version": version, "payload": payload}
        return True, version

    def get(self, scope: str, context_id: str) -> dict:
        key = (scope, context_id)
        return self.store.get(key, {}).get("payload")

    def count_by_scope(self) -> dict:
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        for (scope, _), _ in self.store.items():
            if scope in counts:
                counts[scope] += 1
            else:
                counts[scope] = 1
        return counts

    def clear(self):
        self.store.clear()
