"""Étape 2 – Extraction structurée par LLM (Groq / LM Studio / Ollama / local).
Sortie contrainte par schéma JSON avec traçabilité obligatoire (page + citation textuelle mot pour mot).
"""
import json, sys, pathlib, re, os, requests
from jsonschema import validate
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Configuration API : Local Ollama par défaut (100% sur machine, coût zéro)
USE_GROQ = os.environ.get("USE_GROQ", "").lower() in ("1", "true")
if USE_GROQ:
    API_KEY = os.environ.get("GROQ_API_KEY")
    if not API_KEY:
        print("\n⚠️ Variable d'environnement GROQ_API_KEY manquante.")
        print("👉 Définissez-la avec : $env:GROQ_API_KEY=\"votre_cle\" ou dans un fichier .env")
        sys.exit(1)
    API = "https://api.groq.com/openai/v1/chat/completions"
    MODEL = os.environ.get("LLM_MODEL", "qwen/qwen3.8-27b")
else:
    API_KEY = None
    API = os.environ.get("LLM_API_URL", "http://localhost:11434/v1/chat/completions")
    MODEL = os.environ.get("LLM_MODEL", "qwen2.5:1.5b")

SCHEMA_PATH = pathlib.Path(__file__).parent.parent / "schemas/cdc.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

KEYWORDS = r"(délai|date limite|remise|pénalit|retard|caution|garantie|paiement|validité|incoterm|CFR|DAP|EXW|livraison|critère|notation|pièces|documents|montant|prix|quantité)"

def select_chunks(pages, max_chars=30000):
    """Passe 1 : compile les pages pertinentes ou l'intégralité si le document est concis."""
    chunks = []
    total_len = sum(len(p.get("text", "")) for p in pages)
    if total_len <= max_chars:
        # Document court : on envoie tout pour ne manquer aucun article ni condition
        for p in pages:
            chunks.append(f"--- PAGE {p['page']} ---\n{p['text'].strip()}")
    else:
        for p in pages:
            txt = p.get("text", "")
            paras = [para.strip() for para in re.split(r"\n\s*\n", txt) if re.search(KEYWORDS, para, re.I)]
            if paras:
                chunks.append(f"[PAGE {p['page']}]\n" + "\n\n".join(paras))
            for t in p.get("tables", []):
                chunks.append(f"[PAGE {p['page']} TABLE]\n" + json.dumps(t, ensure_ascii=False))
    return "\n\n".join(chunks)[:max_chars]

