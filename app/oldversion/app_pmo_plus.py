# -*- coding: utf-8 -*-
import gradio as gr
import pandas as pd
import datetime as dt
from pathlib import Path
import tempfile, os

ENCODINGS = ["utf-8-sig","utf-8","cp932","shift_jis","mac_roman"]

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

def read_csv_flex(path):
    last_err = None
    for enc in ENCODINGS:
        try:
            return pd.read_csv(path, encoding=enc), enc
        except Exception as e:
            last_err = e
    raise last_err

def load_df():
    p = Path(__file__).resolve().parents[1] / "data" / "events_sample.csv"
    df, enc = read_csv_flex(p)
    expected = ["event_id","date","actor","category","description","expected_action","success_criteria","risk_level"]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise ValueError(f"CSVの列名が不足: {missing}")
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date_dt"].isna().any():
        df.loc[df["date_dt"].isna(),"date_dt"] = pd.to_datetime(df.loc[df["date_dt"].isna(),"date"], format="%Y/%m/%d", errors="coerce")
    if df["date_dt"].isna().any():
        bad = df[df["date_dt"].isna()]["date"].unique().tolist()
        raise ValueError(f"日付を解釈できません（YYYY-MM-DD / YYYY/MM/DD）: {bad}")
    return df, enc

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

def ics_for_event(event_id, title, date_iso):
    start = pd.to_datetime(date_iso).strftime("%Y%m%d")
    end = pd.to_datetime(date_iso).strftime("%Y%m%d")
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//SellPM//PMOPlus//JP
BEGIN:VEVENT
UID:{event_id}@sellpm
DTSTAMP:{pd.Timestamp.utcnow().strftime('%Y%m%dT%H%M%SZ')}
DTSTART;VALUE=DATE:{start}
DTEND;VALUE=DATE:{end}
SUMMARY:{title}
END:VEVENT
END:VCALENDAR
""".strip()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ics", mode="w", encoding="utf-8")
    tmp.write(ics); tmp.flush(); tmp.close()
    return tmp.name

def build_pack(row, lang):
    actor = str(row["actor"]); cat = str(row["category"]); risk = str(row["risk_level"])
    date = pd.Timestamp(row["date_dt"]).date().isoformat()
    desc = str(row["description"]); exp = str(row["expected_action"]); suc = str(row["success_criteria"])
    due48 = (pd.Timestamp(row["date_dt"]).date() - pd.Timedelta(days=2)).isoformat()

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
        out = header + risksec + "\n\nメール文例（コピー可）\n" + body + "\n\nSlack/チャット用短文\n" + slack
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
        out = header + risksec + "\n\nEmail Draft\n" + body + "\n\nChat Snippet\n" + slack

    ics_path = ics_for_event(str(row["event_id"]), f"{cat}: {desc}", date)
    txt = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    txt.write(out); txt.flush(); txt.close()
    return out, txt.name, ics_path

def init(mode):
    df, _ = load_df()
    summary, top = summary_top(df, mode)
    options = [f"{i}｜{r.event_id}: {r.category} / {str(r.description)[:24]}…" for i, r in enumerate(top.itertuples(index=False))] if not top.empty else []
    return summary, (top.drop(columns=["date_dt"]) if not top.empty else top), gr.update(choices=options, value=(options[0] if options else None))

def generate(mode, lang, selector):
    df, _ = load_df()
    _, top = summary_top(df, mode)
    if top.empty:
        return "該当なし。", None, None
    try:
        idx = int(selector.split("｜")[0])
    except Exception:
        idx = 0
    row = top.iloc[idx:idx+1].copy()
    # merge date_dt back (it was preserved)
    full_df, _ = load_df()
    row = row.merge(full_df[["event_id","date_dt"]], on="event_id", how="left")
    return build_pack(row.iloc[0], lang)

with gr.Blocks() as demo:
    gr.Markdown("## AI売却PMO（PoC） — PMO+（チェックリスト/文例/Slack/ICS）")
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

    refresh.click(init, inputs=mode, outputs=[summary, table, selector])
    demo.load(init, inputs=mode, outputs=[summary, table, selector])
    generate_btn.click(generate, inputs=[mode, lang, selector], outputs=[out, dl_txt, dl_ics])
    gr.Markdown("※ `data/contacts.csv` を用意すると To/Cc/添付の候補を自動挿入します（列: actor,to,cc,attachments）")

if __name__ == "__main__":
    print("Launching Gradio on http://127.0.0.1:7860 ...")
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
