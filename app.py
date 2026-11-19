
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ==========================================
# KONFIGURASI
# ==========================================

st.set_page_config(
    page_title="AI SNR XAUUSD",
    page_icon="📈",
    layout="wide"
)

st.title("📈 AI SNR XAUUSD")
st.caption("Dashboard analisis emas multi-timeframe")

st.warning(
    "Data berasal dari Yahoo Finance, bukan feed resmi HFM. "
    "Gunakan untuk pengujian, bukan jaminan profit."
)

# ==========================================
# PENGAMBILAN DATA
# ==========================================

@st.cache_data(ttl=300)
def get_data(interval, period):

    try:
        df = yf.download(
            "XAUUSD=X",
            interval=interval,
            period=period,
            progress=False,
            auto_adjust=False,
            threads=False,
            timeout=30
        )

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close"]

        if not all(col in df.columns for col in required):
            return pd.DataFrame()

        df = df[required].copy()
        df = df.apply(pd.to_numeric, errors="coerce")
        df = df.dropna()

        return df

    except Exception:
        return pd.DataFrame()


# ==========================================
# MEMBENTUK TIMEFRAME
# ==========================================

@st.cache_data(ttl=300)
def load_all():

    data = {}

    data["MN"] = get_data("1mo", "10y")
    data["W1"] = get_data("1wk", "10y")
    data["D1"] = get_data("1d", "5y")
    data["H1"] = get_data("1h", "730d")
    data["M5"] = get_data("5m", "60d")
    data["M1"] = get_data("1m", "7d")

    h1 = data["H1"]

    if not h1.empty:
        h4 = h1.resample("4h").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last"
        }).dropna()
    else:
        h4 = pd.DataFrame()

    data["H4"] = h4

    return data


# ==========================================
# ANALISIS TREND DAN SNR
# ==========================================

def analyze(df):

    if df is None or len(df) < 50:
        return None

    close = df["Close"]

    ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]

    price = float(close.iloc[-1])

    if price > ema20 and ema20 > ema50:
        trend = "BULLISH"
    elif price < ema20 and ema20 < ema50:
        trend = "BEARISH"
    else:
        trend = "NETRAL"

    recent = df.tail(30)

    support = float(recent["Low"].min())
    resistance = float(recent["High"].max())

    return {
        "trend": trend,
        "price": price,
        "ema20": float(ema20),
        "ema50": float(ema50),
        "support": support,
        "resistance": resistance
    }


# ==========================================
# REFRESH DATA
# ==========================================

if st.button("🔄 Perbarui analisis"):
    st.cache_data.clear()
    st.rerun()


# ==========================================
# DASHBOARD
# ==========================================

