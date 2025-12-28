import streamlit as st
import pandas as pd

# Page Config
st.set_page_config(page_title="Nifty IV Dashboard", layout="wide")

# Title
st.title("📊 Nifty 50 Volatility Tracker")

# Load Data
try:
    df = pd.read_csv("nifty_data.csv")
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(by='Date')
except FileNotFoundError:
    st.warning("No data found yet. Wait for the daily update to run!")
    st.stop()

# Show Latest Metrics
latest = df.iloc[-1]
col1, col2, col3 = st.columns(3)
col1.metric("Date", latest['Date'].strftime('%Y-%m-%d'))
col2.metric("Nifty Spot", f"₹{latest['Spot']}")
col3.metric("ATM Straddle", f"₹{latest['Straddle_Price']}")

# Charts
st.subheader("Trends")
tab1, tab2 = st.tabs(["IV Chart", "Straddle Price"])

with tab1:
    st.line_chart(df.set_index('Date')['Avg_IV'])
with tab2:
    st.line_chart(df.set_index('Date')['Straddle_Price'])

# Data Table
with st.expander("Raw Data"):
    st.dataframe(df.sort_values(by='Date', ascending=False))