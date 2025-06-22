"""
Query Generator for converting parsed input to MongoDB queries.
"""
from typing import Dict, Any

class QueryGenerator:
    def generate(self, parsed_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a MongoDB query dict from parsed input.
        Returns a dict with keys: collection, query, projection, operation
        """
        intent = parsed_input.get("intent", "find")
        collection = parsed_input.get("collection", "")
        fields = parsed_input.get("fields", [])
        filters = parsed_input.get("filters", {})

        query = filters or {}
        #special projection for customers- show only name
        if collection == "customers":
            projection = {"name": 1, "_id": 0}
        elif fields:
            projection = {field: 1 for field in fields}
        else:
            projection = None

        if intent == "count":
            operation = "count_documents"
        elif intent == "find":
            operation = "find"
        elif intent == "aggregate":
            operation = "aggregate"
        else:
            operation = "find"

        return {
            "collection": collection,
            "query": query,
            "projection": projection,
            "operation": operation
        }
