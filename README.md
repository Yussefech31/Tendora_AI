# INDUSERV – Pipeline Local d'Extraction & Chiffrage d'Appels d'Offres (CDC / RFQ)

Système d'automatisation et de structuration d'appels d'offres industriels (Cahiers des Charges / RFQ) conçu pour opérer **100% en local** sur la machine de l'utilisateur (confidentialité totale, zéro coût marginal d'API), avec option d'accélération Cloud via Groq.

Le pipeline lit les documents PDF (numériques ou scannés avec OCR local), extrait avec précision les données techniques et commerciales à l'aide d'un LLM contraint par schéma JSON, effectue une vérification anti-hallucination mot-à-mot, applique une porte de contrôle humain, et remplit de manière déterministe les gabarits Excel (`CA.xlsx`) et Word (`TCO.docx`) sans jamais altérer les formules de calcul.

---

## Architecture du Pipeline

```text
[PDF / CDC / RFQ] (input/)
       │
       ▼
1. INGESTION (pipeline/ingest.py)
   ├── Extraction native texte & tableaux (pdfplumber)
   └── OCR local haute précision si scanné (rapidocr / ocrmac)
       │
       ▼  output/pages.json
2. EXTRACTION LLM (pipeline/extract.py)
   ├── Schéma JSON strict (schemas/cdc.schema.json)
   ├── Vérification anti-hallucination mot-à-mot (source quote)
   └── Normalisation automatique & bilinguisme technique (FR / EN)
       │
       ▼  output/extraction.json
3. REVUE HUMAINE (pipeline/review.py)
   └── Tableau de contrôle des clauses contractuelles & délais (binding)
       │
       ▼
4. GÉNÉRATION DES OFFRES (pipeline/fill_excel.py & fill_docx.py)
   ├── output/CA.xlsx (formules =ROUNDUP, =SUM, Incoterm CFR intacts)
   └── output/TCO.docx (offre technico-commerciale prête pour soumission)
```

---

## Installation

### 1. Cloner le dépôt et créer l'environnement virtuel
```powershell
# Cloner le dépôt
git clone <URL_DU_REPO>
cd cdc_local

# Créer et activer le venv Python
python -m venv .venv
.venv\Scripts\activate   # Sur Windows
# source .venv/bin/activate  # Sur macOS / Linux

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Configuration des modèles LLM

Copiez `.env.example` en `.env` :
```powershell
Copy-Item .env.example .env
```

#### Option A : Exécution 100% Locale avec Ollama (Recommandé en production)
1. Installez [Ollama](https://ollama.com).
2. Téléchargez le modèle adapté à votre matériel :
   ```bash
   # Pour machine de test CPU / portable standard :
   ollama pull qwen2.5:1.5b

   # Pour MacBook M-Series (16 Go - 128 Go) :
   ollama pull qwen2.5:14b
   # ou pour une précision maximale sur 128 Go :
   ollama pull qwen2.5:32b
   ```
3. Dans votre `.env` :
   ```ini
   USE_GROQ=0
   LLM_API_URL=http://localhost:11434/v1/chat/completions
   LLM_MODEL=qwen2.5:1.5b
   ```

#### Option B : Exécution Cloud ultra-rapide (Groq)
Pour des tests instantanés (2 secondes) avec Qwen 27B :
```ini
USE_GROQ=1
GROQ_API_KEY=gsk_votre_cle_groq
```

---

## Utilisation

Le script orchestrateur `run.py` gère toutes les étapes :

### Étape 0 : Auto-test déterministe (sans LLM)
Vérifie la conformité des gabarits Excel et Word en 2 secondes :
```powershell
python run.py selftest
```

### Étape 1 : Ingestion du Cahier des Charges
Convertit le PDF en corpus structuré :
```powershell
python run.py ingest input/RFQ_26020021.pdf
```
*(Si omis, l'étape suivante ingère automatiquement le premier PDF présent dans `input/`).*

### Étape 2 : Extraction intelligente
Extrait les métadonnées et la liste des articles avec spécifications bilingues :
```powershell
python run.py extract
```

### Étape 3 : Revue humaine de conformité
Affiche le tableau des points de vigilance contractuels :
```powershell
python run.py review
```

### Étape 4 : Génération des documents de cotation
Construit le tableau de calcul Excel et le Word commercial :
```powershell
python run.py build --force
```

Les documents générés se trouvent dans le dossier `output/` :
* `output/CA.xlsx` : tableau de cotation prêt pour saisie des prix d'achat en colonne E.
* `output/TCO.docx` : proposition commerciale complète mise en page.

---

## Structure du Répertoire

```text
├── input/                  # PDF d'appels d'offres / CDC à traiter
├── output/                 # Documents générés (ignorés par git)
├── pipeline/
│   ├── ingest.py           # Ingestion PDF & OCR
│   ├── extract.py          # Extraction contrainte LLM & anti-hallucination
│   ├── review.py           # Interface de contrôle des clauses
│   ├── fill_excel.py       # Injection sécurisée dans CA_modele.xlsx
│   └── fill_docx.py        # Fusion documentaire dans TCO_modele.docx
├── samples/                # Jeux de données d'exemple pour tests unitaires
├── schemas/                # Schémas de validation JSON
├── templates/              # Gabarits industriels maîtres (Excel & Word)
├── run.py                  # CLI orchestrateur principal
├── requirements.txt        # Dépendances Python
├── .env.example            # Gabarit de configuration
└── .gitignore              # Fichiers exclus du versionnement
```

---

## Déploiement Cible (MacBook M5 Max 128 Go)

Sur machine Apple Silicon avec mémoire unifiée :
1. OCR natif avec accélération Neural Engine via `ocrmac` (`pip install ocrmac`).
2. Moteur LLM local Metal avec `mlx-lm` ou Ollama :
   ```bash
   ollama run qwen2.5:32b
   ```
   Débit mesuré : **50 à 80+ tokens/seconde**, permettant une extraction complète en **moins de 4 secondes** sans aucune dépendance extérieure.
