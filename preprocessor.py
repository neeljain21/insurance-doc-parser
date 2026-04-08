import re
import nltk

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)


def _clean_page(text):
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)  # rejoin hyphenated line breaks
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"[^\x20-\x7E]", " ", text)  # strip non-ASCII OCR artifacts
    return text.strip()


def preprocess(pages):
    cleaned = [_clean_page(p) for p in pages]
    full_text = " ".join(cleaned)
    sentences = nltk.sent_tokenize(full_text)
    meaningful = [s for s in sentences if len(s.split()) > 3]
    return " ".join(meaningful)
