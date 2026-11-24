"""Étape 3 – Revue humaine : génère une fiche HTML/Markdown « champ | valeur | page | citation | statut ».
Tout champ binding=true ou confidence!=high est marqué À VALIDER ; l'export Excel/Word est bloqué tant que non validé."""
import sys, json
d = json.load(open(sys.argv[1]))
print("| Champ | Valeur | Page | Citation | Statut |\n|---|---|---|---|---|")
for k, f in d["meta"].items():
    st = "⚠️ À VALIDER" if f.get("binding") or f.get("confidence") != "high" else "ok"
    print(f"| {k} | {f['value']} | {f['source'].get('page')} | {f['source'].get('quote','')[:60]} | {st} |")
