# Forex Swing Bot 🤖

Bot de alertas para Forex que replica la lógica del script Pine Script **EURUSD Swing H1-D1 Starter**. Envía señales a Telegram y permite gestionar múltiples pares e indicadores desde una interfaz web simple.

---

## Descripción

Este proyecto ejecuta un servidor Flask que carga perfiles de configuración por par de divisas y programa análisis periódico con APScheduler.

- Calcula señales LONG / SHORT usando medias móviles, RSI y ATR.
- Controla múltiples símbolos con perfiles JSON en `profiles/`.
- Envía alertas a Telegram cuando cambia la dirección de la señal.
- Permite pruebas, escaneos manuales y administración desde una UI web.

---

## Estructura del Proyecto

```
eurusd_bot/
├── main.py             ← Servidor Flask + APScheduler
├── signal_engine.py    ← Cálculo de señales y descarga de datos de Yahoo Finance
├── requirements.txt    ← Dependencias de Python
├── .gitignore          ← Archivos que no deben versionarse
├── LICENSE             ← Licencia del proyecto
├── .env                ← Credenciales y tokens de Telegram (no subir a git)
├── profiles/           ← Configuraciones guardadas por par (.json)
├── signals.log         ← Registro de ejecución generado en tiempo de ejecución
└── templates/
    └── index.html      ← Interfaz web de configuración y monitorización
```

---

## Requisitos

- Python 3.11+ recomendado
- Conexión de red para descargar datos de Yahoo Finance y usar Telegram

---

## Instalación

```bash
cd /Users/kon/Desa/Python/MyAnafund/forex/eurusd_bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Configuración de Telegram

Crea un archivo `.env` en la raíz del proyecto con estas variables:

```dotenv
TELEGRAM_TOKEN=tu_token_de_bot_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui
```

- `TELEGRAM_TOKEN`: token del bot creado con **@BotFather**.
- `TELEGRAM_CHAT_ID`: ID del chat al que se enviarán las alertas.

---

## Ejecución

Inicia el servidor Flask con:

```bash
python main.py
```

Luego abre en el navegador:

```
http://localhost:5000
```

La aplicación arrancará en el puerto `5000` y mostrará la interfaz para gestionar configuraciones.

---

## Uso de la Interfaz Web

La interfaz permite:

- cargar perfiles guardados desde `profiles/`
- activar o desactivar el análisis periódico por par
- modificar parámetros de estrategia
- guardar perfiles
- escanear ahora mismo
- enviar un mensaje de prueba a Telegram

---

## Perfiles de Par

Cada par se guarda en `profiles/` como un JSON independiente. Ejemplo:

```json
{
  "symbol": "GBPUSD=X",
  "timeframe": "60",
  "ema_fast": 50,
  "ema_slow": 200,
  "rsi_len": 19,
  "atr_len": 13,
  "stop_atr": 1.6,
  "tp_atr": 2.0,
  "use_htf": true,
  "htf": "D",
  "interval": 30,
  "enabled": true
}
```

---

## Endpoints disponibles

La aplicación expone estas rutas internas usadas por la UI:

- `GET /` — página principal
- `GET /api/status` — estado actual, señal, perfiles y logs
- `POST /api/config` — guarda o actualiza la configuración activa
- `POST /api/profile/load` — carga un perfil por símbolo
- `POST /api/profile/toggle_enable` — activa / desactiva un perfil
- `POST /api/profile/delete` — elimina un perfil
- `POST /api/scan_now` — ejecuta un escaneo inmediato
- `POST /api/test_telegram` — envía un mensaje de prueba a Telegram

---

## Lógica de Señales

El motor de señales en `signal_engine.py` usa:

- EMA rápida y lenta para determinar tendencia
- RSI para detectar impulso y cruces de 50
- ATR para calcular stop loss y take profit
- Filtro opcional de marco mayor (HTF)

La señal se considera válida cuando:

- hay tendencia clara en el timeframe base
- el precio hace un pullback sobre la EMA rápida
- el RSI cruza 50 en la dirección adecuada
- si `use_htf` está activado, la tendencia en el marco mayor coincide

---

## Notas de Producción

- `signals.log` guarda el historial y los mensajes de depuración.
- `profiles/` se crea automáticamente si no existe.
- `.env` nunca debe subirse a GitHub.
- Si necesitas ejecutar en segundo plano:

```bash
nohup python main.py > bot.log 2>&1 &
```

---

## Dependencias principales

- `flask`
- `python-dotenv`
- `pandas`
- `pandas-ta`
- `yfinance`
- `requests`
- `apscheduler`

---

## Issues / Roadmap

### Cómo reportar un problema

- Abre un issue en GitHub con el título claro y una descripción de la falla.
- Incluye:
  - `symbol` y `timeframe` usados
  - pasos para reproducir
  - mensaje de error o comportamiento observado
  - versión de Python y si usas un entorno virtual

### Mejora del proyecto

Prioridades sugeridas:

1. Soporte para más fuentes de datos y brokers.
2. Validación más completa de configuraciones en la UI.
3. Mejora del historial de señales y exportación a CSV.
4. Alertas más inteligentes y reducción de falsos positivos.
5. Modo de simulación / backtest con datos históricos.

---

## Licencia

Este proyecto está licenciado bajo la licencia MIT. Consulta el archivo `LICENSE` para más detalles.
