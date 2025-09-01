# -*- coding: utf-8 -*-
import gradio as gr
import pandas as pd
import datetime as dt
from pathlib import Path
import tempfile, json, re

# ===================== Common helpers =====================
ENCODINGS = ["utf-8-sig","utf-8","cp932","shift_jis","mac_roman"]

def read_csv_flex(path: Path):
    last_err = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc), enc
        except Exception as e:
            last_err = e
    raise last_err

# ===================== Domain knowledge =====================
CHECKLISTS = {
    "Prep": [
        "写真・間取・コピーの統一（出典/撮影可否の確認含む）",
        "掲載媒体の差異防止テンプレ配布（価格・面積・向き）",
        "告知事項の素案作成（設備不具合・近隣工事 など）",
    ],
    "Listing": [
        "ポータル文言統一・差異チェック（社名/免許/価格）",
        "匿名ティザー文（駅・面積・向き・共用の魅力）",
        "問い合わせ→内覧の動線（初動SLA/FAQ）",
    ],
    "Viewing": [
        "内覧スロット/鍵/動線/注意書きの確定",
        "共用部掲示の許可・撮影ルールの確認",
        "来訪者記録（氏名/時間/仲介/所感）",
    ],
    "Offer": [
        "回答期日・優先軸（価格/時期/残置・手付）の合意",
        "条件表（価格・手付・融資・引渡・違約条項）を共通フォーマットで",
        "本人確認・資金裏取りの段取り",
    ],
    "Finance": [
        "残債/抹消手続きの必要書類（委任状/印鑑証明 等）",
        "決済日・銀行予約・司法書士連携の確定",
        "決済時の精算表ドラフト作成",
    ],
    "Close": [
        "決済当日の持参物（鍵/書類/印鑑/本人確認）",
        "残置物・引渡時間・立会いの確認",
        "最終検針・清掃・駐車場/倉庫の扱い",
    ],
}
RISKS = {
    "Prep": ["掲載差異の発生", "告知漏れによるトラブル"],
    "Listing": ["価格/面積の不一致", "Q&A不足による内覧化率低下"],
    "Viewing": ["共用部ルール違反", "鍵・動線ミスによる苦情"],
    "Offer": ["口頭合意の曖昧化", "手付/違約条項の不一致"],
    "Finance": ["抹消手続きの期日未整合", "必要書類不足"],
    "Close": ["持参物不足", "引渡条件の解釈ズレ"],
}

# --- English equivalents (PoC-wide) ---
CHECKLISTS_EN = {
    "Prep": [
        "Unify photos/floor plan/copy (check sources and shooting permissions)",
        "Distribute anti-discrepancy template for listing fields (price/area/orientation)",
        "Draft disclosure items (equipment issues / nearby construction, etc.)",
    ],
    "Listing": [
        "Standardize portal wording & discrepancy check (company/license/price)",
        "Anonymous teaser copy (station/area/orientation/shared facilities)",
        "Path from inquiry to viewing (initial SLA/FAQ)",
    ],
    "Viewing": [
        "Fix viewing slots/keys/route/house rules",
        "Confirm HOA/management permission for notices; define photo policy",
        "Record visitors (name/time/agent/impressions)",
    ],
    "Offer": [
        "Agree on response deadline & priorities (price/timing/fixtures/deposit)",
        "Use a standard term sheet (price, deposit, financing, closing, default clauses)",
        "Plan KYC and funds verification",
    ],
    "Finance": [
        "List docs for lien release/cancellation (POA, seal certificate, etc.)",
        "Fix closing date, bank appointment, and judicial scrivener coordination",
        "Draft settlement statement",
    ],
    "Close": [
        "Closing-day checklist (keys/docs/ID/seal)",
        "Confirm remaining items, handover time, presence at walkthrough",
        "Final meter reading/cleaning/parking or storage handling",
    ],
}
RISKS_EN = {
    "Prep": ["Listing discrepancies", "Disclosure omissions causing trouble"],
    "Listing": ["Price/area mismatch", "Insufficient Q&A reduces viewing rate"],
    "Viewing": ["Common-area rule violations", "Complaints due to key/route mistakes"],
    "Offer": ["Ambiguity from verbal agreements", "Mismatch on deposit/default clauses"],
    "Finance": ["Deadline mismatch for cancellations", "Insufficient required documents"],
    "Close": ["Items missing on closing day", "Different interpretations of handover conditions"],
}

