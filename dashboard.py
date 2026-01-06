import streamlit as st
import pandas as pd
import datetime
import json
import sys
import os
import google.generativeai as genai
import yfinance as yf # NEW: Import yfinance
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
    st.error("❌ 找不到 API Key。請確認 .streamlit/secrets.toml 設定。")
    st.stop()
    
model = genai.GenerativeModel('gemini-3-flash-preview')

# --- 介面設定 ---
st.set_page_config(page_title="System v14 戰情室", layout="wide", page_icon="🛡️")

# --- Custom CSS ---
def local_css():
    st.markdown("""
    <style>
        /* 全局字體與背景微調 */
        .reportview-container {
            background: #0e1117;
        }
        
        /* 標題樣式 */
        h1, h2, h3 {
            font-family: 'Helvetica Neue', sans-serif;
            font-weight: 600;
        }
        
        /* 卡片樣式 (用於關鍵指標) */
        .metric-card {
            background-color: #262730;
            border: 1px solid #464b5c;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .metric-label {
            color: #9ca0ad;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .metric-value {
            color: #ffffff;
            font-size: 1.5em;
            font-weight: bold;
        }
        
        /* 狀態標籤 */
        .status-tag {
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.85em;
            display: inline-block;
        }
        .status-green { background-color: rgba(76, 175, 80, 0.2); color: #4caf50; border: 1px solid #4caf50; }
        .status-red { background-color: rgba(244, 67, 54, 0.2); color: #f44336; border: 1px solid #f44336; }
        .status-yellow { background-color: rgba(255, 193, 7, 0.2); color: #ffc107; border: 1px solid #ffc107; }
        
    </style>
    """, unsafe_allow_html=True)

local_css()

