"""
Natural Language Processor for parsing user input.
"""
import re
from typing import Dict, Any

class NLProcessor:
    def parse(self, user_input: str) -> Dict[str, Any]:
        """
        Parse user input and extract intent, collection, and fields.
        Returns a dict with keys: intent, collection, fields, filters
        """
        user_input = user_input.lower()
        intent = self._detect_intent(user_input)
        collection = self._extract_collection(user_input)
        fields = self._extract_fields(user_input)
        filters = self._extract_filters(user_input)
        return {
            "intent": intent,
            "collection": collection,
            "fields": fields,
            "filters": filters
        }

    def _detect_intent(self, text: str) -> str:
        if any(word in text for word in ["count", "how many"]):
            return "count"
        if any(word in text for word in ["find", "show", "list"]):
            return "find"
        if "average" in text or "sum" in text:
            return "aggregate"
        return "unknown"

    def _extract_collection(self, text: str) -> str:
        # simple rule look for 'from <collection>'
        match = re.search(r"from ([a-zA-Z0-9_]+)", text)
        if match:
            return match.group(1)
        # fallback- look for 'in <collection>'
        match = re.search(r"in ([a-zA-Z0-9_]+)", text)
        if match:
            return match.group(1)
        # infer collection from keywords for sample analytics dataset
        collection_map = {
            "user": "customers",
            "users": "customers",
            "customer": "customers",
            "customers": "customers",
            "account": "accounts",
            "accounts": "accounts",
            "transaction": "transactions",
            "transactions": "transactions",
            "session": "sessions",
            "sessions": "sessions"
        }
        for keyword, collection in collection_map.items():
            if re.search(rf"\b{keyword}\b", text):
                return collection
        return ""

    def _extract_fields(self, text: str) -> list:
        # look for 'show <fields>' or 'list <fields>'
        match = re.search(r"show ([a-zA-Z0-9_, ]+)", text)
        if match:
            fields = [f.strip() for f in match.group(1).split(",")]
            return fields
        return []

    def _extract_filters(self, text: str) -> dict:
        # placeholder for filter extraction
        # eg 'where age > 30'
        return {}