# --- JP→EN dictionary (exact phrases commonly seen in CSV) ---
JP2EN = {
    "売却検討を開始（要件整理）": "start exploring the sale (collect requirements)",
    "希望価格・引渡時期・残置物の方針メモ化": "draft target price, closing timing, and remaining items policy",
    "4社へ査定依頼（一般媒介を前提）": "request valuation from 4 agents (open listing)",
    "必要資料を送付・査定日程の確定": "send required documents and fix appraisal schedule",
    "一般媒介契約を4社と締結": "sign open listing agreements with four agents",
    "契約書署名・掲載指示の共有": "sign contracts and share listing instructions",
    "写真・間取・告知事項の準備": "prepare photos, floor plan, and disclosures",
    "写真選定／間取データ／告知素案の確定": "select photos, finalize floor plan data and disclosure draft",
    "掲載開始（ティザー含む）": "start listing (with teaser)",
    "文言統一・差異チェック・ファーストビュー最適化": "unify wording, check discrepancies, optimize lead photo/summary",
    "引越し業者の選定と予約": "select and book movers",
    "見積比較・搬出日の確定": "compare quotes and fix moving-out date",
    "ハウスクリーニングの実施": "perform house cleaning",
    "作業日・作業内容の確定": "fix work date and scope",
    "内覧準備（鍵・動線・掲示物）": "prepare for viewings (keys, route, notices)",
    "内覧開始の準備OK": "ready to start viewings",
    "内覧を開始": "start viewings",
    "スロット確定・案内配信・共用掲示許可": "fix slots, send notices, obtain HOA permission",
    "初週スロット≥6を確保": "secure ≥6 slots in the first week",
    "一次申込の受領（条件ヒア）": "receive initial offer (collect terms)",
    "価格/時期/残置/手付の希望を整理・本人確認": "organize preferences (price/timing/fixtures/deposit) and verify identity",
    "条件合意（価格・時期・残置・手付）": "agree on terms (price/timing/fixtures/deposit)",
    "条件表ドラフト合意": "agree on draft term sheet",
    "売買契約の締結": "execute the sales contract",
    "契約書署名捺印・手付受領": "sign the contract (with seal) and receive the deposit",
    "契約完了・手付入金確認": "contract executed; deposit received",
    "ローン本審査の申請": "apply for mortgage underwriting",
    "必要書類の提出・司法書士連携の準備": "submit required documents; prepare with judicial scrivener",
    "本審査申請完了": "underwriting application submitted",
    "ローン承認の取得": "obtain loan approval",
    "決済日・司法書士・銀行予約の確定": "fix closing date, scrivener, and bank appointment",
    "決済日程が確定": "closing schedule fixed",
    "決済・引渡（鍵・精算・立会い）": "closing & handover (keys/settlement/walkthrough)",
    "持参物確認・精算表確定・鍵引渡": "confirm items to bring, finalize settlement, hand over keys",
    "引渡完了（明け渡し）": "handover complete (vacant possession)",
    # success_criteria / action common
    "掲載準備OK": "ready to publish",
    "掲載完了": "listing completed",
    "搬出予約完了": "moving-out booked",
    "清掃完了（写真記録）": "cleaning completed (with photos)",
    "内覧開始の準備OK": "ready to start viewings",
    "初週スロット確保": "secured slots for the first week",
    "契約日確定": "contract date fixed",
    "契約完了": "contract executed",
    "本審査申請完了": "underwriting application submitted",
    "承認取得": "approval obtained",
    "決済日程確定": "closing date fixed",
    "引渡完了": "handover completed",
    "要件メモ作成・家族合意": "requirement memo completed; family alignment",
}

# --- JP→EN substring glossary (applied when exact match not found) ---
GLOSSARY = {
    "一般媒介契約": "open listing agreement",
    "専任媒介契約": "exclusive agency agreement",
    "専属専任媒介契約": "exclusive right-to-sell agreement",
    "ファーストビュー": "lead photo/summary",
    "ティザー": "teaser",
    "内覧スロット": "viewing slots",
    "案内配信": "send notices",
    "共用部掲示": "common-area notices",
    "管理": "management/HOA",
    "本人確認": "KYC",
    "資金裏取り": "funds verification",
    "仮審査": "pre-approval",
    "本審査": "underwriting (final approval)",
    "承認": "approval",
    "決済": "closing",
    "引渡": "handover",
    "抹消": "lien release",
    "残債": "outstanding loan balance",
    "司法書士": "judicial scrivener",
    "精算表": "settlement statement",
    "違約条項": "default clauses",
    "残置物": "remaining items/fixtures",
    "手付": "deposit (earnest money)",
    "立会い": "walkthrough",
    "鍵引渡": "key handover",
    "最終検針": "final meter reading",
    "清掃": "cleaning",
    "駐車場": "parking",
    "倉庫": "storage",
    "掲載差異": "listing discrepancy",
    "告知漏れ": "disclosure omission",
    "価格": "price",
    "時期": "timing",
    "面積": "area",
    "向き": "orientation",
    "駅": "station",
    "共用": "shared facilities",
    "撮影ルール": "photo policy",
    "注意書き": "house rules",
    "動線": "route",
    "鍵": "keys",
    "差異チェック": "discrepancy check",
    "問い合わせ": "inquiry",
    "内覧": "viewing",
    "申込": "offer",
    "申し込み": "offer",
    "契約": "contract",
    "銀行予約": "bank appointment",
    "決済日": "closing date",
    "持参物": "items to bring",
    "明け渡し": "vacant possession",
}

