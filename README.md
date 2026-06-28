# Forex Swing Bot 🤖

Bot de alertas de trading que replica la lógica del script Pine Script **EURUSD Swing H1-D1 Starter**, envía señales a Telegram y permite configurar, gestionar y analizar múltiples pares e indicadores de forma simultánea desde una interfaz web dinámica.

---

## Estructura del Proyecto

```
eurusd_bot/
├── app.py              ← Servidor Flask + APScheduler
├── signal_engine.py    ← Lógica de cálculo de señales (réplica Pine Script)
├── requirements.txt    ← Dependencias de Python
├── .env                ← Credenciales y tokens de Telegram (no subir a git)
├── profiles/           ← Directorio de configuraciones guardadas por par (.json)
└── templates/
    └── index.html      ← Interfaz web multipanel de configuración y monitorización
```

---

## 1. Instalar dependencias

Se recomienda usar un entorno virtual de Python:

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

---

## 2. Configurar Telegram

El bot utiliza la API de Telegram para enviar las señales y alertas directamente a tu chat privado o canal de forma independiente por cada par analizado.

### Crear el bot
1. Abre Telegram y busca a **@BotFather**.
2. Envía el comando `/newbot` y sigue las instrucciones para asignarle un nombre y un usuario.
3. Copia el **token HTTP API** proporcionado (ej. `123456789:AABBccdd...`).

### Obtener tu Chat ID
1. Busca a **@userinfobot** en Telegram.
2. Inicia una conversación y te responderá con tu **ID** (un número de 9-10 dígitos).

### Configurar el archivo `.env`
Crea un archivo llamado `.env` en la raíz del proyecto y añade tus credenciales:

```dotenv
TELEGRAM_TOKEN=tu_token_de_bot_aqui
TELEGRAM_CHAT_ID=tu_chat_id_aqui
```

---

## 3. Arrancar el bot

Ejecuta el servidor web y el programador de tareas:

```bash
python app.py
```

Al iniciarse, **el bot ejecuta un escaneo inicial inmediato en segundo plano** para todos los pares que estén activos para no dejar las tarjetas vacías.

Por defecto, la interfaz web estará disponible en: **http://localhost:5000**

---

## 4. Uso de la Interfaz Web (Frontend)

La interfaz permite controlar las configuraciones en tiempo real sin necesidad de reiniciar el script de Python.

| Sección / Acción | Descripción |
|------------------|-------------|
| **Pares guardados (Marca de Análisis)** | Muestra los perfiles bajo `/profiles`. Puedes pulsar un par para cargarlo en el formulario o borrarlo con **✕**. Cada par cuenta con un **checkbox** para activarlo o desactivarlo del análisis automático al instante. |
| **Bot activo** | Interruptor en el formulario de configuración para habilitar o deshabilitar el análisis del par en edición. |
| **Par (Yahoo Finance)** | Selector desplegable (combo box) con los pares más relevantes de Forex, criptomonedas e índices. Permite agregar cualquier ticker personalizado de Yahoo Finance mediante un prompt (`➕ Añadir otro...`). |
| **Intervalo (min)** | Cada cuántos minutos se escanea de forma independiente este par. |
| **Guardar par** | Guarda la configuración actual en `/profiles` y sincroniza las tareas de fondo en el planificador de inmediato. |
| **Escanear ahora** | Realiza una consulta y cálculo de señal inmediato para **todos los pares que tengan la marca de análisis activa**. |
| **Probar Telegram** | Envía un mensaje corto de prueba para verificar que la integración con Telegram funcione. |

---

## 5. Análisis Concurrentes y Visualización Multitarjeta

* **Planificador Inteligente (APScheduler)**: En lugar de un ciclo global rígido, el back-end corre subprocesos independientes para cada par de monedas habilitado, respetando su propio intervalo de tiempo de consulta configurado (ej. EUR/USD cada 30 min y BTC/USD cada 5 min).
* **Caché y Estados Independientes**: Las señales generadas, marcas de tiempo y el control de alertas duplicadas de Telegram se guardan y aíslan de forma independiente por cada par, evitando interferencias de alertas entre símbolos.
* **Paneles de Señales Dinámicos**: La columna derecha del frontend genera dinámicamente **una tarjeta de estado por cada par que tenga la marca de análisis habilitada**, mostrando de un vistazo sus entradas, stops, targets, valores de RSI, ATR y la confluencia de tendencias base y macro (HTF).

---

## 6. Parámetros equivalentes Pine → Python

| Pine Script | Interfaz Web / JSON | Por defecto | Descripción |
|-------------|---------------------|-------------|-------------|
| `emaFastLen` | EMA rápida | `50` | Periodo de la Media Móvil Exponencial rápida. |
| `emaSlowLen` | EMA lenta | `200` | Periodo de la Media Móvil Exponencial lenta. |
| `rsiLen` | RSI períodos | `14` | Periodos del indicador de fuerza relativa. |
| `atrLen` | ATR períodos | `14` | Periodos del Average True Range para volatilidad. |
| `stopATR` | Stop × ATR | `1.5` | Multiplicador del ATR para definir la distancia del Stop Loss. |
| `tpATR` | TP × ATR | `3.0` | Multiplicador del ATR para definir la distancia del Take Profit. |
| `useHTF` | Filtro marco mayor | `true` | Si está activo, valida que la tendencia HTF coincida con el timeframe base. |
| `htf` | Marco mayor (HTF) | `D` (Diario) | Temporalidad de la tendencia de marco mayor (`60`, `240`, `D`, `W`). |

---

## 7. Lógica de señales (Réplica de Pine Script)

Las señales se generan a partir de la confluencia de filtros de tendencia y momentum:

```text
EMA Rápida > EMA Lenta        → Tendencia alcista (Timeframe Base)
HTF EMA Rápida > EMA Lenta    → Tendencia alcista (Macro HTF)

Compra (LONG) cuando:
  • Tendencia Base es alcista.
  • Tendencia HTF es alcista (si el filtro HTF está activado).
  • Pullback: El Low tocó o cruzó la EMA rápida por debajo y el Close cerró por encima.
  • Momentum: El RSI cruzó 50 hacia arriba en la vela actual.

Venta (SHORT) cuando:
  • Tendencia Base es bajista.
  • Tendencia HTF es bajista (si el filtro HTF está activado).
  • Pullback: El High tocó o cruzó la EMA rápida por arriba y el Close cerró por debajo.
  • Momentum: El RSI cruzó 50 hacia abajo en la vela actual.

Distancias de órdenes:
  • Stop Loss   = Precio de Entrada ± (ATR × stopATR)
  • Take Profit = Precio de Entrada ± (ATR × tpATR)
```

---

## 8. Ejecución en Segundo Plano (Producción)

Para dejar corriendo el bot en Linux o Mac tras cerrar la consola, puedes usar `nohup` o `pm2`:

```bash
nohup python app.py > bot.log 2>&1 &
```

Para ver si sigue ejecutándose:
```bash
ps aux | grep app.py
```

---

## Notas Adicionales
- **Fuente de Datos**: Los datos históricos y en tiempo real se descargan de **Yahoo Finance** de manera gratuita y sin requerir claves de API.
- **Prevención de Alertas Duplicadas**: El bot evita el spam enviando solo un mensaje por dirección de señal (`LONG` o `SHORT`). Una vez enviada una alerta, espera a que cambie la dirección antes de volver a notificar.
- **Historial y Logs**:
  - `signals.log`: Guarda el historial técnico completo de depuración del bot.
  - La interfaz muestra los últimos 10 registros agregados de todos los pares escaneados en el historial global inferior.
