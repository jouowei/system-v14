import streamlit as st
import pandas as pd
import datetime
import json
import sys
import os
import google.generativeai as genai
from io import StringIO
import contextlib

# --- 引用 ---
try:
    from tools.memory_logger import log_decision
    from tools.smart_search import smart_search as run_smart_search
    from prompts import SYSTEM_PROMPT # 引用新版大腦
except ImportError as e:
    st.error(f"❌ 模組引用失敗: {e}")
    st.stop()

# --- Gemini 設定 ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("❌ 找不到 API Key。")
    st.stop()
    
model = genai.GenerativeModel('gemini-3-flash-preview')

# --- 介面設定 ---
st.set_page_config(page_title="System v14 War Room", layout="wide", page_icon="🛡️")

# --- 左側控制欄 ---
with st.sidebar:
    st.title("🛡️ System v14")
    st.caption("Anti-Fragile Investing Agent")
    st.markdown("---")
    
    protocol = st.selectbox(
        "啟動協議",
        ["協議 F: 個股偵察 (Scout)", "協議 A: 情報解碼 (Intel)", "協議 G: 趨勢獵殺 (Hunt)", "協議 C: 宏觀診斷 (Macro)"]
    )
    
    # 依協議變換輸入介面
    if protocol == "協議 C: 宏觀診斷 (Macro)":
        st.subheader("📊 ARI 儀表板數據輸入")
        ticker = "MACRO_ARI" # 固定代號
        
        # 讓指揮官輸入關鍵指標 (預設值僅供參考)
        sofr_iorb = st.text_input("SOFR - IORB (流動性)", value="-0.05")
        hyg_trend = st.selectbox("HYG 高收益債 (信用)", ["上漲 (風險偏好)", "下跌 (避險)", "盤整"])
        btc_trend = st.selectbox("BTC (流動性金絲雀)", ["強勢", "弱勢", "崩盤"])
        cogo_ratio = st.selectbox("銅金比 (景氣)", ["上升 (復甦)", "下降 (衰退/滯脹)"])
        
        macro_context = st.text_area("其他宏觀筆記 (Fed 態度/通膨數據)", height=100)
        
        # 組合給 AI 的指令
        user_input = f"""
        執行協議 C：宏觀週期定位與 ARI 風險檢查。
        【儀表板讀數】
        1. SOFR-IORB: {sofr_iorb} (流動性壓力)
        2. HYG 趨勢: {hyg_trend}
        3. BTC 趨勢: {btc_trend}
        4. 銅金比: {cogo_ratio}
        
        【補充情報】
        {macro_context}
        
        請輸出 L1/L2/L3 坐標，並計算 ARI 風險燈號。
        """

    elif protocol == "協議 F: 個股偵察 (Scout)":
        ticker = st.text_input("輸入代號 (Ticker)", value="NVDA")
        user_input = f"分析個股 {ticker}。請評估其物理層瓶頸、護城河與當前估值。"
        
    elif protocol == "協議 A: 情報解碼 (Intel)":
        ticker = st.text_input("相關代號 (選填)", value="TSM")
        news_content = st.text_area("貼上新聞內容/連結", height=150)
        user_input = f"根據以下情報進行 PACER 解碼，判斷對 {ticker} 的影響：\n{news_content}"
        
    else: # 協議 G
        ticker = "TREND"
        trend_kw = st.text_input("輸入趨勢關鍵字", value="液冷散熱")
        user_input = f"針對趨勢 '{trend_kw}' 進行獵殺分析，尋找供應鏈中的壟斷者。"

    run_btn = st.button("🚀 執行推演")
    st.markdown("---")

# --- 主畫面 ---
st.title("COMMANDER DASHBOARD")

