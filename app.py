
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone

st.set_page_config(
    page_title="AI SNR XAUUSD",
    page_icon="📈",
    layout="wide"
)

st.title("📈 AI SNR XAUUSD")
st.caption("Dashboard analisis emas multi-timeframe MN, W1, D1, H4, H1, M5, M1")

st.warning(
    "Data Yahoo Finance bukan feed resmi HFM. "
    "GC=F adalah Gold Futures, bukan harga spot XAUUSD. "
    "Gunakan untuk pengujian, bukan jaminan profit."
)

TIMEFRAMES = {
    "MN": ("1mo", "10y", "Monthly"),
    "W1": ("1wk", "10y", "Weekly"),
    "D1": ("1d", "5y", "Daily"),
    "H4": ("1h", "730d", "H4"),
    "H1": ("1h", "730d", "Hourly"),
    "M5": ("5m", "60d", "5 menit"),
    "M1": ("1m", "7d", "1 menit")
}

SYMBOLS = ["XAUUSD=X", "GC=F"]


@st.cache_data(ttl=60, show_spinner=False)
def download_history(symbol, interval, period):
    try:
        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if df is None or df.empty:
            return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            for level in range(df.columns.nlevels):
                values = set(
                    map(str, df.columns.get_level_values(level))
                )

                if {"Open", "High", "Low", "Close"}.issubset(values):
                    df.columns = df.columns.get_level_values(level)
                    break

        columns = ["Open", "High", "Low", "Close"]

        if not all(x in df.columns for x in columns):
            return pd.DataFrame()

        df = df[columns].copy()
        df = df.replace([np.inf, -np.inf], np.nan).dropna()

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors="coerce")
            df = df[~df.index.isna()]

        return df

    except Exception:
        return pd.DataFrame()


def load_tf(tf):
    interval, period, label = TIMEFRAMES[tf]

    for symbol in SYMBOLS:
        df = download_history(symbol, interval, period)

        if not df.empty:

            if tf == "H4":
                df = df.resample("4h").agg({
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last"
                }).dropna()

            if not df.empty:
                return df, symbol

    return pd.DataFrame(), None


def analyze(df):

    if df is None or len(df) < 30:
        return None

    close = df["Close"].astype(float)

    ema20 = close.ewm(
        span=20,
        adjust=False
    ).mean().iloc[-1]

    ema50 = close.ewm(
        span=50,
        adjust=False
    ).mean().iloc[-1]

    price = float(close.iloc[-1])

    if price > ema20 > ema50:
        trend = "Bullish"

    elif price < ema20 < ema50:
        trend = "Bearish"

    else:
        trend = "Netral"

    recent = df.tail(30)
    last = df.iloc[-1]

    candle_range = float(last["High"] - last["Low"])
    body = abs(float(last["Close"] - last["Open"]))

    if candle_range <= 0:
        candle = "Tidak jelas"

    elif last["Close"] > last["Open"] and body / candle_range >= 0.5:
        candle = "Bullish kuat"

    elif last["Close"] < last["Open"] and body / candle_range >= 0.5:
        candle = "Bearish kuat"

    else:
        candle = "Netral / belum kuat"

    return {
        "trend": trend,
        "price": price,
        "support": float(recent["Low"].min()),
        "resistance": float(recent["High"].max()),
        "candle": candle
    }


def make_signal(results):

    missing = [
        tf for tf in TIMEFRAMES
        if results.get(tf) is None
    ]

    if missing:
        return (
            "WAIT",
            "Data belum lengkap: " + ", ".join(missing),
            0
        )

    trends = [
        results[x]["trend"]
        for x in TIMEFRAMES
    ]

    score = round(
        max(
            trends.count("Bullish"),
            trends.count("Bearish")
        ) / 7 * 100
    )

    if all(x == "Bullish" for x in trends):
        return (
            "BUY",
            "Semua timeframe bullish. Tunggu harga kembali ke support dan muncul konfirmasi candle sebelum entry.",
            score
        )

    if all(x == "Bearish" for x in trends):
        return (
            "SELL",
            "Semua timeframe bearish. Tunggu harga kembali ke resistance dan muncul konfirmasi candle sebelum entry.",
            score
        )

    return (
        "WAIT",
        "Konfirmasi multi-timeframe belum selaras. Jangan memaksakan entry.",
        score
    )


if st.button("🔄 Perbarui analisis"):
    st.cache_data.clear()
    st.rerun()


data = {}
sources = {}
results = {}

with st.spinner("Mengambil data harga emas..."):

    for tf in TIMEFRAMES:

        data[tf], sources[tf] = load_tf(tf)

        results[tf] = analyze(data[tf])


valid_sources = sorted(
    set(x for x in sources.values() if x)
)

if valid_sources:
    st.info(
        "Sumber data berhasil: " + ", ".join(valid_sources)
    )

else:
    st.error(
        "Data tidak berhasil diambil. "
        "Coba lagi nanti dan periksa koneksi internet."
    )


st.subheader("Ringkasan Multi-Timeframe")

rows = []

for tf, (_, _, label) in TIMEFRAMES.items():

    r = results[tf]

    rows.append({
        "TF": tf,
        "Keterangan": label,
        "Tren": r["trend"] if r else "DATA KOSONG",
        "Harga": round(r["price"], 2) if r else "-",
        "Support": round(r["support"], 2) if r else "-",
        "Resistance": round(r["resistance"], 2) if r else "-",
        "Candle": r["candle"] if r else "-"
    })

st.dataframe(
    pd.DataFrame(rows),
    use_container_width=True,
    hide_index=True
)


bias, reason, score = make_signal(results)

st.subheader("Keputusan Analisis")

if bias == "BUY":
    st.success("BIAS: BUY")

elif bias == "SELL":
    st.error("BIAS: SELL")

else:
    st.warning("BIAS: WAIT")

st.write(reason)

st.metric(
    "Skor Keselarasan Aturan",
    f"{score}/100"
)

st.caption(
    "Skor menunjukkan keselarasan tren timeframe, "
    "bukan probabilitas menang atau jaminan profit."
)


if results.get("H1"):

    r = results["H1"]

    a, b, c = st.columns(3)

    a.metric("Harga H1", f'{r["price"]:.2f}')

    b.metric("Support H1", f'{r["support"]:.2f}')

    c.metric("Resistance H1", f'{r["resistance"]:.2f}')


st.subheader("Catatan Penting")

st.markdown("""
- XAUUSD=X dicoba terlebih dahulu.
- Jika gagal, aplikasi mencoba GC=F.
- GC=F adalah Gold Futures, bukan harga spot HFM.
- H4 dibentuk dari candle H1.
- Yahoo Finance dapat membatasi data M1 dan M5.
- Jika satu timeframe tidak tersedia, keputusan menjadi WAIT.
- Analisis ini masih prototipe EMA 20/50 dan high/low 30 candle.
- Belum memetakan seluruh aturan SNR manual.
- Periksa harga dan spread di MT5 HFM sebelum entry.
- Selalu gunakan Stop Loss dan batasi risiko.
""")

st.caption(
    "Pembaruan: " +
    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
)
