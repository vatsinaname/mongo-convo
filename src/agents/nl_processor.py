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
        # Only lowercase for intent/collection, preserve original for filters
        intent = self._detect_intent(user_input.lower())
        collection = self._extract_collection(user_input.lower())
        fields = self._extract_fields(user_input.lower())
        filters = self._extract_filters(user_input)  # use original casing for names
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
        # Enhanced: extract name-based filters using regex for word match
        # e.g. 'named John', 'with name Smith', 'whose name is Brown', 'list users John'
        name_match = re.search(r"named ([a-zA-Z0-9]+)", text)
        if not name_match:
            name_match = re.search(r"name (?:is|=)? ?([a-zA-Z0-9]+)", text)
        if not name_match:
            # e.g. 'list users John', 'show customers John'
            name_match = re.search(r"(?:users?|customers?) ([a-zA-Z0-9]+)", text)
        if not name_match:
            # fallback: if the query ends with a single capitalized word, treat as name
            tokens = text.strip().split()
            if len(tokens) > 1 and tokens[-1][0].isalpha() and tokens[-1][0].isupper():
                name = tokens[-1]
                return {"name": {"$regex": fr"\\b{name}\\b", "$options": "i"}}
        if name_match:
            name = name_match.group(1)
            return {"name": {"$regex": fr"\\b{name}\\b", "$options": "i"}}
        return {}
