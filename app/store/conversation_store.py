class ConversationStore:
    def __init__(self):
        # conversation_id -> dict with history and metadata
        self.store = {}
    
    def _init_conv(self, conversation_id: str):
        if conversation_id not in self.store:
            self.store[conversation_id] = {
                "history": [],
                "turn_count": 0,
                "repeated_message_count": 0,
                "last_message": None,
                "current_intent": None,
                "last_action": None,
            }
            
    def add_message(self, conversation_id: str, role: str, message: str, timestamp: str):
        self._init_conv(conversation_id)
        conv = self.store[conversation_id]
        
        # Check for repeated merchant/customer message
        if role != "vera":
            if conv["last_message"] == message:
                conv["repeated_message_count"] += 1
            else:
                conv["repeated_message_count"] = 0
            conv["last_message"] = message
            conv["turn_count"] += 1
            
        conv["history"].append({"role": role, "message": message, "timestamp": timestamp})
        
    def get_history(self, conversation_id: str) -> list:
        return self.store.get(conversation_id, {}).get("history", [])
        
    def get_metadata(self, conversation_id: str) -> dict:
        self._init_conv(conversation_id)
        return self.store[conversation_id]
        
    def update_metadata(self, conversation_id: str, updates: dict):
        self._init_conv(conversation_id)
        self.store[conversation_id].update(updates)
    
    def clear(self):
        self.store.clear()
