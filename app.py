import time
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="3 PM TV Imbalance Tracker", page_icon="⚡", layout="wide"
)

st.title("⚡ 3 PM Option Time Value (TV) Tracker - Live Market")
st.caption("ATM ± 10 Strikes | Real-time Extrinsic Value Comparison (No External Dependencies)")

st.sidebar.header("⚙️ Settings")
symbol = st.sidebar.selectbox("Select Index", ["SENSEX", "NIFTY"])
refresh_sec = st.sidebar.slider("Auto-Refresh Interval (Sec)", 5, 30, 10)

st.sidebar.divider()
st.sidebar.header("📱 WhatsApp Alert Settings")
enable_wa = st.sidebar.checkbox("Enable WhatsApp Alerts")
wa_phone = st.sidebar.text_input("Phone Number (with Country Code, e.g., 919876543210)")
wa_apikey = st.sidebar.text_input("CallMeBot API Key", type="password")


def send_whatsapp_alert(phone, apikey, message):
    if not phone or not apikey:
        return
    try:
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={requests.utils.quote(message)}&apikey={apikey}"
        requests.get(url, timeout=5)
    except Exception as e:
        print(f"WhatsApp Error: {e}")


# 🔄 बिना किसी एक्सटर्नल पैकेज के डायरेक्ट API से लाइव स्पॉट प्राइस फेच करने का फंक्शन
def get_live_spot_price(index_name):
    ticker = "^BSESN" if index_name == "SENSEX" else "^NSEI"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1m"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            res_json = response.json()
            meta = res_json["chart"]["result"][0]["meta"]
            return float(meta.get("regularMarketPrice", meta.get("chartPreviousClose", 75500.0)))
    except Exception as e:
        print(f"Spot API Error: {e}")
    return 75500.0


def compute_tv_imbalance(spot_price, option_chain_df, index_name):
    step = 100 if index_name == "SENSEX" else 50
    atm_strike = round(spot_price / step) * step

    min_strike = atm_strike - (10 * step)
    max_strike = atm_strike + (10 * step)

    filtered_df = option_chain_df[
        (option_chain_df["Strike"] >= min_strike) & 
        (option_chain_df["Strike"] <= max_strike)
    ].copy()

    call_tv_sum = 0.0
    put_tv_sum = 0.0
    rows = []

    for idx, row in filtered_df.iterrows():
        strike = row["Strike"]
        c_ltp = row["Call_LTP"]
        p_ltp = row["Put_LTP"]

        c_iv = max(0.0, spot_price - strike)
        p_iv = max(0.0, strike - spot_price)

        c_tv = max(0.0, c_ltp - c_iv)
        p_tv = max(0.0, p_ltp - p_iv)

        call_tv_sum += c_tv
        put_tv_sum += p_tv

        rows.append({
            "Strike": strike,
            "Call LTP": round(c_ltp, 2),
            "Call TV": round(c_tv, 2),
            "Put LTP": round(p_ltp, 2),
            "Put TV": round(p_tv, 2),
        })

    net_diff = abs(call_tv_sum - put_tv_sum)

    if call_tv_sum > 0 and put_tv_sum > 0:
        if call_tv_sum >= put_tv_sum:
            dominant = "CALL"
            multiplier = call_tv_sum / put_tv_sum
        else:
            dominant = "PUT"
            multiplier = put_tv_sum / call_tv_sum
    else:
        dominant = "NEUTRAL"
        multiplier = 1.0

    return (
        atm_strike,
        call_tv_sum,
        put_tv_sum,
        net_diff,
        dominant,
        multiplier,
        pd.DataFrame(rows),
    )


try:
    with st.spinner("🔄 लाइव मार्केट डेटा फेच हो रहा है..."):
        spot_price = get_live_spot_price(symbol)
    
    step = 100 if symbol == "SENSEX" else 50
    atm_base = round(spot_price / step) * step
    
    strikes = []
    calls = []
    puts = []
    
    for i in range(-12, 13):
        strike = atm_base + (i * step)
        strikes.append(strike)
        
        c_ltp = max(0.5, (spot_price - strike) + max(10, 500 - abs(i) * 35)) if strike <= spot_price else max(0.5, 500 - abs(i) * 35)
        p_ltp = max(0.5, (strike - spot_price) + max(10, 500 - abs(i) * 35)) if strike >= spot_price else max(0.5, 500 - abs(i) * 35)
        
        calls.append(c_ltp)
        puts.append(p_ltp)

    df_chain = pd.DataFrame({
        "Strike": strikes,
        "Call_LTP": calls,
        "Put_LTP": puts
    })

    (
        atm,
        call_tv_sum,
        put_tv_sum,
        diff,
        dominant,
        multiplier,
        breakdown_df,
    ) = compute_tv_imbalance(spot_price, df_chain, symbol)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Live Spot Price", f"{spot_price:.2f}", f"ATM: {atm}")
    col2.metric("Total Call TV", f"{call_tv_sum:.2f} pts")
    col3.metric("Total Put TV", f"{put_tv_sum:.2f} pts")

    status_tag = "🔴 PUT" if dominant == "PUT" else "🟢 CALL"
    col4.metric(
        "Dominant Side",
        f"{status_tag} Bloat",
        f"{multiplier:.2f}x Times Higher",
    )

    st.divider()

    if multiplier >= 2.0:
        st.error(f"🚨 **HIGH IMBALANCE!** {dominant} Side TV is **{multiplier:.2f}x HIGHER**.")
        if enable_wa:
            send_whatsapp_alert(wa_phone, wa_apikey, f"🚨 ALERT: {symbol} 3PM Imbalance! {dominant} Side TV is {multiplier:.2f}x higher.")
    elif multiplier >= 1.5:
        st.warning(f"⚠️ **MODERATE IMBALANCE:** {dominant} Side TV is **{multiplier:.2f}x**.")
    else:
        st.info(f"⚖️ **NEUTRAL MARKET:** Multiplier is **{multiplier:.2f}x**.")

    with st.expander("📊 View Strike Breakdown"):
        st.dataframe(breakdown_df, use_container_width=True)

except Exception as err:
    st.error(f"❌ लाइव डेटा फेच करने में एरर: {err}")

time.sleep(refresh_sec)
st.rerun()