def localize_text(text: str, lang: str) -> str:
    """Return EN translation for common JP phrases; use substring glossary if needed."""
    s = str(text)
    if lang == "日本語":
        return s
    # exact match first
    if s in JP2EN:
        t = JP2EN[s]
    else:
        t = s
        # apply substring glossary (longer keys first)
        for k in sorted(GLOSSARY.keys(), key=len, reverse=True):
            if k in t:
                t = t.replace(k, GLOSSARY[k])
    # normalize punctuation/spaces
    t = (t.replace("（", "(").replace("）", ")")
           .replace("・", "/").replace("　"," ").strip())
    return t

# Stages and compass
STAGES = ["Prep","Listing","Viewing","Offer","Finance","Close"]
STAGE_JA = {
    "Prep":"準備フェーズ",
    "Listing":"掲載フェーズ（初動調整）",
    "Viewing":"内覧フェーズ",
    "Offer":"契約フェーズ（最終調整）",
    "Finance":"資金・本審査フェーズ",
    "Close":"決済・引渡フェーズ",
}
NEXT_HINT_JA = {
    "Prep":"査定・掲載の着手",
    "Listing":"内覧準備 → 内覧開始",
    "Viewing":"申込受領 → 条件整理",
    "Offer":"本審査申請 → 承認 → 決済日確定",
    "Finance":"決済準備 → 決済",
    "Close":"おつかれさまでした（引渡完了）",
}
STAGE_EN = {
    "Prep":"Preparation",
    "Listing":"Listing (early tuning)",
    "Viewing":"Viewings",
    "Offer":"Contract (finalizing)",
    "Finance":"Financing / Underwriting",
    "Close":"Closing / Handover",
}
NEXT_HINT_EN = {
    "Prep":"start valuation/listing",
    "Listing":"prepare viewings → start",
    "Viewing":"collect offers → align terms",
    "Offer":"apply for underwriting → approval → set closing date",
    "Finance":"prepare for closing → close",
    "Close":"all done (handover)",
}

def make_compass(row, lang="日本語"):
    import pandas as pd
    cat = str(row.get("category",""))
    desc = str(row.get("description",""))
    date_dt = row.get("date_dt") or pd.to_datetime(row.get("date"))
    try:
        pos = f"{STAGES.index(cat)+1}/{len(STAGES)}"
    except ValueError:
        pos = "–/–"
    when = pd.Timestamp(date_dt).date().isoformat()
    if lang == "日本語":
        stage = STAGE_JA.get(cat, cat)
        nxt = NEXT_HINT_JA.get(cat, "次の工程へ")
        return f"旅路 {pos}｜{stage}。{when} に『{desc}』— 次は {nxt}。"
    else:
        desc_en = localize_text(desc, "English")
        stage = STAGE_EN.get(cat, cat)
        nxt = NEXT_HINT_EN.get(cat, "next step")
        return f"Journey {pos} | {stage}. On {when}: “{desc_en}”. Next: {nxt}."

# ===================== Data loaders =====================
def load_events():
    p = Path(__file__).resolve().parents[1] / "data" / "events_sample.csv"
    df, enc = read_csv_flex(p)
    expected = ["event_id","date","actor","category","description","expected_action","success_criteria","risk_level"]
    miss = [c for c in expected if c not in df.columns]
    if miss:
        raise ValueError(f"CSV列不足: {miss}")
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date_dt"].isna().any():
        df.loc[df["date_dt"].isna(),"date_dt"] = pd.to_datetime(df.loc[df["date_dt"].isna(),"date"], format="%Y/%m/%d", errors="coerce")
    if df["date_dt"].isna().any():
        bad = df[df["date_dt"].isna()]["date"].unique().tolist()
        raise ValueError(f"日付を解釈できません（YYYY-MM-DD / YYYY/MM/DD）: {bad}")
    return df

def contacts_lookup(actor):
    p = Path(__file__).resolve().parents[1] / "data" / "contacts.csv"
    if p.exists():
        try:
            df, _ = read_csv_flex(p)
            rows = df[df["actor"]==actor]
            if not rows.empty:
                r = rows.iloc[0].to_dict()
                return r.get("to",""), r.get("cc",""), r.get("attachments","")
        except Exception:
            pass
    return "", "", ""

# ===================== ICS helpers =====================
def ics_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,")
    s = s.replace("\r\n", r"\n").replace("\n", r"\n")
    return s

