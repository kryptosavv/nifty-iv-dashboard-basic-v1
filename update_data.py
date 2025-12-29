import pandas as pd
import yfinance as yf
import requests
from datetime import date, datetime
import os

CSV_FILE = "nifty_data.csv"
TICKER = "^NSEI"

def get_ticker_with_headers():
    """Creates a Yahoo Ticker with browser headers to bypass blocking"""
    session = requests.Session()
    # Faking a standard Chrome browser
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return yf.Ticker(TICKER, session=session)

def get_monthly_expiries(ticker_obj):
    try:
        expiries = ticker_obj.options
        if not expiries:
            print("⚠️ Yahoo returned NO expiries (Empty List).")
            return []
            
        expiry_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in expiries]
        monthly_map = {}
        for d in expiry_dates:
            key = (d.year, d.month)
            if key not in monthly_map or d > monthly_map[key]:
                monthly_map[key] = d
        return [d.strftime("%Y-%m-%d") for d in sorted(monthly_map.values())]
    except Exception as e:
        print(f"⚠️ Error parsing expiries: {e}")
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
    print("🚀 Script Starting (Browser Mode)...")
    
    # 1. LOAD DataFrame
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        df = pd.read_csv(CSV_FILE)
    else:
        df = pd.DataFrame()

    # 2. FETCH DATA (With Headers)
    nifty = get_ticker_with_headers()
    
    # Fetch Spot
    try:
        hist = nifty.history(period="5d")
        if hist.empty: raise Exception("No history found")
        latest = hist.iloc[-1]
        latest_date = str(hist.index[-1].date())
        spot = latest['Close']
        print(f"📊 Market Date: {latest_date} | Spot: {spot:.2f}")
    except Exception as e:
        print(f"❌ CRITICAL: Spot price fetch failed. {e}")
        return

    # 3. CHECK FOR DUPLICATE
    if not df.empty and 'Date' in df.columns and latest_date in df['Date'].values:
        print("✅ Data for this date already exists. Removing old row to re-try options fetch.")
        df = df[df['Date'] != latest_date] # Remove it so we can try overwriting the 0s

    # 4. GET OPTIONS DATA
    try:
        monthly_expiries = get_monthly_expiries(nifty)
        if len(monthly_expiries) >= 3:
            print(f"✅ Found Expiries: {monthly_expiries[:3]}")
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
            print("❌ Not enough expiries found (Yahoo Blocked?).")
            iv_curr, iv_next, iv_far, straddle, atm_strike = 0, 0, 0, 0, 0
    except Exception as e:
        print(f"⚠️ Options Error: {e}")
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
    
    df_new = pd.DataFrame([new_row])
    
    # Save Logic
    if df.empty:
        df_new.to_csv(CSV_FILE, index=False)
    else:
        # Append
        df = pd.concat([df, df_new], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)
            
    print(f"💾 SAVED: {latest_date} | IV: {iv_curr}% | Straddle: {straddle}")

if __name__ == "__main__":
    update_csv()
