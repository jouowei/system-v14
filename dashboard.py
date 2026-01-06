import streamlit as st
import pandas as pd
import datetime
import json
import sys
import os
import google.generativeai as genai
from io import StringIO
import contextlib

# --- 引用本地工具 ---
try:
    from tools.memory_logger import log_decision
    from tools.smart_search import smart_search as run_smart_search
except ImportError as e:
    st.error(f"❌ 模組引用失敗: {e}")
    st.stop()

# --- 設定 Gemini ---
# 從 secrets.toml 讀取金鑰
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("❌ 找不到 API Key。請在 .streamlit/secrets.toml 中設定 GOOGLE_API_KEY。")
    st.stop()

# 使用 Gemini 1.5 Pro (支援長文本與推理)
model = genai.GenerativeModel('gemini-3-flash-preview')

# --- 介面設定 ---
st.set_page_config(page_title="System v14 War Room", layout="wide", page_icon="🛡️")

# --- System Prompt (包含 PACER 與 投資邏輯) ---
SYSTEM_PROMPT = """
你是一個名為 System v14 的頂級反脆弱投資 AI。你的任務是輔助指揮官進行決策。
請嚴格遵守以下思考框架：

1. **PACER 資訊消化協議**：
   - P (程序): 具體操作策略。
   - A (類比): 歷史對比 (如 2000年泡沫)。
   - C (概念): MFR 物理審計、熱力學瓶頸、週期定位。
   - E (證據): 數據背後的結論 (非單純數字)。
   - R (參考): 僅做索引。

2. **輸出格式要求**：
   請以 JSON 格式輸出最終結論，格式如下：
   {
       "decision": "Buy/Sell/Hold/Monitor",
       "pacer_type": "P/A/C/E/R",
       "target_price": "具體價格或區間",
       "risk_score": "0-100",
       "rationale": "簡短有力的核心理由 (100字內)",
       "keywords": "#Tag1 #Tag2 #Tag3",
       "full_analysis": "完整的分析邏輯，包含 MFR 審計與推演過程..."
   }
"""

# --- 左側控制欄 ---
with st.sidebar:
    st.title("🛡️ System v14")
    st.caption("Anti-Fragile Investing Agent")
    st.markdown("---")
    
    protocol = st.selectbox(
        "啟動協議",
        ["協議 F: 個股偵察 (Scout)", "協議 A: 情報解碼 (Intel)", "協議 G: 趨勢獵殺 (Hunt)"]
    )
    
    if protocol == "協議 F: 個股偵察 (Scout)":
        ticker = st.text_input("輸入代號 (Ticker)", value="NVDA")
        user_input = f"分析個股 {ticker}。請評估其物理層瓶頸、護城河與當前估值。"
    elif protocol == "協議 A: 情報解碼 (Intel)":
        ticker = st.text_input("相關代號 (選填)", value="TSM")
        news_content = st.text_area("貼上新聞內容/連結", height=150)
        user_input = f"根據以下情報進行 PACER 解碼，判斷對 {ticker} 的影響：\n{news_content}"
    else: 
        ticker = "TREND"
        trend_kw = st.text_input("輸入趨勢關鍵字", value="液冷散熱")
        user_input = f"針對趨勢 '{trend_kw}' 進行獵殺分析，尋找供應鏈中的壟斷者。"

    run_btn = st.button("🚀 啟動 Gemini 推演")
    st.markdown("---")
    st.caption("Brain: Gemini 1.5 Pro | Memory: Active")

# --- 主畫面 ---
st.title("COMMANDER DASHBOARD")

if run_btn:
    # 1. 記憶回溯 (Recall)
    st.subheader("📂 記憶回溯 (Memory Retrieval)")
    
    # 執行搜尋
    output_capture = StringIO()
    with contextlib.redirect_stdout(output_capture):
        search_kw = ticker if ticker != "TREND" else trend_kw
        run_smart_search(search_kw)
    
    memory_json = output_capture.getvalue()
    memory_context = ""
    
    # 顯示記憶
    try:
        logs = json.loads(memory_json)
        if logs and isinstance(logs, list):
            df = pd.DataFrame(logs)
            cols_to_show = [c for c in ['timestamp', 'decision', 'rationale', 'keywords'] if c in df.columns]
            st.dataframe(df[cols_to_show], use_container_width=True)
            # 將記憶轉為文字餵給 AI
            memory_context = f"參考過去決策紀錄：{memory_json}"
        else:
            st.info("查無相關歷史紀錄")
            memory_context = "過去無相關紀錄。"
    except:
        st.info("記憶資料庫回傳為空")

    # 2. Gemini 深度思考 (Real AI)
    st.subheader("🧠 System 2 Deep Thinking (Gemini)")
    
    with st.status("正在連線 Google Brain...", expanded=True) as status:
        st.write("正在融合歷史記憶與當前情報...")
        
        # 組合 Prompt
        full_prompt = f"""
        {SYSTEM_PROMPT}
        
        ---
        【歷史記憶】
        {memory_context}
        
        【指揮官指令】
        {user_input}
        
        請開始推演，務必輸出合規的 JSON。
        """
        
        try:
            # 呼叫 API
            response = model.generate_content(full_prompt)
            raw_text = response.text
            
            # 嘗試提取 JSON (有時候 AI 會多講話，我們只要 JSON 部分)
            # 簡單處理：找第一個 { 和最後一個 }
            json_str = raw_text[raw_text.find('{'):raw_text.rfind('}')+1]
            
            ai_result = json.loads(json_str)
            
            status.update(label="✅ 推演完成", state="complete", expanded=False)
            
        except Exception as e:
            st.error(f"AI 推演失敗: {e}")
            st.text(raw_text) # 顯示原始回應以便除錯
            st.stop()

    # 3. 戰術指令展示
    st.subheader("📊 戰術指令 (Tactical Directives)")
    
    # 顯示完整分析文字
    with st.expander("閱讀完整戰略報告 (Full Analysis)", expanded=True):
        st.markdown(ai_result.get("full_analysis", "無詳細分析"))

    st.divider()
    
    # 儀表板數據
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("決策", ai_result.get("decision", "N/A"))
    col2.metric("PACER", ai_result.get("pacer_type", "N/A"))
    col3.metric("目標", ai_result.get("target_price", "N/A"))
    col4.metric("風險", ai_result.get("risk_score", "N/A"))

    st.info(f"**核心理由：** {ai_result.get('rationale', 'N/A')}")

    # 4. 自動歸檔
    st.divider()
    st.success("💾 寫入記憶體...")
    
# 找到這一段，加入 "full_analysis"
    log_payload = json.dumps({
        "log_id": f"{datetime.datetime.now().strftime('%Y%m%d')}-{ticker}",
        "ticker": ticker,
        "decision": ai_result.get("decision"),
        "rationale": ai_result.get("rationale"),
        "keywords": ai_result.get("keywords"),
        "pacer_type": ai_result.get("pacer_type"),
        "risk_score": ai_result.get("risk_score"),
        "entry_price": ai_result.get("target_price"),
        # --- 新增這一行 ---
        "full_analysis": ai_result.get("full_analysis", "N/A") 
        # ----------------
    })
    
    try:
        result = log_decision(log_payload)
        if "Success" in result or "Logged" in result:
             st.toast("✅ 數據已存入 Google Sheets", icon="🎉")
        else:
             st.error(f"寫入失敗: {result}")
    except Exception as e:
        st.error(f"寫入錯誤: {e}")

else:
    st.info("👈 請輸入指令並啟動推演")