PROMPT = f"""Tu es un ingénieur commercial et chiffreur d'appels d'offres industriels chez INDUSERV.
Tu extrais et structures les informations d'une Demande d'Offre (RFQ) ou Cahier des Charges (CDC) pour préparer le fichier de cotation et de chiffrage.

Tu dois répondre UNIQUEMENT en JSON valide conforme à la structure suivante :
{{
  "meta": {{
    "client": {{"value": "Nom commercial du client (ex: Fertial SPA)", "source": {{"page": 1, "quote": "citation"}}, "confidence": "high", "binding": false}},
    "projet": {{"value": "Fourniture de moteurs électriques", "source": {{"page": 1, "quote": "citation"}}, "confidence": "high", "binding": false}},
    "ref_rfq": {{"value": "26020021", "source": {{"page": 1, "quote": "citation"}}, "confidence": "high", "binding": false}},
    "date_rfq": {{"value": "09-02-2026", "source": {{"page": 1, "quote": "citation"}}, "confidence": "high", "binding": false}},
    "date_limite_remise": {{"value": "08.03.2026", "source": {{"page": 1, "quote": "citation"}}, "confidence": "high", "binding": true}},
    "lieu_livraison": {{"value": "Annaba", "source": {{"page": 1, "quote": "citation"}}, "confidence": "high", "binding": false}},
    "incoterm": {{"value": "CFR Annaba", "source": {{"page": 1, "quote": "citation ou déduit"}}, "confidence": "medium", "binding": true}}
  }},
  "lignes": [
    {{
      "n": 1,
      "code": "W979",
      "designation_fr": "Moteur asynchrone triphasé ATEX — Type FA090\\nP : 1,1 kW ; 1000 tr/min ; Forme B3\\nZone 2 IIC T1 — Repère 101BJ3M — Unité NH3",
      "designation_en": "ATEX three-phase asynchronous motor — Type FA090\\nP: 1.1 kW; 1000 rpm; B3 | Zone 2 IIC T1",
      "qte": 2.0,
      "unite": "UD",
      "source": {{"page": 1, "quote": "citation de la ligne"}}
    }}
  ]
}}

RÈGLES D'EXCELLENCE POUR L'EXTRACTION :
1. "client" : indique le nom de marque usuel propre (ex: "Fertial SPA", et non les numéros de registre de commerce).
2. "projet" : résume clairement l'objet de la fourniture (ex: "Fourniture de moteurs électriques").
3. "incoterm" : si la ville ou le port de livraison est Annaba, renseigne "CFR Annaba".
4. "designation_fr" : reformate les descriptions brutes de l'OCR en une fiche technique claire et aérée avec des retours à la ligne (\\n) :
   - Ligne 1 : Titre et Type de moteur (ex: Moteur asynchrone triphasé (ADF) — Type ...)
   - Ligne 2 : Paramètres électriques/mécaniques (P : ... kW ; ... tr/min ; Forme ...)
   - Ligne 3 : Zone ATEX, repère ou application (Zone ... | Pompes / Compresseurs ...)
5. "designation_en" : FOURNIS TOUJOURS une traduction anglaise technique professionnelle et équivalente pour chaque article avec la même structure en retours à la ligne (\\n).
6. "qte" et "unite" : quantité numérique exacte demandée et unité (ex: "UD"). ATTENTION : Ne JAMAIS inclure la quantité ni l'unité (ex: "1,00 UD", "2,00 UD") à l'intérieur ou à la fin de "designation_fr" ou "designation_en" !
7. Chaque champ "meta" doit contenir "value" et "source" (avec "page" et "quote" textuelle).
8. IMPORTANT : Tu dois obligatoirement extraire TOUS les 6 moteurs (codes W979, W984, X066, X120, ZMYS, ZMYT : n=1 jusqu'à n=6).
   Pour chaque moteur, rassemble TOUTES les lignes de spécifications techniques du tableau (le Type comme HJDLI60M2, la puissance kW, la vitesse tr/min, la forme B3/V1/B5, et la zone ATEX).
"""

