import yfinance as yf
import sys

print(f"Python version: {sys.version}")
print(f"yfinance version: {yf.__version__}")

try:
    ticker = "NVDA"
    print(f"Fetching info for {ticker}...")
    stock = yf.Ticker(ticker)
    info = stock.info
    
    print("Success!")
    print(f"Price: {info.get('currentPrice')}")
except Exception as e:
    print(f"Error caught: {e}")
    import traceback
    traceback.print_exc()