if run_btn:
    # 1. 記憶回溯
    st.subheader("📂 記憶回溯 (Memory Retrieval)")
    output_capture = StringIO()
    with contextlib.redirect_stdout(output_capture):
        search_kw = ticker
        run_smart_search(search_kw)
    
    memory_json = output_capture.getvalue()
    # (省略顯示記憶表格的代碼以節省篇幅，邏輯不變)
    if len(memory_json) > 10:
         st.text(f"已載入關於 {ticker} 的歷史決策...")

    # 2. Gemini 深度思考
    st.subheader("🧠 System 2 Deep Thinking")
    
    with st.status("正在執行 MFR 物理審計與週期定位...", expanded=True) as status:
        full_prompt = f"{SYSTEM_PROMPT}\n\n【歷史記憶】{memory_json}\n【指揮官指令】{user_input}"
        
        try:
            response = model.generate_content(full_prompt)
            raw_text = response.text
            json_str = raw_text[raw_text.find('{'):raw_text.rfind('}')+1]
            ai_result = json.loads(json_str)
            status.update(label="✅ 推演完成", state="complete", expanded=False)
        except Exception as e:
            st.error(f"AI 推演失敗: {e}")
            st.stop()

    # 3. 戰術指令展示 (針對協議 C 特別優化介面)
    st.subheader("📊 戰術指令 (Tactical Directives)")
    
    # --- 如果是協議 C，顯示週期儀表板 ---
    if protocol == "協議 C: 宏觀診斷 (Macro)":
        coords = ai_result.get("cycle_coords", {})
        ari = ai_result.get("ari_signals", {})
        
        # 週期坐標列
        c1, c2, c3, c4 = st.columns(4)
        c1.info(f"L1 庫存: {coords.get('L1_Inventory', 'N/A')}")
        c2.info(f"L2 產能: {coords.get('L2_CapEx', 'N/A')}")
        c3.info(f"L3 流動性: {coords.get('L3_Liquidity', 'N/A')}")
        c4.info(f"L4 技術: {coords.get('L4_Tech', 'N/A')}")
        
        st.divider()
        
        # ARI 風險燈號
        col_risk, col_msg = st.columns([1, 3])
        status_color = ari.get("status", "Yellow")
        
        if "Green" in status_color:
            col_risk.success(f"ARI 訊號: {status_color}")
        elif "Red" in status_color:
            col_risk.error(f"ARI 訊號: {status_color}")
        else:
            col_risk.warning(f"ARI 訊號: {status_color}")
            
        col_msg.metric("主要威脅", ari.get("main_threat", "N/A"))

    # --- 通用儀表板 ---
    with st.expander("閱讀完整戰略報告 (Full Analysis)", expanded=True):
        st.markdown(ai_result.get("full_analysis", "無詳細分析"))

    st.divider()
    
    # 關鍵數據
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("決策", ai_result.get("decision", "N/A"))
    col2.metric("風險分 (ARI)", ai_result.get("risk_score", "N/A"))
    col3.metric("目標/點位", ai_result.get("target_price", "N/A"))
    col4.metric("PACER", ai_result.get("pacer_type", "N/A"))

    st.info(f"**核心理由：** {ai_result.get('rationale', 'N/A')}")

    # 4. 自動歸檔
    st.divider()
    st.success("💾 寫入記憶體...")
    
    log_payload = json.dumps({
        "log_id": f"{datetime.datetime.now().strftime('%Y%m%d')}-{ticker}",
        "ticker": ticker,
        "decision": ai_result.get("decision"),
        "rationale": ai_result.get("rationale"),
        "keywords": ai_result.get("keywords"),
        "pacer_type": ai_result.get("pacer_type"),
        "risk_score": ai_result.get("risk_score"),
        "entry_price": ai_result.get("target_price"),
        "full_analysis": ai_result.get("full_analysis", "N/A")
    })
    
    try:
        log_decision(log_payload)
        st.toast("✅ 數據已存入 Google Sheets", icon="🎉")
    except Exception as e:
        st.error(f"寫入錯誤: {e}")

else:
    st.info("👈 請選擇協議並啟動")