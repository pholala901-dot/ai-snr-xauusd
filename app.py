
import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(
    page_title="AI SNR XAUUSD",
    page_icon="📈",
    layout="wide"
)

st.title("📈 AI SNR XAUUSD")
st.caption("Dashboard analisis emas multi-timeframe")

st.warning(
    "Data publik bukan feed resmi HFM. "
    "Gunakan untuk pengujian, bukan jaminan profit."
)


@st.cache_data(ttl=60)
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

        kolom = ["Open", "High", "Low", "Close"]

        if not all(k in df.columns for k in kolom):
            return pd.DataFrame()

        return df[kolom].dropna()

    except Exception as e:
        st.error(f"Error {interval}: {str(e)}")
        return pd.DataFrame()


        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        kolom = ["Open", "High", "Low", "Close"]
        if not all(k in df.columns for k in kolom):
            return pd.DataFrame()

        return df[kolom].dropna()

    except Exception as e:
        st.error(f"Gagal mengambil data {interval}: {e}")
        return pd.DataFrame()


def analyze(df):
    if len(df) < 30:
        return None

    close = df["Close"]
    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]
    price = float(close.iloc[-1])

    if price > ema20 > ema50:
        trend = "Bullish"
    elif price < ema20 < ema50:
        trend = "Bearish"
    else:
        trend = "Netral"

    recent = df.tail(30)
    support = float(recent["Low"].min())
    resistance = float(recent["High"].max())

    return {
        "trend": trend,
        "price": price,
        "support": support,
        "resistance": resistance
    }


@st.cache_data(ttl=300)
def load_all():
    h1 = get_data("1h", "730d")

    h4 = pd.DataFrame()

    if not h1.empty and isinstance(h1.index, pd.DatetimeIndex):
        h4 = h1.resample("4h").agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last"
        }).dropna()

    return {
        "MN": get_data("1mo", "10y"),
        "W1": get_data("1wk", "10y"),
        "D1": get_data("1d", "5y"),
        "H4": h4,
        "H1": h1,
        "M5": get_data("5m", "60d"),
        "M1": get_data("1m", "7d")
    }


if st.button("🔄 Perbarui analisis"):
    st.cache_data.clear()
    st.rerun()

try:
    with st.spinner("Membaca data XAUUSD..."):
        data = load_all()

    results = {
        tf: analyze(df) for tf, df in data.items()
    }

    missing = [
        tf for tf, result in results.items()
        if result is None
    ]

    if missing:
        st.error(
            "Data belum tersedia untuk: "
            + ", ".join(missing)
            + ". Coba perbarui nanti."
        )
        st.stop()

    higher = ["MN", "W1", "D1", "H4", "H1"]

    bullish = sum(
        results[tf]["trend"] == "Bullish"
        for tf in higher
    )

    bearish = sum(
        results[tf]["trend"] == "Bearish"
        for tf in higher
    )

    m5 = data["M5"]
    m1 = results["M1"]
    last = m5.iloc[-1]
    prev = m5.iloc[-2]

    price = results["M5"]["price"]
    support = results["M5"]["support"]
    resistance = results["M5"]["resistance"]

    distance = max(price * 0.001, 0.5)

    near_support = abs(price - support) <= distance
    near_resistance = abs(price - resistance) <= distance

    buy_confirm = (
        last["Close"] > last["Open"]
        and last["Close"] > prev["High"]
        and m1["trend"] == "Bullish"
    )

    sell_confirm = (
        last["Close"] < last["Open"]
        and last["Close"] < prev["Low"]
        and m1["trend"] == "Bearish"
    )

    bias = "WAIT"
    score = max(bullish, bearish) * 20
    entry = sl = tp1 = tp2 = None

    reason = "Belum ada konfirmasi SNR yang valid."
    invalidation = "Tunggu reaksi harga di zona SNR."

    if bullish >= 4 and near_support and buy_confirm:
        bias = "BUY"
        entry = price
        sl = support - distance
        risk = entry - sl
        tp1 = entry + risk
        tp2 = entry + (2 * risk)
        score = min(100, 60 + bullish * 5)
        reason = "Mayoritas timeframe besar bullish dan ada konfirmasi M5/M1 di support."
        invalidation = f"Setup batal jika harga turun di bawah {sl:.2f}."

    elif bearish >= 4 and near_resistance and sell_confirm:
        bias = "SELL"
        entry = price
        sl = resistance + distance
        risk = sl - entry
        tp1 = entry - risk
        tp2 = entry - (2 * risk)
        score = min(100, 60 + bearish * 5)
        reason = "Mayoritas timeframe besar bearish dan ada konfirmasi M5/M1 di resistance."
        invalidation = f"Setup batal jika harga naik di atas {sl:.2f}."

    st.subheader("Hasil sinyal")

    c1, c2, c3 = st.columns(3)
    c1.metric("Harga referensi", f"{price:.2f}")
    c2.metric("Bias", bias)
    c3.metric("Skor aturan", f"{score}/100")

    st.caption(
        "Skor adalah kesesuaian aturan, bukan probabilitas profit."
    )

    st.subheader("Rencana trading")

    if bias == "WAIT":
        st.warning(reason)
    else:
        st.write(f"Entry: {entry:.2f}")
        st.write(f"Stop Loss: {sl:.2f}")
        st.write(f"TP1: {tp1:.2f}")
        st.write(f"TP2: {tp2:.2f}")
        st.write(reason)

    st.write("Invalidasi:", invalidation)

    st.subheader("Multi-timeframe")

    table = []

    for tf, result in results.items():
        table.append({
            "Timeframe": tf,
            "Trend": result["trend"],
            "Harga": round(result["price"], 2),
            "Support": round(result["support"], 2),
            "Resistance": round(result["resistance"], 2)
        })

    st.dataframe(
        pd.DataFrame(table),
        use_container_width=True
    )

except Exception as error:
    st.error(f"Gagal mengambil data: {error}")
