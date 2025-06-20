"""
Schema Analyzer for MongoDB collections.
"""
from collections import defaultdict, Counter
from typing import Any, Dict

class SchemaAnalyzer:
    def analyze(self, collection, sample_size: int = 100) -> Dict[str, Any]:
        """
        Analyze the schema of a MongoDB collection by sampling documents.
        Returns a dict with field names and their most common types.
        """
        field_types = defaultdict(Counter)
        sample_cursor = collection.find({}, limit=sample_size)
        for doc in sample_cursor:
            for field, value in doc.items():
                field_types[field][type(value).__name__] += 1
        schema = {}
        for field, types_counter in field_types.items():
            most_common_type = types_counter.most_common(1)[0][0]
            schema[field] = most_common_type
        return schema
