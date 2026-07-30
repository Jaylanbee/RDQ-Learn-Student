# RDQ-Learn-Student — 國中生課後複習四象限法（OpenCode 版）

**Student Learning Review Quadrant**
專為國中生設計的課後覆盤 OpenCode Skill。

> 先用問的讓你想想看，卡住的時候用選項接住你。全部都在你學過的範圍內，不超綱。

以 RDQ-Learn-Medium（混血版）為基礎，針對**國中生的認知發展階段**與**跨科目需求**最佳化。

> 💡 **戰略定位：教育決策系統 (EDS) 的先鋒探勘兵**
> RDQ 的本質是「日常檢傷分類」，它負責在最低壓力的情況下，測出學生的知識盲點並寫入資料庫 (`review_index.db`)。當遇到段考或大考時，由下游的 **EDS (Educational Decision System)** 接手進行高強度的實戰演練與決策。

---

## 特色

- **科目專屬提問策略** — 國英數社自各有不同的問法
- **範圍邊界機制** — 所有提問鎖定教材，不超綱
- **三層鷹架** — 蘇式開局 → 卡住降級選項 → 再卡住就跳過不糾纏
- **正向鼓勵** — 先說他會的，再說可以加強的，不說「你錯了」

---

## 安裝

```powershell
# Windows
git clone https://github.com/Jaylanbee/RDQ-Learn-Student.git $env:USERPROFILE\.config\opencode\skills\rdq
```

```bash
# Linux / macOS
git clone https://github.com/Jaylanbee/RDQ-Learn-Student.git ~/.config/opencode/skills/rdq
```

裝好後重開 OpenCode。

---

## 使用

講人話：

```
用 RDQ 複習數學第三章
```

或：

```
我剛學完光合作用，幫我複習
```

### 科目自動對應

| 你說 | 技能判斷為 |
|---|---|
| 「幫忙複習二次函數」 | 數學 → 步驟追問型 |
| 「讀完光合作用了」 | 自然 → 現象連結型 |
| 「剛上完陋室銘」 | 國文 → 理解表達型 |
| 「複習過去式」 | 英文 → recall 檢測型 |
| 「第一章臺灣歷史」 | 社會 → 因果連結型 |

---

## 檔案結構

```
rdq/
├── SKILL.md                      # 核心規則、科目策略、邊界機制、鷹架降級
├── .opencode.json                # OpenCode 技能註冊檔
├── migrate_db.py                 # SQLite DB 初始化腳本
├── rdq_store.py                  # Phase 7 資料庫寫入封裝 API
├── check_eds_x_code_null_rate.py # 課綱代碼空缺率檢驗工具
├── RDQ-Shared-Schema/            # (submodule) 跨 agent 資料契約與 leitner 邏輯
├── Docs/                         # 系統設計文件 (COT, WorkFlow, 開發計畫)
└── references/
    ├── question-bank.md          # 五科目起始問句 + 迷思概念
    ├── spec-template.md          # 學習覆盤卡模板
    └── check_table_cols.py       # 表格格式檢查工具
```

---

## 授權

MIT License
