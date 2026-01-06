# tools/memory_logger.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
import json
import datetime
import os
import streamlit as st # 記得引入這個

# --- 1. 自動路徑修正 (Path Logic) ---
# 確保無論是從 dashboard 呼叫還是直接執行，都能找到金鑰
KEY_PATH = 'config/service_account.json'
if not os.path.exists(KEY_PATH):
    # 如果找不到，試試看上一層目錄 (針對直接在 tools 資料夾執行的情況)
    KEY_PATH = '../config/service_account.json'

# --- 2. Google Sheets 連接設定 ---
# tools/memory_logger.py 修正版

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # --- 優先嘗試：從 Streamlit 雲端保險箱讀取 ---
        if "gcp_service_account" in st.secrets:
            # 這是雲端模式
            creds_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # --- 備案：本地模式 (讀取檔案) ---
            key_path = 'config/service_account.json'
            if not os.path.exists(key_path):
                key_path = '../config/service_account.json'
            creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, scope)

        client = gspread.authorize(creds)
        sheet = client.open("System_v14_Memory_Log").sheet1
        return sheet

    except Exception as e:
        print(f"連線失敗: {str(e)}")
        return None

# --- 3. 寫入邏輯 (Append Logic) ---
def log_decision(data_json):
    sheet = get_sheet()
    if not sheet:
        return "Connection Failed"
    
    # --- 新增這行：印出它到底連到哪裡去了 ---
    print(f"🔗 寫入目標網址: {sheet.spreadsheet.url}") 
    # -------------------------------------

    try:
        data = json.loads(data_json)
        
        # 準備寫入的資料列 (Row) - 對應 Google Sheet 的 10 個欄位
        # 順序：ID | Time | Ticker | Decision | Rationale | Risk | Entry | Cycle | Keywords | PACER
        row = [
            data.get('log_id', f"AUTO-{datetime.datetime.now().strftime('%Y%m%d%H%M')}"),
            str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M')),
            data.get('ticker', 'N/A'),
            data.get('decision', 'Watch'),
            data.get('rationale', 'No rationale provided'),
            data.get('risk_score', 0),
            data.get('entry_price', 'Market'),
            data.get('cycle_position', 'Unknown'),
            data.get('keywords', ''),
            data.get('pacer_type', 'R'),
            data.get('full_analysis', 'N/A')
        ]
        
        # 寫入最後一列
        sheet.append_row(row)
        print(f"✅ [System Logged] ID: {row[0]} | Type: {row[9]}")
        return "Success"
        
    except Exception as e:
        print(f"❌ Error logging data: {str(e)}")
        return f"Error: {str(e)}"

# tools/memory_logger.py 的最底部

if __name__ == "__main__":
    # 如果有外部傳入參數，照常處理
    if len(sys.argv) > 1:
        # 嘗試修復 Windows 傳入的 JSON 引號問題
        input_str = sys.argv[1]
        # 如果發現引號被 PowerShell 吃掉 (看起來不像 JSON)，做簡單修補
        if not input_str.startswith('{'): 
            print("⚠️ 警告：輸入格式可能被 Shell 破壞，建議使用 Dashboard 操作。")
        
        log_decision(input_str)
        
    else:
        # 如果沒有參數，自動執行「自我連線測試」
        print("🔧 檢測到無參數輸入，啟動 [自我測試模式]...")
        
        test_payload = json.dumps({
            "ticker": "SYSTEM_CHECK",
            "decision": "Connect_Success",
            "rationale": "這是一條由 Python 直接寫入的測試數據，確認權限正常。",
            "keywords": "#Test #Connection",
            "log_id": "TEST-001",
            "pacer_type": "T"
        })
        
        print(f"📡 正在嘗試寫入測試數據...")
        log_decision(test_payload)