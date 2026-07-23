import datetime
import time
import pandas as pd
import streamlit as st
from dhanhq import dhanhq

st.set_page_config(
    page_title="Live Multi-Index TV Imbalance Tracker",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Real-Time Option Time Value (TV) Tracker - SENSEX & NIFTY")
st.caption(
    "ATM ± 10 Strikes | Live Dhan API Data | Real-time Extrinsic Value"
    " Comparison & Auto-Logging"
)

if "spike_logs" not in st.session_state:
  st.session_state.spike_logs = []

st.sidebar.header("🔑 Dhan API Credentials")
access_token = st.sidebar.text_input("Dhan Access Token", type="password")
symbol = st.sidebar.selectbox("Select Index", ["NIFTY", "SENSEX"])
refresh_sec = st.sidebar.slider("Auto-Refresh Interval (Sec)", 1, 5, 2)

INDEX_CONFIG = {
    "NIFTY": {"security_id": 13, "segment": "IDX_I", "step": 50},
    "SENSEX": {"security_id": 51, "segment": "IDX_I", "step": 100},
}


def fetch_live_option_chain_data(access_token, index_name):
  try:
    dhan = dhanhq(access_token)
    config = INDEX_CONFIG[index_name]

    exp_response = dhan.expiry_list(
        under_security_id=config["security_id"],
        under_exchange_segment=config["segment"],
    )
    if not exp_response or "data" not in exp_response or not exp_response["data"]:
      return None, None, "एक्सपायरी डेट प्राप्त नहीं हो पाई।"

    current_expiry = exp_response["data"][0]

    chain_response = dhan.get_option_chain(
        underlying_security_id=config["security_id"],
        underlying_type="INDEX",
        expiry_date=current_expiry,
    )

    if (
        not chain_response
        or "data" not in chain_response
        or not chain_response["data"]
    ):
      return None, None, "ऑप्शन चेन डेटा खाली है।"

    data_payload = chain_response["data"]
    spot_price = float(data_payload.get("last_price", 0))
    oc_data = data_payload.get("oc", {})

    if not spot_price or not oc_data:
      return None, None, "स्पॉट प्राइस या ऑप्शन चेन नोड्स नहीं मिले।"

    return spot_price, oc_data, None

  except Exception as e:
    return None, None, str(e)


def compute_tv_imbalance_live(spot_price, oc_data, index_name):
  step = INDEX_CONFIG[index_name]["step"]
  atm_strike = round(spot_price / step) * step

  min_strike = atm_strike - (10 * step)
  max_strike = atm_strike + (10 * step)

  call_tv_sum = 0.0
  put_tv_sum = 0.0
  rows = []

  strikes = sorted([float(s) for s in oc_data.keys()])

  for strike in strikes:
    if min_strike <= strike <= max_strike:
      node = oc_data.get(str(int(strike))) or oc_data.get(str(strike))
      if not node:
        continue

      ce_data = node.get("ce", {})
      pe_data = node.get("pe", {})

      c_ltp = float(ce_data.get("last_price", 0.0))
      p_ltp = float(pe_data.get("last_price", 0.0))

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


if access_token:
  spot_price, oc_data, err_msg = fetch_live_option_chain_data(
      access_token, symbol
  )

  if err_msg:
    st.warning(
        f"⚠️ लाइव डेटा प्राप्त नहीं हुआ ({err_msg})। यदि मार्केट बंद है या"
        " क्रेडेंशियल्स अमान्य हैं, तो कृपया लाइव मार्केट के दौरान पुनः"
        " प्रयास करें।"
    )
  elif spot_price and oc_data:
    (
        atm,
        call_tv_sum,
        put_tv_sum,
        diff,
        dominant,
        multiplier,
        breakdown_df,
    ) = compute_tv_imbalance_live(spot_price, oc_data, symbol)

    st.subheader(f"📊 Active Index: {symbol} (Live)")
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
      st.error(
          f"🚨 **LIVE HIGH IMBALANCE ({symbol})!** {dominant} Side TV is"
          f" **{multiplier:.2f}x HIGHER** ({diff:.2f} pts diff)."
      )

      current_time_str = datetime.datetime.now().strftime("%H:%M:%S")
      should_log = True
      if st.session_state.spike_logs:
        last_entry = st.session_state.spike_logs[-1]
        if (
            last_entry["Time"][:5] == current_time_str[:5]
            and last_entry["Index"] == symbol
            and last_entry["Side"] == dominant
        ):
          should_log = False

      if should_log:
        st.session_state.spike_logs.append({
            "Time": current_time_str,
            "Index": symbol,
            "Side": dominant,
            "Multiplier": round(multiplier, 2),
            "Diff (Pts)": round(diff, 2),
        })

    elif multiplier >= 1.5:
      st.warning(
          f"⚠️ **MODERATE IMBALANCE ({symbol}):** {dominant} Side TV is"
          f" **{multiplier:.2f}x**."
      )
    else:
      st.info(
          f"⚖️ **NEUTRAL MARKET ({symbol}):** Multiplier is **{multiplier:.2f}x**."
      )

    with st.expander(f"📊 View Live {symbol} Strike Breakdown"):
      if not breakdown_df.empty:
        st.dataframe(breakdown_df, use_container_width=True)
      else:
        st.info("इस समय स्ट्राइक डेटा उपलब्ध नहीं है।")

    st.divider()
    st.subheader("📝 Real-Time Imbalance Spike History (All Indices)")
    if st.session_state.spike_logs:
      log_df = pd.DataFrame(st.session_state.spike_logs)
      st.dataframe(log_df, use_container_width=True)
      if st.button("Clear History Log"):
        st.session_state.spike_logs = []
        st.rerun()
    else:
      st.info(
          "लाइव मार्केट में 2x+ इम्बैलेंस स्पाइक्स का इंतज़ार है... ऐप लगातार"
          " मॉनिटर कर रही है।"
      )
else:
  st.info("👈 कृपया साइडबार में अपना असली Dhan Access Token दर्ज करें।")

time.sleep(refresh_sec)
st.rerun()