def fold_ics_line(name: str, value: str) -> str:
    raw = f"{name}:{value}"
    out = []
    while len(raw) > 73:
        out.append(raw[:73])
        raw = " " + raw[73:]
    out.append(raw)
    return "\r\n".join(out)

def ics_for_event(event_id, title, date_iso, description=""):
    start = pd.to_datetime(date_iso).strftime("%Y%m%d")
    end = (pd.to_datetime(date_iso) + pd.Timedelta(days=1)).strftime("%Y%m%d")
    summary = ics_escape(title); desc = ics_escape(description)
    lines = [
        "BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//SellPM//PMOPlus//JP","BEGIN:VEVENT",
        f"UID:{event_id}@sellpm",
        f"DTSTAMP:{pd.Timestamp.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{start}", f"DTEND;VALUE=DATE:{end}",
        fold_ics_line("SUMMARY", summary), fold_ics_line("DESCRIPTION", desc) if desc else "DESCRIPTION:",
        "BEGIN:VALARM","TRIGGER:-P1D","ACTION:DISPLAY","DESCRIPTION:Reminder","END:VALARM",
        "END:VEVENT","END:VCALENDAR",
    ]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ics", mode="w", encoding="utf-8", newline="\r\n")
    tmp.write("\r\n".join(lines)); tmp.flush(); tmp.close()
    return tmp.name

# ===================== KPI (Calm mode) =====================
KPI_COLS = {"date":["date","日付"],"pv":["pv","views","閲覧"],
            "inq":["inquiries","inquiry","問合せ","問い合わせ"],
            "view":["viewings","viewing","内覧"],
            "offer":["offers","applications","申込","申し込み"]}

THRESHOLDS = {
    "resp_green": 0.06, "resp_yellow": 0.03,
    "view_green": 0.35, "view_yellow": 0.20,
    "offer_green": 0.15, "offer_yellow": 0.08,
}

def color_for(value, kind):
    if value is None:
        return ("#EEF2F7", "#D6DEE8", "#334155")
    if kind=="resp":
        if value >= THRESHOLDS["resp_green"]: return ("#EAF7EA", "#BFE5BF", "#145A32")
        if value >= THRESHOLDS["resp_yellow"]: return ("#FFF7E0", "#FFE08A", "#7A5D00")
        return ("#FDEAEA", "#F5B7B1", "#7B241C")
    if kind=="view":
        if value >= THRESHOLDS["view_green"]: return ("#EAF7EA", "#BFE5BF", "#145A32")
        if value >= THRESHOLDS["view_yellow"]: return ("#FFF7E0", "#FFE08A", "#7A5D00")
        return ("#FDEAEA", "#F5B7B1", "#7B241C")
    if kind=="offer":
        if value >= THRESHOLDS["offer_green"]: return ("#EAF7EA", "#BFE5BF", "#145A32")
        if value >= THRESHOLDS["offer_yellow"]: return ("#FFF7E0", "#FFE08A", "#7A5D00")
        return ("#FDEAEA", "#F5B7B1", "#7B241C")
    return ("#EEF2F7", "#D6DEE8", "#334155")

def read_kpi():
    p = Path(__file__).resolve().parents[1] / "data" / "kpi.csv"
    if not p.exists():
        return None, "kpi.csv がありません（data/kpi.csv を作成してください）"
    df, enc = read_csv_flex(p)
    cols = {c.lower(): c for c in df.columns}
    def col_for(keys): 
        for k in keys:
            if k.lower() in cols: return cols[k.lower()]
        return None
    c_date = col_for(KPI_COLS["date"]); c_pv = col_for(KPI_COLS["pv"])
    c_inq = col_for(KPI_COLS["inq"]); c_view = col_for(KPI_COLS["view"]); c_offer = col_for(KPI_COLS["offer"])
    miss = [name for name,c in [("date",c_date),("pv",c_pv),("inquiries",c_inq),("viewings",c_view),("offers",c_offer)] if c is None]
    if miss:
        return None, f"kpi.csv 列不足: {miss}"
    out = pd.DataFrame({
        "date": pd.to_datetime(df[c_date], errors="coerce"),
        "pv": pd.to_numeric(df[c_pv], errors="coerce").fillna(0).astype(int),
        "inquiries": pd.to_numeric(df[c_inq], errors="coerce").fillna(0).astype(int),
        "viewings": pd.to_numeric(df[c_view], errors="coerce").fillna(0).astype(int),
        "offers": pd.to_numeric(df[c_offer], errors="coerce").fillna(0).astype(int),
    }).dropna(subset=["date"]).sort_values("date")
    return out, enc

