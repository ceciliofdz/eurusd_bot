// ── Estado local ───────────────────────────────────────────────────────────────
let activeSymbol = 'EURUSD=X';
let initialConfigLoaded = false;

// ── Utilidades ─────────────────────────────────────────────────────────────────
function toast(msg, type = 'ok') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'show ' + type;
  setTimeout(() => t.className = '', 2800);
}

function fmtTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('es-ES') + ' ' + d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
}

function renderTelegramStatus(isConfigured) {
  const badge = document.getElementById('telegram-status');
  if (!badge) return;
  badge.textContent = isConfigured ? '✓ Telegram' : '✗ Telegram';
  badge.className = 'badge-telegram ' + (isConfigured ? 'ok' : 'error');
}

// ── Render perfiles ────────────────────────────────────────────────────────────
function renderProfiles(profiles) {
  const container = document.getElementById('profiles-list');
  const counter   = document.getElementById('profile-count');
  counter.textContent = profiles.length;

  if (!profiles.length) {
    container.innerHTML = '<div class="profiles-empty">Sin perfiles aún. Configura un par y guárdalo.</div>';
    return;
  }

  const tfLabel = { '15':'15m', '30':'30m', '60':'1h', '240':'4h', 'D':'D', 'W':'W' };
  const htfLabel = { '60':'1h', '240':'4h', 'D':'D', 'W':'W' };

  container.innerHTML = profiles.map(p => `
    <div class="profile-item ${p.symbol === activeSymbol ? 'active' : ''}"
         onclick="loadProfile('${p.symbol}')">
      <input type="checkbox" class="profile-enable-chk" 
             ${p.enabled ? 'checked' : ''} 
             onclick="toggleProfileEnable(event, '${p.symbol}')"
             title="Activar para análisis automático">
      <span class="profile-sym">${p.symbol.replace('=X','').replace('=','')}</span>
      <span class="profile-meta">${tfLabel[p.timeframe] || p.timeframe} · HTF ${htfLabel[p.htf] || p.htf}</span>
      <button class="profile-delete" title="Eliminar" onclick="deleteProfile(event, '${p.symbol}')">✕</button>
    </div>
  `).join('');
}

async function toggleProfileEnable(event, symbol) {
  event.stopPropagation(); // Evitar cambiar de par activo al pulsar el checkbox
  try {
    const r = await fetch('/api/profile/toggle_enable', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol })
    });
    const d = await r.json();
    if (d.ok) {
      if (d.profiles) renderProfiles(d.profiles);
      if (d.config) applyConfigToForm(d.config);
      toast(`✓ Configuración de ${symbol} actualizada`, 'ok');
    }
  } catch(e) {
    toast('✗ Error de red', 'err');
  }
}

