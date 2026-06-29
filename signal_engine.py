"""
signal_engine.py
Replica la logica Pine Script EURUSD Swing H1-D1 Starter sin dependencias nativas.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Mapa de timeframes de Pine -> intervalos internos.
TIMEFRAME_MAP = {
    "1": "1m", "3": "3m", "5": "5m", "15": "15m", "30": "30m",
    "60": "1h", "120": "2h", "240": "4h", "D": "1d", "W": "1wk", "M": "1mo"
}

YAHOO_INTERVAL_MAP = {
    "1m": "1m",
    "3m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "2h": "60m",
    "4h": "60m",
    "1d": "1d",
    "1wk": "1wk",
    "1mo": "1mo",
}

RESAMPLE_SECONDS = {
    "2h": 2 * 60 * 60,
    "4h": 4 * 60 * 60,
}


@dataclass
class Candle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


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


def _ema(values: list[float], length: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (length + 1)
    out = [float(values[0])]
    for value in values[1:]:
        out.append((float(value) * alpha) + (out[-1] * (1 - alpha)))
    return out


def _rsi(values: list[float], length: int) -> list[float]:
    if not values:
        return []

    gains = [0.0]
    losses = [0.0]
    for prev, current in zip(values, values[1:]):
        delta = current - prev
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))

    avg_gain = _rma(gains, length)
    avg_loss = _rma(losses, length)

    out = []
    for gain, loss in zip(avg_gain, avg_loss):
        if loss == 0:
            out.append(100.0)
        else:
            rs = gain / loss
            out.append(100 - (100 / (1 + rs)))
    return out


def _atr(candles: list[Candle], length: int) -> list[float]:
    if not candles:
        return []

    true_ranges = []
    previous_close = candles[0].close
    for candle in candles:
        true_ranges.append(max(
            candle.high - candle.low,
            abs(candle.high - previous_close),
            abs(candle.low - previous_close),
        ))
        previous_close = candle.close
    return _rma(true_ranges, length)


def _rma(values: list[float], length: int) -> list[float]:
    if not values:
        return []
    alpha = 1 / length
    out = [float(values[0])]
    for value in values[1:]:
        out.append((float(value) * alpha) + (out[-1] * (1 - alpha)))
    return out


def _crossover(values: list[float], level: float, index: int) -> bool:
    if index <= 0:
        return False
    return values[index] > level and values[index - 1] <= level


def _crossunder(values: list[float], level: float, index: int) -> bool:
    if index <= 0:
        return False
    return values[index] < level and values[index - 1] >= level


def _resample_candles(candles: list[Candle], seconds: int) -> list[Candle]:
    grouped = {}
    for candle in candles:
        bucket = (candle.timestamp // seconds) * seconds
        current = grouped.get(bucket)
        if current is None:
            grouped[bucket] = Candle(
                timestamp=bucket,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
        else:
            current.high = max(current.high, candle.high)
            current.low = min(current.low, candle.low)
            current.close = candle.close
            current.volume += candle.volume
    return [grouped[key] for key in sorted(grouped)]


def _parse_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_data(symbol: str, interval: str, period: str) -> Optional[list[Candle]]:
    try:
        yahoo_interval = YAHOO_INTERVAL_MAP.get(interval, "60m")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        response = requests.get(
            url,
            params={
                "range": period,
                "interval": yahoo_interval,
                "includePrePost": "false",
                "events": "div,splits",
            },
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        response.raise_for_status()

        payload = response.json()
        chart = payload.get("chart", {})
        if chart.get("error"):
            logger.error(f"Yahoo error para {symbol} {interval}: {chart['error']}")
            return None

        result = (chart.get("result") or [None])[0]
        if not result or not result.get("timestamp"):
            logger.warning(f"Sin datos para {symbol} {interval}")
            return None

        quote = (result.get("indicators", {}).get("quote") or [None])[0]
        if not quote:
            logger.warning(f"Sin OHLC para {symbol} {interval}")
            return None

        candles = []
        rows = zip(
            result["timestamp"],
            quote.get("open") or [],
            quote.get("high") or [],
            quote.get("low") or [],
            quote.get("close") or [],
            quote.get("volume") or [],
        )
        for timestamp, open_, high, low, close, volume in rows:
            parsed = [_parse_float(v) for v in (open_, high, low, close)]
            if any(v is None for v in parsed):
                continue
            candles.append(Candle(
                timestamp=int(timestamp),
                open=parsed[0],
                high=parsed[1],
                low=parsed[2],
                close=parsed[3],
                volume=_parse_float(volume) or 0.0,
            ))

        resample_seconds = RESAMPLE_SECONDS.get(interval)
        if resample_seconds:
            candles = _resample_candles(candles, resample_seconds)

        if len(candles) < 250:
            logger.warning(f"Datos insuficientes para {symbol} {interval}")
            return None

        return candles
    except Exception as e:
        logger.error(f"Error descargando {symbol} {interval}: {e}")
        return None


def compute_signal(config: dict) -> Optional[Signal]:
    """
    Recibe el diccionario de configuracion y devuelve la senal actual.
    Replica fiel de la logica Pine Script.
    """
    symbol = config.get("symbol", "EURUSD=X")
    tf = config.get("timeframe", "60")
    htf = config.get("htf", "D")
    ema_fast = int(config.get("ema_fast", 50))
    ema_slow = int(config.get("ema_slow", 200))
    rsi_len = int(config.get("rsi_len", 14))
    atr_len = int(config.get("atr_len", 14))
    stop_atr = float(config.get("stop_atr", 1.5))
    tp_atr = float(config.get("tp_atr", 3.0))
    use_htf = bool(config.get("use_htf", True))

    yf_tf = TIMEFRAME_MAP.get(tf, "1h")
    yf_htf = TIMEFRAME_MAP.get(htf, "1d")

    period_map = {
        "1m": "7d", "3m": "60d", "5m": "60d", "15m": "60d", "30m": "60d",
        "1h": "2y", "2h": "2y", "4h": "2y", "1d": "5y", "1wk": "10y",
        "1mo": "10y",
    }
    period = period_map.get(yf_tf, "2y")
    period_htf = period_map.get(yf_htf, "5y")

    candles = fetch_data(symbol, yf_tf, period)
    if candles is None:
        return None

    closes = [c.close for c in candles]
    ema_fast_values = _ema(closes, ema_fast)
    ema_slow_values = _ema(closes, ema_slow)
    rsi_values = _rsi(closes, rsi_len)
    atr_values = _atr(candles, atr_len)

    htf_bull = False
    htf_bear = False
    if use_htf:
        htf_candles = fetch_data(symbol, yf_htf, period_htf)
        if htf_candles is not None:
            htf_closes = [c.close for c in htf_candles]
            htf_ema_fast = _ema(htf_closes, ema_fast)[-1]
            htf_ema_slow = _ema(htf_closes, ema_slow)[-1]
            htf_bull = htf_ema_fast > htf_ema_slow
            htf_bear = htf_ema_fast < htf_ema_slow

    index = len(candles) - 1
    last = candles[index]
    last_ema_fast = ema_fast_values[index]
    last_ema_slow = ema_slow_values[index]

    trend_bull = last_ema_fast > last_ema_slow
    trend_bear = last_ema_fast < last_ema_slow
    long_filter = trend_bull and (not use_htf or htf_bull)
    short_filter = trend_bear and (not use_htf or htf_bear)

    pullback_long = last.low <= last_ema_fast and last.close > last_ema_fast
    pullback_short = last.high >= last_ema_fast and last.close < last_ema_fast
    momentum_long = _crossover(rsi_values, 50, index)
    momentum_short = _crossunder(rsi_values, 50, index)

    long_entry = long_filter and pullback_long and momentum_long
    short_entry = short_filter and pullback_short and momentum_short

    close_price = float(last.close)
    atr_val = float(atr_values[index])
    rsi_val = float(rsi_values[index])

    def trend_label(bull, bear):
        return "Alcista" if bull else ("Bajista" if bear else "Neutra")

    htf_labels = {
        "1": "1m", "5": "5m", "15": "15m", "30": "30m", "60": "1h",
        "240": "4h", "D": "Diario", "W": "Semanal", "M": "Mensual",
    }

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

    logger.info(
        "Signal computed %s %s at %s",
        symbol,
        yf_tf,
        datetime.fromtimestamp(last.timestamp, tz=timezone.utc).isoformat(),
    )

    return Signal(
        direction=direction,
        entry_price=round(close_price, 5),
        stop_loss=round(sl, 5),
        take_profit=round(tp, 5),
        rsi=round(rsi_val, 2),
        atr=round(atr_val, 5),
        trend_h1=trend_label(trend_bull, trend_bear),
        trend_htf=trend_label(htf_bull, htf_bear),
        htf_label=htf_labels.get(htf, htf),
        symbol=symbol,
        timeframe=yf_tf,
    )
