# Workflow — Decision Log

Everything that was decided in the insurance document parser, why it was decided, and what every function and line does. Written so someone with zero prior knowledge can follow along.

---

## What does this tool do?

An insurance policy PDF contains structured information — policy numbers, coverage amounts, effective dates, names of insured parties — but it is stored as unstructured text. There is no database, no API, no consistent formatting across insurers.

This tool reads a PDF, pulls out the raw text, cleans it up, and then runs two extraction passes:

1. **Regex patterns** — for things that follow a predictable format (policy numbers, dollar amounts)
2. **Named Entity Recognition (NER)** — for things that require language understanding (dates, person names, company names)

The result is a structured JSON object with confidence scores attached to each extracted value.

---

## What is Named Entity Recognition?

NER is a task in NLP (Natural Language Processing) where a model reads text and labels spans of words as specific types of entities — PERSON, ORGANIZATION, DATE, MONEY, and so on.

**Example:**

> "John Smith is the named insured under policy POL-884721 effective January 1, 2024."

A NER model would identify:
- `John Smith` → PERSON
- `January 1, 2024` → DATE

We use spaCy, which ships with pre-trained NER models. The model was trained on large amounts of English text and learned what patterns correspond to each entity type.

NER handles ambiguity that regex can't. A regex can match `$1,500,000` reliably, but it can't tell the difference between a person's name and a company name without understanding context. That's what the model is for.

---

## Libraries Used

**`PyPDF2`**
Reads PDF files and extracts the embedded text layer page by page. Only works on PDFs that have real text (not scanned images). For scanned PDFs, you'd need an OCR step first.

**`nltk`**
Natural Language Toolkit. Used here for sentence tokenization — splitting a block of text into individual sentences using punctuation and language rules. We use this during preprocessing to filter out short fragments that are likely headers or page numbers.

**`spacy`**
Industrial-strength NLP library. We load its `en_core_web_sm` model which includes a trained NER pipeline. When you pass text to spaCy, it returns a `Doc` object where each detected entity is a `Span` with a label.

**`re`**
Python's built-in regular expression module. Used for deterministic pattern matching — things like policy number formats and dollar amounts that follow a predictable structure.

**`streamlit`**
Python library for building web apps with minimal code. You write a Python script, Streamlit turns it into a UI in the browser. No HTML or JavaScript needed.

---

## pdf_reader.py — Line by Line

```python
import PyPDF2
```
Imports the PDF parsing library.

```python
def extract_text(pdf_path):
    pages = []
    with open(pdf_path, "rb") as f:
```
Opens the file in binary mode (`"rb"`) — PDFs are not plain text files, they are binary formats. PyPDF2 requires binary mode.

```python
        reader = PyPDF2.PdfReader(f)
```
Creates a reader object from the file handle. This parses the PDF structure but does not extract text yet.

```python
        for page in reader.pages:
            text = page.extract_text()
```
Iterates over each page and calls `extract_text()`. This is the actual text extraction step — PyPDF2 walks the PDF's content stream and assembles the character positions into a string.

```python
            if text and text.strip():
                pages.append(text)
```
Only appends the page if it has non-whitespace content. Some PDFs have blank pages or pages that extract as empty strings.

```python
    return pages
```
Returns a list of strings, one per page. We keep them separate so the preprocessor can work page by page.

---

## preprocessor.py — Line by Line

```python
import re
import nltk

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)
```
Downloads NLTK's sentence tokenizer data files if they're not already on disk. `punkt` is the tokenizer model. `quiet=True` suppresses the download message so it doesn't clutter the Streamlit output. These downloads happen once and are cached locally.

```python
def _clean_page(text):
```
The leading underscore is a Python convention meaning this function is internal — it's a helper for `preprocess()` and not meant to be called from outside this file.

```python
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
```
Fixes hyphenated line breaks. When a word is too long to fit at the end of a line, PDFs often break it with a hyphen and continue on the next line — e.g., `cover-\nage`. This regex finds a word, a hyphen, a newline, and another word, then rejoins them as one word (`coverage`). The `\1` and `\2` refer back to the two captured groups.