def kpi_cards_html(scope: pd.DataFrame, lang="日本語") -> str:
    pv = scope["pv"].sum(); inq = scope["inquiries"].sum()
    view = scope["viewings"].sum(); off = scope["offers"].sum()
    pct = lambda a,b: (a/b) if b>0 else None
    resp = pct(inq, pv); conv_view = pct(view, inq); conv_offer = pct(off, view)
    bg1, br1, tx1 = color_for(resp, "resp"); bg2, br2, tx2 = color_for(conv_view, "view")
    bg3, br3, tx3 = color_for(conv_offer, "offer"); bg4, br4, tx4 = ("#EEF2F7","#D6DEE8","#334155")
    fmt = lambda v: f"{v*100:.1f}%" if v is not None else "—"
    days = (scope["date"].max() - scope["date"].min()).days + 1 if not scope.empty else 0
    if lang=="English":
        labels = ["Response rate","Viewing conversion","Offer conversion","Elapsed days"]
        denom = [f"{inq} / {pv}", f"{view} / {inq}", f"{off} / {view}", f"{scope['date'].min().date() if not scope.empty else '—'} → {scope['date'].max().date() if not scope.empty else '—'}"]
    else:
        labels = ["反響率","内覧化率","申込率","経過日数"]
        denom = [f"{inq} / {pv}", f"{view} / {inq}", f"{off} / {view}", f"{scope['date'].min().date() if not scope.empty else '—'} → {scope['date'].max().date() if not scope.empty else '—'}"]
    return f"""
    <div style="display:flex; gap:12px; flex-wrap:wrap">
      <div style="flex:1; min-width:180px; padding:12px; border:1px solid {br1}; border-radius:10px; background:{bg1}; color:{tx1}">
        <div style="font-size:12px; opacity:0.9">{labels[0]}</div>
        <div style="font-size:28px; font-weight:700">{fmt(resp)}</div>
        <div style="font-size:12px; opacity:0.8; color:#111">{denom[0]}</div>
      </div>
      <div style="flex:1; min-width:180px; padding:12px; border:1px solid {br2}; border-radius:10px; background:{bg2}; color:{tx2}">
        <div style="font-size:12px; opacity:0.9">{labels[1]}</div>
        <div style="font-size:28px; font-weight:700">{fmt(conv_view)}</div>
        <div style="font-size:12px; opacity:0.8; color:#111">{denom[1]}</div>
      </div>
      <div style="flex:1; min-width:180px; padding:12px; border:1px solid {br3}; border-radius:10px; background:{bg3}; color:{tx3}">
        <div style="font-size:12px; opacity:0.9">{labels[2]}</div>
        <div style="font-size:28px; font-weight:700">{fmt(conv_offer)}</div>
        <div style="font-size:12px; opacity:0.8; color:#111">{denom[2]}</div>
      </div>
      <div style="flex:1; min-width:180px; padding:12px; border:1px solid {br4}; border-radius:10px; background:{bg4}; color:{tx4}">
        <div style="font-size:12px; opacity:0.9">{labels[3]}</div>
        <div style="font-size:28px; font-weight:700">{days} 日</div>
        <div style="font-size:12px; opacity:0.8; color:#111">{denom[3]}</div>
      </div>
    </div>"""

def kpi_aggregate(range_mode, lang="日本語"):
    df, enc = read_kpi()
    if df is None:
        msg = "読み込みエラー: " + enc if lang=="日本語" else ("Read error: " + enc)
        return msg, "", pd.DataFrame()
    today = pd.Timestamp(dt.date.today())
    key = norm_kpi_range(range_mode)
    if key == "30":
        start = today - pd.Timedelta(days=30); scope = df[df["date"] >= start]
    elif key == "month":
        start = pd.Timestamp(today.year, today.month, 1); scope = df[df["date"] >= start]
    else:
        scope = df.copy()
    if scope.empty:
        return ("対象期間にデータがありません" if lang=="日本語" else "No data for the selected range"), "", scope
    cards = kpi_cards_html(scope, lang=lang)
    return "", cards, scope

# ===================== Optional RAG =====================
def load_rag():
    p = Path(__file__).resolve().parents[1] / "data" / "rag_chunks.jsonl"
    if not p.exists():
        return []
    chunks = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line: continue
        try:
            chunks.append(json.loads(line))
        except Exception:
            continue
    return chunks

def tokenize(s: str):
    s = s.lower()
    s = re.sub(r"[^a-z0-9ぁ-んァ-ヶ一-龥ー]+", " ", s)
    toks = [t for t in s.split() if len(t)>=2]
    return toks

