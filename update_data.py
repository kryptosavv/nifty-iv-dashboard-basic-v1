import pandas as pd
import yfinance as yf
from datetime import date, datetime
import os

CSV_FILE = "nifty_data.csv"
TICKER = "^NSEI"

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
    print("🚀 Script Starting...")
    
    # 1. LOAD or INIT DataFrame
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        try:
            df = pd.read_csv(CSV_FILE)
            print(f"✅ Loaded existing CSV with {len(df)} rows.")
        except:
            print("⚠️ CSV file corrupted or empty. Starting fresh.")
            df = pd.DataFrame()
    else:
        print("⚠️ File is empty or missing. Creating new DataFrame.")
        df = pd.DataFrame()

    # 2. FETCH DATA
    print("🔍 Fetching Market Data...")
    nifty = yf.Ticker(TICKER)
    # Get 5 days history to be safe
    hist = nifty.history(period="5d")
    
    if hist.empty:
        print("❌ CRITICAL: Yahoo returned NO data. Script stopping.")
        return

    latest = hist.iloc[-1]
    latest_date = str(hist.index[-1].date())
    spot = latest['Close']
    print(f"📊 Market Date: {latest_date} | Spot: {spot}")

    # 3. AVOID DUPLICATES
    if not df.empty and 'Date' in df.columns and latest_date in df['Date'].values:
        print("✅ Data for this date already exists. Exiting.")
        return

    # 4. GET OPTIONS DATA
    try:
        monthly_expiries = get_monthly_expiries(nifty)
        if len(monthly_expiries) >= 3:
            curr, next_exp, far_exp = monthly_expiries[:3]
            iv_curr = get_atm_iv(nifty, curr, spot)
            iv_next = get_atm_iv(nifty, next_exp, spot)
            iv_far  = get_atm_iv(nifty, far_exp, spot)
            
            # Straddle Price
            chain = nifty.option_chain(curr)
            strikes = chain.calls['strike']
            atm_strike = strikes.iloc[(strikes - spot).abs().argsort()[:1]].iloc[0]
            c = chain.calls[chain.calls['strike'] == atm_strike].iloc[0]['lastPrice']
            p = chain.puts[chain.puts['strike'] == atm_strike].iloc[0]['lastPrice']
            straddle = c + p
        else:
            print("⚠️ Not enough expiries. Using 0.")
            iv_curr, iv_next, iv_far, straddle, atm_strike = 0, 0, 0, 0, 0
    except Exception as e:
        print(f"⚠️ Options Error: {e}. Using 0.")
        iv_curr, iv_next, iv_far, straddle, atm_strike = 0, 0, 0, 0, 0

    # 5. SAVE
    new_row = {
        "Date": latest_date,
        "Spot": round(spot, 2),
        "ATM_Strike": atm_strike,
        "Avg_IV_Current_Month": round(iv_curr, 2),
        "Avg_IV_Next_Month": round(iv_next, 2),
        "Avg_IV_Far_Month": round(iv_far, 2),
        "Straddle_Price": round(straddle, 2)
    }
    
    # Append properly
    df_new = pd.DataFrame([new_row])
    if df.empty:
        df_new.to_csv(CSV_FILE, index=False)
    else:
        # Check if columns match, if not, reset
        if not set(new_row.keys()).issubset(df.columns):
            print("⚠️ Schema changed. Overwriting file.")
            df_new.to_csv(CSV_FILE, index=False)
        else:
            df_new.to_csv(CSV_FILE, mode='a', header=False, index=False)
            
    print(f"💾 SAVED SUCCESS: {latest_date} written to {CSV_FILE}")

if __name__ == "__main__":
    update_csv()
