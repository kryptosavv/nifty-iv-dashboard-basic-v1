import pandas as pd
import yfinance as yf
from datetime import date
import os

# CONFIG
CSV_FILE = "nifty_data.csv"
TICKER = "^NSEI"

def fetch_data():
    print("Fetching data...")
    try:
        nifty = yf.Ticker(TICKER)
        
        # 1. Get Spot Price
        hist = nifty.history(period="1d")
        if hist.empty:
            print("No data found.")
            return None
        spot = hist['Close'].iloc[-1]
        
        # 2. Get Option Chain (Mocking ATM logic for Yahoo)
        # Yahoo doesn't give easy historical options, so we approximate
        # ATM IV using the VIX or calculating from available chain (simplified here)
        expiries = nifty.options
        if not expiries: return None
        
        # Fetch Nearest Expiry Chain
        chain = nifty.option_chain(expiries[0])
        
        # Find ATM Strike
        strikes = chain.calls['strike']
        atm_strike = strikes.iloc[(strikes - spot).abs().argsort()[:1]].iloc[0]
        
        # Get ATM IV & Price
        call_row = chain.calls[chain.calls['strike'] == atm_strike].iloc[0]
        put_row = chain.puts[chain.puts['strike'] == atm_strike].iloc[0]
        
        avg_iv = (call_row['impliedVolatility'] + put_row['impliedVolatility']) / 2 * 100
        straddle_price = call_row['lastPrice'] + put_row['lastPrice']
        
        # 3. Create Record
        new_row = {
            "Date": str(date.today()),
            "Spot": round(spot, 2),
            "ATM_Strike": atm_strike,
            "Avg_IV": round(avg_iv, 2),
            "Straddle_Price": round(straddle_price, 2)
        }
        return new_row

    except Exception as e:
        print(f"Error: {e}")
        return None

def update_csv():
    data = fetch_data()
    if not data: return
    
    # Load existing or create new
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
    else:
        df = pd.DataFrame(columns=data.keys())
    
    # Check if today's data already exists
    if str(date.today()) in df['Date'].values:
        print("Today's data already exists.")
    else:
        # Append new data
        df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
        df.to_csv(CSV_FILE, index=False)
        print("✅ Data updated successfully!")

if __name__ == "__main__":
    update_csv()