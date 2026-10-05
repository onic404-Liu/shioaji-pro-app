---
name: 我的投資簿
description: 亮色台股正式庫存工作台，資料來源與操作狀態清楚可見。
colors:
  primary: "#146447"
  primary-deep: "#104d37"
  ink: "#25352f"
  muted: "#5d6b65"
  canvas: "#f1f4f2"
  surface: "#ffffff"
  line: "#dce3df"
  selected: "#eaf3ed"
  up: "#ac3f36"
  down: "#18694c"
  warning: "#785818"
typography:
  body:
    fontFamily: '"Segoe UI", "Microsoft JhengHei", sans-serif'
    fontSize: "13px"
  title:
    fontSize: "20px"
    fontWeight: 650
    lineHeight: 1.3
  label:
    fontSize: "11px"
    fontWeight: 600
  section:
    fontSize: "12px"
    fontWeight: 650
  quote:
    fontSize: "30px"
    fontWeight: 650
    lineHeight: 1.2
rounded:
  panel: "3px"
  input: "4px"
  dialog: "8px"
spacing:
  workspace-gap: "10px"
  panel-inline: "12px"
  quote-inline: "16px"
  desktop-gutter: "18px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.panel}"
    padding: "8px 12px"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.panel}"
    padding: "8px 12px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.input}"
    padding: "8px 10px"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
  symbol-selected:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.ink}"
    padding: "11px 12px"
---

# Design System: 我的投資簿

## Overview

**Creative North Star: "亮色交易工作桌"**

以清楚的資料層級、緊湊工具列及白色工作區呈現正式台股庫存、關注標的與 B15 追蹤位置。沿用既有淡綠背景與深綠操作色；使用繁體中文和系統字型，讓數字與來源先被讀懂。

主要參考是使用者指定的[官方 Shioaji Pro 專案](https://github.com/Sinotrade/shioaji-pro-app)及其[淺色交易工作台](https://sinotrade.github.io/shioaji-pro-app/shot-terminal-light.png)。參考畫面的價格與帳務只用於版面判讀，不是本專案資料，也不代表已驗證該專案的登入或交易。

**Key Characteristics:**
- 白色資料面板、淡綠工作區與深綠操作色。
- 細分隔線、緊湊工具列與對齊數字。
- 帳戶、用途、資料來源與回報狀態清楚可見。
- 桌面多欄工作台，窄螢幕依序展開。

## Colors

主要操作色為深綠，懸停使用更深的綠色。中性色由白色資料面板、淡綠灰工作區、深色內文及細線構成；選取標的用淡綠底與左緣深綠指示線。色彩值以前置 tokens 為準。

台股上漲／正損益使用紅色，下跌／負損益使用綠色；警示採褐色系。新版不顯示買賣操作。

**The 來源可讀 Rule.** 模擬、正式唯讀、設計預覽與離線假服務必須用文字標明；不能僅靠色點區別。

## Typography

正文採 Segoe UI、Microsoft JhengHei 與系統 sans-serif。主標題與所選股票名稱使用 title，區塊標題使用 section，欄位標籤與表格保持緊湊。

報價採 quote 層級，行動版縮至（27px）；摘要數字桌面為（17px），行動版為（18px）。金融數字使用 tabular-nums，同欄數值靠右並保留漲跌正負號。

## Layout

目前實作已依參考重排：頂端為橫向主導覽與連線／帳戶工具列，其下是緊湊資產摘要。交易工作台左側為自選股及持有標的，中間依序為所選行情、持股明細與委託紀錄，右側為模擬委託表單與價格提醒。

桌面（1440px）採三欄，左欄（205px）、右欄（286px），中央彈性延展，欄距使用 workspace-gap。大螢幕（1600px 以上）左右欄增至（230px／320px）。筆電（1024px）保留三欄，左右欄為（175px／265px），行情事實格改成兩欄。

寬度（950px 以下）改成兩欄，B15 與提醒移到中央資料區下方。行動版（600px 以下；檢視寬度 390px）依序顯示標的清單、行情／庫存、B15／提醒；股票清單與導覽可橫向操作，表格在自身容器內水平捲動。

新版瀏覽器檢視紀錄位於 `data/v1-review/desktop.png`、`mobile.png`。這些是假資料介面證據，不能作為真實券商連線證據。舊版截圖已封存。

## Elevation & Depth

常態工作區以背景、細框及分隔線分層，不使用裝飾陰影。所選股票左緣有內側（2px）指示線，表示選取狀態。

確認對話框與短暫訊息有陰影，用於區別需要確認的操作及暫時回饋。一般面板不套用浮層樣式。

## Shapes

面板與主要按鈕採小圓角 panel。輸入欄沿用 input 圓角，確認對話框採 dialog 圓角。表格、工具列與導覽以直線結構為主；連線色點保持圓形。

## Components

主導覽使用頂端水平按鈕，選取頁面有淡色底與深綠底線。手機仍可橫向操作；連線列保留帳戶選擇與來源。

主要按鈕為深綠實底，次要操作為白底綠字細框。停用狀態降低透明度並顯示不可操作游標；鍵盤焦點使用（3px）綠色外框。遵循減少動態偏好，取消轉場。

股票清單按鈕顯示名稱、代號、報價與漲跌。點選清單或持股列同步更新行情、持股事實與 B15 追蹤位置；預覽中的價格為虛構資料，不是市場報價。

**The 草稿環境 Rule.** 設計預覽、連線用途或帳戶變更時清除所選標的與委託代號／限價，避免將另一環境的草稿帶入後續操作。

右側呈現 B15 持倉追蹤與一般價格提醒。B15 判定與加減碼紀錄標示尚未接入；模擬委託及回報區塊隱藏且不可互動。設計預覽停用 API 操作與儲存；正式查詢用途在後端封鎖交易。

行情區顯示最近報價、來源／接收時間及持股事實。沒有歷史資料時不繪製走勢圖。空值顯示破折號，離線與查詢失敗顯示原因；持股查詢時間與報價接收時間分別呈現。

**The 回報狀態 Rule.** 傳送中、已受理、成交、取消、失敗與結果未知使用明確文字；不能把送出當成成交或官方測試審核通過。

## Do's and Don'ts

### Do:
- **Do** 以白色工作區、細框、緊湊工具列與小圓角保持終端介面的可讀性。
- **Do** 同步所選標的的行情、持倉及 B15 位置；切換帳戶時清除前帳戶資料。
- **Do** 在數字附近標明來源、單位與時間，紅綠之外保留正負號與文字狀態。
- **Do** 檢查桌面、筆電及手機的實際捲動與選取操作。

### Don't:
- **Don't** 使用裝飾漸層、發光效果、浮動宣傳卡片、襯線大數字或 emoji。
- **Don't** 用沒有來源的圖表、示範數字或空值冒充真實帳務。
- **Don't** 將離線介面驗證、下單呼叫成功或自動掃描通過視為真實帳戶驗證。
- **Don't** 將金鑰回傳至網頁、存入瀏覽器儲存或寫入 OneDrive 專案設定。

