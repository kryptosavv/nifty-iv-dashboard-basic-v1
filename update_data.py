import pandas as pd
import yfinance as yf
from datetime import date, datetime, timedelta
import os

# CONFIG
CSV_FILE = "nifty_data.csv"
TICKER = "^NSEI"
COLUMNS = ["Date", "Spot", "ATM_Strike", "Avg_IV_Current_Month", "Avg_IV_Next_Month", "Avg_IV_Far_Month", "Straddle_Price"]

def init_csv():
    """Creates the CSV file with headers if it doesn't exist."""
    if not os.path.exists(CSV_FILE):
        print(f"⚠️ File {CSV_FILE} not found. Creating it with headers...")
        df = pd.DataFrame(columns=COLUMNS)
        df.to_csv(CSV_FILE, index=False)

def get_monthly_expiries(ticker_obj):
    expiries = ticker_obj.options
    if not expiries: return []
    expiry_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in expiries]
    monthly_map = {}
    for d in expiry_dates:
        key = (d.year, d.month)
        if key not in monthly_map or d > monthly_map[key]:
            monthly_map[key] = d
    return [d.strftime("%Y-%m-%d") for d in sorted(monthly_map.values())]

def get_atm_iv(ticker_obj, expiry, spot):
    try:
        chain = ticker_obj.option_chain(expiry)
        strikes = chain.calls['strike']
        atm_strike = strikes.iloc[(strikes - spot).abs().argsort()[:1]].iloc[0]
        call_iv = chain.calls[chain.calls['strike'] == atm_strike].iloc[0]['impliedVolatility']
        put_iv = chain.puts[chain.puts['strike'] == atm_strike].iloc[0]['impliedVolatility']
        return (call_iv + put_iv) / 2 * 100
    except:
        return 0

def update_csv():
    # 1. FORCE CREATE THE FILE (Fixes the "pathspec" error)
    init_csv()

    print("🚀 Starting Data Fetch...")
    nifty = yf.Ticker(TICKER)
    hist = nifty.history(period="5d") # Fetch 5 days to ensure we get something
    
    if hist.empty:
        print("❌ Error: Yahoo Finance returned no data. File initialized but empty.")
        return

    latest_row = hist.iloc[-1]
    latest_date = hist.index[-1].date()
    spot = latest_row['Close']
    
    print(f"📊 Latest Market Data: {latest_date} | Spot: {spot:.2f}")

    # 2. Check duplicate
    df = pd.read_csv(CSV_FILE)
    if not df.empty and str(latest_date) in df['Date'].values:
        print(f"✅ Data for {latest_date} already exists. No update needed.")
        return

    # 3. Fetch IVs
    try:
        monthly_expiries = get_monthly_expiries(nifty)
        if len(monthly_expiries) < 3:
            print("❌ Not enough expiries found.")
            return

        iv_curr = get_atm_iv(nifty, monthly_expiries[0], spot)
        iv_next = get_atm_iv(nifty, monthly_expiries[1], spot)
        iv_far  = get_atm_iv(nifty, monthly_expiries[2], spot)
        
        # Straddle
        chain = nifty.option_chain(monthly_expiries[0])
        strikes = chain.calls['strike']
        atm_strike = strikes.iloc[(strikes - spot).abs().argsort()[:1]].iloc[0]
        c_ltp = chain.calls[chain.calls['strike'] == atm_strike].iloc[0]['lastPrice']
        p_ltp = chain.puts[chain.puts['strike'] == atm_strike].iloc[0]['lastPrice']
        
        new_row = {
            "Date": str(latest_date),
            "Spot": round(spot, 2),
            "ATM_Strike": atm_strike,
            "Avg_IV_Current_Month": round(iv_curr, 2),
            "Avg_IV_Next_Month": round(iv_next, 2),
            "Avg_IV_Far_Month": round(iv_far, 2),
            "Straddle_Price": round(c_ltp + p_ltp, 2)
        }
        
        # Save
        df_new = pd.DataFrame([new_row])
        df_new.to_csv(CSV_FILE, mode='a', header=df.empty, index=False)
        print(f"💾 Success! Saved data for {latest_date}")
        
    except Exception as e:
        print(f"⚠️ Error calculating options data: {e}")

if __name__ == "__main__":
    update_csv()
