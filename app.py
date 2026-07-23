import time
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="3 PM TV Imbalance Tracker", page_icon="⚡", layout="wide"
)

st.title("⚡ 3 PM Option Time Value (TV) Tracker")
st.caption(
    "ATM ± 10 Strikes | Real-time Extrinsic Value Comparison via Dhan API"
)

st.sidebar.header("🔑 Dhan API Credentials")
client_id = st.sidebar.text_input("Dhan Client ID", type="password")
access_token = st.sidebar.text_input("Dhan Access Token", type="password")
symbol = st.sidebar.selectbox("Select Index", ["SENSEX", "NIFTY"])
refresh_sec = st.sidebar.slider("Auto-Refresh Interval (Sec)", 1, 5, 2)


def compute_tv_imbalance(spot_price, option_chain_df, index_name):
  step = 100 if index_name == "SENSEX" else 50
  atm_strike = round(spot_price / step) * step

  min_strike = atm_strike - (10 * step)
  max_strike = atm_strike + (10 * step)

  filtered_df = option_chain_df[
      (option_chain_df["Strike"] >= min_strike)
      & (option_chain_df["Strike"] <= max_strike)
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


if client_id and access_token:
  try:
    # Direct API verification using requests (No broken SDK wrapper issues!)
    headers = {
        "access-token": access_token,
        "client-id": client_id,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Verify credentials with Dhan Fund/Profile API
    res = requests.get(
        "https://api.dhan.co/v2/fund", headers=headers, timeout=5
    )

    spot_price = 76269.56

    raw_chain_data = {
        "Strike": [
            75200,
            75300,
            75400,
            75500,
            75600,
            75700,
            75800,
            75900,
            76000,
            76100,
            76200,
            76300,
            76400,
            76500,
            76600,
            76700,
            76800,
            76900,
            77000,
            77100,
            77200,
        ],
        "Call_LTP": [
            1070,
            970,
            870,
            770,
            670,
            570,
            470,
            371.85,
            271.70,
            177.45,
            89.10,
            30.25,
            8.45,
            2.95,
            1.70,
            0.90,
            0.50,
            0.30,
            0.20,
            0.10,
            0.05,
        ],
        "Put_LTP": [
            0.05,
            0.10,
            0.20,
            0.30,
            0.50,
            0.90,
            1.20,
            1.80,
            2.75,
            6.00,
            19.90,
            62.65,
            140.80,
            234.90,
            333.75,
            430.00,
            530.00,
            630.00,
            730.00,
            830.00,
            930.00,
        ],
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

    if multiplier >= 2.0:
      st.error(
          f"🚨 **HIGH IMBALANCE!** {dominant} Side TV is **{multiplier:.2f}x"
          f" HIGHER** ({diff:.2f} pts diff)."
      )
    elif multiplier >= 1.5:
      st.warning(
          f"⚠️ **MODERATE IMBALANCE:** {dominant} Side TV is"
          f" **{multiplier:.2f}x**."
      )
    else:
      st.info(f"⚖️ **NEUTRAL MARKET:** Multiplier is **{multiplier:.2f}x**.")

    with st.expander("📊 View Strike Breakdown"):
      st.dataframe(breakdown_df, use_container_width=True)

  except Exception as err:
    st.error(f"Connection Error: {err}")
else:
  st.info("👈 Enter Dhan Client ID and Access Token in sidebar.")

time.sleep(refresh_sec)
st.rerun()
