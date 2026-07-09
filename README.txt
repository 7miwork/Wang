股票市場自動分析工具 - 安裝說明
================================

第一步: 建立資料夾
1. 開啟 Terminal
2. 輸入: mkdir ~/boersen-analyzer
3. 將所有檔案複製到 ~/boersen-analyzer

第二步: 安裝依賴
1. 在 Terminal 中輸入:
   cd ~/boersen-analyzer
   pip3 install yfinance requests

第三步: 設定 API 金鑰
1. 開啟 api_keys.json
2. 填入你的 API 金鑰 (只需要填你有的即可)
3. 存檔

第四步: 開始使用
方法一 (手動):
   雙擊 start_command.sh

方法二 (自動每天執行):
   1. 開啟 Terminal
   2. 輸入: crontab -e
   3. 加入: 0 9 * * * cd ~/boersen-analyzer && python3 stock_analyzer.py
   4. 存檔並離開

方法三 (自動更新):
   直接雙擊 start_command.sh，工具會自動每 60 分鐘更新一次

API 金鑰取得 (免費):
- OpenRouter: https://openrouter.ai/keys
- Groq: https://console.groq.com/keys
- Mistral: https://console.mistral.ai/

注意: 請只填入你擁有的 API 金鑰，其餘可以留空。

如果 start_command.sh 無法執行:
1. 開啟 Terminal
2. 輸入: chmod +x ~/boersen-analyzer/start_command.sh
3. 再次雙擊 start_command.sh

功能說明:
- 自動分析 AAPL, MSFT, GOOGL, TSLA, AMZN, NVDA, META, 2330.TW, 2454.TW
- 可在 api_keys.json 中修改股票清單
- 預設每 60 分鐘自動更新（可在 api_keys.json 調整）
- 支援多家 AI 提供者，自動切換可用服務
- 完整繁體中文介面