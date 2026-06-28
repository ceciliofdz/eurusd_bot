# Contributing to Forex Swing Bot

Gracias por tu interés en contribuir al proyecto.

## Cómo contribuir

1. Haz un fork del repositorio.
2. Crea una rama nueva para tu cambio:

```bash
git checkout -b feature/nombre-de-tu-mejora
```

3. Realiza tus cambios y prueba que todo funcione.
4. Envía un pull request describiendo los cambios y por qué son útiles.

## Buenas prácticas

- Abre un issue antes de trabajar en cambios grandes.
- Mantén los commits claros y enfocados.
- Usa `python -m venv .venv` y `pip install -r requirements.txt` para reproducir el entorno.
- No subas credenciales ni archivos generados como `signals.log` o `.env`.

## Reportar bugs

Incluye siempre:

- Descripción del problema
- Pasos para reproducirlo
- Comportamiento esperado
- Comportamiento real
- Configuración usada (`symbol`, `timeframe`, `enabled`, etc.)

## Sugerencias de mejora

- Añadir soporte para más activos y timeframes.
- Integración con otras APIs de datos.
- Backtesting y simulación.
- Mejora de la interfaz de usuario.
- Añadir tests automatizados.
