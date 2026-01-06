# tools/smart_search.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sys
import json
import pandas as pd
import os
import streamlit as st

# 自動判斷金鑰路徑 (相容 Dashboard 和 獨立執行)
# 如果是從上層目錄呼叫，路徑是 config/...
# 如果是直接執行，路徑是 ../config/...
KEY_PATH = 'config/service_account.json'
if not os.path.exists(KEY_PATH):
    KEY_PATH = '../config/service_account.json'
    
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # --- 優先嘗試：從 Streamlit 雲端保險箱讀取 ---
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # --- 備案：本地模式 ---
        key_path = 'config/service_account.json'
        if not os.path.exists(key_path):
            key_path = '../config/service_account.json'
        creds = ServiceAccountCredentials.from_json_keyfile_name(key_path, scope)
        
    return gspread.authorize(creds)

def smart_search(query):
    try:
        client = get_client()
        sheet = client.open("System_v14_Memory_Log").sheet1
        
        # 獲取所有紀錄
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            print(json.dumps([]))
            return

        # 轉為小寫進行模糊搜尋
        query_lower = query.lower()
        
        # 搜尋邏輯
        mask = (
            df['ticker'].astype(str).str.lower().str.contains(query_lower) | 
            df['keywords'].astype(str).str.lower().str.contains(query_lower) |
            df['rationale'].astype(str).str.lower().str.contains(query_lower) |
            df['pacer_type'].astype(str).str.lower().str.contains(query_lower)
        )
        
        results = df[mask]
        
        if not results.empty:
            # 只回傳最近的 5 筆
            print(results.tail(5).to_json(orient='records', force_ascii=False))
        else:
            print(json.dumps([]))
            
    except Exception as e:
        # 回傳空的 JSON 陣列，避免 Dashboard 報錯
        print(json.dumps({"error": str(e)}))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        smart_search(sys.argv[1])
    else:
        print(json.dumps({"error": "No query provided"}))