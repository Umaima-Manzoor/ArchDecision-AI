"""
Checks user input for common attack patterns before the text reaches the LLM. Rejects queries that try to override the agent's instructions or extract the system prompt.
"""

# Each tuple is a set of words that must ALL appear in the input to trigger a block.
# Using word combinations instead of single words prevents false positives.
# For example, "instruction" alone is fine (e.g. "instruction pipelining in PostgreSQL")
# but "ignore" + "previous" + "instruction" together is almost certainly an attack.
INJECTION_PATTERNS: list[tuple[str, ...]] = [       # ... means tuple of any length
    ("ignore", "previous", "instruction"),
    ("ignore", "all", "instruction"),
    ("ignore", "above", "instruction"),
    ("forget", "everything"),
    ("forget", "all", "instruction"),
    ("disregard", "previous"),
    ("disregard", "above"),
    ("override", "instruction"),
    ("override", "system"),
    ("system", "prompt"),
    ("your", "instruction"),
    ("new", "instruction"),
    ("you", "are", "now"),
    ("act", "as", "if"),
    ("pretend", "you", "are"),
    ("do", "not", "follow"),
    ("reveal", "your", "prompt"),
    ("show", "your", "prompt"),
    ("output", "your", "prompt"),
]


def check_injection(text: str) -> str | None:       # returns the matched pattern as a string if injection detected, or None if the input is clean
    lower = text.lower()        # case-insensitive check
    for pattern in INJECTION_PATTERNS:
        if all(word in lower for word in pattern):       # all words in the tuple must be present
            return " ".join(pattern)       # return the matched pattern for logging
    return None       # no pattern matched, input is safe