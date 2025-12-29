import pandas as pd
import yfinance as yf
from datetime import date, datetime, timedelta
import os

# CONFIG
CSV_FILE = "nifty_data.csv"
TICKER = "^NSEI"

def get_monthly_expiries(ticker_obj):
    """Returns the monthly expiries (last Thurs of month)"""
    expiries = ticker_obj.options
    if not expiries: return []
    
    # Convert to dates and group by YYYY-MM
    expiry_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in expiries]
    monthly_map = {}
    for d in expiry_dates:
        key = (d.year, d.month)
        # Keep the latest date for that month (e.g., last Thurs)
        if key not in monthly_map or d > monthly_map[key]:
            monthly_map[key] = d
            
    return [d.strftime("%Y-%m-%d") for d in sorted(monthly_map.values())]

def get_atm_iv(ticker_obj, expiry, spot):
    try:
        chain = ticker_obj.option_chain(expiry)
        strikes = chain.calls['strike']
        # Find ATM strike
        atm_strike = strikes.iloc[(strikes - spot).abs().argsort()[:1]].iloc[0]
        
        call_iv = chain.calls[chain.calls['strike'] == atm_strike].iloc[0]['impliedVolatility']
        put_iv = chain.puts[chain.puts['strike'] == atm_strike].iloc[0]['impliedVolatility']
        
        return (call_iv + put_iv) / 2 * 100
    except:
        return 0

def update_csv():
    print("🚀 Starting Data Fetch...")
    
    # 1. Fetch Data (Get last 5 days to ensure we always find SOMETHING)
    nifty = yf.Ticker(TICKER)
    hist = nifty.history(period="5d")
    
    if hist.empty:
        print("❌ Error: Yahoo Finance returned no data.")
        return

    # Get the absolutely latest data point available
    latest_row = hist.iloc[-1]
    latest_date = hist.index[-1].date()
    spot = latest_row['Close']
    
    print(f"📊 Latest Market Data: {latest_date} | Spot: {spot:.2f}")

    # 2. Check if we actually need to update
    file_exists = os.path.exists(CSV_FILE)
    if file_exists:
        df = pd.read_csv(CSV_FILE)
        last_saved_date = df.iloc[-1]['Date']
        if str(latest_date) == str(last_saved_date):
            print(f"✅ Data for {latest_date} already exists. No update needed.")
            return
    else:
        print("⚠️ File not found. Creating new database from scratch...")

    # 3. Fetch Options Data (Expensive Step)
    print("🔍 Fetching Option Chain...")
    monthly_expiries = get_monthly_expiries(nifty)
    
    if len(monthly_expiries) < 3:
        print("❌ Not enough expiries found. Skipping.")
        return

    # Term Structure IVs
    iv_curr = get_atm_iv(nifty, monthly_expiries[0], spot)
    iv_next = get_atm_iv(nifty, monthly_expiries[1], spot)
    iv_far  = get_atm_iv(nifty, monthly_expiries[2], spot)
    
    # Straddle Price (Current Month)
    try:
        chain = nifty.option_chain(monthly_expiries[0])
        strikes = chain.calls['strike']
        atm_strike = strikes.iloc[(strikes - spot).abs().argsort()[:1]].iloc[0]
        c_ltp = chain.calls[chain.calls['strike'] == atm_strike].iloc[0]['lastPrice']
        p_ltp = chain.puts[chain.puts['strike'] == atm_strike].iloc[0]['lastPrice']
        straddle_price = c_ltp + p_ltp
    except:
        straddle_price = 0

    # 4. Save to CSV
    new_data = {
        "Date": str(latest_date),
        "Spot": round(spot, 2),
        "ATM_Strike": atm_strike,
        "Avg_IV_Current_Month": round(iv_curr, 2),
        "Avg_IV_Next_Month": round(iv_next, 2),
        "Avg_IV_Far_Month": round(iv_far, 2),
        "Straddle_Price": round(straddle_price, 2)
    }

    df_new = pd.DataFrame([new_data])
    
    if file_exists:
        # Append to existing
        df_new.to_csv(CSV_FILE, mode='a', header=False, index=False)
    else:
        # Create new file
        df_new.to_csv(CSV_FILE, index=False)
        
    print(f"💾 Success! Saved data for {latest_date} to {CSV_FILE}")

if __name__ == "__main__":
    update_csv()
