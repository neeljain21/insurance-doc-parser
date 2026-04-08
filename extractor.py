import re
import spacy

nlp = spacy.load("en_core_web_sm")

_POLICY_RE = re.compile(r"\b[A-Z]{2,4}[-\s]?\d{6,10}\b")
_AMOUNT_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?")

_POLICY_KEYWORDS = {"policy", "certificate", "no.", "number", "id", "#"}
_AMOUNT_KEYWORDS = {"premium", "deductible", "coverage", "limit", "amount", "benefit", "pay"}
_DATE_KEYWORDS = {"effective", "expiry", "expiration", "issued", "inception", "renewal", "from", "to", "date"}
_PARTY_KEYWORDS = {"insured", "policyholder", "beneficiary", "insurer", "named insured", "claimant"}


def _has_keyword_context(text, pos, keywords, window=40):
    snippet = text[max(0, pos - window): pos].lower()
    return any(kw in snippet for kw in keywords)


def extract_entities(text):
    doc = nlp(text)

    entities = {
        "policy_numbers": [],
        "dates": [],
        "amounts": [],
        "parties": [],
    }
    seen = {k: set() for k in entities}

    for match in _POLICY_RE.finditer(text):
        val = match.group()
        if val in seen["policy_numbers"]:
            continue
        seen["policy_numbers"].add(val)
        score = 0.95 if _has_keyword_context(text, match.start(), _POLICY_KEYWORDS) else 0.88
        entities["policy_numbers"].append({"value": val, "confidence": score})

    for match in _AMOUNT_RE.finditer(text):
        val = match.group().replace(" ", "")
        if val in seen["amounts"]:
            continue
        seen["amounts"].add(val)
        score = 0.93 if _has_keyword_context(text, match.start(), _AMOUNT_KEYWORDS) else 0.88
        entities["amounts"].append({"value": val, "confidence": score})

    for ent in doc.ents:
        val = ent.text.strip()
        if not val:
            continue

        if ent.label_ == "DATE":
            if val in seen["dates"]:
                continue
            seen["dates"].add(val)
            score = 0.88 if _has_keyword_context(text, ent.start_char, _DATE_KEYWORDS) else 0.78
            entities["dates"].append({"value": val, "confidence": score})

        elif ent.label_ in ("PERSON", "ORG"):
            if val in seen["parties"]:
                continue
            seen["parties"].add(val)
            score = 0.88 if _has_keyword_context(text, ent.start_char, _PARTY_KEYWORDS) else 0.75
            entities["parties"].append({
                "value": val,
                "type": "person" if ent.label_ == "PERSON" else "organization",
                "confidence": score,
            })

        elif ent.label_ == "MONEY":
            val_clean = val.replace(" ", "")
            if val_clean in seen["amounts"]:
                continue
            seen["amounts"].add(val_clean)
            score = 0.88 if _has_keyword_context(text, ent.start_char, _AMOUNT_KEYWORDS) else 0.80
            entities["amounts"].append({"value": val, "confidence": score})

    return entities
