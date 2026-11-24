"""Étape 1 – Ingestion : PDF/scan/Word/mail -> pages de texte (Markdown) avec n° de page.
Local uniquement. PDF natif : pdfplumber. Scan : OCR local (ocrmac/Vision sur Mac, ou Surya/PaddleOCR).
"""
import sys, json, pathlib
import pdfplumber

MIN_CHARS = 80  # en dessous => page considérée comme scan

def ocr_page(pil_image) -> str:
    """OCR local multi-plateforme : Vision (macOS) > RapidOCR (Windows/Linux) > Tesseract."""
    import sys
    if sys.platform == "darwin":
        try:
            from ocrmac import ocrmac
            res = ocrmac.OCR(pil_image, language_preference=["fr-FR", "en-US"]).recognize()
            return "\n".join(t for t, _c, _b in res)
        except ImportError:
            pass
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
        res, _ = RapidOCR()(np.array(pil_image.convert("RGB")))
        return "\n".join(r[1] for r in (res or []))
    except ImportError:
        pass
    import pytesseract   # nécessite Tesseract installé + pack langue 'fra'
    return pytesseract.image_to_string(pil_image, lang="fra+eng")

def ingest_pdf(path):
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, p in enumerate(pdf.pages, 1):
            txt = p.extract_text(layout=True) or ""
            method = "text"
            if len(txt.strip()) < MIN_CHARS:
                txt = ocr_page(p.to_image(resolution=300).original); method = "ocr"
            tables = [t for t in p.extract_tables() if t]
            pages.append({"page": i, "method": method, "text": txt, "tables": tables})
    return pages

if __name__ == "__main__":
    src = pathlib.Path(sys.argv[1])
    out = ingest_pdf(src)
    pathlib.Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{len(out)} pages ; OCR sur {sum(p['method']=='ocr' for p in out)}")
