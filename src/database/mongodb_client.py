from typing import Optional, Dict, Any, List
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
        if self.current_db is None:
            raise ValueError("No database selected. Call connect_to_database first.")
        return self.current_db[collection_name]
    
    def execute_query(self, collection_name: str, query: Dict[str, Any], projection: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
        """Execute a MongoDB find query with optional projection."""
        collection = self.get_collection(collection_name)
        if collection is None:
            return []
        # Treat empty dict as None for projection
        if not projection:
            result = list(collection.find(query))
        else:
            result = list(collection.find(query, projection))
        return result if result else []

    def count_documents(self, collection_name: str, query: Dict[str, Any]) -> int:
        """Count documents matching a query."""
        collection = self.get_collection(collection_name)
        if collection is None:
            return 0
        return collection.count_documents(query)

    def aggregate(self, collection_name: str, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run an aggregation pipeline on a collection."""
        collection = self.get_collection(collection_name)
        if collection is None:
            return []
        result = list(collection.aggregate(pipeline))
        return result if result else []
