# 我的投資簿：正式庫存工作台

目前只保留正式唯讀庫存工作台。雙擊 **啟動投資簿.cmd** 開啟，不要直接開 web/index.html；背景服務關閉後，行情與提醒也會停止。

## 使用

1. 在「連線與金鑰」輸入正式查詢用途的 API Key／Secret Key，或使用 Windows 已保存的金鑰。
2. 按「連線到正式查詢環境」，核對證券帳戶。
3. 在「庫存工作台」查看股數、成本、行情、未實現損益及更新時間。
4. 可保存關注清單與一般價格提醒。B15 追蹤區已保留，策略判定及歷史加減碼紀錄尚未接入。

此版本封鎖所有下單路由。庫存使用股數單位，支援含 A、B 等尾碼的 ETF。查詢失敗保留上次成功資料；行情時間與庫存查詢時間分開顯示。

每次重新啟動可能取得不同網址與本機連線憑證，請使用本次啟動的新分頁。只關閉瀏覽器不一定會停止背景服務；結束時可使用介面的「登出並結束本機服務」。

## 資料與備份

- 金鑰可由 Windows 認證管理員保護，不放進 GitHub、程式或 OneDrive。
- 關注／提醒設定存於 `%LOCALAPPDATA%\Onic\SinoPac\web-settings.json`。
- 真實庫存與行情目前只保留於本次連線記憶體，尚無歷史持倉資料庫。
- `github-backup` 是與 GitHub 同步的 Git 儲存庫，程式位於 `apps/onic-portfolio`。
- `data/inventory-v1-source.zip` 是明確檔案清單的程式備份，不含帳務與金鑰。
- `data/v1-review` 保留此版的假資料介面驗證截圖。

2026-10-05 已實測成功取得 7 筆正式庫存及 7 筆行情；與券商帳戶畫面逐項核對仍是獨立驗收。假服務測試不代表正式帳戶驗證。

## 維護

請保留 `.venv`：新版啟動器需要其中的套件，使用電腦上已允許的 Python 3.11，不執行曾被封鎖的虛擬環境啟動器。

離線檢查：`python -m unittest test_inventory_v1 test_web.WorkspaceTests test_web.HttpSecurityTests`。實際執行可使用啟動器指定的 Python 3.11。

完整資料流程見 INVENTORY_V1.md；安裝說明見 README_INVENTORY.md；本次整理範圍見 CLEANUP.md。
