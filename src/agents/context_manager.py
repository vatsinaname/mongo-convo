"""
Context Manager for maintaining conversation state, now with Mem0 memory integration.
"""
from typing import List, Dict, Optional
import os
try:
    from mem0 import Mem0
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False

class ContextManager:
    def __init__(self, user_id: Optional[str] = None):
        self.history: List[Dict[str, str]] = []  # fallback in-memory
        self.user_id = user_id or os.getenv("MEM0_USER_ID", "default_user")
        if MEM0_AVAILABLE:
            self.mem0_client = Mem0(api_key=os.getenv("MEM0_API_KEY"))
        else:
            self.mem0_client = None

    def add_message(self, role: str, message: str):
        """Add a message to the conversation history and Mem0 memory."""
        self.history.append({"role": role, "message": message})
        if self.mem0_client:
            self.mem0_client.add(
                text=message,
                metadata={"role": role, "user_id": self.user_id}
            )

    def get_history(self, n: int = 5) -> List[Dict[str, str]]:
        """Get the last n messages from the conversation history."""
        return self.history[-n:]

    def get_relevant_memories(self, query: str, top_k: int = 5) -> List[str]:
        """Retrieve relevant memories from Mem0 for a given query."""
        if self.mem0_client:
            results = self.mem0_client.search(query, filters={"user_id": self.user_id})
            return [m["text"] for m in results[:top_k]]
        return []

    def clear(self):
        """Clear the conversation history (does not clear Mem0 memories)."""
        self.history = []
