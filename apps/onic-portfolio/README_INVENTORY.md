# 我的投資簿：正式庫存工作台

這是本機 Python + HTML/CSS/JavaScript 的獨立工作台，位於官方 Shioaji Pro fork 的 apps/onic-portfolio，尚未整合原作 React 前端。

## Windows 使用

既有專案可雙擊「啟動投資簿.cmd」。需已安裝 Python 3.11 與 .venv/Lib/site-packages 內的 requirements.txt 套件；launch_web.py 沿用已允許的 Python 執行檔，不執行曾被 Device Guard 擋下的 .venv 啟動程式。

新環境也可使用組織允許的 Python 3.11，安裝 requirements.txt 的依賴後執行 `python web_app.py`。勿調整或繞過組織安全政策。

網頁只能經由本機啟動 URL 開啟，直接開 index.html 無法連線。選取正式查詢金鑰或在本機輸入 Key/Secret，登入後選擇證券帳戶，再更新庫存。金鑰需有正式環境、帳務與所需行情權限。

## 狀態

- 正式唯讀：後端拒絕模擬登入與所有下單路由。
- 股數、成本、未實現損益來自帳務；行情獨立更新。
- B15 是策略追蹤位置，規則與歷史加減碼紀錄尚未接入。
- 本機假服務測試不能證明正式登入或真實庫存已驗證。
- 設定存於 LOCALAPPDATA/Onic/SinoPac；金鑰可由 Windows 認證管理員保護。

## 測試與備份

`python -m unittest test_inventory_v1 test_web.WorkspaceTests test_web.HttpSecurityTests`

backup_source.py 只匯出明列的程式與文件，另附 UTF-8 內容 SHA-256。輸出不是帳務備份，需由有權限的 GitHub 連線提交到 onic-portfolio-v1 分支並核對提交內容。勿把 data、.env、日誌或憑證加入公開版本。

完整第一版資料流程與驗收邊界見 INVENTORY_V1.md。