try:

    with st.spinner("Mengambil data harga emas..."):

        data = load_all()

    results = {
        tf: analyze(df)
        for tf, df in data.items()
    }

    available = {
        tf: result
        for tf, result in results.items()
        if result is not None
    }

    missing = [
        tf for tf in data
        if results[tf] is None
    ]

    if not available:

        st.error(
            "Belum ada data XAUUSD dari Yahoo Finance. "
            "Periksa koneksi atau sumber data."
        )

        st.stop()

    # ======================================
    # HARGA TERKINI
    # ======================================

    current_price = available["M1"]["price"] if "M1" in available else (
        available["H1"]["price"] if "H1" in available else
        list(available.values())[0]["price"]
    )

    st.subheader("Harga XAUUSD")

    st.metric(
        "Harga terakhir",
        f"{current_price:.2f}"
    )

    # ======================================
    # TABEL MULTI TIMEFRAME
    # ======================================

    st.subheader("Analisis Multi-Timeframe")

    rows = []

    for tf in ["MN", "W1", "D1", "H4", "H1", "M5", "M1"]:

        if tf in available:

            r = available[tf]

            rows.append({
                "Timeframe": tf,
                "Trend": r["trend"],
                "Harga": round(r["price"], 2),
                "Support": round(r["support"], 2),
                "Resistance": round(r["resistance"], 2)
            })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True
    )

    # ======================================
    # BIAS MULTI TIMEFRAME
    # ======================================

    main_tfs = ["MN", "W1", "D1", "H4", "H1"]

    bullish = sum(
        1 for tf in main_tfs
        if tf in available and available[tf]["trend"] == "BULLISH"
    )

    bearish = sum(
        1 for tf in main_tfs
        if tf in available and available[tf]["trend"] == "BEARISH"
    )

    total_main = sum(
        1 for tf in main_tfs
        if tf in available
    )

    st.subheader("Keputusan Analisis")

    bias = "WAIT"

    if total_main >= 4 and bullish >= 4:
        bias = "BUY"
    elif total_main >= 4 and bearish >= 4:
        bias = "SELL"

    # ======================================
    # LEVEL ENTRY
    # ======================================

    if bias == "BUY" and "H1" in available:

        support = available["H1"]["support"]
        resistance = available["H1"]["resistance"]

        entry_low = support
        entry_high = support + (resistance - support) * 0.15

        sl = support - (resistance - support) * 0.10

        risk = entry_high - sl

        tp1 = entry_high + risk
        tp2 = entry_high + risk * 2
        tp3 = entry_high + risk * 3

        invalidation = sl

        reason = (
            "Minimal 4 timeframe utama menunjukkan bullish. "
            "Area support H1 digunakan sebagai referensi entry."
        )

    elif bias == "SELL" and "H1" in available:

        support = available["H1"]["support"]
        resistance = available["H1"]["resistance"]

        entry_low = resistance - (resistance - support) * 0.15
        entry_high = resistance

        sl = resistance + (resistance - support) * 0.10

        risk = sl - entry_low

        tp1 = entry_low - risk
        tp2 = entry_low - risk * 2
        tp3 = entry_low - risk * 3

        invalidation = sl

        reason = (
            "Minimal 4 timeframe utama menunjukkan bearish. "
            "Area resistance H1 digunakan sebagai referensi entry."
        )

    else:

        entry_low = None
        entry_high = None
        sl = None
        tp1 = None
        tp2 = None
        tp3 = None
        invalidation = None

        reason = (
            "Arah timeframe utama belum cukup sejalan. "
            "Tunggu konfirmasi berikutnya."
        )

    # ======================================
    # SKOR KESESUAIAN
    # ======================================

    if total_main > 0:
        score = round(
            max(bullish, bearish) / total_main * 100
        )
    else:
        score = 0

    st.metric(
        "Skor kesesuaian arah timeframe",
        f"{score}%"
    )

    st.caption(
        "Skor menunjukkan keselarasan arah timeframe, "
        "bukan probabilitas kemenangan transaksi."
    )

    # ======================================
    # HASIL SINYAL
    # ======================================

    if bias == "BUY":

        st.success("BIAS: BUY")

    elif bias == "SELL":

        st.error("BIAS: SELL")

    else:

        st.warning("BIAS: WAIT")

    if bias != "WAIT":

        col1, col2 = st.columns(2)

        with col1:

            st.write("**Area Entry**")
            st.write(
                f"{entry_low:.2f} - {entry_high:.2f}"
            )

            st.write("**Stop Loss**")
            st.write(f"{sl:.2f}")

            st.write("**Invalidasi**")
            st.write(f"{invalidation:.2f}")

        with col2:

            st.write("**Target Profit**")
            st.write(f"TP1: {tp1:.2f}")
            st.write(f"TP2: {tp2:.2f}")
            st.write(f"TP3: {tp3:.2f}")

    else:

        st.info(
            "Belum ada entry. Jangan memaksakan BUY atau SELL."
        )

    st.write("**Alasan:**")
    st.write(reason)

    # ======================================
    # KONFIRMASI M5 DAN M1
    # ======================================

    st.subheader("Konfirmasi Entry")

    for tf in ["M5", "M1"]:

        if tf in available:

            st.write(
                f"{tf}: {available[tf]['trend']}"
            )

        else:

            st.write(
                f"{tf}: Data belum tersedia"
            )

    st.caption(
        "Entry tetap memerlukan reaksi harga dan "
        "konfirmasi candlestick pada zona SNR. "
        "Dashboard ini belum memvalidasi pola candlestick."
    )

    # ======================================
    # DATA YANG TIDAK TERSEDIA
    # ======================================

    if missing:

        st.warning(
            "Timeframe belum tersedia: "
            + ", ".join(missing)
        )

except Exception as e:

    st.error(f"Terjadi kesalahan: {str(e)}")