```python
    text = re.sub(r"\n+", " ", text)
```
Replaces all newlines (including consecutive ones) with a single space. After this, the page is one long string without line breaks.

```python
    text = re.sub(r"\s{2,}", " ", text)
```
Collapses multiple consecutive spaces into one. PDF extraction often produces extra whitespace where the original document had spacing, tabs, or column layouts.

```python
    text = re.sub(r"[^\x20-\x7E]", " ", text)
```
Strips any character outside the printable ASCII range (space through `~`). OCR errors and PDF encoding issues sometimes produce characters like `\x00`, `\xa0` (non-breaking space), or ligature characters (`ﬁ` for "fi") that break downstream processing.

```python
    return text.strip()
```
Removes leading and trailing whitespace from the cleaned page.

```python
def preprocess(pages):
    cleaned = [_clean_page(p) for p in pages]
    full_text = " ".join(cleaned)
```
Cleans each page and joins them all into one big string with a space between pages.

```python
    sentences = nltk.sent_tokenize(full_text)
```
Splits the full text into individual sentences using NLTK's Punkt tokenizer. Punkt was trained to recognize sentence boundaries — it knows that "Inc." at the end of a company name is not a sentence boundary, but "Inc. The policy..." is. This is smarter than just splitting on periods.

```python
    meaningful = [s for s in sentences if len(s.split()) > 3]
```
Filters out sentences with 3 or fewer words. Page numbers, headers like "Page 2 of 10", and column labels like "Coverage Amount" are too short to contain useful entities and would just add noise. Four words minimum is a practical threshold.

```python
    return " ".join(meaningful)
```
Rejoins the kept sentences into one clean string. This is what gets passed to the extractor.

---

## extractor.py — Line by Line

```python
import re
import spacy

nlp = spacy.load("en_core_web_sm")
```
Loads the small English spaCy model into memory. This happens once at module load time, not on every call — loading the model is slow (about 1–2 seconds), so we don't want to do it inside a function that gets called repeatedly.

`en_core_web_sm` is a pipeline with three components: a tokenizer, a part-of-speech tagger, and a NER model. "sm" means small — it's fast and compact but slightly less accurate than the medium or large models.

