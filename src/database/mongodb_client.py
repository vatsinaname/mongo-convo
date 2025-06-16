from typing import Optional, Dict, Any
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

class MongoDBClient:
    def __init__(self, connection_string: str):
        """Initialize MongoDB client with connection string."""
        self.client = MongoClient(connection_string)
        self.current_db: Optional[Database] = None
        
    def connect_to_database(self, database_name: str) -> None:
        """Connect to a specific database."""
        self.current_db = self.client[database_name]
        
    def get_collection(self, collection_name: str) -> Optional[Collection]:
        """Get a collection from the current database."""
        if not self.current_db:
            raise ValueError("No database selected. Call connect_to_database first.")
        return self.current_db[collection_name]
    
    def execute_query(self, collection_name: str, query: Dict[str, Any]) -> list:
        """Execute a MongoDB query on the specified collection."""
        collection = self.get_collection(collection_name)
        return list(collection.find(query))
