import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
from dotenv import load_dotenv
from fredapi import Fred
import google.generativeai as genai

load_dotenv()

st.set_page_config(page_title="Terminal Finance", page_icon="📈", layout="wide")

st.title("Financial Dashboard")
st.markdown("A simple dashboard displaying the latest prices for major indices and commodities.")

# Create tabs
tab1, tab2, tab3 = st.tabs(['Macro & AI Briefing', 'Forex & Cross-Asset', 'Smart Money (COT)'])

with tab1:
    briefing_placeholder = st.empty()

sp500_val, dxy_val, vix_val, fed_funds_val, asset_mgr_net_val, lev_money_net_val = "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"

# Define the tickers
tickers = {
    "S&P 500": "^GSPC",
    "DXY (Dollar Index)": "DX-Y.NYB",
    "Gold": "GC=F",
    "Crude Oil": "CL=F"
}

@st.cache_data(ttl=300) # Cache data for 5 minutes
def fetch_data(tickers_dict):
    data = []
    for name, symbol in tickers_dict.items():
        try:
            ticker = yf.Ticker(symbol)
            # Get the latest daily data
            hist = ticker.history(period="5d")
            if not hist.empty:
                last_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else last_price
                change = last_price - prev_price
                pct_change = (change / prev_price) * 100 if prev_price != 0 else 0
                
                data.append({
                    "Asset": name,
                    "Symbol": symbol,
                    "Last Price": round(last_price, 2),
                    "Change": round(change, 2),
                    "% Change": f"{pct_change:.2f}%"
                })
            else:
                data.append({
                    "Asset": name,
                    "Symbol": symbol,
                    "Last Price": "N/A",
                    "Change": "N/A",
                    "% Change": "N/A"
                })
        except Exception as e:
            data.append({
                "Asset": name,
                "Symbol": symbol,
                "Last Price": "Error",
                "Change": "Error",
                "% Change": "Error"
            })
    return pd.DataFrame(data)

with tab1:
    st.markdown("---")
    st.subheader("Latest Market Catalysts & News")
    try:
        with st.spinner("Fetching news..."):
            news_spy = yf.Ticker('SPY').news
            news_dxy = yf.Ticker('DX-Y.NYB').news
            
            all_news = []
            for item in (news_spy + news_dxy):
                content = item.get('content', {})
                if content:
                    title = content.get('title')
                    pubDate = content.get('pubDate', '')
                    provider = content.get('provider', {}).get('displayName', 'Unknown')
                    url = content.get('clickThroughUrl', {}).get('url', '')
                    if title and url:
                        all_news.append({
                            'title': title,
                            'publisher': provider,
                            'link': url,
                            'pubDate': pubDate
                        })
            
            all_news = sorted(all_news, key=lambda x: x['pubDate'], reverse=True)[:5]
            
            if all_news:
                for article in all_news:
                    st.markdown(f"- **[{article['title']}]({article['link']})** ({article['publisher']})")
            else:
                st.info("No recent news found.")
                
    except Exception as e:
        st.error(f"Error fetching news: {e}")

    with st.spinner("Fetching data..."):
        df = fetch_data(tickers)
        if not df.empty:
            sp500_row = df[df['Symbol'] == '^GSPC']
            if not sp500_row.empty: sp500_val = sp500_row['Last Price'].values[0]
            dxy_row = df[df['Symbol'] == 'DX-Y.NYB']
            if not dxy_row.empty: dxy_val = dxy_row['Last Price'].values[0]

    # Display the data in a neat table
    st.dataframe(
        df,
        column_config={
            "Asset": st.column_config.TextColumn("Asset", width="medium"),
            "Symbol": st.column_config.TextColumn("Symbol", width="small"),
            "Last Price": st.column_config.NumberColumn("Last Price", format="%.2f"),
            "Change": st.column_config.NumberColumn("Change", format="%.2f"),
            "% Change": st.column_config.TextColumn("% Change"),
        },
        hide_index=True,
        width="stretch"
    )

    st.markdown("---")
    st.subheader("Market Risk Gauge")

    risk_tickers = {
        "VIX Index": "^VIX",
        "Crude Oil Volatility (OVX)": "^OVX"
    }

    with st.spinner("Fetching risk data..."):
        risk_df = fetch_data(risk_tickers)
        if not risk_df.empty:
            vix_row = risk_df[risk_df['Symbol'] == '^VIX']
            if not vix_row.empty: vix_val = vix_row['Last Price'].values[0]

    if not risk_df.empty:
        cols = st.columns(len(risk_tickers))
        for i, row in risk_df.iterrows():
            with cols[i]:
                if row["Last Price"] not in ["N/A", "Error"]:
                    st.metric(
                        label=row["Asset"],
                        value=f"{row['Last Price']:.2f}",
                        delta=f"{row['Change']:.2f} ({row['% Change']})",
                        delta_color="inverse"
                    )
                else:
                    st.metric(label=row["Asset"], value="Data Unavailable")

