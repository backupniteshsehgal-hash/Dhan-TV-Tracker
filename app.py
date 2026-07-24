import time
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="3 PM TV Imbalance Tracker", page_icon="⚡", layout="wide"
)

st.title("⚡ 3 PM Option Time Value (TV) Tracker")
st.caption("ATM ± 10 Strikes | Real-time Extrinsic Value Comparison with WhatsApp Alerts")

# 🛑 यहाँ अपनी सही Client ID और नया Access Token सीधे स्थायी रूप से दर्ज करें (कभी नहीं उड़ेगा)
CLIENT_ID = "1104978491"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzg0OTUwMDg1LCJpYXQiOjE3ODQ4NjM2ODUsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA0OTc4NDkxIn0.Vox2yz26LF5BdVQBfPV8P36RVV3KsPyzcn-NPOghGTwKG025z1Qa3HGJWYuu3QZ8uJ63pAEn4HcZ41CC-sLP5A"

st.sidebar.header("⚙️ Settings")
symbol = st.sidebar.selectbox("Select Index", ["SENSEX", "NIFTY"])
refresh_sec = st.sidebar.slider("Auto-Refresh Interval (Sec)", 1, 5, 2)

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


# जाँच करें कि क्रेडेंशियल्स कोड में डाले गए हैं या नहीं
if CLIENT_ID == "अपनी_क्लाइंट_आईडी_यहाँ_डालें" or ACCESS_TOKEN == "धन_पोर्टल_से_निकाला_गया_नया_टोकन_यहाँ_डालें":
    st.error("⚠️ कृपया कोड के अंदर अपनी सही Client ID और Access Token दर्ज करें।")
else:
    try:
        headers = {
            "access-token": ACCESS_TOKEN,
            "client-id": CLIENT_ID,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        # धन API से कनेक्ट करने की कोशिश
        # (यहाँ इंडেক्स के आधार पर लाइव स्पॉट और ऑप्शन चेन का एपीआई कॉल जोड़ा जा सकता है)
        
        # टेस्टिंग के लिए वर्तमान में फिक्स्ड स्पॉट (लाइव मार्केट में इसे धन एपीआई से जोड़ा जाएगा)
        spot_price = 76269.56

        # लाइव ऑप्शन चेन डेटा स्ट्रक्चर
        raw_chain_data = {
            "Strike": [75200, 75300, 75400, 75500, 75600, 75700, 75800, 75900, 76000, 76100, 76200, 76300, 76400, 76500, 76600, 76700, 76800, 76900, 77000, 77100, 77200],
            "Call_LTP": [1070, 970, 870, 770, 670, 570, 470, 371.85, 271.70, 177.45, 89.10, 30.25, 8.45, 2.95, 1.70, 0.90, 0.50, 0.30, 0.20, 0.10, 0.05],
            "Put_LTP": [0.05, 0.10, 0.20, 0.30, 0.50, 0.90, 1.20, 1.80, 2.75, 6.00, 19.90, 62.65, 140.80, 234.90, 333.75, 430.00, 530.00, 630.00, 730.00, 830.00, 930.00],
        }
        df_chain = pd.DataFrame(raw_chain_data)

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
        col1.metric("Spot Price", f"{spot_price:.2f}", f"ATM: {atm}")
        col2.metric("Total Call TV", f"{call_tv_sum:.2f} pts")
        col3.metric("Total Put TV", f"{put_tv_sum:.2f} pts")

        status_tag = "🔴 PUT" if dominant == "PUT" else "🟢 CALL"
        col4.metric(
            "Dominant Side",
            f"{status_tag} Bloat",
            f"{multiplier:.2f}x Times Higher",
        )

        st.divider()

        # अलर्ट कंडीशन चेक
        if multiplier >= 2.0:
            st.error(
                f"🚨 **HIGH IMBALANCE!** {dominant} Side TV is **{multiplier:.2f}x HIGHER** ({diff:.2f} pts diff)."
            )

            if enable_wa:
                msg = (
                    f"🚨 ALERT: {symbol} 3PM Imbalance! {dominant} Side TV is "
                    f"{multiplier:.2f}x higher. Diff: {diff:.2f} pts."
                )
                send_whatsapp_alert(wa_phone, wa_apikey, msg)

        elif multiplier >= 1.5:
            st.warning(
                f"⚠️ **MODERATE IMBALANCE:** {dominant} Side TV is **{multiplier:.2f}x**."
            )
        else:
            st.info(f"⚖️ **NEUTRAL MARKET:** Multiplier is **{multiplier:.2f}x**.")

        with st.expander("📊 View Strike Breakdown"):
            st.dataframe(breakdown_df, use_container_width=True)

    except Exception as err:
        st.error(f"Connection Error: {err}")

time.sleep(refresh_sec)
st.rerun()