```python
_POLICY_RE = re.compile(r"\b[A-Z]{2,4}[-\s]?\d{6,10}\b")
```
Compiles a regex pattern for policy numbers. `re.compile()` pre-compiles the pattern so it runs faster when used multiple times. Breaking it down:
- `\b` — word boundary (ensures we don't match the middle of a longer string)
- `[A-Z]{2,4}` — 2 to 4 uppercase letters (the letter prefix, like `POL` or `AB`)
- `[-\s]?` — an optional hyphen or space between the letters and numbers
- `\d{6,10}` — 6 to 10 digits (the numeric part of the policy ID)
- `\b` — word boundary at the end

This covers formats like `POL-884721`, `AB 123456`, `LIFE8847219`.

```python
_AMOUNT_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?")
```
Regex for dollar amounts:
- `\$` — literal dollar sign
- `\s?` — optional space (some PDFs render "$1,000" as "$ 1,000")
- `[\d,]+` — one or more digits or commas (handles thousand separators like `1,500,000`)
- `(?:\.\d{2})?` — optionally followed by a decimal point and exactly two digits. `(?:...)` is a non-capturing group — we want to match this as a group but don't need to reference it later.

```python
_POLICY_KEYWORDS = {"policy", "certificate", "no.", "number", "id", "#"}
_AMOUNT_KEYWORDS = {"premium", "deductible", "coverage", "limit", "amount", "benefit", "pay"}
_DATE_KEYWORDS = {"effective", "expiry", "expiration", "issued", "inception", "renewal", "from", "to", "date"}
_PARTY_KEYWORDS = {"insured", "policyholder", "beneficiary", "insurer", "named insured", "claimant"}
```
Sets of keywords used for confidence scoring. If any of these words appear in the 40 characters before a matched entity, we know it's appearing in a relevant context — for example, "Premium: $1,500" is a much more reliable amount extraction than "$1,500" floating in the middle of a paragraph.

Using sets (not lists) because membership checks on sets are O(1) — instant regardless of how many items are in the set. For lists it's O(n) — slower as the list grows.

```python
def _has_keyword_context(text, pos, keywords, window=40):
    snippet = text[max(0, pos - window): pos].lower()
    return any(kw in snippet for kw in keywords)
```
Checks whether a keyword appears in the 40 characters before a given position.

- `max(0, pos - window)` — prevents a negative index if the entity is near the start of the document
- `.lower()` — makes the comparison case-insensitive (the keywords are lowercase, so we lowercase the snippet too)
- `any(kw in snippet for kw in keywords)` — returns True if at least one keyword is found

```python
def extract_entities(text):
    doc = nlp(text)
```
Runs the full spaCy pipeline on the text. After this line, `doc` is a `Doc` object containing tokens, part-of-speech tags, and detected entities. All the NER work happens in this single call.

```python
    entities = {
        "policy_numbers": [],
        "dates": [],
        "amounts": [],
        "parties": [],
    }
    seen = {k: set() for k in entities}
```
`entities` is the output structure — a dict of lists, one per category.
`seen` is a deduplication tracker — a dict of sets, one per category. Before adding any value we check if it's already in `seen`. This prevents duplicates when the same policy number or amount appears multiple times in the document.

**Pass 1 — Regex (policy numbers and amounts):**

```python
    for match in _POLICY_RE.finditer(text):
        val = match.group()
        if val in seen["policy_numbers"]:
            continue
        seen["policy_numbers"].add(val)
        score = 0.95 if _has_keyword_context(text, match.start(), _POLICY_KEYWORDS) else 0.88
        entities["policy_numbers"].append({"value": val, "confidence": score})
```
`finditer()` returns an iterator over all non-overlapping regex matches. For each match:
- `match.group()` returns the full matched string
- We skip it if already seen
- `match.start()` is the character position where the match starts — passed to the context checker
- If a policy keyword appears before it → 0.95 confidence. Otherwise → 0.88. Both are high because regex matches are deterministic — if the pattern matched, it almost certainly is a policy number.

The same logic applies to the `_AMOUNT_RE` loop (0.93 with context, 0.88 without).

**Pass 2 — spaCy NER (dates, persons, organizations, money):**

```python
    for ent in doc.ents:
        val = ent.text.strip()
        if not val:
            continue
```
`doc.ents` is a tuple of all entities the NER model found. Each entity is a `Span` — a slice of the `Doc`. `.text` gives the raw text of the span.

```python
        if ent.label_ == "DATE":
```
`ent.label_` is the entity type string. spaCy uses all-caps labels: DATE, PERSON, ORG, MONEY, etc.

```python
            score = 0.88 if _has_keyword_context(text, ent.start_char, _DATE_KEYWORDS) else 0.78
```
`ent.start_char` is the character offset in the original text where this entity starts — the same kind of position that `match.start()` returns for regex, so we can use the same `_has_keyword_context` function.

Model-based confidence is lower than regex-based (0.78–0.88 vs 0.88–0.95) because the NER model can make mistakes, especially on domain-specific text it wasn't trained on.

```python
        elif ent.label_ in ("PERSON", "ORG"):
            entities["parties"].append({
                "value": val,
                "type": "person" if ent.label_ == "PERSON" else "organization",
                "confidence": score,
            })
```
Both PERSON and ORG go into the `parties` category, but we preserve the distinction with the `type` field. This is useful downstream — you'd treat an insured person differently from an insurer company.

```python
        elif ent.label_ == "MONEY":
            val_clean = val.replace(" ", "")
            if val_clean in seen["amounts"]:
                continue
```
spaCy also detects money entities. We add these if they weren't already caught by the regex pass. We strip spaces before the deduplication check because our regex normalizes out spaces (e.g., `$ 1,500` → `$1,500`) but spaCy preserves the original text.

---

## app.py — Line by Line

```python
st.set_page_config(page_title="Insurance Doc Parser", layout="wide")
```
Must be the first Streamlit call in the script. Sets the browser tab title and uses the full page width instead of the default narrow center column.

```python
uploaded = st.file_uploader("Upload an insurance PDF", type="pdf")
```
Renders a file upload widget restricted to PDFs. Returns `None` until a file is uploaded, then returns a file-like object.

```python
if uploaded:
```
Everything below this runs only when a file has been uploaded. Streamlit reruns the entire script top-to-bottom on every user interaction — this `if` prevents the extraction from trying to run before there's any file.

```python
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name
```
Streamlit's uploaded file is an in-memory object, not a file on disk. PyPDF2 needs a real file path. We write the uploaded bytes to a temporary file and save its path. `delete=False` means the file stays on disk after the `with` block closes — we need it to still exist when we open it in `extract_text()`.

```python
    try:
        ...
    finally:
        os.unlink(tmp_path)
```
The `finally` block runs whether extraction succeeds or throws an error. `os.unlink()` deletes the temporary file. Without this, every upload would leave a temp file on disk.

```python
        if not pages:
            st.error("No text found. The document may be image-only and require OCR.")
            st.stop()
```
`st.stop()` halts script execution for this run — equivalent to an early return but for Streamlit's execution model. We show an error and stop rather than crashing in the extraction step.

```python
        col1, col2 = st.columns(2)
```
Creates two equal-width columns side by side. Everything written inside `with col1:` appears in the left column, `with col2:` in the right.

```python
                    color = "green" if conf >= 0.90 else "orange" if conf >= 0.80 else "red"
                    st.markdown(
                        f"`{item['value']}`{type_tag} "
                        f"<span style='color:{color}'>▮ {conf:.0%}</span>",
                        unsafe_allow_html=True,
                    )
```
Color-codes the confidence indicator: green for high confidence (≥90%), orange for medium (80–89%), red for low (<80%). The `▮` character is a filled square used as a color swatch. `unsafe_allow_html=True` is required to render the inline HTML `<span>` tag — by default Streamlit escapes HTML in markdown strings.

`{conf:.0%}` formats the float as a percentage with no decimal places (0.88 → "88%").

```python
    st.download_button(
        "Download JSON",
        data=json.dumps(entities, indent=2),
        file_name="extracted_entities.json",
        mime="application/json",
    )
```
Renders a button that triggers a file download in the browser. `json.dumps(entities, indent=2)` serializes the dict to a formatted JSON string. `indent=2` means each level of nesting is indented by 2 spaces — readable output.

---

## Confidence Scoring — Design Decision

spaCy's NER model does not expose a confidence score per entity in its standard output. The `doc.ents` spans have no `.score` attribute.

The scores in this project are heuristic — they are based on two signals:

1. **Method**: Regex matches are more reliable than model predictions because they are deterministic. If the pattern matches, it either is or isn't a policy number — there's no ambiguity in the matching itself (though the regex might miss unusual formats). Model predictions can be wrong in ways regex can't.

2. **Context**: An entity preceded by a relevant keyword is more likely to be correctly identified. "Deductible: $500" is almost certainly an insurance amount. "$500 was the cost of dinner" is not.

These aren't calibrated probabilities — they're relative signals. The purpose is to give a user a quick way to spot which extractions are high-confidence vs. which to double-check.

---

## Key Concepts Recap

**NER (Named Entity Recognition):** A model that reads text and labels spans as entity types. Works well for things that require language context (names, dates) but can't match deterministic patterns better than regex.

**Regex:** A pattern language for matching text structures. Perfect for things with a fixed format (policy numbers, dollar amounts). Brittle for anything that varies in unexpected ways.

**Confidence score:** A signal (not a true probability) indicating how reliable an extraction is. Combines method type (regex vs model) and contextual keyword presence.

**Sentence tokenization:** Splitting text into sentences using language rules rather than just splitting on periods. Important because periods appear in abbreviations, decimals, and other non-sentence-ending contexts.

**Temporary files:** Streamlit uploads live in memory. PyPDF2 needs a file path. Temporary files bridge this gap — write bytes to disk, pass the path, clean up after.

**Module-level model loading:** `nlp = spacy.load(...)` runs once when the module is first imported, not on every function call. Avoids reloading a 50MB model on every PDF upload.
