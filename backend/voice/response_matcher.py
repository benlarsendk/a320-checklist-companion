"""Matches spoken responses to expected checklist responses."""

import re
from typing import Optional, List, Tuple


# Universal responses that can be accepted for any item
UNIVERSAL_RESPONSES = [
    "check", "checked",
    "confirm", "confirmed",
    "set",
    "yes",
    "affirmative",
]

# Mapping of expected responses to acceptable spoken phrases
# Key: normalized response text, Value: list of acceptable phrases
RESPONSE_PHRASES = {
    # Basic states
    "removed": ["removed", "remove"],
    "checked": ["checked", "check"],
    "on": ["on"],
    "off": ["off"],
    "set": ["set"],
    "closed": ["closed", "close"],
    "zero": ["zero", "neutral"],

    # Confirmations
    "confirmed": ["confirmed", "confirm", "affirm"],

    # As required variations
    "as rqrd": ["as required", "as needed", "set"],
    "as required": ["as required", "as needed", "set"],

    # Navigation/systems
    "nav": ["nav", "navigation", "navigate"],
    "ta/ra": ["t a r a", "ta ra", "tara", "traffic alert", "traffic"],

    # Takeoff related
    "t.o.": ["takeoff", "t o", "take off", "set"],
    "t.o. (both)": ["takeoff", "t o", "take off", "takeoff both", "set"],
    "t.o. no blue": ["no blue", "takeoff no blue", "t o no blue"],

    # Landing related
    "ldg no blue": ["no blue", "landing no blue", "l d g no blue"],
    "up": ["up", "gear up"],
    "down": ["down", "gear down"],
    "retracted": ["retracted", "up", "zero", "flaps up"],
    "armed": ["armed", "arm"],
    "disarmed": ["disarmed", "disarm", "retracted"],

    # Monitoring
    "review": ["review", "reviewed"],
    "monitor": ["monitor", "monitored", "monitoring"],
    "adjust": ["adjust", "adjusted", "set"],

    # TCAS
    "all or blw": ["all", "below", "all or below", "traffic all", "traffic below"],

    # Values with placeholders (___KG, ___%, etc.)
    "___kg checked": ["checked", "fuel checked", "kilos checked"],
    "___set (both)": ["set", "set both", "both set"],
    "___% set": ["set", "percent set", "trim set"],
    "___set": ["set"],
    "closed (both)": ["closed", "closed both", "both closed"],
    "checked (both)": ["checked", "checked both", "both checked"],
}


class ResponseMatcher:
    """Matches spoken phrases to expected checklist responses."""

    def __init__(self):
        # Build reverse lookup: phrase -> list of responses it matches
        self._phrase_to_responses = {}
        for response, phrases in RESPONSE_PHRASES.items():
            for phrase in phrases:
                if phrase not in self._phrase_to_responses:
                    self._phrase_to_responses[phrase] = []
                self._phrase_to_responses[phrase].append(response)

    def normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Lowercase
        text = text.lower().strip()
        # Remove punctuation except hyphens
        text = re.sub(r'[^\w\s\-]', '', text)
        # Collapse multiple spaces
        text = re.sub(r'\s+', ' ', text)
        return text

    def match(self, spoken: str, expected_response: str) -> Tuple[bool, float]:
        """
        Check if spoken text matches expected response.

        Returns:
            Tuple of (is_match, confidence)
            confidence is 1.0 for exact match, 0.8 for universal, 0.9 for phrase match
        """
        spoken_norm = self.normalize_text(spoken)
        expected_norm = self.normalize_text(expected_response)

        # Exact match
        if spoken_norm == expected_norm:
            return True, 1.0

        # Check universal responses
        for universal in UNIVERSAL_RESPONSES:
            if universal in spoken_norm:
                return True, 0.8

        # Check if spoken matches any phrase for this response
        if expected_norm in RESPONSE_PHRASES:
            for phrase in RESPONSE_PHRASES[expected_norm]:
                if phrase in spoken_norm or spoken_norm in phrase:
                    return True, 0.9

        # Check reverse lookup - does spoken phrase match expected?
        if spoken_norm in self._phrase_to_responses:
            matched_responses = self._phrase_to_responses[spoken_norm]
            if expected_norm in matched_responses:
                return True, 0.9

        # Partial match - spoken contains key words from expected
        expected_words = set(expected_norm.split())
        spoken_words = set(spoken_norm.split())
        if expected_words & spoken_words:  # Any overlap
            overlap = len(expected_words & spoken_words) / len(expected_words)
            if overlap >= 0.5:
                return True, 0.7

        return False, 0.0

    def get_accepted_phrases(self, expected_response: str) -> List[str]:
        """Get list of phrases that would be accepted for a response."""
        expected_norm = self.normalize_text(expected_response)
        phrases = list(UNIVERSAL_RESPONSES)  # Always include universal

        if expected_norm in RESPONSE_PHRASES:
            phrases.extend(RESPONSE_PHRASES[expected_norm])

        return list(set(phrases))
