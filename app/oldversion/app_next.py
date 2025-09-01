# -*- coding: utf-8 -*-
import gradio as gr
import pandas as pd
import datetime as dt
from pathlib import Path
from io import StringIO
import tempfile, os

ENCODINGS = ["utf-8-sig","utf-8","cp932","shift_jis","mac_roman"]

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
    # Closer date => higher urgency. Convert to factor 1.0 .. 0.2 over 0..60 days
    time_factor = max(0.2, 1.0 - (days/60.0))
    return round(risk * 33 * time_factor)  # 0..~100

def summarize(df, mode):
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
    return "\n".join(lines), tmp.drop(columns=["date_dt"])

def make_outputs(row, lang="日本語"):
    actor = str(row["actor"]); cat = str(row["category"]); risk = str(row["risk_level"])
    date = pd.Timestamp(row["date_dt"]).date().isoformat()
    desc = str(row["description"]); exp = str(row["expected_action"]); suc = str(row["success_criteria"])
    due48 = (pd.Timestamp(row["date_dt"]).date() - pd.Timedelta(days=2)).isoformat()

    if lang=="日本語":
        next_actions = [
            f"{date} までに {actor} が {exp} を完了。",
            "PMOから全関係者へ進捗共有（要点: 目的/期限/責任者/完了条件）。",
        ]
        if cat=="Prep":
            next_actions += ["写真・間取・コピーを統一。掲載差異が出ないようテンプレ配布。"]
        elif cat=="Viewing":
            next_actions += ["内覧スロット/鍵/動線/注意書きを確定。共用部掲示の許可確認。"]
        elif cat=="Offer":
            next_actions += ["回答期日・条件の優先度（価格/時期/残置/手付）を事前合意。"]
        elif cat=="Finance":
            next_actions += ["残債/抹消手続きの必要書類と予約枠を確定。"]
        elif cat=="Close":
            next_actions += ["決済当日のタスク（鍵/書類/精算）をチェックリスト化。"]

        template = f"""件名: {cat} / {desc[:18]}… 進行のお願い（{date} まで）
{actor} 各位
以下のとおりご対応をお願いします。
- 目的: {desc}
- 依頼: {exp}
- 期限: {date}（可能であれば {due48} までの事前確認）
- 完了条件: {suc}
ご不明点はPMOまで。"""

        risks = []
        if cat in ["Listing","Viewing"]:
            risks += ["掲載内容の不一致（価格/面積/向き）。", "共用部撮影・掲示のルール違反。"]
        if cat=="Offer":
            risks += ["口頭合意のみで条件が曖昧になる。", "手付や違約条項の事前確認不足。"]
        if cat=="Finance":
            risks += ["抹消・残債手続きの期日未整合。", "必要書類の不足（印鑑証明 等）。"]
        if not risks:
            risks = ["関係者間の前提ズレ。", "期限直前の修正で手戻り。"]

        alt = []
        if cat in ["Offer","Negotiation","Close"]:
            alt += ["譲歩ラインを金額・期日・残置で3軸定義。", "代替買主/予備日程を仮押さえ。"]
        else:
            alt += ["ステップを前倒しし初動の遅れを回避。", "品質担保（ダブルチェック担当を置く）。"]

        header = f"次の一手（48h）\n- " + "\n- ".join(next_actions)
        body = f"\n\nメッセージ雛形\n{template}"
        risksec = "\n\nリスク/確認\n- " + "\n- ".join(risks)
        altsec = "\n\n代替案\n- " + "\n- ".join(alt)
        return header + body + risksec + altsec
    else:
        next_actions = [
            f"Complete '{exp}' by {date} (owner: {actor}).",
            "PMO shares a brief update (goal / deadline / owner / done‑criteria).",
        ]
        if cat=="Prep":
            next_actions += ["Unify photo/floorplan/copy across all listings."]
        elif cat=="Viewing":
            next_actions += ["Lock slots/keys/flow/signage. Confirm building rules."]
        elif cat=="Offer":
            next_actions += ["Align priorities: price / timeline / fixtures / deposit."]
        elif cat=="Finance":
            next_actions += ["Confirm payoff + lien release docs and reservations."]
        elif cat=="Close":
            next_actions += ["Checklist for closing day: keys/docs/settlement."]

        template = f"""Subject: {cat} — action needed by {date}
Dear {actor},
Please proceed as follows:
- Goal: {desc}
- Action: {exp}
- Deadline: {date} (early check by {due48} if possible)
- Done: {suc}
PMO remains the point of contact."""

        risks = []
        if cat in ["Listing","Viewing"]:
            risks += ["Inconsistent listing details (price/size/orientation).", "Common‑area photo/signage violations."]
        if cat=="Offer":
            risks += ["Ambiguous oral agreements.", "Deposit/penalty terms not pre‑agreed."]
        if cat=="Finance":
            risks += ["Mismatched payoff/lien release schedule.", "Missing documents (e.g., seal certificate)."]
        if not risks:
            risks = ["Stakeholder assumption mismatch.", "Late changes causing rework."]

        alt = []
        if cat in ["Offer","Negotiation","Close"]:
            alt += ["Define concession bands for price/timing/fixtures.", "Hold backups: alternate buyer or dates."]
        else:
            alt += ["Front‑load steps to avoid early delays.", "Add QA: double‑check owner."]

        header = "Next 48h\n- " + "\n- ".join(next_actions)
        body = f"\n\nMessage Draft\n{template}"
        risksec = "\n\nRisks / Checks\n- " + "\n- ".join(risks)
        altsec = "\n\nAlternatives\n- " + "\n- ".join(alt)
        return header + body + risksec + altsec

