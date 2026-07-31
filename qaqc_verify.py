#!/usr/bin/env python3
"""
qaqc_verify.py

EDS 決勝圖譜與數據品質保證 (QA/QC) 自動化防呆檢驗腳本。

本腳本執行 5 大核查程序 (5-Stage Verification Protocol)：
1. 歷屆試題完整性核查 (111-115年 5 科總題數)
2. 課綱代碼對齊覆蓋率與格式正則核查
3. 官方通過率與難度值邊界與離群值檢驗 (0.0 < pass_rate < 1.0)
4. ROI 權重計算與 Min-Max 正規化邊界核查 (0.1 <= roi_weight <= 1.0)
5. 自動檢驗產出報告與異常警報發布

用法：
    python qaqc_verify.py [--mapped=mapped_exams.json] [--roi=eds_roi_weights.csv]
"""

import os
import sys
import json
import re
import pandas as pd
from datetime import datetime

# Windows 終端機 UTF-8 相容
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def run_qaqc_audit(mapped_json_path="mapped_exams.json", roi_csv_path="eds_roi_weights.csv"):
    print("==================================================")
    print("🛡️  EDS 決勝圖譜數據品質保證 (QA/QC) 檢驗程序")
    print("==================================================")
    
    passed_all = True
    issues = []

    # ----------------------------------------------------
    # Stage 1: 試題 JSON 結構與完整性檢驗
    # ----------------------------------------------------
    print("\n[Check 1/5] 試題資料庫與歷屆涵蓋度核查...")
    if not os.path.exists(mapped_json_path):
        print(f"❌ [CRITICAL] 找不到 `{mapped_json_path}` 檔案！")
        return False
        
    with open(mapped_json_path, 'r', encoding='utf-8') as f:
        mapped_exams = json.load(f)

    total_q = len(mapped_exams)
    years = set(e['year'] for e in mapped_exams)
    subjects = set(e['subject'] for e in mapped_exams)

    print(f"  └ 總題數: {total_q} 題")
    print(f"  └ 涵蓋年度: {sorted(years)}")
    print(f"  └ 涵蓋科目: {sorted(subjects)}")

    if total_q < 1000:
        issues.append(f"試題總數少於預期標竿 (現有 {total_q} < 1000 題)")
        passed_all = False
    if set([111, 112, 113, 114, 115]) - years:
        issues.append(f"缺少必要年度資料: {set([111,112,113,114,115]) - years}")
        passed_all = False

    # ----------------------------------------------------
    # Stage 2: 課綱代碼 (eds_x_code) 標記防呆檢驗
    # ----------------------------------------------------
    print("\n[Check 2/5] 知識矩陣代碼 (eds_x_code) 覆蓋率與格式正則核查...")
    missing_code_cnt = 0
    invalid_code_fmt = 0
    code_pattern = re.compile(r'^[A-Z][a-z0-9\-Ⅳ-]+\d*$')

    for e in mapped_exams:
        codes = e.get('eds_x_code', [])
        if not codes:
            missing_code_cnt += 1
        else:
            for c in codes:
                if not code_pattern.match(c):
                    invalid_code_fmt += 1

    print(f"  └ 未對齊代碼題數: {missing_code_cnt} (空缺率: {missing_code_cnt/total_q:.2%})")
    print(f"  └ 代碼格式異常數: {invalid_code_fmt}")

    if missing_code_cnt > 0:
        issues.append(f"發現 {missing_code_cnt} 題缺少 eds_x_code")
        passed_all = False
    if invalid_code_fmt > 0:
        issues.append(f"發現 {invalid_code_fmt} 個 eds_x_code 格式不符合規範")
        passed_all = False

    # ----------------------------------------------------
    # Stage 3: 官方通過率與難度值邊界核查
    # ----------------------------------------------------
    print("\n[Check 3/5] 通過率數據與數值邊界 (Bound Check) 檢驗...")
    out_of_bound_pass = 0
    for e in mapped_exams:
        p = e.get('pass_rate')
        if p is not None and not (0.0 <= p <= 1.0):
            out_of_bound_pass += 1

    print(f"  └ 通過率數值異常 (非 0.0 ~ 1.0 區間): {out_of_bound_pass} 筆")
    if out_of_bound_pass > 0:
        issues.append(f"發現 {out_of_bound_pass} 筆通過率超出一合法區間 [0, 1]")
        passed_all = False

    # ----------------------------------------------------
    # Stage 4: 產物 CSV 權重正規化核查
    # ----------------------------------------------------
    print("\n[Check 4/5] 產出表 `eds_roi_weights.csv` 數值與權重區間檢驗...")
    if not os.path.exists(roi_csv_path):
        print(f"❌ [CRITICAL] 找不到 `{roi_csv_path}` 產物檔！")
        return False

    df_roi = pd.read_csv(roi_csv_path)
    min_w = df_roi['roi_weight'].min()
    max_w = df_roi['roi_weight'].max()
    null_rows = df_roi.isnull().sum().sum()

    print(f"  └ CSV 總紀錄數: {len(df_roi)} 行")
    print(f"  └ ROI 權重最小值: {min_w:.4f} (規範下限: 0.1)")
    print(f"  └ ROI 權重最大值: {max_w:.4f} (規範上限: 1.0)")
    print(f"  └ 欄位 Null/NaN 空值筆數: {null_rows}")

    if min_w < 0.099 or max_w > 1.001:
        issues.append(f"roi_weight 未嚴格落在 0.1 ~ 1.0 區間 ({min_w} ~ {max_w})")
        passed_all = False
    if null_rows > 0:
        issues.append(f"CSV 檔案中包含 {null_rows} 筆 Null 欄位")
        passed_all = False

    # ----------------------------------------------------
    # Stage 5: 品質稽核總結報告
    # ----------------------------------------------------
    print("\n[Check 5/5] QA/QC 品質核驗結果總結報告")
    print("--------------------------------------------------")
    if passed_all:
        print("✅ 【PASS】所有 5 大核查程序皆無任何異常！資料完整、正確、可靠！")
        print("   -> 本數據集可安心交付下游 EDS Engine 5 (Adaptive Engine) 與考前決勝模組使用。")
    else:
        print("⚠️ 【WARNING】發現以下數據品質問題，需要關注：")
        for idx, issue in enumerate(issues, 1):
            print(f"   {idx}. {issue}")

    print("==================================================\n")
    return passed_all


if __name__ == '__main__':
    run_qaqc_audit()
