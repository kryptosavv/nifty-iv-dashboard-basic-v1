import pandas as pd
import yfinance as yf
import requests
from datetime import date, datetime
import os

CSV_FILE = "nifty_data.csv"
TICKER = "^NSEI"

def get_ticker_with_headers():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return yf.Ticker(TICKER, session=session)

def get_monthly_expiries(ticker_obj):
    try:
        expiries = ticker_obj.options
        if not expiries: return []
        expiry_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in expiries]
        monthly_map = {}
        for d in expiry_dates:
            key = (d.year, d.month)
            if key not in monthly_map or d > monthly_map[key]:
                monthly_map[key] = d
        return [d.strftime("%Y-%m-%d") for d in sorted(monthly_map.values())]
    except:
        return []

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

    # --- FIX FOR EMPTY DATA ERROR ---
    # We check if file exists AND has content (> 0 bytes)
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        try:
            df = pd.read_csv(CSV_FILE)
            print(f"✅ Loaded existing CSV with {len(df)} rows.")
        except Exception as e:
            print(f"⚠️ CSV readable error: {e}. Starting fresh.")
            df = pd.DataFrame()
    else:
        print("⚠️ File is empty (created by touch). Starting fresh.")
        df = pd.DataFrame()

    # --- FETCH DATA ---
    print("🔍 Fetching Market Data...")
    nifty = get_ticker_with_headers()
    
    try:
        hist = nifty.history(period="5d")
        if hist.empty: raise Exception("Yahoo returned no history")
        latest = hist.iloc[-1]
        latest_date = str(hist.index[-1].date())
        spot = latest['Close']
        print(f"📊 Date: {latest_date} | Spot: {spot:.2f}")
    except Exception as e:
        print(f"❌ Critical Error: {e}")
        return

    # Check for duplicate date
    if not df.empty and 'Date' in df.columns and latest_date in df['Date'].values:
        print("✅ Data for this date already exists. Removing old row to retry options.")
        df = df[df['Date'] != latest_date]

    # --- OPTIONS DATA (With Fail-Safe for Zeros) ---
    try:
        monthly_expiries = get_monthly_expiries(nifty)
        if len(monthly_expiries) >= 3:
            curr, next_exp, far_exp = monthly_expiries[:3]
            iv_curr = get_atm_iv(nifty, curr, spot)
            iv_next = get_atm_iv(nifty, next_exp, spot)
            iv_far  = get_atm_iv(nifty, far_exp, spot)
            
            # Straddle
            chain = nifty.option_chain(curr)
            strikes = chain.calls['strike']
            atm_strike = strikes.iloc[(strikes - spot).abs().argsort()[:1]].iloc[0]
            c = chain.calls[chain.calls['strike'] == atm_strike].iloc[0]['lastPrice']
            p = chain.puts[chain.puts['strike'] == atm_strike].iloc[0]['lastPrice']
            straddle = c + p
        else:
            print("⚠️ Yahoo returned empty expiries (BLOCKED). Saving 0s.")
            iv_curr, iv_next, iv_far, straddle, atm_strike = 0, 0, 0, 0, 0
    except Exception as e:
        print(f"⚠️ Options Error: {e}")
        iv_curr, iv_next, iv_far, straddle, atm_strike = 0, 0, 0, 0, 0

    # --- SAVE ---
    new_row = {
        "Date": latest_date,
        "Spot": round(spot, 2),
        "ATM_Strike": atm_strike,
        "Avg_IV_Current_Month": round(iv_curr, 2),
        "Avg_IV_Next_Month": round(iv_next, 2),
        "Avg_IV_Far_Month": round(iv_far, 2),
        "Straddle_Price": round(straddle, 2)
    }
    
    df_new = pd.DataFrame([new_row])
    
    if df.empty:
        df_new.to_csv(CSV_FILE, index=False)
    else:
        # Concatenate and save
        df = pd.concat([df, df_new], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)
            
    print(f"💾 SAVED: {latest_date} | Spot: {spot} | Straddle: {straddle}")

if __name__ == "__main__":
    update_csv()
