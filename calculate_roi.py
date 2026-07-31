#!/usr/bin/env python3
"""
calculate_roi.py

EDS 決勝圖譜模組：ROI 權重計算與正規化腳本。

本腳本功能：
1. 讀取 `map_exam_to_matrix.py` 產出的 `mapped_exams.json` 中間檔。
2. 自動掃描與解析心測中心試題分析官方資料（包含 111-114 年各科獨立 PDF 以及 115 年總合通過率 PDF）。
3. 計算單題鑑別度分數 (Difficulty Value = 1 - 通過率)，防呆機制：若缺失預設帶入 0.5。
4. 按 `eds_x_code` Group By 統計出題次數 (Exam Frequency) 與平均鑑別度。
5. 計算 Raw_ROI = 總出題次數 × 平均鑑別度分數。
6. 將 Raw_ROI 進行 Min-Max 正規化壓縮至 0.1 ~ 1.0 區間。
7. 輸出最終標籤權重檔 `eds_roi_weights.csv`。

用法：
    python calculate_roi.py [--input=mapped_exams.json] [--output=eds_roi_weights.csv]
"""

import os
import sys
import json
import glob
import re
import pandas as pd
import pypdf
from datetime import datetime

# Windows 終端機 UTF-8 相容
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ANALYSIS_BASE_DIR = r"D:\InputCenter\國中會考\EDS\試題分析"


def parse_115_summary_pdf(pdf_path):
    """專門解析 115 年總合格式通過率 PDF"""
    if not os.path.exists(pdf_path):
        return {}

    headers = ['國文', '英語_聽力', '英語', '數學', '社會', '自然']
    parsed_115 = {}

    try:
        reader = pypdf.PdfReader(pdf_path)
        for page in reader.pages:
            lines = page.extract_text().split('\n')
            for line in lines:
                parts = line.strip().split()
                if not parts:
                    continue
                if parts[0].isdigit():
                    q_no = int(parts[0])
                    vals = []
                    for p in parts[1:]:
                        try:
                            vals.append(float(p))
                        except ValueError:
                            pass

                    # 動態欄位對齊
                    if q_no <= 21 and len(vals) == 6:
                        for idx, s in enumerate(headers):
                            parsed_115[(115, s, q_no)] = vals[idx]
                    elif 22 <= q_no <= 25 and len(vals) == 5:
                        active_s = ['國文', '英語', '數學', '社會', '自然']
                        for idx, s in enumerate(active_s):
                            parsed_115[(115, s, q_no)] = vals[idx]
                    elif 26 <= q_no <= 42 and len(vals) == 4:
                        active_s = ['國文', '英語', '社會', '自然']
                        for idx, s in enumerate(active_s):
                            parsed_115[(115, s, q_no)] = vals[idx]
                    elif q_no == 43 and len(vals) == 3:
                        active_s = ['英語', '社會', '自然']
                        for idx, s in enumerate(active_s):
                            parsed_115[(115, s, q_no)] = vals[idx]
                    elif 44 <= q_no <= 50 and len(vals) == 2:
                        active_s = ['社會', '自然']
                        for idx, s in enumerate(active_s):
                            parsed_115[(115, s, q_no)] = vals[idx]
                    elif 51 <= q_no <= 54 and len(vals) == 1:
                        active_s = ['社會']
                        for idx, s in enumerate(active_s):
                            parsed_115[(115, s, q_no)] = vals[idx]
    except Exception as e:
        print(f"⚠️ 解析 115 年 PDF 時發生錯誤: {e}", file=sys.stderr)

    return parsed_115


def extract_official_pass_rates():
    """解析心測中心試題分析官方資料 (包含 111-114 獨立檔與 115 總合檔)"""
    print("📊 正在讀取心測中心歷屆試題分析 (通過率) PDF 檔案...")
    pass_rate_map = {}

    # 1. 先處理 115 年總合 PDF
    p115 = os.path.join(ANALYSIS_BASE_DIR, '115年國中會考', '115年國中教育會考各題通過率.pdf')
    r115 = parse_115_summary_pdf(p115)
    pass_rate_map.update(r115)
    if r115:
        print(f"  └ ✅ 成功解析 115 年最新官方通過率共 {len(r115)} 筆試題資料！")

    # 2. 處理 111-114 年分科 PDF
    pdf_files = sorted(glob.glob(os.path.join(ANALYSIS_BASE_DIR, '**', '*.pdf'), recursive=True))

    for pdf_path in pdf_files:
        if '115' in pdf_path:
            continue

        parts = pdf_path.split(os.sep)
        year_str = parts[-2]
        m_year = re.search(r'\d+', year_str)
        if not m_year:
            continue
        year = int(m_year.group())

        fname = parts[-1]
        subject = None
        if '國文' in fname: subject = '國文'
        elif '數學' in fname: subject = '數學'
        elif '社會' in fname: subject = '社會'
        elif '自然' in fname: subject = '自然'
        elif '英語' in fname or '英文' in fname:
            if '聽力' in fname: subject = '英語_聽力'
            else: subject = '英語'

        if not subject:
            continue

        try:
            reader = pypdf.PdfReader(pdf_path)
            is_mc = True
            for page in reader.pages:
                text = page.extract_text()
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                for i, line in enumerate(lines):
                    if '選擇題' in line:
                        is_mc = True
                    elif '非選擇題' in line:
                        is_mc = False

                    if is_mc and line.startswith('全體'):
                        tokens = line.split()
                        if len(tokens) >= 2:
                            try:
                                val = float(tokens[1])
                                q_no = None
                                if i >= 1 and lines[i-1].isdigit():
                                    q_no = int(lines[i-1])
                                elif i >= 2 and lines[i-2].isdigit():
                                    q_no = int(lines[i-2])

                                if q_no is not None:
                                    pass_rate_map[(year, subject, q_no)] = val
                            except ValueError:
                                pass
        except Exception as e:
            print(f"⚠️ 解析 PDF {fname} 時發生錯誤: {e}", file=sys.stderr)

    print(f"✅ 完成官方通過率全解析，共讀取 {len(pass_rate_map)} 個題目的官方統計數據。")
    return pass_rate_map