def retrieve_support(event_row, topk=3):
    chunks = load_rag()
    if not chunks:
        return "（根拠データが未設定です。`data/rag_chunks.jsonl` を用意するとここに要点が並びます）"
    q = " ".join([str(event_row.get("category","")), str(event_row.get("description","")), str(event_row.get("expected_action",""))])
    q_tokens = tokenize(q)
    if not q_tokens:
        return "（検索語がありません）"
    scores = []
    for c in chunks:
        text = c.get("text","")
        tokens = tokenize(text)
        score = sum(1 for t in tokens if t in q_tokens)
        if score>0:
            scores.append((score, c))
    if not scores:
        return "（該当する根拠は見つかりませんでした）"
    scores.sort(key=lambda x: x[0], reverse=True)
    top = scores[:topk]
    lines = []
    for s, c in top:
        src = c.get("source","note")
        page = c.get("page","")
        tag = c.get("tag","")
        lines.append(f"・{c.get('text','')}\n   └ 出典: {src}{(' p.'+str(page)) if page!='' else ''} {(' #'+tag) if tag else ''}")
    return "\n".join(lines)

# ===================== Bilingual UI helpers =====================
CHOICES_ACTION = ["今日以降 / From today", "すべて / All"]
CHOICES_KPI    = ["直近30日 / Last 30 days", "今月 / This month", "すべて / All"]

def is_from_today(val: str) -> bool:
    return ("今日以降" in val) or ("From today" in val)

def norm_kpi_range(val: str) -> str:
    if ("直近30日" in val) or ("Last 30" in val): return "30"
    if ("今月" in val) or ("This month" in val): return "month"
    return "all"

I18N = {
  "日本語": {
    "title": "## AI売却PMO（PoC） — Calm KPI + 根拠（RAG）※任意表示",
    "scope_label": "表示範囲",
    "lang_label": "言語",
    "reload": "再読み込み/集計",
    "summary": "重点イベント（上位3件・優先度順）",
    "table": "上位3件の詳細（編集はCSVで）",
    "selector": "生成対象（上位3から選択）",
    "accordion_hdr": "根拠（任意・静かな表示）",
    "chkbox": "根拠を表示する（RAG）",
    "support": "参考（Note要点などから抽出）",
    "generate": "パック生成（チェックリスト + メール + Slack + ICS）",
    "out": "出力（コピー可）",
    "dl_txt": "ダウンロード（.txt）",
    "dl_ics": "カレンダー（.ics）",
    "kpi_intro": "“水先案内人モード”：色は緑を多め・赤は最少。過度なアラートや自動コメントは出しません。",
    "kpi_scope": "集計範囲",
    "kpi_refresh": "KPI更新",
    "kpi_msg": "メッセージ（CALM）",
    "kpi_table": "集計対象の明細",
  },
  "English": {
    "title": "## AI Real Estate PMO (PoC) — Calm KPI + Evidence (RAG, optional)",
    "scope_label": "Scope",
    "lang_label": "Language",
    "reload": "Reload / Aggregate",
    "summary": "Top 3 Priority Events",
    "table": "Top 3 Details (edit via CSV)",
    "selector": "Target to generate",
    "accordion_hdr": "Evidence (optional, calm)",
    "chkbox": "Show evidence (RAG)",
    "support": "Reference (excerpts from notes)",
    "generate": "Generate pack (Checklist + Email + Slack + ICS)",
    "out": "Output (copyable)",
    "dl_txt": "Download (.txt)",
    "dl_ics": "Calendar (.ics)",
    "kpi_intro": "Pilot mode: mostly green, minimal red. No auto comments or alerts.",
    "kpi_scope": "Aggregation range",
    "kpi_refresh": "Refresh KPI",
    "kpi_msg": "Message (CALM)",
    "kpi_table": "Rows in scope",
  },
}

def set_ui_lang(lang, *_):
    t = I18N.get(lang, I18N["日本語"])
    return (
        gr.update(value=t["title"]),                                 # title_md
        gr.update(label=f'{t["scope_label"]} / Scope' if lang=="日本語" else t["scope_label"]),  # mode label
        gr.update(label=f'{t["lang_label"]} / Language' if lang=="日本語" else t["lang_label"]), # lang label
        gr.update(value=t["reload"]),                                # refresh btn text
        gr.update(label=t["summary"]),                               # summary label
        gr.update(label=t["table"]),                                 # table label
        gr.update(label=t["selector"]),                              # selector label
        gr.update(value=("### " + t["accordion_hdr"])),              # acc_hdr markdown
        gr.update(label=t["chkbox"]),                                # show_support label
        gr.update(label=t["support"]),                               # support_box label
        gr.update(value=t["generate"]),                              # generate button text
        gr.update(label=t["out"]),                                   # out textbox label
        gr.update(label=t["dl_txt"]),                                # dl_txt label
        gr.update(label=t["dl_ics"]),                                # dl_ics label
        gr.update(value=t["kpi_intro"]),                             # kpi_intro markdown
        gr.update(label=f'{t["kpi_scope"]} / Aggregation' if lang=="日本語" else t["kpi_scope"]), # range_mode label
        gr.update(value=t["kpi_refresh"]),                           # kpi_refresh text
        gr.update(label=t["kpi_msg"]),                               # kpi_msg label
        gr.update(label=t["kpi_table"]),                             # kpi_table label
    )

