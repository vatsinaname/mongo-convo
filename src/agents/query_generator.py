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
        print("[DEBUG] Parsed input to QueryGenerator:", parsed_input)  # TEMP DEBUG
        intent = parsed_input.get("intent", "find")
        collection = parsed_input.get("collection", "")
        fields = parsed_input.get("fields", [])
        filters = parsed_input.get("filters", {})

        print(f"[DEBUG] intent: {intent}, collection: {collection}, fields: {fields}, filters: {filters}")  # TEMP DEBUG

        query = filters or {}
        # generalised
        default_fields = {
            "customers": ["name"],
            "accounts": ["account_id"],
            "transactions": ["amount", "account_id"],
            "sessions": ["session_id"]
        }
        if fields:
            projection = {field: 1 for field in fields}
            projection["_id"] = 0
        elif collection in default_fields:
            projection = {field: 1 for field in default_fields[collection]}
            projection["_id"] = 0
        else:
            projection = None

        print(f"[DEBUG] query: {query}, projection: {projection}")  # TEMP DEBUG

        if intent == "count":
            operation = "count_documents"
        elif intent == "find":
            operation = "find"
        elif intent == "aggregate":
            operation = "aggregate"
        else:
            operation = "find"

        result = {
            "collection": collection,
            "query": query,
            "projection": projection,
            "operation": operation
        }
        print("[DEBUG] QueryGenerator output:", result)  # TEMP DEBUG
        return result
