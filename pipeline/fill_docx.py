"""Étape 5 – Génération du TCO Word depuis un modèle à balises {{...}} (python-docx, déterministe).
Le texte standard (Origine, Garantie, présentation OME…) vit dans le modèle ; seul le variable est injecté.
"""
import sys, json, re, docx

def replace_in_par(p, mapping):
    full = "".join(r.text for r in p.runs)
    if "{{" not in full: return
    for k, v in mapping.items(): full = full.replace("{{%s}}" % k, str(v))
    for r in p.runs[1:]: r.text = ""
    p.runs[0].text = full

def render(template, mapping, out):
    d = docx.Document(template)
    for p in d.paragraphs: replace_in_par(p, mapping)
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                for p in c.paragraphs: replace_in_par(p, mapping)
    left = [m for p in d.paragraphs for m in re.findall(r"\{\{(\w+)\}\}", p.text)]
    if left: raise SystemExit(f"Balises non remplies : {left}")
    d.save(out)

if __name__ == "__main__":
    data = json.load(open(sys.argv[2]))["meta"]
    render(sys.argv[1], {k: v["value"] for k, v in data.items() if isinstance(v, dict)}, sys.argv[3])