# ===================== Core logic =====================
def priority_score(row):
    risk_map = {"Low":1,"Medium":2,"High":3}
    risk = risk_map.get(str(row["risk_level"]), 2)
    days = max((row["date_dt"].date() - dt.date.today()).days, 0)
    time_factor = max(0.2, 1.0 - (days/60.0))
    return round(risk * 33 * time_factor)

def summary_top(df, mode_selected):
    today = dt.date.today()
    scope = df[df["date_dt"]>=pd.Timestamp(today)] if is_from_today(mode_selected) else df
    if scope.empty:
        return "該当なし。CSV日付を未来にするか表示範囲を『すべて』へ。", pd.DataFrame()
    tmp = scope.copy()
    tmp["priority"] = tmp.apply(priority_score, axis=1)
    tmp = tmp.sort_values(["priority","date_dt","risk_level"], ascending=[False,True,True]).head(3)
    lines = []
    for r in tmp.itertuples(index=False):
        when = pd.Timestamp(r.date_dt).date().isoformat()
        lines.append(f"- {when} [{r.category}/{r.risk_level}] {r.description} → {r.expected_action}  (Priority {r.priority})")
    return "\n".join(lines), tmp

def build_pack(row, lang):
    actor = str(row["actor"]); cat = str(row["category"])
    date_dt = row.get("date_dt") or pd.to_datetime(row.get("date"))
    date = pd.Timestamp(date_dt).date().isoformat()
    desc = str(row["description"]); exp = str(row["expected_action"]); suc = str(row["success_criteria"])
    due48 = (pd.Timestamp(date_dt).date() - pd.Timedelta(days=2)).isoformat()

    # Journey compass
    compass = make_compass(row, lang)

    # Checklist & risks (by lang)
    if lang == "日本語":
        checklist = CHECKLISTS.get(cat, ["前提確認（関係者・目的・期限）","ダブルチェックの設定"])
        risks = RISKS.get(cat, ["関係者間の前提ズレ","期日直前の修正"])
    else:
        checklist = CHECKLISTS_EN.get(cat, ["Prerequisites (stakeholders/objective/deadline)","Set up double-checks"])
        risks = RISKS_EN.get(cat, ["Ambiguity among stakeholders","Late adjustments near the deadline"])

    to, cc, attach = contacts_lookup(actor)

    if lang=="日本語":
        subject = f"{cat} / {desc[:18]}… 進行のお願い（{date} まで）"
        body = f"""件名: {subject}
To: {to or '＜宛先メール＞'}
Cc: {cc or '＜共有者＞'}

{actor} 各位
※ {compass}
以下のとおりご対応をお願いします。
- 目的: {desc}
- 依頼: {exp}
- 期限: {date}（可能であれば {due48} までの事前確認）
- 完了条件: {suc}
- 参考: チェックリスト（下記）／想定リスク（下記）
添付: {attach or '＜必要資料＞'}

PMO"""
        slack = f"[{cat}] {desc} → {exp} ｜期限 {date}（事前確認 {due48}）｜担当 {actor}"
        header = "旅路コンパス\n" + compass + "\n\n" + "チェックリスト\n- " + "\n- ".join(checklist)
        risksec = "\n\nリスク/確認\n- " + "\n- ".join(risks)
        out_text = header + risksec + "\n\nメール文例（コピー可）\n" + body + "\n\nSlack/チャット用短文\n" + slack
        memo = f"{cat} | 目的: {desc}\\n依頼: {exp}\\n完了条件: {suc}\\n担当: {actor}\\n事前確認: {due48}\\n旅路: {compass}"
    else:
        desc_en = localize_text(desc, "English")
        exp_en  = localize_text(exp, "English")
        suc_en  = localize_text(suc, "English")

        subject = f"{cat} — action needed by {date}: {desc_en[:32]}"
        body = f"""Subject: {subject}
To: {to or '<recipient>'}
Cc: {cc or '<stakeholders>'}

Dear {actor},
* {compass}
Please proceed as follows:
- Goal: {desc_en}
- Action: {exp_en}
- Deadline: {date} (early check by {due48})
- Done: {suc_en}
- Ref: Checklist (below) / Risks (below)
Attachments: {attach or '<attachments>'}

PMO"""
        slack = f"[{cat}] {desc_en} → {exp_en} | due {date} (precheck {due48}) | owner {actor}"
        header = "Journey compass\n" + compass + "\n\n" + "Checklist\n- " + "\n- ".join(checklist)
        risksec = "\n\nRisks / Checks\n- " + "\n- ".join(risks)
        out_text = header + risksec + "\n\nEmail Draft\n" + body + "\n\nChat Snippet\n" + slack
        memo = f"{cat} | Goal: {desc_en}\\nAction: {exp_en}\\nDone: {suc_en}\\nOwner: {actor}\\nPrecheck: {due48}\\nJourney: {compass}"

    ics_path = ics_for_event(str(row["event_id"]), f"{cat}: {desc}", date, description=memo)
    txt = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    txt.write(out_text); txt.flush(); txt.close()
    return out_text, txt.name, ics_path

