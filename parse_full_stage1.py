import os
import json
import re

def parse_full_stage1():
    base_dir = r"D:\Kid's Vault\60_會考歷屆試題\01_依年度全卷"
    years = ["110年", "109年", "108年"]
    
    # 讀取現有的 mapped_exams.json 取得 108 課綱 eds_x_code 知識點庫
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mapped_json_path = os.path.join(script_dir, 'mapped_exams.json')
    
    existing_items = []
    if os.path.exists(mapped_json_path):
        with open(mapped_json_path, 'r', encoding='utf-8') as f:
            existing_items = json.load(f)
            
    print(f"Loaded existing {len(existing_items)} items from mapped_exams.json.")
    
    # 科目關鍵字與 eds_x_code 預設對應 Mapping
    default_x_code = {
        "國文": "Ab-Ⅳ-1",
        "數學": "N-Ⅳ-1",
        "自然": "Bc-Ⅳ-1",
        "社會": "Ge-Ⅳ-1",
        "英文": "Ae-Ⅳ-1"
    }
    
    new_extracted = []
    
    for y in years:
        ydir = os.path.join(base_dir, y)
        if not os.path.exists(ydir):
            continue
            
        files = [f for f in os.listdir(ydir) if f.endswith('.md')]
        for f in files:
            subject = "國文"
            if "數學" in f: subject = "數學"
            elif "自然" in f: subject = "自然"
            elif "社會" in f: subject = "社會"
            elif "英文" in f or "英語" in f: subject = "英文"
            
            fpath = os.path.join(ydir, f)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
                
            blocks = re.split(r'\n(?=#{1,4}\s+|\d+[\.\、])', content)
            q_num = 1
            for b in blocks:
                if len(b.strip()) > 20 and ("(A)" in b or "(B)" in b or "【" in b):
                    qid = f"{subject[:3]}_{y[:3]}_{q_num:03d}"
                    x_code = default_x_code.get(subject, "Bc-Ⅳ-1")
                    
                    item = {
                        "question_id": qid,
                        "year": int(y.replace("年", "")),
                        "subject": subject,
                        "eds_x_code": x_code,
                        "passing_rate": 0.55,  # 預設通過率 P=0.55
                        "time_decay_weight": 0.7, # 110-108 年衰減權重 0.7
                        "is_out_of_scope": False,
                        "tags": [f"#{y}", f"#{subject}", "#108課綱對位"],
                        "raw_snippet": b.strip()[:300]
                    }
                    new_extracted.append(item)
                    q_num += 1

    print(f"Successfully extracted {len(new_extracted)} items for Stage 1 (110-108年).")
    
    # 兼併資料
    combined_items = existing_items + new_extracted
    
    # 寫回 mapped_exams.json (或輸出 Stage 1 成果檔)
    output_stage1_path = os.path.join(script_dir, 'mapped_exams_stage1.json')
    with open(output_stage1_path, 'w', encoding='utf-8') as f:
        json.dump(combined_items, f, ensure_ascii=False, indent=2)
        
    print(f"Stage 1 Complete: Total database size expanded from {len(existing_items)} to {len(combined_items)} items!")
    print(f"Saved Stage 1 dataset to: {output_stage1_path}")

if __name__ == '__main__':
    parse_full_stage1()
