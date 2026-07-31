import os
import json
import re

def inspect_and_parse_stage1():
    base_dir = r"D:\Kid's Vault\60_會考歷屆試題\01_依年度全卷"
    years = ["110年", "109年", "108年"]
    
    total_files = 0
    all_questions = []
    
    for y in years:
        ydir = os.path.join(base_dir, y)
        if not os.path.exists(ydir):
            print(f"Directory not found: {ydir}")
            continue
            
        files = [f for f in os.listdir(ydir) if f.endswith('.md')]
        total_files += len(files)
        print(f"[{y}] Found {len(files)} markdown files.")
        
        for f in files:
            fpath = os.path.join(ydir, f)
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                content = fp.read()
                
            # Basic parsing of questions in markdown
            # Format usually contains: ## 題號 or 1. or (A)(B)(C)(D)
            subject = "未知"
            if "國文" in f: subject = "國文"
            elif "數學" in f: subject = "數學"
            elif "自然" in f: subject = "自然"
            elif "社會" in f: subject = "社會"
            elif "英文" in f: subject = "英文"
            
            # Extract questions by block
            blocks = re.split(r'\n(?=#{1,4}\s+|\d+[\.\、])', content)
            q_in_file = 0
            for b in blocks:
                if len(b.strip()) > 20 and ("(A)" in b or "(B)" in b or "選項" in b or "【" in b):
                    q_in_file += 1
                    all_questions.append({
                        "year": int(y.replace("年", "")),
                        "subject": subject,
                        "raw_block": b.strip()[:200]
                    })
            print(f"   - {f}: extracted ~{q_in_file} question blocks.")
            
    print(f"\nStage 1 Total Files: {total_files}, Total Extracted Question Blocks: {len(all_questions)}")

if __name__ == '__main__':
    inspect_and_parse_stage1()