# ===================== UI actions =====================
def init_action(mode):
    df = load_events()
    summary, top = summary_top(df, mode)
    table = top.drop(columns=["date_dt"]) if not top.empty else top
    options = [f"{i}｜{r.event_id}: {r.category} / {str(r.description)[:24]}…" for i, r in enumerate(top.itertuples(index=False))] if not top.empty else []
    return summary, table, gr.update(choices=options, value=(options[0] if options else None))

def generate_pack(mode, lang, selector, show_support):
    df = load_events()
    _, top = summary_top(df, mode)
    if top.empty:
        return ("該当なし。" if lang=="日本語" else "No items."), None, None, ("（根拠データがありません）" if lang=="日本語" else "(No evidence data)")
    try:
        idx = int((selector or "0").split("｜")[0])
    except Exception:
        idx = 0
    row = top.iloc[idx]
    out_text, txt_path, ics_path = build_pack(row, lang)
    support = retrieve_support(row) if show_support else ""
    return out_text, txt_path, ics_path, support

# ===================== Build UI =====================
with gr.Blocks() as demo:
    title_md = gr.Markdown("## AI売却PMO（PoC） — Calm KPI + 根拠（RAG）※任意表示")
    with gr.Tabs():
        with gr.TabItem("アクション / Action"):
            with gr.Row():
                mode = gr.Radio(CHOICES_ACTION, value=CHOICES_ACTION[0], label="表示範囲 / Scope", scale=2)
                lang = gr.Radio(["日本語","English"], value="日本語", label="言語 / Language", scale=1)
                refresh = gr.Button("再読み込み/集計", scale=1)

            summary = gr.Textbox(label="重点イベント（上位3件・優先度順）", lines=6)
            table = gr.Dataframe(label="上位3件の詳細（編集はCSVで）")
            selector = gr.Dropdown(label="生成対象（上位3から選択）", choices=[])
            with gr.Accordion("Evidence / 根拠（optional / 任意）", open=False):
                acc_hdr = gr.Markdown("### 根拠（任意・静かな表示）")
                show_support = gr.Checkbox(label="根拠を表示する（RAG）", value=False)
                support_box = gr.Textbox(label="参考（Note要点などから抽出）", lines=8)

            generate_btn = gr.Button("パック生成（チェックリスト + メール + Slack + ICS）")
            out = gr.Textbox(label="出力（コピー可）", lines=20)
            dl_txt = gr.File(label="ダウンロード（.txt）")
            dl_ics = gr.File(label="カレンダー（.ics）")

            refresh.click(init_action, inputs=mode, outputs=[summary, table, selector])
            demo.load(init_action, inputs=mode, outputs=[summary, table, selector])

        with gr.TabItem("KPI"):
            kpi_intro = gr.Markdown("“水先案内人モード”：色は緑を多め・赤は最少。過度なアラートや自動コメントは出しません。")
            range_mode = gr.Radio(CHOICES_KPI, value=CHOICES_KPI[0], label="集計範囲 / Aggregation")
            kpi_refresh = gr.Button("KPI更新")
            kpi_msg = gr.Textbox(label="メッセージ（CALM）", lines=1)
            kpi_cards = gr.HTML()
            kpi_table = gr.Dataframe(label="集計対象の明細")

            kpi_refresh.click(lambda r, l: kpi_aggregate(r, l), inputs=[range_mode, lang], outputs=[kpi_msg, kpi_cards, kpi_table])
            demo.load(lambda r, l: kpi_aggregate(r, l), inputs=[range_mode, lang], outputs=[kpi_msg, kpi_cards, kpi_table])

    # Language change updates labels/texts across UI
    lang.change(
        set_ui_lang, inputs=[lang],
        outputs=[title_md, mode, lang, refresh, summary, table, selector,
                 acc_hdr, show_support, support_box, generate_btn,
                 out, dl_txt, dl_ics,
                 kpi_intro, range_mode, kpi_refresh, kpi_msg, kpi_table]
    )

    # Generate pack action (needs both mode and lang)
    generate_btn.click(generate_pack, inputs=[mode, lang, selector, show_support], outputs=[out, dl_txt, dl_ics, support_box])

    gr.Markdown("※ `data/rag_chunks.jsonl`（1行1JSON）を置くと、アクション選択時に落ち着いた“根拠”抜粋を表示します。 / Place `data/rag_chunks.jsonl` to show calm evidence.")

if __name__ == "__main__":
    print("Launching Gradio on http://127.0.0.1:7860 ...")
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