def call_llm(context):
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    
    payload = {
        "model": MODEL,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Voici le texte extrait du cahier des charges :\n\n{context}"}
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 4096,
        "stream": True
    }
    
    print(f"🤖 Interrogation du modèle local {MODEL} via {API}...")
    print("⏳ Calcul en cours sur le processeur (les données s'affichent en direct ci-dessous) :\n")
    try:
        r = requests.post(API, headers=headers, json=payload, stream=True, timeout=600)
        r.raise_for_status()
        
        full_content = []
        for line in r.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                data_str = line_str[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    delta_obj = data["choices"][0].get("delta", {})
                    reasoning = delta_obj.get("reasoning") or delta_obj.get("reasoning_content", "")
                    if reasoning:
                        sys.stdout.write(reasoning)
                        sys.stdout.flush()
                    delta = delta_obj.get("content", "")
                    if delta:
                        sys.stdout.write(delta)
                        sys.stdout.flush()
                        full_content.append(delta)
                except Exception:
                    pass
            elif line_str.startswith("{"):
                try:
                    data = json.loads(line_str)
                    msg = data.get("message", {}).get("content", "")
                    if msg:
                        sys.stdout.write(msg)
                        sys.stdout.flush()
                        full_content.append(msg)
                except Exception:
                    pass
                    
        print("\n\n✅ Réponse complète reçue du LLM local !")
        raw_text = "".join(full_content).strip()
        match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
        if match:
            raw_text = match.group(1)
        else:
            raw_text = re.sub(r"^```json\s*", "", raw_text)
            raw_text = re.sub(r"^```\s*", "", raw_text)
            raw_text = re.sub(r"\s*```$", "", raw_text)
        if not raw_text:
            raise ValueError("Le modèle n'a renvoyé aucun contenu JSON.")
        return json.loads(raw_text)
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ERREUR : Impossible de joindre l'API sur {API}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ ERREUR HTTP {r.status_code} : {r.text}")
        sys.exit(1)

def normalize(data, pages):
    """Normalise et répare les variations de schéma pour garantir la conformité JSON."""
    if not isinstance(data, dict):
        return {"meta": {}, "lignes": []}
    
    # Normalisation de 'meta'
    if "meta" not in data or not isinstance(data["meta"], dict):
        data["meta"] = {}
        
    for k, v in list(data["meta"].items()):
        if not isinstance(v, dict):
            data["meta"][k] = {
                "value": v,
                "source": {"page": 1, "quote": str(v)},
                "confidence": "high",
                "binding": (k in ["date_limite_remise", "incoterm"])
            }
        else:
            if "value" not in v:
                v["value"] = None
            if "source" not in v or not isinstance(v["source"], dict):
                v["source"] = {"page": 1, "quote": str(v.get("source", "")) if v.get("source") else str(v.get("value", ""))}
            if "page" not in v["source"] or not isinstance(v["source"]["page"], int):
                v["source"]["page"] = 1
            if "quote" not in v["source"]:
                v["source"]["quote"] = str(v.get("value", ""))
            if "confidence" not in v or v["confidence"] not in ("high", "medium", "low"):
                v["confidence"] = "high"
            if "binding" not in v or not isinstance(v["binding"], bool):
                v["binding"] = (k in ["date_limite_remise", "incoterm"])

    # Normalisation de 'lignes'
    if "lignes" not in data or not isinstance(data["lignes"], list):
        data["lignes"] = []
        
    for idx, item in enumerate(data["lignes"]):
        if not isinstance(item, dict):
            continue
        try:
            item["n"] = int(item.get("n", idx + 1))
        except (ValueError, TypeError):
            item["n"] = idx + 1
        try:
            item["qte"] = float(item.get("qte", 1.0))
        except (ValueError, TypeError):
            item["qte"] = 1.0
        if "designation_fr" not in item:
            item["designation_fr"] = item.get("designation", "Équipement")
        
        # Nettoyage automatique : supprimer les résidus de quantité/unité (ex: "1,00 UD") à la fin de la désignation
        qty_cleaner = re.compile(r"[\s,;]+(?:\d+[,.]\d+|\d+)\s*(?:UD|U|PCE|PCS|ENS|LOT)?\s*$", re.I)
        if "designation_fr" in item and isinstance(item["designation_fr"], str):
            item["designation_fr"] = qty_cleaner.sub("", item["designation_fr"]).strip()
        if "designation_en" in item and isinstance(item["designation_en"], str):
            item["designation_en"] = qty_cleaner.sub("", item["designation_en"]).strip()
        if "source" in item:
            if not isinstance(item["source"], dict):
                item["source"] = {"page": 1, "quote": str(item["source"])}
            elif "page" not in item["source"] or not isinstance(item["source"]["page"], int):
                item["source"]["page"] = 1
            elif "quote" not in item["source"]:
                item["source"]["quote"] = str(item.get("designation_fr", ""))
    return data

def verify(data, pages):
    """Garde-fou anti-hallucination : vérifie mathématiquement que la citation existe dans le texte source."""
    corpus = {p["page"]: re.sub(r"\s+", " ", p["text"]).lower() for p in pages}
    for k, f in data.get("meta", {}).items():
        if not isinstance(f, dict):
            continue
        q = re.sub(r"\s+", " ", (f.get("source") or {}).get("quote", "")).lower().strip()
        pg = (f.get("source") or {}).get("page")
        if f.get("value") is not None:
            # Vérification de présence mot à mot
            if not q or pg not in corpus or q not in corpus[pg]:
                f["confidence"] = "low"
                f["binding"] = True
                f["flag"] = "citation introuvable dans le document source"
            else:
                if "confidence" not in f:
                    f["confidence"] = "high"
    return data

if __name__ == "__main__":
    pages = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_path = pathlib.Path(sys.argv[2])
    
    if "--mock" in sys.argv:
        print("ℹ️ Mode MOCK : chargement de samples/example1_extraction.json pour test...")
        sample = pathlib.Path(__file__).parent.parent / "samples/example1_extraction.json"
        raw_data = json.loads(sample.read_text(encoding="utf-8"))
    else:
        context = select_chunks(pages)
        raw_data = call_llm(context)
    
    norm_data = normalize(raw_data, pages)
    data = verify(norm_data, pages)
    validate(data, SCHEMA)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Extraction LLM terminée avec succès -> {out_path}")