# Setup FRED API shared instance
fred_api_key = os.getenv("FRED_API_KEY")
fred = None
if fred_api_key:
    fred = Fred(api_key=fred_api_key)

with tab1:
    st.markdown("---")
    st.subheader("Treasury Yield Curve (Recession Gauge)")
    try:
        if fred:
            with st.spinner("Fetching Yield Curve data..."):
                import datetime
                end_date = datetime.datetime.today()
                start_date = end_date - datetime.timedelta(days=5*365)
                yield_curve_data = fred.get_series('T10Y2Y', observation_start=start_date, observation_end=end_date)
                yield_curve_data = yield_curve_data.dropna()
                
                st.line_chart(yield_curve_data)
                st.caption("A value below 0 indicates an inverted yield curve and a high probability of an impending recession.")
        else:
            st.warning("FRED_API_KEY not found in .env file.")
    except Exception as e:
        st.error(f"Error fetching Yield Curve data: {e}")

    st.markdown("---")
    st.subheader("Macroeconomic Indicators (FRED)")

    try:
        if fred:
            fred_series = {
                "Federal Funds Rate": "FEDFUNDS",
                "Consumer Price Index": "CPIAUCSL",
                "Unemployment Rate": "UNRATE"
            }
            
            with st.spinner("Fetching macro data..."):
                cols_fred = st.columns(len(fred_series))
                for i, (name, series_id) in enumerate(fred_series.items()):
                    series = fred.get_series(series_id)
                    latest_value = series.dropna().iloc[-1]
                    if name == "Federal Funds Rate":
                        fed_funds_val = latest_value
                    
                    with cols_fred[i]:
                        if name == "Consumer Price Index":
                            st.metric(label=name, value=f"{latest_value:.2f}")
                        else:
                            st.metric(label=name, value=f"{latest_value:.2f}%")
        else:
            st.warning("FRED_API_KEY not found in .env file.")
    except Exception as e:
        st.error(f"Error fetching FRED data: {e}")

