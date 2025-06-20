"""
Context Manager for maintaining conversation state.
"""
from typing import List, Dict

class ContextManager:
    def __init__(self):
        self.history: List[Dict[str, str]] = []  # each entry- {"role": "user"|"agent", "message": str}

    def add_message(self, role: str, message: str):
        """Add a message to the conversation history."""
        self.history.append({"role": role, "message": message})

    def get_history(self, n: int = 5) -> List[Dict[str, str]]:
        """Get the last n messages from the conversation history."""
        return self.history[-n:]

    def clear(self):
        """Clear the conversation history."""
        self.history = []
