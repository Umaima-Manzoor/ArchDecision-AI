"""
Checks user input for common attack patterns before the text reaches the LLM. Rejects queries that try to override the agent's instructions or extract the system prompt.
"""

import re

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

# Attackers often wrap injected instructions in markdown/HTML/role-play delimiters to separate them from the real question. These markers are meaningless in a technology-comparison question, so any match is suspicious.
_DELIMITER_RE = re.compile(
    r"```|<\s*/?\s*(system|user|assistant|instructions?|prompt)\s*>"
    r"|^\s*(system|user|assistant)\s*:\s*"
    r"|\[INST\]|<\|im_start\|>|<\|im_end\|>",
    re.IGNORECASE | re.MULTILINE,
)

# Hard cap on input length. Beyond this the string is almost certainly not a genuine comparison question and scanning it is wasted work (and the planner schema already enforces 500 chars, so this is a second, independent guard).
MAX_INPUT_LENGTH = 500


def check_injection(text: str) -> str | None:       # returns the matched pattern as a string if injection detected, or None if the input is clean
    if not text or len(text) > MAX_INPUT_LENGTH:
        return "input_too_long"
    lower = text.lower()        # case-insensitive check
    for pattern in INJECTION_PATTERNS:
        if all(word in lower for word in pattern):       # all words in the tuple must be present
            return " ".join(pattern)       # return the matched pattern for logging
    if _DELIMITER_RE.search(text):
        return "instruction_delimiter"
    return None       # no pattern matched, input is safe