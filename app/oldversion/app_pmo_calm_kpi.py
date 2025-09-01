# -*- coding: utf-8 -*-
import gradio as gr
import pandas as pd
import datetime as dt
from pathlib import Path
import tempfile

# ---------------- Common helpers ----------------
ENCODINGS = ["utf-8-sig","utf-8","cp932","shift_jis","mac_roman"]

def read_csv_flex(path: Path):
    last_err = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc), enc
        except Exception as e:
            last_err = e
    raise last_err

# ---------------- Action (packs) ----------------
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
        "回答期日・優先軸（価格/時期/残置/手付）の合意",
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

def priority_score(row):
    risk_map = {"Low":1,"Medium":2,"High":3}
    risk = risk_map.get(str(row["risk_level"]), 2)
    days = max((row["date_dt"].date() - dt.date.today()).days, 0)
    time_factor = max(0.2, 1.0 - (days/60.0))
    return round(risk * 33 * time_factor)

def summary_top(df, mode):
    today = dt.date.today()
    scope = df[df["date_dt"]>=pd.Timestamp(today)] if mode=="今日以降" else df
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

def build_pack(row, lang):
    actor = str(row["actor"]); cat = str(row["category"])
    date_dt = row.get("date_dt") or pd.to_datetime(row.get("date"))
    date = pd.Timestamp(date_dt).date().isoformat()
    desc = str(row["description"]); exp = str(row["expected_action"]); suc = str(row["success_criteria"])
    due48 = (pd.Timestamp(date_dt).date() - pd.Timedelta(days=2)).isoformat()

    checklist = CHECKLISTS.get(cat, ["前提確認（関係者・目的・期限）", "ダブルチェックの設定"])
    risks = RISKS.get(cat, ["関係者間の前提ズレ","期日直前の修正"])
    to, cc, attach = contacts_lookup(actor)

    if lang=="日本語":
        subject = f"{cat} / {desc[:18]}… 進行のお願い（{date} まで）"
        body = f"""件名: {subject}
To: {to or '＜宛先メール＞'}
Cc: {cc or '＜共有者＞'}

{actor} 各位
以下のとおりご対応をお願いします。
- 目的: {desc}
- 依頼: {exp}
- 期限: {date}（可能であれば {due48} までの事前確認）
- 完了条件: {suc}
- 参考: チェックリスト（下記）／想定リスク（下記）
添付: {attach or '＜必要資料＞'}

PMO"""
        slack = f"[{cat}] {desc} → {exp} ｜期限 {date}（事前確認 {due48}）｜担当 {actor}"
        header = "チェックリスト\n- " + "\n- ".join(checklist)
        risksec = "\n\nリスク/確認\n- " + "\n- ".join(risks)
        out_text = header + risksec + "\n\nメール文例（コピー可）\n" + body + "\n\nSlack/チャット用短文\n" + slack
        memo = f"{cat} | 目的: {desc}\\n依頼: {exp}\\n完了条件: {suc}\\n担当: {actor}\\n事前確認: {due48}"
    else:
        subject = f"{cat} — action needed by {date}: {desc[:32]}"
        body = f"""Subject: {subject}
To: {to or '<recipient>'}
Cc: {cc or '<stakeholders>'}

Dear {actor},
Please proceed as follows:
- Goal: {desc}
- Action: {exp}
- Deadline: {date} (early check by {due48})
- Done: {suc}
- Ref: Checklist (below) / Risks (below)
Attachments: {attach or '<attachments>'}

PMO"""
        slack = f"[{cat}] {desc} → {exp} | due {date} (precheck {due48}) | owner {actor}"
        header = "Checklist\n- " + "\n- ".join(checklist)
        risksec = "\n\nRisks / Checks\n- " + "\n- ".join(risks)
        out_text = header + risksec + "\n\nEmail Draft\n" + body + "\n\nChat Snippet\n" + slack
        memo = f"{cat} | Goal: {desc}\\nAction: {exp}\\nDone: {suc}\\nOwner: {actor}\\nPrecheck: {due48}"

    ics_path = ics_for_event(str(row["event_id"]), f"{cat}: {desc}", date, description=memo)
    txt = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    txt.write(out_text); txt.flush(); txt.close()
    return out_text, txt.name, ics_path

# ---------------- KPI (CALM mode) ----------------
KPI_COLS = {"date":["date","日付"],"pv":["pv","views","閲覧"],
            "inq":["inquiries","inquiry","問合せ","問い合わせ"],
            "view":["viewings","viewing","内覧"],
            "offer":["offers","applications","申込","申し込み"]}