// ── Render señal ───────────────────────────────────────────────────────────────
// ── Render señales de todos los pares activos ──────────────────────────────────
function renderSignals(profiles, lastSignals, lastChecks) {
  const container = document.getElementById('signals-container');
  if (!container) return;

  const enabledProfiles = profiles.filter(p => p.enabled);

  if (!enabledProfiles.length) {
    container.innerHTML = `
      <div class="card">
        <div class="card-header">📡 Señales de análisis</div>
        <div style="padding: 24px; text-align: center; color: var(--muted); font-family: var(--mono); font-size: 12px;">
          Sin pares marcados para analizar. Marca los checkboxes en "Pares guardados" para iniciar el escaneo.
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = enabledProfiles.map(p => {
    const symbol = p.symbol;
    const sig = lastSignals[symbol];
    const checkTime = lastChecks[symbol];
    
    const direction = sig ? sig.direction : 'NONE';
    const badgeText = direction === 'NONE' ? 'ESPERANDO' : direction;
    const timestampText = checkTime ? 'Último escaneo: ' + fmtTime(checkTime) : 'Esperando primer escaneo...';
    
    const entry = (sig && direction !== 'NONE') ? sig.entry_price : '—';
    const sl = (sig && direction !== 'NONE') ? sig.stop_loss : '—';
    const tp = (sig && direction !== 'NONE') ? sig.take_profit : '—';
    
    const rsi = sig ? (sig.rsi ?? '—') : '—';
    const atr = sig ? (sig.atr ?? '—') : '—';
    
    const trendH1 = sig ? (sig.trend_h1 ?? '—') : '—';
    const trendHTF = sig ? (sig.trend_htf ?? '—') : '—';
    const htfLabel = sig ? (sig.htf_label ?? '') : '';

    return `
      <div class="card">
        <div class="card-header" style="display: flex; justify-content: space-between; align-items: center;">
          <span>📡 Análisis: <b>${symbol.replace('=X','').replace('=','')}</b></span>
          <span style="color:var(--accent2); font-family:var(--mono); font-size:11px;">TF: ${p.timeframe}m | HTF: ${p.htf}</span>
        </div>

        <div class="signal-panel">
          <div class="signal-badge ${direction}">${badgeText}</div>
          <div class="signal-ts">${timestampText}</div>
        </div>

        <div class="metrics">
          <div class="metric">
            <div class="metric-label">Entrada</div>
            <div class="metric-value entry">${entry}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Stop Loss</div>
            <div class="metric-value stop">${sl}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Take Profit</div>
            <div class="metric-value tp">${tp}</div>
          </div>
        </div>

        <div class="metrics">
          <div class="metric">
            <div class="metric-label">RSI</div>
            <div class="metric-value">${rsi}</div>
          </div>
          <div class="metric">
            <div class="metric-label">ATR</div>
            <div class="metric-value">${atr}</div>
          </div>
          <div class="metric">
            <div class="metric-label">Periodicidad</div>
            <div class="metric-value" style="font-size:11px;">Cada ${p.interval || 30} min</div>
          </div>
        </div>

        <div class="trends">
          <div class="trend-item">
            <span class="trend-key">Tendencia base</span>
            <span class="trend-val ${trendH1}">${trendH1}</span>
          </div>
          <div class="trend-item">
            <span class="trend-key">HTF (${htfLabel || p.htf})</span>
            <span class="trend-val ${trendHTF}">${trendHTF}</span>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function renderLog(log) {
  const container = document.getElementById('log-container');
  if (!log || !log.length) {
    container.innerHTML = '<div class="empty-log">Sin señales aún.</div>';
    return;
  }
  container.innerHTML = log.map(s => `
    <div class="log-item">
      <span class="log-dir ${s.direction}">${s.direction}</span>
      <span class="log-sym">${(s.symbol || '').replace('=X','').replace('=','')}</span>
      <span class="log-entry">${s.entry_price}</span>
      <span>SL <span class="log-sl">${s.stop_loss}</span></span>
      <span>TP <span class="log-tp">${s.take_profit}</span></span>
      <span class="log-time">${fmtTime(s.timestamp)}</span>
    </div>
  `).join('');
}

// ── Gestión del valor del par (Select / Custom) ───────────────────────────────
function setSymbolValue(symbol) {
  const sel = document.getElementById('symbol');
  if (!sel) return;
  
  // Buscar si la opción ya existe
  let exists = false;
  for (let i = 0; i < sel.options.length; i++) {
    if (sel.options[i].value === symbol) {
      exists = true;
      break;
    }
  }
  
  // Si no existe, crear la opción en el optgroup de personalizados
  if (!exists && symbol && symbol !== '__custom__') {
    const customGroup = document.getElementById('custom-optgroup');
    if (customGroup) {
      const opt = document.createElement('option');
      opt.value = symbol;
      opt.textContent = symbol + ' (Personalizado)';
      customGroup.appendChild(opt);
    }
  }
  sel.value = symbol;
}

// ── Aplicar config al formulario ───────────────────────────────────────────────
function applyConfigToForm(cfg) {
  setSymbolValue(cfg.symbol ?? '');
  document.getElementById('ema_fast').value  = cfg.ema_fast  ?? 50;
  document.getElementById('ema_slow').value  = cfg.ema_slow  ?? 200;
  document.getElementById('rsi_len').value   = cfg.rsi_len   ?? 14;
  document.getElementById('atr_len').value   = cfg.atr_len   ?? 14;
  document.getElementById('stop_atr').value  = cfg.stop_atr  ?? 1.5;
  document.getElementById('tp_atr').value    = cfg.tp_atr    ?? 3.0;
  document.getElementById('interval').value  = cfg.interval  ?? 30;
  document.getElementById('enabled').checked = cfg.enabled   ?? true;
  document.getElementById('use_htf').checked = cfg.use_htf   ?? true;

  // selects
  ['timeframe', 'htf'].forEach(id => {
    const sel = document.getElementById(id);
    const val = cfg[id];
    if (val) [...sel.options].forEach(o => o.selected = o.value === val);
  });

  activeSymbol = cfg.symbol;
}

// ── API calls ──────────────────────────────────────────────────────────────────
async function fetchStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    document.getElementById('last-check').textContent = '↻ ' + fmtTime(new Date().toISOString());
    renderTelegramStatus(Boolean(d.telegram_ok));
    if (!initialConfigLoaded && d.config) {
      applyConfigToForm(d.config);
      initialConfigLoaded = true;
    }
    renderSignals(d.profiles || [], d.last_signals || {}, d.last_checks || {});
    renderLog(d.log);
    renderProfiles(d.profiles || []);
  } catch(e) {}
}

