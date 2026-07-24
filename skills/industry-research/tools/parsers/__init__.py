"""Site-specific data parsers.

Each parser module exports a parse(html: str) -> dict function.
Register new parsers by adding them to PARSER_REGISTRY.
"""

PARSER_REGISTRY = {}
