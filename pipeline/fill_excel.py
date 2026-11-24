"""Étape 4 – Remplissage DÉTERMINISTE du modèle Excel (aucun LLM, aucune régénération).
On ne touche que les cellules d'entrée ; les formules du modèle (ROUNDUP, totaux, MICAM/INDUSERV) restent intactes.
"""
import sys, json, copy, openpyxl
from openpyxl.styles import Alignment

FIRST_ROW, LAST_LINE_ROW = 4, 9      # lignes articles du modèle (6 max) ; Packing/CFR en 10-11

def fill(template, data, out, incoterm_label=None):
    wb = openpyxl.load_workbook(template); ws = wb.active
    meta, lignes = data["meta"], data["lignes"]
    n_slots = LAST_LINE_ROW - FIRST_ROW + 1
    extra = len(lignes) - n_slots
    if extra > 0:                     # plus d'articles que de lignes => insertion + recopie style/formules
        ws.insert_rows(LAST_LINE_ROW + 1, extra)
        for k in range(extra):
            r = LAST_LINE_ROW + 1 + k
            for col in range(2, 9):
                src = ws.cell(LAST_LINE_ROW, col); dst = ws.cell(r, col)
                dst._style = copy.copy(src._style)
                if isinstance(src.value, str) and src.value.startswith("="):
                    dst.value = src.value.replace(str(LAST_LINE_ROW), str(r))
        LAST_LINE_ROW_EFF = LAST_LINE_ROW + extra
    else:
        LAST_LINE_ROW_EFF = LAST_LINE_ROW
    for i, l in enumerate(lignes):
        r = FIRST_ROW + i
        ws.cell(r, 2).value = l["n"]
        c = ws.cell(r, 3); c.value = l["designation_fr"] + ("\n" + l["designation_en"] if l.get("designation_en") else "")
        c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(r, 4).value = l["qte"]            # prix (col E) laissés vides : saisis par l'humain
    # Titre en C2
    client_raw = (meta.get("client") or {}).get("value", "")
    if "fertial" in client_raw.lower():
        client_name = "Fertial SPA"
    else:
        client_name = client_raw.split("-")[0].strip() if client_raw else "Client"

    projet = (meta.get("projet") or {}).get("value") or (meta.get("objet") or {}).get("value") or "Fourniture de moteurs électriques"
    ref_rfq = (meta.get("ref_rfq") or {}).get("value", "")
    ref_str = f"(RFQ N° {ref_rfq})" if ref_rfq else ""
    ws["C2"] = f"{client_name} — {projet} {ref_str}".strip()

    # Incoterm & Totaux
    inc = incoterm_label or (meta.get("incoterm") or {}).get("value")
    if not inc or str(inc).lower() in ("none", "null", ""):
        lieu = str((meta.get("lieu_livraison") or {}).get("value", ""))
        if "annaba" in lieu.lower():
            inc = "CFR Annaba"
        else:
            inc = "CFR"
    
    off = extra if extra > 0 else 0
    ws.cell(11 + off, 3).value = inc
    ws.cell(12 + off, 2).value = f"Total {inc}"

    # sécurité : SUM du total qté couvre toutes les lignes
    ws["D2"] = f"=SUM(D{FIRST_ROW}:D{LAST_LINE_ROW_EFF})"
    try:
        wb.save(out)
    except PermissionError:
        print(f"\n⚠️ ATTENTION : Le fichier '{out}' est actuellement ouvert dans Excel !")
        print("👉 Veuillez fermer Excel pour que le script puisse enregistrer le fichier, puis relancez la commande.\n")
        sys.exit(1)

if __name__ == "__main__":
    fill(sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3])
