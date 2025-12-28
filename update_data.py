import pandas as pd
import yfinance as yf
from datetime import date, datetime
import os

# CONFIG
CSV_FILE = "nifty_data.csv"
TICKER = "^NSEI"

def is_trading_day():
    # 1. Check Weekend (5=Sat, 6=Sun)
    if date.today().weekday() > 4:
        print(f"Skipping: Today is {date.today().strftime('%A')} (Weekend).")
        return False
    return True

def get_monthly_expiries(ticker_obj):
    """
    Filters the list of expiries to find only the 'Monthly' ones.
    Logic: The last expiry date available for any given month is considered the Monthly expiry.
    """
    expiries = ticker_obj.options
    if not expiries: return []
    
    # Convert strings to date objects
    expiry_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in expiries]
    
    # Group by (Year, Month) and find the max date in each group
    monthly_map = {}
    for d in expiry_dates:
        key = (d.year, d.month)
        if key not in monthly_map:
            monthly_map[key] = d
        else:
            if d > monthly_map[key]:
                monthly_map[key] = d
                
    # Sort them to get Near, Next, Far order
    sorted_monthly = sorted(monthly_map.values())
    
    # Convert back to string format for yfinance
    return [d.strftime("%Y-%m-%d") for d in sorted_monthly]

def get_atm_iv(ticker_obj, expiry, spot):
    try:
        chain = ticker_obj.option_chain(expiry)
        
        # Find ATM Strike
        strikes = chain.calls['strike']
        atm_strike = strikes.iloc[(strikes - spot).abs().argsort()[:1]].iloc[0]
        
        # Extract IVs
        call_row = chain.calls[chain.calls['strike'] == atm_strike]
        put_row = chain.puts[chain.puts['strike'] == atm_strike]
        
        if call_row.empty or put_row.empty:
            return 0
            
        avg_iv = (call_row.iloc[0]['impliedVolatility'] + put_row.iloc[0]['impliedVolatility']) / 2 * 100
        return avg_iv
    except Exception as e:
        print(f"Error fetching IV for {expiry}: {e}")
        return 0

def fetch_data():
    if not is_trading_day():
        return None

    print("Fetching data...")
    try:
        nifty = yf.Ticker(TICKER)
        hist = nifty.history(period="1d")
        
        if hist.empty:
            print("❌ Market data empty.")
            return None
            
        # Check if data is stale (Holiday check)
        data_date = hist.index[-1].date()
        today = date.today()
        
        if data_date != today:
            print(f"⚠️ Market Closed? Data date ({data_date}) does not match today ({today}). Skipping.")
            return None

        spot = hist['Close'].iloc[-1]
        
        # --- IV Logic ---
        monthly_expiries = get_monthly_expiries(nifty)
        
        # We need at least 3 monthly expiries
        if len(monthly_expiries) < 3:
            print("Not enough monthly expiries found.")
            return None
            
        curr_expiry = monthly_expiries[0]
        next_expiry = monthly_expiries[1]
        far_expiry  = monthly_expiries[2]
        
        print(f"Expiries Selected: Current={curr_expiry}, Next={next_expiry}, Far={far_expiry}")

        # Get IVs
        iv_curr = get_atm_iv(nifty, curr_expiry, spot)
        iv_next = get_atm_iv(nifty, next_expiry, spot)
        iv_far  = get_atm_iv(nifty, far_expiry, spot)
        
        # Get Straddle Price (Using Current Month)
        # Note: Straddle price usually tracks the NEAREST expiry (even if weekly). 
        # If you want strictly Monthly straddle, use curr_expiry chain.
        chain = nifty.option_chain(curr_expiry)
        strikes = chain.calls['strike']
        atm_strike = strikes.iloc[(strikes - spot).abs().argsort()[:1]].iloc[0]
        c_price = chain.calls[chain.calls['strike'] == atm_strike].iloc[0]['lastPrice']
        p_price = chain.puts[chain.puts['strike'] == atm_strike].iloc[0]['lastPrice']

        new_row = {
            "Date": str(today),
            "Spot": round(spot, 2),
            "ATM_Strike": atm_strike,
            "Avg_IV_Current_Month": round(iv_curr, 2),
            "Avg_IV_Next_Month": round(iv_next, 2),
            "Avg_IV_Far_Month": round(iv_far, 2),
            "Straddle_Price": round(c_price + p_price, 2)
        }
        return new_row

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        return None

def update_csv():
    data = fetch_data()
    if not data:
        return
    
    # 1. Handle Schema Changes (New columns)
    # If file exists but has old columns, we might need to recreate it or append carefully.
    # For simplicity: If columns don't match, we recreate the file (Archiving old data is better but complex for this script)
    
    write_header = False
    if os.path.exists(CSV_FILE):
        df_existing = pd.read_csv(CSV_FILE)
        # Check if columns match
        if list(df_existing.columns) != list(data.keys()):
            print("⚠️ Schema mismatch detected (New Columns). Recreating CSV to fit new format.")
            # Option: You could try to backfill old rows with NaN, but starting fresh is safer for the dashboard
            df = pd.DataFrame(columns=data.keys())
            write_header = True
        else:
            df = df_existing
    else:
        df = pd.DataFrame(columns=data.keys())

    # 2. Check for Duplicate Date
    if str(date.today()) in df['Date'].values:
        print("Data for today already exists. Updating row.")
        df = df[df['Date'] != str(date.today())]
        
    # 3. Save
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    df.to_csv(CSV_FILE, index=False)
    print(f"✅ Data saved successfully to {CSV_FILE}")

if __name__ == "__main__":
    update_csv()
