"""Orchestrateur. Exemples :
  python run.py selftest                      # sans LLM : vérifie Excel + Word
  python run.py ingest input\\RFQ_26020021.pdf # PDF -> output\\pages.json
  python run.py extract                       # pages.json -> extraction.json (LLM local requis)
  python run.py review                        # tableau de contrôle
  python run.py build                         # extraction.json -> Excel + Word
"""
import sys, json, pathlib, subprocess
R = pathlib.Path(__file__).parent; P = R/"pipeline"; O = R/"output"; O.mkdir(exist_ok=True)
sys.path.insert(0, str(P))

def selftest():
    import fill_excel, fill_docx, openpyxl
    d = json.load(open(R/"samples/example1_extraction.json"))
    fill_excel.fill(R/"templates/CA_modele.xlsx", d, O/"CA_test.xlsx")
    ws = openpyxl.load_workbook(O/"CA_test.xlsx").active
    assert ws["D4"].value == 2 and ws["F4"].value.startswith("=ROUNDUP"), "Excel KO"
    m = json.load(open(R/"samples/example2_meta.json"))["meta"]
    fill_docx.render(R/"templates/TCO_modele.docx", {k: v["value"] for k, v in m.items()}, O/"TCO_test.docx")
    print("OK -> fichiers dans", O)

def build():
    d = json.load(open(O/"extraction.json", encoding="utf-8"))
    flagged = [k for k, f in d["meta"].items() if f.get("binding") or f.get("confidence") not in (None, "high")]
    if flagged and "--force" not in sys.argv:
        sys.exit(f"\n⚠️ Champs à valider avant export : {flagged}\nCorrigez output\\extraction.json puis relancez avec : python run.py build --force")
    import fill_excel, fill_docx
    fill_excel.fill(R/"templates/CA_modele.xlsx", d, O/"CA.xlsx")
    print("-> output\\CA.xlsx généré avec succès")
    # Génération du TCO Word
    meta_flat = {k: v["value"] for k, v in d["meta"].items() if isinstance(v, dict)}
    if (R/"samples/example2_meta.json").exists():
        defaults = {k: v["value"] for k, v in json.load(open(R/"samples/example2_meta.json"))["meta"].items()}
        defaults.update(meta_flat)
        meta_flat = defaults
    fill_docx.render(R/"templates/TCO_modele.docx", meta_flat, O/"TCO.docx")
    print("-> output\\TCO.docx généré avec succès")

c = sys.argv[1] if len(sys.argv) > 1 else "selftest"
if c == "selftest": selftest()
elif c == "ingest": subprocess.run([sys.executable, P/"ingest.py", sys.argv[2], O/"pages.json"], check=True)
elif c == "extract":
    if not (O/"pages.json").exists():
        pdfs = list((R/"input").glob("*.pdf"))
        if pdfs:
            print(f"📄 pages.json absent -> Ingestion automatique de {pdfs[0]}...")
            subprocess.run([sys.executable, P/"ingest.py", str(pdfs[0]), str(O/"pages.json")], check=True)
    subprocess.run([sys.executable, "-u", P/"extract.py", O/"pages.json", O/"extraction.json"] + sys.argv[2:], check=True)
elif c == "review": subprocess.run([sys.executable, P/"review.py", O/"extraction.json"], check=True)
elif c == "build": build()
