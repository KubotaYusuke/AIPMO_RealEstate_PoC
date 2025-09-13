## Hackathon submission (Tokyo AI Festival 2025)

- Status: submitted on **2025-09-10**; attending **Demo Day (Sep 13)** as observer.
- 4-min demo video: <https://www.youtube.com/watch?v=2EWPqylrXTA&t=15s>
- Slide deck (PDF): ./assets/slides/AIPMO_PoC_slides_v010.pdf
- Release tag: **v0.1.0**

---

## What this PoC does (1-minute read)

**AI as a calm “pilot” (PMO)** for first-time real-estate sellers.  
It quietly shows **where you are** and **the next single action**, without alarm fatigue.

- **Action → Pack:** Journey compass + checklist + risks + email draft + Slack snippet + **.ics** (calendar memo includes key points)
- **KPI (Calm):** green-heavy / minimal red to reduce anxiety; alerts only when truly risky
- **Optional “Evidence”:** brief references (RAG), shown only when needed

---

## Story & How-to (EN)

- Long-form note (EN): **[Selling a Condo with AI as PMO — Story & Playbook](https://note.com/usekbota/n/n580a95f811f3)**
  > Why “calm mode” matters, how the journey compass guides decisions, and a step-by-step walk-through.
- (JP preview available separately)

---

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app/app.py  # http://127.0.0.1:7860

# AI Real Estate PMO (PoC)

Bilingual Gradio app that guides first‑time home sellers through a stepwise journey (Prep → Listing → Viewing → Offer → Finance → Close).
Calm KPI cards (green‑heavy thresholds), pack generation (Checklist + Email + Slack + ICS), and optional Evidence (RAG).

## Features
- 🇯🇵/🇬🇧 toggle switches **UI and outputs**.
- **Pack generator**: checklist, risks, email draft, chat snippet, and `.ics` calendar.
- **Calm KPI**: response/viewing/offer rates with gentle thresholds.
- **Evidence (optional)**: show note snippets via `data/rag_chunks.jsonl`.

## Project layout
```
AIPMO_RealEstate_PoC/
├── app/
│   └── app.py                 # main Gradio app
├── data/
│   ├── events_sample.csv      # required: event timeline
│   ├── contacts.csv           # optional: actor → to/cc/attachments (ignored by git)
│   ├── kpi.csv                # optional: KPI timeseries (ignored by git)
│   └── rag_chunks.jsonl       # optional: RAG evidence (ignored by git)
└── README.md
```

## Requirements
- Python 3.10+
- macOS/Windows/Linux

## Quick start
```bash
cd AIPMO_RealEstate_PoC
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install gradio pandas pyyaml
python app/app.py
# Open http://127.0.0.1:7860
```

## CSV schema (events_sample.csv)
Columns (header row required):
```
event_id,date,actor,category,description,expected_action,success_criteria,risk_level
E101,2025-07-01,Seller,Prep,売却検討を開始（要件整理）,要件メモ作成・家族合意,掲載準備OK,Low
...
```
- `date` accepts `YYYY-MM-DD` or `YYYY/MM/DD`.

## KPI (data/kpi.csv)
Columns: `date,pv,inquiries,viewings,offers` (any case).

## Evidence (data/rag_chunks.jsonl)
One JSON per line:
```
{"text":"Use a standard term sheet to avoid verbal ambiguity","source":"MyNote","tag":"offer"}
```

## English translations
- Exact phrases → `JP2EN` dictionary
- Substrings → `GLOSSARY`
Add entries in `app/app.py` and restart.

## License
MIT (or choose your own before publishing).

## Release v0.1.0
- Initial PoC demo (tagged).
