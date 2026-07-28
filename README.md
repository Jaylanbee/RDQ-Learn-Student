# RDQ-Learn-Student — 國中生課後複習四象限法（OpenCode 版）

**Student Learning Review Quadrant**
專為國中生設計的課後覆盤 OpenCode Skill。

> 先用問的讓你想想看，卡住的時候用選項接住你。全部都在你學過的範圍內，不超綱。

以 RDQ-Learn-Medium（混血版）為基礎，針對**國中生的認知發展階段**與**跨科目需求**最佳化。

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
└── references/
    ├── question-bank.md          # 五科目起始問句 + 迷思概念
    └── spec-template.md          # 學習覆盤卡模板
```

---

## 授權

MIT License
