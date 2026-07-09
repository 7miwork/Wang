#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票市場自動分析工具 - Stock Market Auto Analyzer
主程式: GUI 介面 + AI 分析 + 自動更新
"""

import json
import os
import sys
import threading
import time
import subprocess
import platform
import traceback
from datetime import datetime, timedelta
from tkinter import (
    Tk, Frame, Text, Scrollbar, Button, Label,
    BOTH, END, LEFT, RIGHT, TOP, BOTTOM, X, Y, messagebox, font
)
from tkinter import ttk

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import requests
except ImportError:
    requests = None


# ============================================================
# 路徑設定
# ============================================================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
KEYS_FILE = os.path.join(APP_DIR, "api_keys.json")
CACHE_FILE = os.path.join(APP_DIR, ".last_analysis_cache.json")


# ============================================================
# 工具函式
# ============================================================
def load_config():
    """讀取 api_keys.json 設定檔"""
    if not os.path.exists(KEYS_FILE):
        return None
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cache(data):
    """儲存分析結果快取"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_cache():
    """讀取快取的分析結果"""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def open_file(path):
    """用系統預設程式開啟檔案"""
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        elif platform.system() == "Windows":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


# ============================================================
# API 提供者管理
# ============================================================
class AIProviderManager:
    """管理多個 AI 提供者，自動切換可用服務"""

    def __init__(self, config):
        self.providers = config.get("providers", {})
        self.status = {}  # provider_name -> True/False/None (None=未測試)
        self.current_provider = None
        self.current_model = None

    def test_all(self):
        """測試所有 API Keys 是否有效"""
        results = []
        for name, info in self.providers.items():
            key = info.get("api_key", "")
            if not key or key.startswith("DEIN_"):
                self.status[name] = False
                results.append((name, False, "未設定 API Key"))
                continue

            # 用簡單請求測試 key 是否有效
            is_valid = self._test_provider(name, info)
            self.status[name] = is_valid
            if is_valid:
                results.append((name, True, "有效"))
            else:
                results.append((name, False, "API Key 無效或無法連線"))

        # 選擇第一個可用的提供者
        for name in self.providers:
            if self.status.get(name):
                models = self.providers[name].get("free_models", [])
                if models:
                    self.current_provider = name
                    self.current_model = models[0]
                    break

        return results

    def _test_provider(self, name, info):
        """測試單一提供者"""
        if requests is None:
            return False
        try:
            api_key = info.get("api_key", "")
            base_url = info.get("base_url", "")
            models = info.get("free_models", [])

            if not api_key or not models:
                return False

            # 簡單的 curl-like 請求測試
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            test_payload = {
                "model": models[0],
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5
            }
            resp = requests.post(
                base_url,
                headers=headers,
                json=test_payload,
                timeout=10
            )
            return resp.status_code in (200, 201, 202)
        except Exception:
            return False

    def analyze_stock(self, stock_symbol, stock_data):
        """使用 AI 分析股票"""
        if self.current_provider is None:
            return "⚠ 目前沒有可用的 AI 提供者，請先設定有效的 API Key。"

        provider_info = self.providers.get(self.current_provider, {})
        api_key = provider_info.get("api_key", "")
        base_url = provider_info.get("base_url", "")
        model = self.current_model

        if not api_key or not base_url or not model:
            return "⚠ API 設定不完整"

        # 建立分析用的 prompt（傳統中文）
        prompt = self._build_analysis_prompt(stock_symbol, stock_data)

        # 嘗試發送請求
        max_retries = len(self.providers)
        for attempt in range(max_retries):
            try:
                if requests is None:
                    return "⚠ 未安裝 requests 套件。請執行: pip3 install requests"

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是一位專業的股票分析師。請用繁體中文回答。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1024
                }

                resp = requests.post(base_url, headers=headers, json=payload, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    # 解析不同 API 的回應格式
                    content = ""
                    if "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        if "message" in choice and "content" in choice["message"]:
                            content = choice["message"]["content"]
                        elif "text" in choice:
                            content = choice["text"]
                    if content:
                        return content.strip()
                    return "⚠ API 回傳格式異常"
                elif resp.status_code == 401 or resp.status_code == 403:
                    # Key 失效，切換到下一個
                    self.status[self.current_provider] = False
                    self._switch_to_next_provider()
                    if self.current_provider is None:
                        return "⚠ 所有 API Key 都已失效，請更新設定。"
                    # 更新資訊重試
                    provider_info = self.providers.get(self.current_provider, {})
                    api_key = provider_info.get("api_key", "")
                    base_url = provider_info.get("base_url", "")
                    model = self.current_model
                    continue
                else:
                    return f"⚠ API 錯誤 ({resp.status_code}): {resp.text[:200]}"
            except requests.exceptions.Timeout:
                return "⚠ API 請求超時，請檢查網路連線。"
            except requests.exceptions.ConnectionError:
                return "⚠ 無法連接 API 伺服器，請檢查網路。"
            except Exception as e:
                return f"⚠ API 請求失敗: {str(e)}"

        return "⚠ 所有 API 嘗試均失敗。"

    def _switch_to_next_provider(self):
        """切換到下一個可用的提供者"""
        found = False
        for name in self.providers:
            if found:
                if self.status.get(name):
                    self.current_provider = name
                    models = self.providers[name].get("free_models", [])
                    self.current_model = models[0] if models else None
                    return
            if name == self.current_provider:
                found = True

        # 如果沒有找到下一個，從頭開始找
        for name in self.providers:
            if self.status.get(name):
                self.current_provider = name
                models = self.providers[name].get("free_models", [])
                self.current_model = models[0] if models else None
                return

        self.current_provider = None
        self.current_model = None

    def _build_analysis_prompt(self, symbol, data):
        """建立分析用的提示詞"""
        price = data.get("price", "N/A")
        change = data.get("change", "N/A")
        change_pct = data.get("change_pct", "N/A")
        volume = data.get("volume", "N/A")
        high_5d = data.get("high_5d", "N/A")
        low_5d = data.get("low_5d", "N/A")
        trend = data.get("trend_5d", "N/A")

        prompt = f"""
請分析以下股票數據，並使用繁體中文提供專業分析：

股票代號: {symbol}
目前價格: {price}
今日變動: {change} ({change_pct}%)
5日最高: {high_5d}
5日最低: {low_5d}
5日趨勢: {trend}
成交量: {volume}

請提供以下分析：
1. 技術分析 - 根據價格趨勢和成交量判斷
2. 市場情緒 - 短期市場對該股的看法
3. 投資建議 - 短線操作建議（3-5天）
4. 風險提示 - 需要注意的風險點

請保持客觀，並明確標示每個分析區塊。
"""
        return prompt


# ============================================================
# 股票資料擷取
# ============================================================
class StockDataFetcher:
    """從 yfinance 擷取股票資料"""

    @staticmethod
    def fetch(symbol, days=5):
        """取得單一股票資料"""
        result = {
            "symbol": symbol,
            "price": "N/A",
            "change": "N/A",
            "change_pct": "N/A",
            "volume": "N/A",
            "high_5d": "N/A",
            "low_5d": "N/A",
            "trend_5d": "N/A",
            "error": None
        }

        if yf is None:
            result["error"] = "未安裝 yfinance。請執行: pip3 install yfinance"
            return result

        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{days}d")

            if hist.empty:
                result["error"] = f"無法取得 {symbol} 的資料"
                return result

            # 最新價格
            latest = hist.iloc[-1]
            result["price"] = round(float(latest["Close"]), 2)

            # 今日變動 (如果今天有資料)
            if len(hist) >= 2:
                prev_close = hist.iloc[-2]["Close"]
                change_val = float(latest["Close"]) - float(prev_close)
                result["change"] = round(change_val, 2)
                if prev_close != 0:
                    result["change_pct"] = round((change_val / float(prev_close)) * 100, 2)
                else:
                    result["change_pct"] = 0
            else:
                result["change"] = 0
                result["change_pct"] = 0

            # 成交量
            result["volume"] = int(latest["Volume"]) if "Volume" in hist.columns else "N/A"

            # 5日高低
            result["high_5d"] = round(float(hist["High"].max()), 2)
            result["low_5d"] = round(float(hist["Low"].min()), 2)

            # 5日趨勢 (簡單判斷)
            if len(hist) >= 3:
                first_close = float(hist.iloc[0]["Close"])
                last_close = float(hist.iloc[-1]["Close"])
                if last_close > first_close * 1.02:
                    result["trend_5d"] = "📈 上升趨勢 (+2%以上)"
                elif last_close < first_close * 0.98:
                    result["trend_5d"] = "📉 下降趨勢 (-2%以上)"
                else:
                    result["trend_5d"] = "➡ 橫盤整理"
            else:
                result["trend_5d"] = "數據不足"

        except Exception as e:
            result["error"] = f"{symbol} 擷取錯誤: {str(e)}"

        return result

    @staticmethod
    def fetch_all(symbols, days=5):
        """取得多檔股票資料"""
        results = []
        for sym in symbols:
            data = StockDataFetcher.fetch(sym, days)
            results.append(data)
        return results


# ============================================================
# 主 GUI 應用程式
# ============================================================
class StockAnalyzerApp:
    """股票分析工具的主視窗"""

    def __init__(self, root):
        self.root = root
        self.root.title("股票市場自動分析工具")
        self.root.geometry("900x700")
        self.root.minsize(700, 500)

        # 設定圖示 (如果有的話)
        try:
            self.root.iconbitmap(default=None)
        except Exception:
            pass

        # 設定字型
        self.default_font = font.nametofont("TkDefaultFont")
        self.default_font.configure(size=11)

        # 載入設定
        self.config = load_config()
        if self.config is None:
            self.config = {
                "settings": {"auto_refresh_minutes": 60, "start_automatically": True, "language": "traditional_chinese"},
                "providers": {},
                "stocks": ["AAPL", "MSFT", "GOOGL"],
                "analysis_days": 5
            }

        self.settings = self.config.get("settings", {})
        self.refresh_interval = self.settings.get("auto_refresh_minutes", 60) * 60  # 轉換為秒
        self.start_auto = self.settings.get("start_automatically", True)
        self.stock_symbols = self.config.get("stocks", ["AAPL", "MSFT", "GOOGL"])
        self.analysis_days = self.config.get("analysis_days", 5)

        # 狀態變數
        self.is_running = False
        self.auto_refresh_active = False
        self.last_refresh_time = None
        self.refresh_thread = None
        self.analysis_results = []  # 存最新的分析結果
        self.ai_manager = AIProviderManager(self.config)

        # 建立 GUI
        self._build_gui()

        # 啟動後的初始化
        self.root.after(500, self._on_startup)

    def _build_gui(self):
        """建立 GUI 元件"""
        # --- 頂部標題 ---
        title_frame = Frame(self.root, bg="#2c3e50")
        title_frame.pack(fill=X)

        title_label = Label(
            title_frame,
            text="📊 股票市場自動分析工具",
            font=("Helvetica", 16, "bold"),
            fg="white",
            bg="#2c3e50",
            pady=10
        )
        title_label.pack()

        # --- 狀態列 (顯示 API 狀態 & 下次更新倒數) ---
        self.status_frame = Frame(self.root, bg="#ecf0f1", height=30)
        self.status_frame.pack(fill=X)
        self.status_frame.pack_propagate(False)

        self.status_label = Label(
            self.status_frame,
            text="初始化中...",
            font=("Helvetica", 10),
            bg="#ecf0f1",
            fg="#2c3e50",
            anchor="w",
            padx=10
        )
        self.status_label.pack(side=LEFT, fill=X, expand=True)

        self.refresh_countdown_label = Label(
            self.status_frame,
            text="",
            font=("Helvetica", 10),
            bg="#ecf0f1",
            fg="#7f8c8d",
            anchor="e",
            padx=10
        )
        self.refresh_countdown_label.pack(side=RIGHT)

        # --- 按鈕列 ---
        button_frame = Frame(self.root, bg="#bdc3c7", pady=5)
        button_frame.pack(fill=X)

        btn_style = {"font": ("Helvetica", 11, "bold"), "padx": 15, "pady": 5, "borderwidth": 0}

        self.btn_manual = Button(
            button_frame,
            text="🔄 手動分析",
            bg="#3498db",
            fg="white",
            activebackground="#2980b9",
            activeforeground="white",
            command=self.start_manual_analysis,
            **btn_style
        )
        self.btn_manual.pack(side=LEFT, padx=5)

        self.btn_stop = Button(
            button_frame,
            text="⏹ 停止自動更新",
            bg="#e74c3c",
            fg="white",
            activebackground="#c0392b",
            activeforeground="white",
            command=self.stop_auto_refresh,
            state="disabled",
            **btn_style
        )
        self.btn_stop.pack(side=LEFT, padx=5)

        self.btn_settings = Button(
            button_frame,
            text="⚙ 設定",
            bg="#95a5a6",
            fg="white",
            activebackground="#7f8c8d",
            activeforeground="white",
            command=self.open_settings,
            **btn_style
        )
        self.btn_settings.pack(side=LEFT, padx=5)

        # --- 分析結果文字區 ---
        text_frame = Frame(self.root)
        text_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        self.text_area = Text(
            text_frame,
            wrap="word",
            font=("Menlo", 11),
            bg="#fafafa",
            fg="#2c3e50",
            relief="flat",
            borderwidth=2,
            padx=10,
            pady=10
        )
        self.text_area.pack(side=LEFT, fill=BOTH, expand=True)

        scrollbar = Scrollbar(text_frame, command=self.text_area.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.text_area.config(yscrollcommand=scrollbar.set)

        # 插入歡迎訊息
        self._show_welcome_message()

        # 設定標籤樣式
        self.text_area.tag_config("header", font=("Helvetica", 14, "bold"), foreground="#2c3e50", spacing1=10, spacing3=5)
        self.text_area.tag_config("subheader", font=("Helvetica", 12, "bold"), foreground="#2980b9", spacing1=8, spacing3=3)
        self.text_area.tag_config("content", font=("Menlo", 10), foreground="#34495e")
        self.text_area.tag_config("positive", foreground="#27ae60", font=("Menlo", 10, "bold"))
        self.text_area.tag_config("negative", foreground="#e74c3c", font=("Menlo", 10, "bold"))
        self.text_area.tag_config("neutral", foreground="#f39c12", font=("Menlo", 10))
        self.text_area.tag_config("error", foreground="#e74c3c", font=("Menlo", 10, "bold"))
        self.text_area.tag_config("warning", foreground="#e67e22", font=("Menlo", 10))
        self.text_area.tag_config("divider", foreground="#bdc3c7")
        self.text_area.tag_config("timestamp", font=("Helvetica", 9), foreground="#95a5a6")

    def _show_welcome_message(self):
        """顯示歡迎訊息"""
        self.text_area.insert(END, "📊 股票市場自動分析工具\n\n", "header")
        self.text_area.insert(END, "歡迎使用！\n\n", "subheader")
        self.text_area.insert(END, "功能說明：\n", "subheader")
        self.text_area.insert(END, "• 點擊「手動分析」立即分析所有股票\n")
        self.text_area.insert(END, "• 程式會自動定時更新（設定檔可調整間隔）\n")
        self.text_area.insert(END, "• 支援多家 AI 提供者，自動切換可用服務\n")
        self.text_area.insert(END, "• 點擊「設定」可修改 API Keys 和股票清單\n\n")
        self.text_area.insert(END, "目前監控的股票：\n", "subheader")
        self.text_area.insert(END, f"{', '.join(self.stock_symbols)}\n\n")
        self.text_area.insert(END, "─" * 60 + "\n", "divider")
        self.text_area.insert(END, "正在初始化，請稍候...\n", "content")

    def _on_startup(self):
        """啟動後的初始化"""
        # 測試 API 連線
        self._update_status("正在測試 API 連線...")
        self.root.update_idletasks()

        api_results = self.ai_manager.test_all()
        self._update_api_status(api_results)

        # 檢查必要套件
        if yf is None:
            self._append_text("⚠ 警告：未安裝 yfinance 套件！\n", "warning")
            self._append_text("請在終端機執行: pip3 install yfinance\n\n", "content")
        if requests is None:
            self._append_text("⚠ 警告：未安裝 requests 套件！\n", "warning")
            self._append_text("請在終端機執行: pip3 install requests\n\n", "content")

        # 自動啟動分析
        if self.start_auto and yf is not None:
            self._append_text("🔄 正在執行首次自動分析...\n", "content")
            self.start_auto_refresh()
        else:
            if yf is None:
                self._append_text("請先安裝必要套件後，點擊「手動分析」開始。\n", "content")
            else:
                self._append_text("自動啟動已關閉。點擊「手動分析」開始。\n", "content")

    def _update_status(self, text):
        """更新狀態列文字"""
        self.status_label.config(text=text)

    def _update_api_status(self, results):
        """更新 API 狀態顯示"""
        parts = []
        for name, valid, msg in results:
            icon = "✓" if valid else "✗"
            color = "#27ae60" if valid else "#e74c3c"
            parts.append(f"{icon} {name}")
        status_text = " | ".join(parts)

        if self.ai_manager.current_provider:
            status_text += f" | 使用: {self.ai_manager.current_provider} / {self.ai_manager.current_model}"
        else:
            status_text += " | ⚠ 無可用 AI 提供者"

        self._update_status(status_text)

    def _append_text(self, text, tag=None):
        """在文字區追加內容並自動滾動"""
        self.text_area.insert(END, text, tag)
        self.text_area.see(END)

    def start_manual_analysis(self):
        """手動分析（在背景執行緒執行）"""
        if self.is_running:
            messagebox.showinfo("提示", "分析正在進行中，請稍候。")
            return
        thread = threading.Thread(target=self._run_analysis, daemon=True)
        thread.start()

    def start_auto_refresh(self):
        """啟動自動更新"""
        if self.auto_refresh_active:
            return
        self.auto_refresh_active = True
        self.btn_stop.config(state="normal")
        self.btn_manual.config(state="disabled")
        self._update_status("自動更新已啟動")
        # 立即執行第一次分析，然後啟動排程
        thread = threading.Thread(target=self._run_analysis, daemon=True)
        thread.start()
        # 啟動倒數計時
        self._start_countdown()

    def stop_auto_refresh(self):
        """停止自動更新"""
        self.auto_refresh_active = False
        self.btn_stop.config(state="disabled")
        self.btn_manual.config(state="normal")
        self.refresh_countdown_label.config(text="")
        self._update_status("自動更新已停止")
        self._append_text("\n⏹ 自動更新已停止。\n", "warning")

    def _start_countdown(self):
        """啟動倒數計時顯示"""
        def countdown():
            if not self.auto_refresh_active:
                return
            if self.last_refresh_time:
                elapsed = time.time() - self.last_refresh_time
                remaining = max(0, self.refresh_interval - elapsed)
                mins = int(remaining // 60)
                secs = int(remaining % 60)
                self.refresh_countdown_label.config(
                    text=f"下次更新: {mins:02d}:{secs:02d}"
                )
            self.root.after(1000, countdown)
        self.root.after(1000, countdown)

    def _run_analysis(self):
        """執行完整的分析流程"""
        self.is_running = True
        start_time = time.time()

        try:
            self.root.after(0, lambda: self._update_status("正在擷取股票資料..."))
            self.root.after(0, lambda: self._append_text(
                f"\n{'='*60}\n📊 分析開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*60}\n\n", "header"
            ))

            # 1. 擷取所有股票資料
            stock_datas = StockDataFetcher.fetch_all(self.stock_symbols, self.analysis_days)

            # 2. 對每檔股票進行 AI 分析
            cache_data = []
            for stock_data in stock_datas:
                symbol = stock_data["symbol"]
                if stock_data.get("error"):
                    self.root.after(0, lambda s=symbol, e=stock_data["error"]: self._append_text(
                        f"⚠ {s}: {e}\n", "error"
                    ))
                    cache_data.append({"symbol": symbol, "analysis": f"錯誤: {stock_data['error']}", "stock_data": stock_data})
                    continue

                self.root.after(0, lambda s=symbol: self._update_status(f"正在分析 {s}..."))

                # 顯示基本數據
                self.root.after(0, lambda d=stock_data: self._display_stock_data(d))

                # AI 分析
                analysis = self.ai_manager.analyze_stock(symbol, stock_data)
                self.root.after(0, lambda a=analysis, s=symbol: self._display_analysis(s, a))

                cache_data.append({
                    "symbol": symbol,
                    "analysis": analysis,
                    "stock_data": stock_data,
                    "timestamp": datetime.now().isoformat()
                })

                # 短暫暫停，避免 API 限流
                time.sleep(1)

            # 儲存快取
            save_cache({
                "timestamp": datetime.now().isoformat(),
                "stocks": cache_data
            })
            self.analysis_results = cache_data

            # 完成
            elapsed = time.time() - start_time
            self.last_refresh_time = time.time()
            self.root.after(0, lambda: self._append_text(
                f"\n{'='*60}\n✅ 分析完成！耗時: {elapsed:.1f} 秒\n", "header"
            ))
            self.root.after(0, lambda: self._update_api_status(
                [(name, self.ai_manager.status.get(name, False),
                  "有效" if self.ai_manager.status.get(name) else "無效")
                 for name in self.config.get("providers", {})]
            ))

            # 如果自動更新開啟，排程下一次
            if self.auto_refresh_active:
                self.root.after(0, lambda: self._update_status(
                    f"等待下一次更新（{self.refresh_interval//60} 分鐘後）"
                ))

        except Exception as e:
            error_msg = f"分析過程發生錯誤: {str(e)}\n{traceback.format_exc()}"
            self.root.after(0, lambda: self._append_text(f"\n❌ {error_msg}\n", "error"))

            # 嘗試顯示快取資料
            cached = load_cache()
            if cached:
                self.root.after(0, lambda: self._append_text(
                    "\n📂 顯示上次快取的資料：\n", "warning"
                ))
                for item in cached.get("stocks", []):
                    self.root.after(0, lambda s=item["symbol"], a=item.get("analysis", "N/A"): self._display_analysis(s, a))
        finally:
            self.is_running = False

    def _display_stock_data(self, data):
        """顯示股票基本數據"""
        symbol = data["symbol"]
        price = data.get("price", "N/A")
        change = data.get("change", "N/A")
        change_pct = data.get("change_pct", "N/A")
        volume = data.get("volume", "N/A")
        high = data.get("high_5d", "N/A")
        low = data.get("low_5d", "N/A")
        trend = data.get("trend_5d", "N/A")

        # 決定顏色
        if isinstance(change, (int, float)):
            if change > 0:
                change_str = f"+{change}"
                tag = "positive"
            elif change < 0:
                change_str = f"{change}"
                tag = "negative"
            else:
                change_str = "0"
                tag = "neutral"
        else:
            change_str = str(change)
            tag = "content"

        if isinstance(change_pct, (int, float)):
            change_pct_str = f"+{change_pct}%" if change_pct > 0 else f"{change_pct}%"
        else:
            change_pct_str = str(change_pct)

        text = (
            f"\n{'─'*60}\n"
            f"📈 {symbol}\n"
            f"價格: ${price}  "
            f"變動: {change_str} ({change_pct_str})\n"
            f"5日高低: ${high} ~ ${low}  "
            f"成交量: {volume:,}\n" if isinstance(volume, int) else f"5日高低: ${high} ~ ${low}  成交量: {volume}\n"
        )
        # 修正成交量顯示
        vol_str = f"{volume:,}" if isinstance(volume, int) else str(volume)

        display_text = (
            f"\n{'─'*60}\n"
            f"📈 {symbol}\n"
            f"價格: ${price}  "
            f"變動: {change_str} ({change_pct_str})\n"
            f"5日高低: ${high} ~ ${low}  "
            f"成交量: {vol_str}\n"
            f"5日趨勢: {trend}\n"
        )

        self.root.after(0, lambda t=display_text: self._append_text(t, tag if tag != "neutral" else "content"))

    def _display_analysis(self, symbol, analysis_text):
        """顯示 AI 分析結果"""
        header = f"\n🔍 {symbol} AI 分析結果:\n"
        self.root.after(0, lambda: self._append_text(header, "subheader"))
        self.root.after(0, lambda: self._append_text(analysis_text + "\n", "content"))

    def open_settings(self):
        """開啟設定檔"""
        if os.path.exists(KEYS_FILE):
            open_file(KEYS_FILE)
            self._append_text(f"\n⚙ 已開啟設定檔：{KEYS_FILE}\n請修改後儲存，然後重新啟動程式。\n", "warning")
        else:
            messagebox.showerror("錯誤", f"找不到設定檔：{KEYS_FILE}")


# ============================================================
# 主程式進入點
# ============================================================
def main():
    root = Tk()
    app = StockAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()