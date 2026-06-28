"""
signal_engine.py
Replica exacta de la lógica Pine Script EURUSD Swing H1-D1 Starter
"""

import pandas as pd
import pandas_ta as ta
import yfinance as yf
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Mapa de timeframes de Pine → yfinance
TIMEFRAME_MAP = {
    "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m",
    "60": "1h", "120": "2h", "240": "4h", "D": "1d", "W": "1wk", "M": "1mo"
}

HTF_PERIOD_MAP = {
    "1": "7d",  "5": "7d",  "15": "60d", "30": "60d",
    "60": "60d", "240": "180d", "D": "2y", "W": "5y"
}


@dataclass
class Signal:
    direction: str          # "LONG" | "SHORT" | "NONE"
    entry_price: float
    stop_loss: float
    take_profit: float
    rsi: float
    atr: float
    trend_h1: str           # "Alcista" | "Bajista" | "Neutra"
    trend_htf: str
    htf_label: str          # "4h" | "Diario" etc.
    symbol: str
    timeframe: str


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _rsi(series: pd.Series, length: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(com=length - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=length - 1, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, length: int) -> pd.Series:
    hl = high - low
    hc = (high - close.shift()).abs()
    lc = (low - close.shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(com=length - 1, adjust=False).mean()


def _crossover(series: pd.Series, level: float) -> pd.Series:
    """Replica ta.crossover: cruza el nivel hacia arriba"""
    above = series > level
    return above & ~above.shift(1).fillna(False)


def _crossunder(series: pd.Series, level: float) -> pd.Series:
    """Replica ta.crossunder: cruza el nivel hacia abajo"""
    below = series < level
    return below & ~below.shift(1).fillna(False)


def fetch_data(symbol: str, interval: str, period: str) -> Optional[pd.DataFrame]:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty or len(df) < 250:
            logger.warning(f"Datos insuficientes para {symbol} {interval}")
            return None
        df.index = pd.to_datetime(df.index)
        return df
    except Exception as e:
        logger.error(f"Error descargando {symbol} {interval}: {e}")
        return None


def compute_signal(config: dict) -> Optional[Signal]:
    """
    Recibe el diccionario de configuración y devuelve la señal actual.
    Replica fiel de la lógica Pine Script.
    """
    symbol     = config.get("symbol", "EURUSD=X")
    tf         = config.get("timeframe", "60")       # Pine timeframe string
    htf        = config.get("htf", "D")
    ema_fast   = int(config.get("ema_fast", 50))
    ema_slow   = int(config.get("ema_slow", 200))
    rsi_len    = int(config.get("rsi_len", 14))
    atr_len    = int(config.get("atr_len", 14))
    stop_atr   = float(config.get("stop_atr", 1.5))
    tp_atr     = float(config.get("tp_atr", 3.0))
    use_htf    = bool(config.get("use_htf", True))

    yf_tf   = TIMEFRAME_MAP.get(tf,  "1h")
    yf_htf  = TIMEFRAME_MAP.get(htf, "1d")

    # Período de descarga proporcional al timeframe
    period_map = {
        "1m":"7d","3m":"60d","5m":"60d","15m":"60d","30m":"60d",
        "1h":"2y","2h":"2y","4h":"2y","1d":"5y","1wk":"10y","1mo":"10y"
    }
    period     = period_map.get(yf_tf, "2y")
    period_htf = period_map.get(yf_htf, "5y")

    # ── Descargar datos base ──────────────────────────────────────────────────
    df = fetch_data(symbol, yf_tf, period)
    if df is None:
        return None

    df["ema_fast"] = _ema(df["Close"], ema_fast)
    df["ema_slow"] = _ema(df["Close"], ema_slow)
    df["rsi"]      = _rsi(df["Close"], rsi_len)
    df["atr"]      = _atr(df["High"], df["Low"], df["Close"], atr_len)

    # ── HTF ──────────────────────────────────────────────────────────────────
    htf_bull = False
    htf_bear = False
    if use_htf:
        df_htf = fetch_data(symbol, yf_htf, period_htf)
        if df_htf is not None:
            df_htf["ema_fast"] = _ema(df_htf["Close"], ema_fast)
            df_htf["ema_slow"] = _ema(df_htf["Close"], ema_slow)
            htf_last = df_htf.iloc[-1]
            htf_bull = htf_last["ema_fast"] > htf_last["ema_slow"]
            htf_bear = htf_last["ema_fast"] < htf_last["ema_slow"]

    # ── Señales (últimas 2 velas para detectar cruces) ───────────────────────
    df["pullback_long"]  = (df["Low"] <= df["ema_fast"]) & (df["Close"] > df["ema_fast"])
    df["pullback_short"] = (df["High"] >= df["ema_fast"]) & (df["Close"] < df["ema_fast"])
    df["momentum_long"]  = _crossover(df["rsi"], 50)
    df["momentum_short"] = _crossunder(df["rsi"], 50)
    df["trend_bull"]     = df["ema_fast"] > df["ema_slow"]
    df["trend_bear"]     = df["ema_fast"] < df["ema_slow"]

    last = df.iloc[-1]

    trend_bull = bool(last["trend_bull"])
    trend_bear = bool(last["trend_bear"])

    long_filter  = trend_bull and (not use_htf or htf_bull)
    short_filter = trend_bear and (not use_htf or htf_bear)

    long_entry  = long_filter  and bool(last["pullback_long"])  and bool(last["momentum_long"])
    short_entry = short_filter and bool(last["pullback_short"]) and bool(last["momentum_short"])

    close_price = float(last["Close"])
    atr_val     = float(last["atr"])
    rsi_val     = float(last["rsi"])

    # Etiquetas de tendencia
    def trend_label(bull, bear):
        return "Alcista" if bull else ("Bajista" if bear else "Neutra")

    htf_labels = {"1":"1m","5":"5m","15":"15m","30":"30m",
                  "60":"1h","240":"4h","D":"Diario","W":"Semanal","M":"Mensual"}

    direction = "NONE"
    sl = tp = 0.0

    if long_entry:
        direction = "LONG"
        sl = close_price - atr_val * stop_atr
        tp = close_price + atr_val * tp_atr
    elif short_entry:
        direction = "SHORT"
        sl = close_price + atr_val * stop_atr
        tp = close_price - atr_val * tp_atr

    return Signal(
        direction   = direction,
        entry_price = round(close_price, 5),
        stop_loss   = round(sl, 5),
        take_profit = round(tp, 5),
        rsi         = round(rsi_val, 2),
        atr         = round(atr_val, 5),
        trend_h1    = trend_label(trend_bull, trend_bear),
        trend_htf   = trend_label(htf_bull, htf_bear),
        htf_label   = htf_labels.get(htf, htf),
        symbol      = symbol,
        timeframe   = yf_tf,
    )
