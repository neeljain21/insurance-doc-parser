import PyPDF2


def extract_text(pdf_path):
    pages = []
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text)
    return pages
