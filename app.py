import time
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="3 PM TV Imbalance Tracker", page_icon="⚡", layout="wide"
)

st.title("⚡ 3 PM Option Time Value (TV) Tracker - Live Market")
st.caption("ATM ± 10 Strikes | Real-time Extrinsic Value Comparison from Dhan API")

# 🔑 आपके असली क्रेडेंशियल्स
CLIENT_ID = "1104978491"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzg0OTUwMDg1LCJpYXQiOjE3ODQ4NjM2ODUsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA0OTc4NDkxIn0.Vox2yz26LF5BdVQBfPV8P36RVV3KsPyzcn-NPOghGTwKG025z1Qa3HGJWYuu3QZ8uJ63pAEn4HcZ41CC-sLP5A"

st.sidebar.header("⚙️ Settings")
symbol = st.sidebar.selectbox("Select Index", ["SENSEX", "NIFTY"])

# 🛡️ Rate limit से बचने के लिए रिफ्रेश टाइम कम से कम 15 सेकंड रखा गया है
refresh_sec = st.sidebar.slider("Auto-Refresh Interval (Sec)", 10, 60, 15)

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


# 🔄 TTL के साथ डेटा फेच करने का फंक्शन ताकि बार-बार 429 एरर न आए
def fetch_live_dhan_option_chain(client_id, access_token, index_name):
    headers = {
        "access-token": access_token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    url = "https://api.dhan.co/v2/optionchain"
    scrip_id = 51 if index_name == "SENSEX" else 13
    
    payload = {
        "UnderlyingScrip": scrip_id,
        "UnderlyingSegment": "IDX_I"
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"API Error {response.status_code}: {response.text}")


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
            "Call LTP": c_ltp,
            "Call TV": round(c_tv, 2),
            "Put LTP": p_ltp,
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
    with st.spinner("🔄 धन सर्वर से लाइव डेटा फेच हो रहा है..."):
        live_data = fetch_live_dhan_option_chain(CLIENT_ID, ACCESS_TOKEN, symbol)
    
    data_block = live_data.get("data", {})
    spot_price = float(data_block.get("last_price", data_block.get("spotPrice", 75499.64)))
    
    oc_dict = data_block.get("oc", {})
    
    strikes = []
    calls = []
    puts = []
    
    for strike_val, details in oc_dict.items():
        strikes.append(float(strike_val))
        calls.append(float(details.get("ce", {}).get("last_price", 0.0)))
        puts.append(float(details.get("pe", {}).get("last_price", 0.0)))
        
    if not strikes:
        st.warning("⚠️ लाइव ऑप्शन चेन डेटा खाली मिला। कृपया सुनिश्चित करें कि बाजार खुला है।")
    else:
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