function collectConfig() {
  return {
    symbol:    document.getElementById('symbol').value.trim(),
    timeframe: document.getElementById('timeframe').value,
    ema_fast:  +document.getElementById('ema_fast').value,
    ema_slow:  +document.getElementById('ema_slow').value,
    rsi_len:   +document.getElementById('rsi_len').value,
    atr_len:   +document.getElementById('atr_len').value,
    stop_atr:  +document.getElementById('stop_atr').value,
    tp_atr:    +document.getElementById('tp_atr').value,
    use_htf:   document.getElementById('use_htf').checked,
    htf:       document.getElementById('htf').value,
    interval:  +document.getElementById('interval').value,
    enabled:   document.getElementById('enabled').checked,
  };
}

async function saveConfig({ silent = false } = {}) {
  const cfg = collectConfig();
  if (!cfg.symbol) { toast('✗ Introduce un par válido', 'err'); return false; }
  try {
    const r = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(cfg)
    });
    const d = await r.json();
    if (d.profiles) renderProfiles(d.profiles);
    activeSymbol = cfg.symbol;
    if (!silent) toast(`✓ "${cfg.symbol}" guardado`, 'ok');
    return d.ok;
  } catch(e) {
    if (!silent) toast('✗ Error de red', 'err');
    return false;
  }
}

async function loadProfile(symbol) {
  try {
    const r = await fetch('/api/profile/load', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol })
    });
    const d = await r.json();
    if (d.ok) {
      applyConfigToForm(d.config);
      if (d.profiles) renderProfiles(d.profiles);
      toast(`✓ Par cargado: ${symbol}`, 'ok');
    }
  } catch(e) { toast('✗ Error de red', 'err'); }
}

async function deleteProfile(event, symbol) {
  event.stopPropagation();
  if (!confirm(`¿Eliminar el perfil de ${symbol}?`)) return;
  try {
    const r = await fetch('/api/profile/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbol })
    });
    const d = await r.json();
    if (d.profiles) renderProfiles(d.profiles);
    if (d.config)   applyConfigToForm(d.config);
    toast(`✓ Perfil eliminado: ${symbol}`, 'ok');
  } catch(e) { toast('✗ Error de red', 'err'); }
}

async function scanNow() {
  toast('Guardando y escaneando…');
  const saved = await saveConfig({ silent: true });
  if (!saved) { toast('✗ No se pudo guardar la config', 'err'); return; }
  try {
    const r = await fetch('/api/scan_now', { method: 'POST' });
    const d = await r.json();
    await fetchStatus();
    toast('✓ Escaneo completado', 'ok');
  } catch(e) { toast('✗ Error de red', 'err'); }
}

async function testTelegram() {
  toast('Enviando prueba…');
  try {
    const r = await fetch('/api/test_telegram', { method: 'POST' });
    const d = await r.json();
    toast(d.ok ? '✓ Mensaje enviado a Telegram' : '✗ Revisa el .env', d.ok ? 'ok' : 'err');
  } catch(e) { toast('✗ Error de red', 'err'); }
}

function switchTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  document.querySelectorAll('.tab-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `tab-${tabName}`);
  });
}

// Arranque
setSymbolValue(activeSymbol);

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

switchTab('config');

document.getElementById('symbol').addEventListener('change', function(e) {
  if (this.value === '__custom__') {
    const customSymbol = prompt('Introduce el ticker de Yahoo Finance (ej. USDMXN=X, GBPJPY=X, BTC-USD):');
    if (customSymbol && customSymbol.trim()) {
      const cleanSymbol = customSymbol.trim().toUpperCase();
      setSymbolValue(cleanSymbol);
      activeSymbol = cleanSymbol;
    } else {
      // Si cancela, revertimos al par activo anterior
      this.value = activeSymbol;
    }
  } else {
    activeSymbol = this.value;
  }
});

fetchStatus();
setInterval(fetchStatus, 30000);