def on_select(mode, lang, row_json):
    df, _ = load_df()
    _, top = summarize(df, mode)
    if top.empty:
        return "該当なし。", None
    try:
        idx = int(row_json.split("｜")[0])  # "0｜E11: Viewing …" の先頭
        row = top.iloc[idx:idx+1].copy()
    except Exception:
        row = top.iloc[:1].copy()
    # rebuild 'date_dt' for generator
    full_df, _ = load_df()
    joined = row.merge(full_df[["event_id","date_dt"]], on="event_id", how="left")
    text = make_outputs(joined.iloc[0], lang=lang)
    # Create a downloadable txt
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    tmp.write(text); tmp.flush(); tmp.close()
    return text, tmp.name

def init(mode):
    df, enc = load_df()
    summary, top = summarize(df, mode)
    if top.empty:
        options = []
    else:
        options = [f"{i}｜{r.event_id}: {r.category} / {str(r.description)[:24]}…" for i, r in enumerate(top.itertuples(index=False))]
    return summary, top.drop(columns=[] if "date_dt" not in top.columns else ["date_dt"]), gr.update(choices=options, value=(options[0] if options else None))

with gr.Blocks() as demo:
    gr.Markdown("## AI売却PMO（PoC） — 次の一手サジェスト + 自動文面生成")
    with gr.Row():
        mode = gr.Radio(["今日以降","すべて"], value="今日以降", label="表示範囲", scale=2)
        lang = gr.Radio(["日本語","English"], value="日本語", label="言語", scale=1)
        refresh = gr.Button("再読み込み/集計", scale=1)
    summary = gr.Textbox(label="重点イベント（上位3件・優先度順）", lines=6)
    table = gr.Dataframe(label="上位3件の詳細（編集はCSVで）")
    selector = gr.Dropdown(label="文面生成対象（上位3から選択）", choices=[])
    generate = gr.Button("文面生成")
    out = gr.Textbox(label="出力（コピー可）", lines=16)
    dl = gr.File(label="ダウンロード（.txt）")

    refresh.click(init, inputs=mode, outputs=[summary, table, selector])
    demo.load(init, inputs=mode, outputs=[summary, table, selector])
    generate.click(on_select, inputs=[mode, lang, selector], outputs=[out, dl])
    gr.Markdown("CSVは UTF-8 / UTF-8-BOM / Shift_JIS に対応。日付は YYYY-MM-DD または YYYY/MM/DD。")

if __name__ == "__main__":
    print("Launching Gradio on http://127.0.0.1:7860 ...")
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