THRESHOLDS = {  # green-friendly
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

def kpi_cards_html(scope: pd.DataFrame) -> str:
    pv = scope["pv"].sum(); inq = scope["inquiries"].sum()
    view = scope["viewings"].sum(); off = scope["offers"].sum()
    pct = lambda a,b: (a/b) if b>0 else None
    resp = pct(inq, pv); conv_view = pct(view, inq); conv_offer = pct(off, view)
    bg1, br1, tx1 = color_for(resp, "resp"); bg2, br2, tx2 = color_for(conv_view, "view")
    bg3, br3, tx3 = color_for(conv_offer, "offer"); bg4, br4, tx4 = ("#EEF2F7","#D6DEE8","#334155")
    fmt = lambda v: f"{v*100:.1f}%" if v is not None else "—"
    days = (scope["date"].max() - scope["date"].min()).days + 1 if not scope.empty else 0
    return f"""
    <div style="display:flex; gap:12px; flex-wrap:wrap">
      <div style="flex:1; min-width:180px; padding:12px; border:1px solid {br1}; border-radius:10px; background:{bg1}; color:{tx1}">
        <div style="font-size:12px; opacity:0.9">反響率</div>
        <div style="font-size:28px; font-weight:700">{fmt(resp)}</div>
        <div style="font-size:12px; opacity:0.8; color:#111">{inq} / {pv}</div>
      </div>
      <div style="flex:1; min-width:180px; padding:12px; border:1px solid {br2}; border-radius:10px; background:{bg2}; color:{tx2}">
        <div style="font-size:12px; opacity:0.9">内覧化率</div>
        <div style="font-size:28px; font-weight:700">{fmt(conv_view)}</div>
        <div style="font-size:12px; opacity:0.8; color:#111">{view} / {inq}</div>
      </div>
      <div style="flex:1; min-width:180px; padding:12px; border:1px solid {br3}; border-radius:10px; background:{bg3}; color:{tx3}">
        <div style="font-size:12px; opacity:0.9">申込率</div>
        <div style="font-size:28px; font-weight:700">{fmt(conv_offer)}</div>
        <div style="font-size:12px; opacity:0.8; color:#111">{off} / {view}</div>
      </div>
      <div style="flex:1; min-width:180px; padding:12px; border:1px solid {br4}; border-radius:10px; background:{bg4}; color:{tx4}">
        <div style="font-size:12px; opacity:0.9">経過日数</div>
        <div style="font-size:28px; font-weight:700">{days} 日</div>
        <div style="font-size:12px; opacity:0.8; color:#111">{scope['date'].min().date() if not scope.empty else '—'} → {scope['date'].max().date() if not scope.empty else '—'}</div>
      </div>
    </div>"""

def kpi_aggregate(range_mode):
    df, enc = read_kpi()
    if df is None:
        return f"読み込みエラー: {enc}", "", pd.DataFrame()
    today = pd.Timestamp(dt.date.today())
    if range_mode == "直近30日":
        start = today - pd.Timedelta(days=30); scope = df[df["date"] >= start]
    elif range_mode == "今月":
        start = pd.Timestamp(today.year, today.month, 1); scope = df[df["date"] >= start]
    else:
        scope = df.copy()
    if scope.empty:
        return "対象期間にデータがありません", "", scope
    cards = kpi_cards_html(scope)
    return "", cards, scope

# ---------------- UI ----------------
def init_action(mode):
    df = load_events()
    summary, top = summary_top(df, mode)
    table = top.drop(columns=["date_dt"]) if not top.empty else top
    options = [f"{i}｜{r.event_id}: {r.category} / {str(r.description)[:24]}…" for i, r in enumerate(top.itertuples(index=False))] if not top.empty else []
    return summary, table, gr.update(choices=options, value=(options[0] if options else None))

def generate_pack(mode, lang, selector):
    df = load_events()
    _, top = summary_top(df, mode)
    if top.empty:
        return "該当なし。", None, None
    try:
        idx = int((selector or "0").split("｜")[0])
    except Exception:
        idx = 0
    row = top.iloc[idx]
    return build_pack(row, lang)

with gr.Blocks() as demo:
    gr.Markdown("## AI売却PMO（PoC） — Calm KPI（緑多め・赤最少・コメント無し）")
    with gr.Tabs():
        with gr.TabItem("アクション"):
            with gr.Row():
                mode = gr.Radio(["今日以降","すべて"], value="今日以降", label="表示範囲", scale=2)
                lang = gr.Radio(["日本語","English"], value="日本語", label="言語", scale=1)
                refresh = gr.Button("再読み込み/集計", scale=1)
            summary = gr.Textbox(label="重点イベント（上位3件・優先度順）", lines=6)
            table = gr.Dataframe(label="上位3件の詳細（編集はCSVで）")
            selector = gr.Dropdown(label="生成対象（上位3から選択）", choices=[])
            generate_btn = gr.Button("パック生成（チェックリスト + メール + Slack + ics）")
            out = gr.Textbox(label="出力（コピー可）", lines=20)
            dl_txt = gr.File(label="ダウンロード（.txt）")
            dl_ics = gr.File(label="カレンダー（.ics）")

            refresh.click(init_action, inputs=mode, outputs=[summary, table, selector])
            demo.load(init_action, inputs=mode, outputs=[summary, table, selector])
            generate_btn.click(generate_pack, inputs=[mode, lang, selector], outputs=[out, dl_txt, dl_ics])

        with gr.TabItem("KPI"):
            gr.Markdown("“水先案内人モード”：色は**緑を多め・赤は最少**。過度なアラートや自動コメントは出しません。")
            range_mode = gr.Radio(["直近30日","今月","すべて"], value="直近30日", label="集計範囲")
            kpi_refresh = gr.Button("KPI更新")
            kpi_msg = gr.Textbox(label="メッセージ（CALM）", lines=1)
            kpi_cards = gr.HTML()
            kpi_table = gr.Dataframe(label="集計対象の明細")
            kpi_refresh.click(kpi_aggregate, inputs=range_mode, outputs=[kpi_msg, kpi_cards, kpi_table])
            demo.load(kpi_aggregate, inputs=range_mode, outputs=[kpi_msg, kpi_cards, kpi_table])

    gr.Markdown("※ 反響率>=6%、内覧化率>=35%、申込率>=15%で緑。それ未満も赤域を狭く設定（反響<3%、内覧<20%、申込<8%のみ赤）。")

if __name__ == "__main__":
    print("Launching Gradio on http://127.0.0.1:7860 ...")
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
