"""
app.py  —  Forex Swing Bot
Flask + APScheduler + Telegram
Config guardada por par
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

import requests
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from signal_engine import compute_signal, Signal

# ── Configuración ──────────────────────────────────────────────────────────────
load_dotenv()

BASE_DIR     = Path(__file__).parent
PROFILES_DIR = BASE_DIR / "profiles"   # un JSON por par
PROFILES_DIR.mkdir(exist_ok=True)
LOG_FILE     = BASE_DIR / "signals.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Config por defecto ────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "symbol":    "EURUSD=X",
    "timeframe": "60",
    "ema_fast":  50,
    "ema_slow":  200,
    "rsi_len":   14,
    "atr_len":   14,
    "stop_atr":  1.5,
    "tp_atr":    3.0,
    "use_htf":   True,
    "htf":       "D",
    "interval":  30,
    "enabled":   True,
}

HTF_OPTIONS = [
    ("60",  "1 hora"),
    ("240", "4 horas"),
    ("D",   "Diario"),
    ("W",   "Semanal"),
]

TF_OPTIONS = [
    ("15",  "15 minutos"),
    ("30",  "30 minutos"),
    ("60",  "1 hora"),
    ("240", "4 horas"),
    ("D",   "Diario"),
]


# ── Gestión de perfiles por par ───────────────────────────────────────────────
def symbol_to_filename(symbol: str) -> str:
    """EURUSD=X → EURUSD_X.json"""
    return symbol.replace("=", "_").replace("/", "_").replace("^", "_") + ".json"


def list_profiles() -> list[dict]:
    """Devuelve todos los perfiles guardados, ordenados alfabéticamente."""
    profiles = []
    for f in sorted(PROFILES_DIR.glob("*.json")):
        try:
            with open(f) as fp:
                cfg = json.load(fp)
            profiles.append({
                "symbol":    cfg.get("symbol", f.stem),
                "timeframe": cfg.get("timeframe", "60"),
                "htf":       cfg.get("htf", "D"),
                "enabled":   cfg.get("enabled", True),
                "interval":  cfg.get("interval", 30),
                "filename":  f.name,
            })
        except Exception:
            pass
    return profiles


def load_profile(symbol: str) -> dict:
    """Carga la config de un par. Si no existe, devuelve defaults con ese par."""
    path = PROFILES_DIR / symbol_to_filename(symbol)
    if path.exists():
        try:
            with open(path) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return {**DEFAULT_CONFIG, "symbol": symbol}


def save_profile(cfg: dict):
    """Guarda la config en el archivo del par correspondiente."""
    path = PROFILES_DIR / symbol_to_filename(cfg["symbol"])
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    logger.info(f"Perfil guardado: {path.name}")


def delete_profile(symbol: str) -> bool:
    path = PROFILES_DIR / symbol_to_filename(symbol)
    if path.exists():
        path.unlink()
        return True
    return False


# ── Estado compartido ─────────────────────────────────────────────────────────
# Al arrancar, carga el primer perfil disponible o el default
_existing = list_profiles()
_initial_symbol = _existing[0]["symbol"] if _existing else DEFAULT_CONFIG["symbol"]

state = {
    "last_signals":   {},   # dict: symbol -> signal_data
    "last_checks":    {},   # dict: symbol -> iso_timestamp
    "last_alert_dir": {},   # dict: symbol -> direction_str
    "config":         load_profile(_initial_symbol),
    "log":            [],
}


# ── Telegram ──────────────────────────────────────────────────────────────────
def send_telegram(message: str) -> bool:
    token   = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        logger.warning("Telegram no configurado en .env")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id":    chat_id,
            "text":       message,
            "parse_mode": "HTML"
        }, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error Telegram: {e}")
        return False


def build_telegram_message(sig: Signal) -> str:
    emoji = "🟢" if sig.direction == "LONG" else "🔴"
    arrow = "📈" if sig.direction == "LONG" else "📉"
    return (
        f"{emoji} <b>Setup Swing {sig.direction}</b> {arrow}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Par:</b> {sig.symbol}\n"
        f"⏱ <b>TF:</b> {sig.timeframe}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Entrada:</b> {sig.entry_price}\n"
        f"🛑 <b>Stop Loss:</b> {sig.stop_loss}\n"
        f"🎯 <b>Take Profit:</b> {sig.take_profit}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📐 <b>RSI:</b> {sig.rsi}\n"
        f"📏 <b>ATR:</b> {sig.atr}\n"
        f"🧭 <b>Tendencia H1:</b> {sig.trend_h1}\n"
        f"🔭 <b>Tendencia HTF ({sig.htf_label}):</b> {sig.trend_htf}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )


# ── Scheduler ─────────────────────────────────────────────────────────────────
def scan_single_profile_job(cfg):
    symbol = cfg.get("symbol", "EURUSD=X")
    logger.info(f"Escaneando {symbol} TF:{cfg.get('timeframe')} HTF:{cfg.get('htf')}")
    sig = compute_signal(cfg)
    now_str = datetime.now().isoformat()
    state["last_checks"][symbol] = now_str

    if sig is None:
        logger.warning(f"No se pudo obtener señal para {symbol}")
        return

    sig_data = {
        "direction":   sig.direction,
        "entry_price": sig.entry_price,
        "stop_loss":   sig.stop_loss,
        "take_profit": sig.take_profit,
        "rsi":         sig.rsi,
        "atr":         sig.atr,
        "trend_h1":    sig.trend_h1,
        "trend_htf":   sig.trend_htf,
        "htf_label":   sig.htf_label,
        "symbol":      sig.symbol,
        "timeframe":   sig.timeframe,
        "timestamp":   now_str,
    }

    state["last_signals"][symbol] = sig_data

    if sig.direction != "NONE":
        log_entry = {**sig_data}
        state["log"] = ([log_entry] + state["log"])[:20]

        last_dir = state["last_alert_dir"].get(symbol)
        if sig.direction != last_dir:
            state["last_alert_dir"][symbol] = sig.direction
            send_telegram(build_telegram_message(sig))
            logger.info(f"Señal {sig.direction} para {symbol}: entry={sig.entry_price}")
    else:
        state["last_alert_dir"][symbol] = None


def sync_scheduler():
    """Sincroniza los trabajos del planificador con los perfiles guardados y habilitados."""
    existing_jobs = {job.id: job for job in scheduler.get_jobs()}
    
    # Cargar todos los perfiles
    configs = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            with open(f) as fp:
                cfg = json.load(fp)
                configs.append({**DEFAULT_CONFIG, **cfg})
        except Exception as e:
            logger.error(f"Error cargando perfil {f.name}: {e}")

    active_job_ids = set()
    for cfg in configs:
        symbol = cfg["symbol"]
        job_id = f"scan_{symbol}"
        
        if cfg.get("enabled", True):
            active_job_ids.add(job_id)
            interval_mins = cfg.get("interval", 30)
            
            if job_id in existing_jobs:
                job = existing_jobs[job_id]
                trigger = job.trigger
                job_interval_mins = int(trigger.interval.total_seconds() // 60)
                if job_interval_mins != interval_mins:
                    logger.info(f"Actualizando intervalo de {symbol} a {interval_mins} min")
                    scheduler.reschedule_job(job_id, trigger="interval", minutes=interval_mins)
            else:
                logger.info(f"Agregando planificador para {symbol} cada {interval_mins} min")
                scheduler.add_job(
                    scan_single_profile_job,
                    "interval",
                    minutes=interval_mins,
                    id=job_id,
                    args=[cfg],
                    replace_existing=True
                )
                
    # Eliminar trabajos deshabilitados o eliminados
    for job_id in list(existing_jobs.keys()):
        if job_id.startswith("scan_") and job_id not in active_job_ids:
            logger.info(f"Removiendo planificador para {job_id}")
            scheduler.remove_job(job_id)


def run_initial_scan():
    logger.info("Ejecutando escaneo inicial de arranque para perfiles habilitados...")
    for f in PROFILES_DIR.glob("*.json"):
        try:
            with open(f) as fp:
                cfg = json.load(fp)
                full_cfg = {**DEFAULT_CONFIG, **cfg}
                if full_cfg.get("enabled", True):
                    scan_single_profile_job(full_cfg)
        except Exception as e:
            logger.error(f"Error en escaneo inicial de {f.name}: {e}")


scheduler = BackgroundScheduler(timezone="Europe/Madrid")
scheduler.start()
sync_scheduler()
scheduler.add_job(run_initial_scan, id="initial_scan")


# ── Rutas Flask ───────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html",
                           config=state["config"],
                           htf_options=HTF_OPTIONS,
                           tf_options=TF_OPTIONS,
                           telegram_ok=bool(
                               os.getenv("TELEGRAM_TOKEN") and
                               os.getenv("TELEGRAM_CHAT_ID")))


@app.route("/api/status")
def api_status():
    return jsonify({
        "last_signals": state["last_signals"],
        "last_checks":  state["last_checks"],
        "config":      state["config"],
        "log":         state["log"][:10],
        "profiles":    list_profiles(),
    })


@app.route("/api/config", methods=["POST"])
def api_config():
    """Guarda la config del par activo y la activa en el estado."""
    data = request.json or {}
    cfg  = state["config"]

    cfg["symbol"]    = data.get("symbol",    cfg["symbol"]).strip()
    cfg["timeframe"] = data.get("timeframe", cfg["timeframe"])
    cfg["ema_fast"]  = int(data.get("ema_fast",  cfg["ema_fast"]))
    cfg["ema_slow"]  = int(data.get("ema_slow",  cfg["ema_slow"]))
    cfg["rsi_len"]   = int(data.get("rsi_len",   cfg["rsi_len"]))
    cfg["atr_len"]   = int(data.get("atr_len",   cfg["atr_len"]))
    cfg["stop_atr"]  = float(data.get("stop_atr", cfg["stop_atr"]))
    cfg["tp_atr"]    = float(data.get("tp_atr",   cfg["tp_atr"]))
    cfg["use_htf"]   = bool(data.get("use_htf",   cfg["use_htf"]))
    cfg["htf"]       = data.get("htf",       cfg["htf"])
    cfg["interval"]  = int(data.get("interval",  cfg["interval"]))
    cfg["enabled"]   = bool(data.get("enabled",  cfg["enabled"]))

    save_profile(cfg)
    sync_scheduler()
    return jsonify({"ok": True, "config": cfg, "profiles": list_profiles()})


@app.route("/api/profile/load", methods=["POST"])
def api_profile_load():
    """Carga el perfil de un par y lo activa."""
    symbol = (request.json or {}).get("symbol", "").strip()
    if not symbol:
        return jsonify({"ok": False, "error": "symbol requerido"}), 400

    cfg = load_profile(symbol)
    state["config"] = cfg
    logger.info(f"Perfil cargado y activo: {symbol}")
    return jsonify({"ok": True, "config": cfg, "profiles": list_profiles()})


@app.route("/api/profile/toggle_enable", methods=["POST"])
def api_profile_toggle_enable():
    """Alterna el estado 'enabled' de un perfil directamente desde la lista."""
    symbol = (request.json or {}).get("symbol", "").strip()
    if not symbol:
        return jsonify({"ok": False, "error": "symbol requerido"}), 400

    cfg = load_profile(symbol)
    cfg["enabled"] = not cfg.get("enabled", True)
    save_profile(cfg)

    # Si modificamos el perfil que actualmente está activo, sincronizar en memoria
    if state["config"]["symbol"] == symbol:
        state["config"]["enabled"] = cfg["enabled"]

    sync_scheduler()
    logger.info(f"Perfil {symbol} habilitado={cfg['enabled']}")
    return jsonify({"ok": True, "profiles": list_profiles(), "config": state["config"]})


@app.route("/api/profile/delete", methods=["POST"])
def api_profile_delete():
    """Elimina el perfil de un par."""
    symbol = (request.json or {}).get("symbol", "").strip()
    if not symbol:
        return jsonify({"ok": False, "error": "symbol requerido"}), 400

    deleted = delete_profile(symbol)

    # Si era el activo, cargar otro o default
    if state["config"]["symbol"] == symbol:
        remaining = list_profiles()
        next_sym  = remaining[0]["symbol"] if remaining else DEFAULT_CONFIG["symbol"]
        state["config"] = load_profile(next_sym)

    # Limpiar estado obsoleto
    state["last_signals"].pop(symbol, None)
    state["last_checks"].pop(symbol, None)
    state["last_alert_dir"].pop(symbol, None)

    sync_scheduler()
    return jsonify({"ok": deleted, "profiles": list_profiles(), "config": state["config"]})


@app.route("/api/scan_now", methods=["POST"])
def api_scan_now():
    """Escanea inmediatamente todos los perfiles habilitados."""
    configs = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            with open(f) as fp:
                cfg = json.load(fp)
                configs.append({**DEFAULT_CONFIG, **cfg})
        except Exception:
            pass

    scanned_any = False
    for cfg in configs:
        if cfg.get("enabled", True):
            scan_single_profile_job(cfg)
            scanned_any = True

    # Si no hay ninguno habilitado, escanear al menos el activo actual
    if not scanned_any:
        scan_single_profile_job(state["config"])

    return jsonify({"ok": True})


@app.route("/api/test_telegram", methods=["POST"])
def api_test_telegram():
    ok = send_telegram(
        "✅ <b>Forex Swing Bot conectado</b>\n"
        f"Par activo: <b>{state['config']['symbol']}</b>\n"
        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )
    return jsonify({"ok": ok})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
