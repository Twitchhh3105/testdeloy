import re
import unicodedata

# Known speech-to-text corrections for Vietnamese M365 content
STT_CORRECTIONS = {
    "Onrif": "OneDrive",
    "onrif": "OneDrive",
    "Onrift": "OneDrive",
    "onrift": "OneDrive",
    "drift": "Drive",
    "Tìm sẽ": "Teams sẽ",
}


def normalize_text(text: str) -> str:
    """Normalize unicode and whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def fix_stt_errors(text: str) -> str:
    """Apply known speech-to-text corrections."""
    for wrong, correct in STT_CORRECTIONS.items():
        text = text.replace(wrong, correct)
    return text


def remove_filler_endings(text: str) -> str:
    """Remove trailing filler sounds/words."""
    text = re.sub(r"\s*[.!?]?\s*(Yeah|M)\.\s*$", ".", text)
    return text


def clean_transcript(raw: str) -> str:
    """Full cleaning pipeline for a single transcript."""
    if not raw:
        return ""
    text = normalize_text(raw)
    text = fix_stt_errors(text)
    text = remove_filler_endings(text)
    return text
