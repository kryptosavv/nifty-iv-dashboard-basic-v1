import streamlit as st
import pandas as pd
import os

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Nifty Volatility Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 NIFTY 50 Volatility & Term Structure")
st.markdown("---")

# ==========================================
# 2. DATA LOADING
# ==========================================
CSV_FILE = "nifty_data.csv"

def load_data():
    if not os.path.exists(CSV_FILE):
        return None
    
    try:
        df = pd.read_csv(CSV_FILE)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values(by='Date')
        return df
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        return None

df = load_data()

# ==========================================
# 3. DASHBOARD LOGIC
# ==========================================
if df is None or df.empty:
    st.warning("⚠️ No data found. Please wait for the daily automation to run (or run it manually in GitHub Actions).")
    st.stop()

# Get Latest Record
latest = df.iloc[-1]

# --- Signal Logic ---
# 1. Term Structure Signal
iv_curr = latest.get('Avg_IV_Current_Month', 0)
iv_next = latest.get('Avg_IV_Next_Month', 0)
iv_far  = latest.get('Avg_IV_Far_Month', 0)

if iv_curr < iv_next < iv_far:
    ts_signal = "🟢 STEEPENING (Normal)"
    ts_desc = "Expect Stable/Bullish Moves"
elif iv_curr > iv_next:
    ts_signal = "🔴 INVERTED (Fear)"
    ts_desc = "Expect High Volatility / Crash Risk"
else:
    ts_signal = "🟡 FLAT / MIXED"
    ts_desc = "Uncertain Regime"

# ==========================================
# 4. METRICS DISPLAY
# ==========================================
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("📅 Date", latest['Date'].strftime('%Y-%m-%d'))
    
with col2:
    st.metric("📉 Nifty Spot", f"{latest['Spot']:.2f}")

with col3:
    st.metric("💰 ATM Straddle", f"₹{latest['Straddle_Price']:.2f}")

with col4:
    # Color-coded IV Metric
    st.metric("⚡ Current IV", f"{iv_curr:.2f}%", 
              delta=f"{iv_curr - df.iloc[-2]['Avg_IV_Current_Month']:.2f}%" if len(df) > 1 else None,
              delta_color="inverse")

# --- Signal Banner ---
st.info(f"**Term Structure Signal:** {ts_signal} — *{ts_desc}*")

# ==========================================
# 5. CHARTS SECTION
# ==========================================
tab1, tab2, tab3 = st.tabs(["📈 Volatility Term Structure", "💵 Straddle Price", "📄 Raw Data"])

with tab1:
    st.subheader("IV Term Structure (Current vs Next vs Far)")
    
    # Check if we have the new columns before plotting
    required_cols = ['Avg_IV_Current_Month', 'Avg_IV_Next_Month', 'Avg_IV_Far_Month']
    if all(col in df.columns for col in required_cols):
        chart_data = df.set_index('Date')[required_cols]
        st.line_chart(chart_data)
        
        st.caption("""
        **Interpretation:**
        - **Green Line (Far) > Blue Line (Current):** Normal Market (Steepening).
        - **Blue Line (Current) > Green Line (Far):** Fear Market (Inverted).
        """)
    else:
        st.error("⚠️ Data columns for Term Structure missing. Waiting for next update.")

with tab2:
    st.subheader("ATM Straddle Price History")
    st.line_chart(df.set_index('Date')['Straddle_Price'])

with tab3:
    st.dataframe(df.sort_values(by='Date', ascending=False), use_container_width=True)

# ==========================================
# 6. FOOTER
# ==========================================
st.markdown("---")
st.caption(f"Last updated: {latest['Date']}")
