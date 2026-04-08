# Insurance Document Parser

End-to-end tool that extracts key entities from insurance policy PDFs using Named Entity Recognition. Upload a PDF, get structured JSON back.

## What it extracts

| Entity | Method | Example |
|---|---|---|
| Policy numbers | Regex (`AB-123456`) | `POL-884721` |
| Dates | spaCy NER + keyword context | `January 1, 2024` |
| Amounts | Regex + spaCy MONEY | `$1,500,000.00` |
| Parties | spaCy PERSON / ORG | `John Smith`, `State Farm` |

Each entity comes with a confidence score. Score is boosted when the entity appears near relevant keywords (e.g. "Premium:" before a dollar amount → higher confidence than a standalone dollar figure).

## Stack

Python · spaCy · NLTK · PyPDF2 · Streamlit

## How it works

1. **PyPDF2** extracts raw text page by page
2. **Preprocessor** cleans OCR artifacts, rejoins hyphenated line breaks, and uses NLTK sentence tokenization to filter out headers and page number fragments
3. **Extractor** runs two passes:
   - Regex patterns for policy numbers and dollar amounts (deterministic, high confidence)
   - spaCy `en_core_web_sm` NER for dates, persons, and organizations
   - Context window check: if a keyword like "Insured:" or "Effective Date:" appears within 40 chars before the entity, confidence is boosted
4. **Streamlit UI** displays results side by side — entity list with color-coded confidence + raw JSON download

## Limitations

- PDFs that are scanned images (no embedded text) will return nothing — PyPDF2 can't do OCR
- Policy number regex covers common formats (`XX-123456`, `XXXX 123456`); non-standard formats may be missed
- spaCy's small model (`en_core_web_sm`) is fast but less accurate than `lg` on unusual text

## Setup

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
streamlit run app.py
```

## Sample output

```json
{
  "policy_numbers": [
    { "value": "POL-884721", "confidence": 0.95 }
  ],
  "dates": [
    { "value": "January 1, 2024", "confidence": 0.88 },
    { "value": "December 31, 2024", "confidence": 0.88 }
  ],
  "amounts": [
    { "value": "$1,500,000.00", "confidence": 0.93 },
    { "value": "$500", "confidence": 0.88 }
  ],
  "parties": [
    { "value": "John Smith", "type": "person", "confidence": 0.88 },
    { "value": "State Farm", "type": "organization", "confidence": 0.75 }
  ]
}
```
