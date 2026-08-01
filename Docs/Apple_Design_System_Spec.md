# RDQ 儀表板：蘋果極簡風設計規範 (Apple Design System v1.0)

本規範基於 Apple Design System，作為 RDQ 學習儀表板前端 UI (`static/dashboard.html`) 的最高開發準則。

## 1. Design Philosophy
*   **Less, but Better：** 去除不必要的裝飾，專注於錯題複習核心功能。
*   **Content First：** 內容即介面，透過排版與留白引導視覺動線。
*   **Progressive Disclosure：** 漸進式揭露資訊 (實體阻力區)，降低認知負荷。
*   **Motion Follows Physics：** 動態效果嚴格遵循真實世界物理法則（重量感、慣性、彈力）。

## 2. Foundations
*   **Grid System：** 最大內容寬度 1440px，居中對齊。
*   **Spacing System (8pt)：** `--sp-1: 8px`, `--sp-2: 16px`, `--sp-3: 24px`, `--sp-4: 32px`, `--sp-6: 48px`, `--sp-8: 64px`。
*   **Radius Scale：** Small (16px), Medium (20px), Large (24px), Hero (32px), CTA (9999px / Pill-shape)。
*   **Typography：**
    *   字型：`SF Pro Display`, `SF Pro Text` (Windows 退回 `Noto Sans TC`, `sans-serif`)。
    *   層級：Hero 64px, H1 32px, H2 22px, Body 17px, Caption 13px。使用極端對比 (Bold/Regular)。
*   **Z-index 圖層規範：**
    *   `--z-base: 0` (底層內容)
    *   `--z-floating: 100` (浮動按鈕/卡片)
    *   `--z-navbar: 500`
    *   `--z-dropdown: 1000`
    *   `--z-modal: 2000`
    *   `--z-toast: 3000`

## 3. Light Theme
*   **Colors：**
    *   Background: `#F5F5F7`
    *   Surface: `#FFFFFF`
    *   Surface Secondary: `#FBFBFD`
    *   Text Primary: `#1D1D1F`
    *   Text Secondary: `#6E6E73`
    *   Divider: `#D2D2D7`
    *   Accent: `#0071E3`
*   **Categorical Colors：**
    *   Chart Blue: `#5AC8FA` (用於雷達圖)
    *   Chart Green: `#34C759`
    *   Chart Indigo: `#5856D6`
    *   Chart Orange: `#FF9F0A`
*   **Status Colors：**
    *   Error/Reject: `#FF3B30`
    *   Warning/Pending: `#FF9F0A`
    *   Success: `#34C759`
*   **Material：**
    *   Glass: `rgba(255,255,255,.72)` + `blur(20px)` + `saturate(180%)`
    *   Shadow: `0 8px 32px rgba(0,0,0,.04)`
    *   Border: `1px solid rgba(0,0,0,.05)`

## 4. Dark Theme
*   **Colors：**
    *   Background: `#000000`
    *   Surface: `#1C1C1E`
    *   Surface Secondary: `#2C2C2E`
    *   Text Primary: `#F5F5F7`
    *   Text Secondary: `#AEAEB2`
    *   Divider: `#3A3A3C`
    *   Accent: `#0A84FF`
*   **Categorical Colors：**
    *   Chart Blue: `#64D2FF`
    *   Chart Green: `#30D158`
    *   Chart Indigo: `#5E5CE6`
    *   Chart Orange: `#FFD60A`
*   **Material：**
    *   Glass: `rgba(28,28,30,.72)` + `blur(20px)` + `saturate(180%)`
    *   Shadow: `none`
    *   Border: `1px solid rgba(255,255,255,.08)`

## 5. Motion
*   **Hover：** `250ms ease-out`
*   **Click：** `300ms cubic-bezier(0.175, 0.885, 0.32, 1.275)` (Spring)
*   **Expand/Fade：** `350ms cubic-bezier(0.175, 0.885, 0.32, 1.275)`
*   **Collapse：** `250ms ease-in-out`

## 6. Components
*   **Cards (`.section`, `.task-card`)**：捨棄剛硬邊框，依賴陰影(Light)/微弱邊界(Dark)與大圓角。
*   **Buttons (`.btn`)**：Pill-shaped (全圓角)，無陰影(Flat)，利用顏色深淺區分階層。點擊時有 `scale(0.96)` 的 Spring 回饋。
*   **Pending Zone (`.pending-card`)**：套用 Glass 材質，建立空間階層感。
*   **Friction Textarea**：無邊框大圓角，Focus 時產生 Accent Color 光暈 (`box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.2)`)。