with tab2:
    st.subheader("FX Strength Meter (1-Week Relative to USD)")

    try:
        fx_tickers = ['EURUSD=X', 'GBPUSD=X', 'AUDUSD=X', 'JPY=X', 'CAD=X', 'CHF=X']
        inverse_tickers = ['JPY=X', 'CAD=X', 'CHF=X']
        
        with st.spinner("Fetching FX data..."):
            fx_data = {}
            for ticker in fx_tickers:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if not hist.empty and len(hist) >= 2:
                    first_close = hist['Close'].iloc[0]
                    last_close = hist['Close'].iloc[-1]
                    pct_change = ((last_close - first_close) / first_close) * 100
                    
                    # Invert logic for USD base currencies
                    if ticker in inverse_tickers:
                        pct_change = pct_change * -1
                    
                    # Clean up the ticker name for display
                    display_name = ticker.replace('=X', '').replace('USD', '')
                    fx_data[display_name] = pct_change
                    
            if fx_data:
                fx_df = pd.DataFrame(list(fx_data.items()), columns=["Currency", "1W % Change"])
                fx_df.set_index("Currency", inplace=True)
                
                st.bar_chart(fx_df)
                st.caption("Positive values indicate the currency strengthened against the USD over the last 5 days. Negative values indicate weakening.")
            else:
                st.warning("Could not fetch FX data.")
                
    except Exception as e:
        st.error(f"Error fetching FX data: {e}")

    st.markdown("---")
    st.subheader("Cross-Asset Correlation Matrix")

    try:
        with st.spinner("Fetching data for correlation matrix..."):
            corr_tickers = ['^GSPC', 'DX-Y.NYB', 'GC=F', 'CL=F', 'EURUSD=X', 'JPY=X']
            ticker_map = {
                '^GSPC': 'S&P 500',
                'DX-Y.NYB': 'DXY',
                'GC=F': 'Gold',
                'CL=F': 'Crude Oil',
                'EURUSD=X': 'EUR/USD',
                'JPY=X': 'USD/JPY'
            }
            
            corr_data = yf.download(corr_tickers, period="3mo")
            
            if not corr_data.empty:
                if isinstance(corr_data.columns, pd.MultiIndex):
                    if 'Close' in corr_data.columns.levels[0]:
                        close_data = corr_data['Close'].copy()
                    else:
                        close_data = corr_data.copy()
                else:
                    close_data = corr_data.copy()
                    
                close_data = close_data.rename(columns=ticker_map)
                
                # Keep only the columns we actually care about
                valid_cols = [col for col in close_data.columns if col in ticker_map.values()]
                close_data = close_data[valid_cols]
                
                # Calculate daily percentage returns and Pearson correlation
                daily_returns = close_data.pct_change().dropna()
                corr_matrix = daily_returns.corr(method='pearson')
                
                # Apply background gradient styling
                styled_corr = corr_matrix.style.background_gradient(cmap='coolwarm', axis=None).format("{:.2f}")
                
                st.dataframe(styled_corr)
                st.caption("3-Month Daily Returns Pearson Correlation. Values closer to 1 indicate strong positive correlation, while values closer to -1 indicate strong negative correlation.")
            else:
                st.warning("Could not fetch data for correlation matrix.")
                
    except Exception as e:
        st.error(f"Error calculating correlation matrix: {e}")

    st.markdown("---")
    st.subheader("Automated Support & Resistance (20-Day Rolling)")

    try:
        with st.spinner("Calculating Support & Resistance..."):
            sr_tickers = ['EURUSD=X', 'GBPUSD=X', 'GC=F', 'CL=F']
            sr_map = {
                'EURUSD=X': 'EUR/USD',
                'GBPUSD=X': 'GBP/USD',
                'GC=F': 'Gold',
                'CL=F': 'Crude Oil'
            }
            
            sr_data = yf.download(sr_tickers, period="3mo")
            
            if not sr_data.empty:
                sr_results = []
                for ticker in sr_tickers:
                    if isinstance(sr_data.columns, pd.MultiIndex):
                        try:
                            high_series = sr_data['High'][ticker].dropna()
                            low_series = sr_data['Low'][ticker].dropna()
                            close_series = sr_data['Close'][ticker].dropna()
                        except KeyError:
                            continue
                    else:
                        continue
                    
                    if not close_series.empty and len(close_series) >= 20:
                        current_price = close_series.iloc[-1]
                        
                        rolling_res = high_series.rolling(window=20).max()
                        nearest_res = rolling_res.dropna().iloc[-1]
                        
                        rolling_sup = low_series.rolling(window=20).min()
                        nearest_sup = rolling_sup.dropna().iloc[-1]
                        
                        sr_results.append({
                            "Asset": sr_map.get(ticker, ticker),
                            "Current Price": current_price,
                            "Nearest Support": nearest_sup,
                            "Nearest Resistance": nearest_res
                        })
                
                if sr_results:
                    sr_df = pd.DataFrame(sr_results)
                    st.dataframe(
                        sr_df,
                        column_config={
                            "Asset": st.column_config.TextColumn("Asset"),
                            "Current Price": st.column_config.NumberColumn("Current Price", format="%.4f"),
                            "Nearest Support": st.column_config.NumberColumn("Nearest Support", format="%.4f"),
                            "Nearest Resistance": st.column_config.NumberColumn("Nearest Resistance", format="%.4f"),
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.warning("Could not calculate Support & Resistance (insufficient data).")
            else:
                st.warning("Could not fetch data for Support & Resistance.")
                
    except Exception as e:
        st.error(f"Error calculating Support & Resistance: {e}")

with tab3:
    st.subheader("Smart Money Positioning (COT Report)")

    try:
        cot_url = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
        cot_params = {
            "market_and_exchange_names": "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 1
        }
        
        with st.spinner("Fetching COT data..."):
            cot_response = requests.get(cot_url, params=cot_params)
            cot_response.raise_for_status()
            cot_data = cot_response.json()
            
            if cot_data:
                latest_cot = cot_data[0]
                report_date = latest_cot.get("report_date_as_yyyy_mm_dd", "Unknown Date")
                if "T" in report_date:
                    report_date = report_date.split("T")[0]
                
                asset_mgr_long = float(latest_cot.get('asset_mgr_positions_long', 0))
                asset_mgr_short = float(latest_cot.get('asset_mgr_positions_short', 0))
                lev_money_long = float(latest_cot.get('lev_money_positions_long', 0))
                lev_money_short = float(latest_cot.get('lev_money_positions_short', 0))
                
                asset_mgr_net = asset_mgr_long - asset_mgr_short
                lev_money_net = lev_money_long - lev_money_short
                asset_mgr_net_val = asset_mgr_net
                lev_money_net_val = lev_money_net
                
                st.caption(f"E-MINI S&P 500 Net Positions (Report Date: {report_date})")
                
                cot_cols = st.columns(2)
                with cot_cols[0]:
                    st.metric("Asset Manager/Institutional (Net)", f"{asset_mgr_net:,.0f}")
                with cot_cols[1]:
                    st.metric("Leveraged Funds (Net)", f"{lev_money_net:,.0f}")
                    
                chart_df = pd.DataFrame({
                    "Net Positions": [asset_mgr_net, lev_money_net]
                }, index=["Asset Manager", "Leveraged Funds"])
                
                st.bar_chart(chart_df)
            else:
                st.warning("No COT data found for E-MINI S&P 500.")

    except Exception as e:
        st.error(f"Error fetching COT data: {e}")

st.markdown("---")
st.caption("Data provided by Yahoo Finance, FRED, and CFTC. Prices may be delayed.")

try:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)
        prompt_data = f"S&P 500: {sp500_val}\nDXY: {dxy_val}\nVIX: {vix_val}\nFed Funds Rate: {fed_funds_val}\nCOT Asset Managers Net: {asset_mgr_net_val}\nCOT Leveraged Funds Net: {lev_money_net_val}"
        system_instruction = "Act as a ruthless macro hedge fund analyst. Based on this data, write a 3-sentence actionable market briefing outlining the current risk regime (risk-on/risk-off) and the primary threat or opportunity for retail traders. Be direct and cynical. No fluff."
        model = genai.GenerativeModel('gemini-2.5-flash', system_instruction=system_instruction)
        response = model.generate_content(prompt_data)
        briefing_placeholder.info(f"**AI Macro Briefing:**\n\n{response.text}")
    else:
        briefing_placeholder.warning("GEMINI_API_KEY not found. AI Briefing disabled.")
except Exception as e:
    briefing_placeholder.error(f"Error generating AI briefing: {e}")
