# 🛒 CazaOfertas Perú
Ofertas y errores de precio, directo a tu Telegram.

Vigila **Falabella, Ripley, Oechsle (oh!), Hiraoka, Plaza Vea y Promart** en **artefactos, celulares, zapatillas, ropa y juguetes** y avisa por **Telegram** con un botón **🛒 Comprar ahora** cuando un precio cae fuerte o parece un error de precio.

## Cómo funciona en GitHub
- El flujo **Actions → CazaOfertas** corre solo cada 30 minutos.
- El historial de precios se guarda entre ejecuciones (caché de Actions).
- El token del bot va en **Settings → Secrets and variables → Actions**: `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`. Nunca en el código.

## Cómo decide
- **Con historial** (3 o más lecturas): alerta si el precio cae 40% o más bajo la mediana de 30 días.
- **Sin historial:** usa el precio "antes" de la tienda, pero exige 60% o más.
- **70% o más** se marca como 🚨 **POSIBLE ERROR DE PRECIO**.
- Ignora accesorios y productos baratos (`CATEGORIES` y `EXCLUDE_WORDS` en `config.py`).

## En tu PC
```
python cazaofertas.py               revisa cada 10 minutos
python cazaofertas.py --once        una sola pasada
python cazaofertas.py --diagnostico prueba cada tienda
```

## Importante
- No compra solo: la alerta te lleva al enlace y tú confirmas.
- Las tiendas pueden cancelar pedidos con error de precio.

---
**Elaborado por: HuachOfertas** · © 2026 · Hecho en Huacho, Perú