# --- Helper Function: 顯示指標卡片 ---
def metric_card(label, value, color=None):
    color_style = f"color: {color};" if color else ""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="{color_style}">{value}</div>
    </div>
    """, unsafe_allow_html=True)

# --- Helper Function: 取得股價資訊 ---
@st.cache_data(ttl=300) # 快取 5 分鐘
def get_stock_info(symbol):
    try:
        stock = yf.Ticker(symbol)
        info = stock.info
        
        # 嘗試取得即時價格，若無則用前收盤
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        previous_close = info.get('previousClose')
        
        change = 0
        pct_change = 0
        if price and previous_close:
            change = price - previous_close
            pct_change = (change / previous_close) * 100
            
        return {
            "price": price,
            "change": change,
            "pct_change": pct_change,
            "name": info.get('shortName', symbol),
            "sector": info.get('sector', 'N/A'),
            "market_cap": info.get('marketCap', 0),
            "summary": info.get('longBusinessSummary', '無描述')
        }
    except Exception as e:
        return None

# --- 左側控制欄 ---
with st.sidebar:
    st.title("🛡️ System v14")
    st.caption("Anti-Fragile Investing Agent")
    st.markdown("---")
    
    protocol = st.selectbox(
        "啟動協議",
        ["協議 A: 情報解碼 (Intel)", "協議 C: 宏觀診斷 (Macro)", "協議 F: 個股偵察 (Scout)", "協議 G: 趨勢獵殺 (Hunt)"]
    )
    
    current_ticker_data = None # 用於儲存抓到的資料供後續使用
    
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
        ticker = st.text_input("輸入代號 (Ticker)", value="NVDA").upper()
        
        # --- 顯示即時股價 ---
        if ticker:
            with st.spinner(f"正在連線交易所取得 {ticker} 報價..."):
                current_ticker_data = get_stock_info(ticker)
            
            if current_ticker_data:
                p = current_ticker_data['price']
                c = current_ticker_data['change']
                pc = current_ticker_data['pct_change']
                
                st.metric(
                    label=current_ticker_data['name'],
                    value=f"${p:,.2f}" if p else "N/A",
                    delta=f"{c:+.2f} ({pc:+.2f}%)" if p else None
                )
                st.caption(f"領域: {current_ticker_data['sector']}")
                with st.expander("公司簡介"):
                    st.caption(current_ticker_data['summary'][:300] + "...")
            else:
                st.warning("⚠️ 無法取得股價資訊，請確認代號正確。")
        # -------------------
        
        user_input = f"分析個股 {ticker}。請評估其物理層瓶頸、護城河與當前估值。"
        
    elif protocol == "協議 A: 情報解碼 (Intel)":
        ticker = st.text_input("相關代號 (選填)", value="TSM").upper()
        
        # --- 顯示即時股價 (若有輸入) ---
        if ticker:
            current_ticker_data = get_stock_info(ticker)
            if current_ticker_data:
                 st.metric(
                    label=current_ticker_data['name'],
                    value=f"${current_ticker_data['price']:,.2f}",
                    delta=f"{current_ticker_data['pct_change']:+.2f}%"
                )
        # -------------------

        news_content = st.text_area("貼上新聞內容/連結", height=150)
        user_input = f"根據以下情報進行 PACER 解碼，判斷對 {ticker} 的影響：\n{news_content}"
        
    else: # 協議 G
        ticker = "TREND"
        trend_kw = st.text_input("輸入趨勢關鍵字", value="液冷散熱")
        user_input = f"針對趨勢 '{trend_kw}' 進行獵殺分析，尋找供應鏈中的壟斷者。"

    run_btn = st.button("🚀 執行推演", type="primary")
    st.markdown("---")

# --- 主畫面 ---
st.title("COMMANDER DASHBOARD")

if run_btn:
    # 建立進度條與狀態區
    status_container = st.container()
    
    with status_container:
        # 1. 記憶回溯
        with st.status("🔍 正在檢索歷史記憶...", expanded=True) as status_box:
            output_capture = StringIO()
            with contextlib.redirect_stdout(output_capture):
                search_kw = ticker
                run_smart_search(search_kw)
            
            memory_json = output_capture.getvalue()
            status_box.update(label="✅ 記憶檢索完成", state="complete", expanded=False)

        # 2. Gemini 深度思考
        with st.status("🧠 System 2 正在進行 MFR 物理審計...", expanded=True) as status_box:
            
            # 將基本面資料加入 Prompt 增強 AI 判斷
            fundamental_context = ""
            if current_ticker_data:
                fundamental_context = f"""
                【即時市場數據】
                - 現價: {current_ticker_data.get('price')}
                - 市值: {current_ticker_data.get('market_cap')}
                - 產業: {current_ticker_data.get('sector')}
                """
            
            full_prompt = f"{SYSTEM_PROMPT}\n\n{fundamental_context}\n\n【歷史記憶】{memory_json}\n【指揮官指令】{user_input}"
            
            try:
                response = model.generate_content(full_prompt)
                raw_text = response.text
                
                # 簡單的 JSON 提取邏輯
                json_start = raw_text.find('{')
                json_end = raw_text.rfind('}') + 1
                if json_start != -1 and json_end != -1:
                    json_str = raw_text[json_start:json_end]
                    ai_result = json.loads(json_str)
                else:
                    # Fallback if no JSON found
                    ai_result = {"full_analysis": raw_text, "decision": "Error", "rationale": "無法解析 JSON"}
                
                status_box.update(label="⚡ 推演完成", state="complete", expanded=False)
            except Exception as e:
                status_box.update(label="❌ AI 推演失敗", state="error")
                st.error(f"詳細錯誤: {e}")
                st.stop()

    # --- 結果呈現區 (Tabs) ---
    tab_summary, tab_report, tab_debug = st.tabs(["📊 戰情摘要", "📝 完整戰略報告", "🛠️ 系統日誌"])

    with tab_summary:
        st.subheader("核心決策看板")
        
        # 第一排：關鍵指標
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            metric_card("投資決策", ai_result.get("decision", "N/A"), "#4caf50" if "Buy" in ai_result.get("decision", "") else "#ffc107")
        with col2:
            metric_card("風險評分 (ARI)", ai_result.get("risk_score", "N/A"), "#f44336")
        with col3:
            metric_card("目標/點位", ai_result.get("target_price", "N/A"))
        with col4:
            metric_card("PACER 型態", ai_result.get("pacer_type", "N/A"))

        # 核心理由
        st.info(f"💡 **核心理由：** {ai_result.get('rationale', 'N/A')}")
        
        st.divider()

        # 協議 C 特別區塊：週期儀表板
        if protocol == "協議 C: 宏觀診斷 (Macro)":
            st.subheader("🌐 宏觀週期定位")
            coords = ai_result.get("cycle_coords", {})
            ari = ai_result.get("ari_signals", {})
            
            # 使用兩欄佈局
            c_left, c_right = st.columns([2, 1])
            
            with c_left:
                # 模擬週期雷達圖或列表
                st.markdown("#### 週期四象限數據")
                l1_col, l2_col = st.columns(2)
                l3_col, l4_col = st.columns(2)
                
                l1_col.metric("L1 庫存週期", coords.get('L1_Inventory', 'N/A'))
                l2_col.metric("L2 產能週期", coords.get('L2_CapEx', 'N/A'))
                l3_col.metric("L3 流動性", coords.get('L3_Liquidity', 'N/A'))
                l4_col.metric("L4 技術創新", coords.get('L4_Tech', 'N/A'))

            with c_right:
                st.markdown("#### ARI 風險燈號")
                status_color = ari.get("status", "Yellow")
                
                if "Green" in status_color:
                    st.success(f"🟢 安全: {status_color}")
                elif "Red" in status_color:
                    st.error(f"🔴 危險: {status_color}")
                else:
                    st.warning(f"🟡 警戒: {status_color}")
                
                st.markdown(f"**主要威脅:** {ari.get('main_threat', 'N/A')}")

    with tab_report:
        st.markdown(ai_result.get("full_analysis", "無詳細分析"))

    with tab_debug:
        st.subheader("原始資料查核")
        with st.expander("查看 Memory JSON"):
            st.text(memory_json)
        with st.expander("查看 AI Response JSON"):
            st.json(ai_result)

    # 4. 自動歸檔 (放在外面或隱藏執行)
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
        st.toast("✅ 數據已自動存入 Google Sheets 資料庫", icon="💾")
    except Exception as e:
        st.error(f"⚠️ 資料庫寫入錯誤: {e}")

else:
    # 歡迎畫面
    st.info("👈 請從左側側邊欄選擇行動協議，並按下「執行推演」此按鈕。")
    st.markdown("""
    ### 🛡️ System v14 戰情室使用指南
    
    1. **選擇協議**: 根據任務屬性選擇 Macro (宏觀), Scout (個股), Intel (新聞) 或 Hunt (趨勢)。
    2. **輸入參數**: 填寫必要的關鍵數據或文本。
    3. **執行推演**: AI 將結合 Memory 與 Gemini 3 模型進行分析。
    4. **審閱報告**: 在「戰情摘要」查看核心結論，在「完整報告」閱讀深度分析。
    """)