# -*- coding: utf-8 -*-
import gradio as gr
import pandas as pd
import datetime as dt
from pathlib import Path

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
    # normalize columns
    expected_cols = ["event_id","date","actor","category","description","expected_action","success_criteria","risk_level"]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSVの列名が不足しています: {missing}")
    # parse dates (allow YYYY-MM-DD or YYYY/M/D)
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date_dt"].isna().any():
        # try alternative formats
        df.loc[df["date_dt"].isna(),"date_dt"] = pd.to_datetime(df.loc[df["date_dt"].isna(),"date"], format="%Y/%m/%d", errors="coerce")
    if df["date_dt"].isna().any():
        bad = df[df["date_dt"].isna()]["date"].unique().tolist()
        raise ValueError(f"日付の形式を解釈できませんでした（例: YYYY-MM-DD または YYYY/MM/DD）: {bad}")
    return df, enc

def next_actions(mode):
    df, enc = load_df()
    today = dt.date.today()
    if mode == "今日以降":
        scope = df[df["date_dt"] >= pd.Timestamp(today)]
    else:
        scope = df.copy()
    pending = scope.sort_values(["date_dt","risk_level"]).head(3)
    lines = []
    for row in pending.itertuples(index=False):
        when = pd.Timestamp(row.date_dt).date().isoformat()
        lines.append(f"- {when} [{row.category}] {row.description} → {row.expected_action}")
    text = "\n".join(lines) if lines else f"該当なし。CSVの日時を見直すか、表示範囲を『すべて』へ。  (読み込みエンコーディング: {enc})"
    show = pending.drop(columns=["date_dt"]) if not pending.empty else scope.head(0)
    return text, show

with gr.Blocks() as demo:
    gr.Markdown("## AI売却PMO（PoC） — 次の一手サジェスト")
    mode = gr.Radio(["今日以降","すべて"], value="今日以降", label="表示範囲")
    btn = gr.Button("更新")
    out_text = gr.Textbox(label="提案", lines=8)
    out_table = gr.Dataframe(label="重点イベント（3件）")
    btn.click(fn=next_actions, inputs=mode, outputs=[out_text, out_table])
    demo.load(fn=next_actions, inputs=mode, outputs=[out_text, out_table])
    gr.Markdown("CSVは UTF-8 / UTF-8-BOM / Shift_JIS いずれでも読み取れます。日付は YYYY-MM-DD か YYYY/MM/DD。")

if __name__ == "__main__":
    print("Launching Gradio on http://127.0.0.1:7860 ...")
    demo.launch(server_name="127.0.0.1", server_port=7860, show_error=True)
