class ConversationStore:
    def __init__(self):
        # conversation_id -> list of messages
        self.store = {}
    
    def add_message(self, conversation_id: str, role: str, message: str, timestamp: str):
        if conversation_id not in self.store:
            self.store[conversation_id] = []
        self.store[conversation_id].append({"role": role, "message": message, "timestamp": timestamp})
        
    def get_history(self, conversation_id: str) -> list:
        return self.store.get(conversation_id, [])
    
    def clear(self):
        self.store.clear()