def calculate_roi_weights(input_json_path, output_csv_path):
    if not os.path.exists(input_json_path):
        print(f"❌ 找不到中間檔 `{input_json_path}`，請先執行 `map_exam_to_matrix.py`。", file=sys.stderr)
        sys.exit(1)

    with open(input_json_path, 'r', encoding='utf-8') as f:
        mapped_exams = json.load(f)

    official_rates = extract_official_pass_rates()

    flattened_rows = []
    default_pass_count = 0

    for exam in mapped_exams:
        year = exam['year']
        subject = exam['subject']
        q_no = exam['no']

        pass_rate = exam.get('pass_rate')
        if pass_rate is None or not (0.0 <= pass_rate <= 1.0):
            pass_rate = official_rates.get((year, subject, q_no))

        if pass_rate is None or not (0.0 <= pass_rate <= 1.0):
            pass_rate = 0.5  # 防呆機制：預設通過率 0.5
            default_pass_count += 1

        difficulty_value = 1.0 - pass_rate

        codes = exam.get('eds_x_code', [])
        if isinstance(codes, str):
            codes = [codes]

        for code in codes:
            flattened_rows.append({
                'year': year,
                'subject': subject,
                'no': q_no,
                'eds_x_code': code,
                'pass_rate': pass_rate,
                'difficulty_value': difficulty_value
            })

    df = pd.DataFrame(flattened_rows)

    if df.empty:
        print("❌ 沒有可計算的資料。")
        return

    if default_pass_count > 0:
        print(f"ℹ️ 防呆提醒：共有 {default_pass_count} 筆題目無官方通過率，已採用預設值 0.5 (難度 0.5)。")
    else:
        print("🎉 恭喜！100% 所有題目皆已精準匹配到官方通過率數據！")

    grouped = df.groupby(['subject', 'eds_x_code']).agg(
        exam_frequency=('no', 'count'),
        avg_difficulty=('difficulty_value', 'mean')
    ).reset_index()

    grouped['raw_roi'] = grouped['exam_frequency'] * grouped['avg_difficulty']

    min_raw = grouped['raw_roi'].min()
    max_raw = grouped['raw_roi'].max()

    if max_raw == min_raw:
        grouped['roi_weight'] = 0.55
    else:
        grouped['roi_weight'] = 0.1 + (grouped['raw_roi'] - min_raw) / (max_raw - min_raw) * (1.0 - 0.1)

    grouped['roi_weight'] = grouped['roi_weight'].round(4)
    grouped['avg_difficulty'] = grouped['avg_difficulty'].round(4)
    grouped['last_updated'] = datetime.now().strftime('%Y-%m-%d')

    final_df = grouped[[
        'eds_x_code',
        'subject',
        'exam_frequency',
        'avg_difficulty',
        'roi_weight',
        'last_updated'
    ]].sort_values(by=['subject', 'roi_weight'], ascending=[True, False])

    final_df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')

    print(f"\n🎉 成功產出 EDS ROI 權重表：`{os.path.abspath(output_csv_path)}`")
    print(f"📊 統計概要：共處理 {len(final_df)} 個 108 課綱知識代碼 (eds_x_code)。")
    print("\n前 5 項最高 ROI 權重知識點：")
    print(final_df.head(5).to_string(index=False))


if __name__ == '__main__':
    input_json = "mapped_exams.json"
    output_csv = "eds_roi_weights.csv"

    for arg in sys.argv[1:]:
        if arg.startswith("--input="):
            input_json = arg.split("=")[1]
        elif arg.startswith("--output="):
            output_csv = arg.split("=")[1]

    calculate_roi_weights(input_json, output_csv)
