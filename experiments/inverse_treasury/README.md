# Experimento registrado: ETFs inversos del Tesoro (TBT, TBX, TBF)

Muestra completa de la funcionalidad: receta → paquete de insumos → experimento
declarativo → ejecución con salvaguardas → bitácora → resultados.

| Archivo | Qué es |
|---------|--------|
| `recipe.toml` | receta de datos (Yahoo + FRED); única parte que depende de la fuente |
| `data/` | paquete de insumos generado (no versionado: datos de Yahoo no redistribuibles) |
| `experiment.toml` | hipótesis, activos, ideas, supuestos, validación y modelos econométricos |
| `results/20261109T153204Z-fcab6b/result.json` | resultado legible por máquina (para agentes) |
| `results/20261109T153204Z-fcab6b/report.md` | reporte para humanos |
| `../registry.jsonl` | bitácora permanente (58 pruebas de esta ejecución) |

Reproducir:

```bash
cd experiments/inverse_treasury
export FRED_API_KEY=...                       # sólo para descargar
uv run tsinsurance bundle fetch recipe.toml data
uv run tsinsurance experiment run experiment.toml
```

> **TFT**: no existe en Yahoo Finance. Junto con TBX y TBF forma la familia de ETFs
> inversos del Tesoro de ProShares cuyo tercer miembro es **TBT** (UltraShort 20+ años,
> −2x diario); se usó TBT. TLT (subyacente de TBT/TBF) se incluye como referencia.

## Hipótesis

Los ETFs inversos del Tesoro pierden valor en el tiempo (tendencia de tasas, costo de
financiamiento y rebalanceo diario). Una regla de tendencia o momentum que sólo los
mantenga en ciclos alcistas de tasas, o un modelo macro que anticipe esos ciclos, debería
superar a comprar y mantener ajustado por riesgo.

## Datos y supuestos

- Precios ajustados de Yahoo: TBT (desde 2008-05), TBF (2009-08), TBX (2011-04), TLT.
- FRED: DTB3 (tasa libre de riesgo), T10Y2Y, DGS10, T10YIE (rezago 1 día hábil) y
  CPIAUCNS (variación anual, rezago 20 días). Sin BAA10Y (derechos de Moody's).
- Ventana 2008-2025; decisión al cierre, ejecución al cierre siguiente; costo 5 pb +
  deslizamiento 2 pb; sin cortos; retornos en exceso de la tasa libre de riesgo.
- Calibración 2008-2018, validación única 2019-2025.

## Comprar y mantener (2008-2025)

| ETF | Retorno anual | Volatilidad | Máxima caída |
|-----|---------------|-------------|--------------|
| TBT (−2x 20+ años) | −10,4 % | 30,1 % | −95,0 % |
| TBF (−1x 20+ años) | −3,3 % | 14,8 % | −70,4 % |
| TBX (−1x 7-10 años) | −1,4 % | 7,2 % | −41,0 % |
| TLT (referencia) | +2,6 % | 15,4 % | −48,4 % |

## Resultados

**Prueba de anticipación**: superada por todas las ideas en los 4 activos.

**Mejor configuración por idea y activo** (ratio de información = retorno activo frente a
comprar y mantener; DSR deflactado con todas las pruebas del activo; significativo exige
DSR > 0,95 y SPA p < 0,05):

| Idea | Activo | Mejor configuración | Sharpe | Ratio de inf. | Pruebas | DSR | SPA p | ¿Significativo? |
|------|--------|---------------------|--------|---------------|---------|-----|-------|-----------------|
| Tendencia | TBT | 20/150 | −0,02 | +0,26 | 6 | 0,76 | 0,25 | no |
| Tendencia | TBX | 20/200 | +0,04 | +0,42 | 6 | 0,88 | 0,11 | no |
| Tendencia | TBF | 20/150 | +0,04 | +0,33 | 6 | 0,86 | 0,14 | no |
| Tendencia | TLT | 50/150 | +0,23 | +0,04 | 6 | 0,48 | 0,62 | no |
| Momentum | TBT | 63, salto 21 | −0,02 | +0,31 | 12 | 0,79 | 0,27 | no |
| Momentum | TBX | 126, salto 0 | −0,11 | +0,25 | 12 | 0,57 | 0,12 | no |
| Momentum | TBF | 63, salto 21 | −0,07 | +0,19 | 12 | 0,57 | 0,31 | no |
| Momentum + vol. | TBT | 252/21, 8 % | −0,14 | +0,24 | 14 | 0,70 | 0,28 | no |

**Calibración 2008-2018 → validación 2019-2025 (tendencia)**: fuera de muestra la regla
elegida tuvo Sharpe 0,27 / 0,13 / 0,22 en TBT / TBX / TBF frente a 0,14 / −0,06 / 0,11 de
comprar y mantener; ninguna diferencia es significativa (p = 0,34 / 0,17 / 0,33).
Momentum no mejoró fuera de muestra.

**Modelos macro** (pendiente, cambio de la tasa a 10 años, inflación implícita, inflación
del IPC; regla largo/efectivo):

| Modelo | Pronósticos | R² fuera de muestra | Clark-West p | Pesaran-Timmermann p | Sharpe modelo vs regla con media histórica | Veredicto |
|--------|-------------|---------------------|--------------|----------------------|--------------------------------------------|-----------|
| TBF | 135 | −9,7 % | 0,25 | 0,86 | −0,19 vs 0,00 (p = 0,74) | sin evidencia, diagnósticos no superados |
| TBX | 115 | −8,0 % | 0,34 | 0,72 | −0,25 vs 0,00 (p = 0,76) | sin evidencia, diagnósticos no superados |

(La media histórica de los inversos es negativa: la regla con la media histórica queda
siempre en efectivo, con Sharpe 0.)

## Conclusión

- Las reglas de tendencia **reducen las pérdidas** de mantener ETFs inversos (ratio de
  información positivo en los tres), pero la evidencia **no es significativa** tras el
  ajuste por pruebas múltiples, y en validación la mejora no es estadísticamente distinta
  de cero.
- Mantener ETFs inversos apalancados como inversión es costoso (TBT: −95 % de caída
  máxima); su uso es táctico.
- Los modelos macro no anticipan los ciclos: peor que la media histórica en error
  cuadrático y sin valor económico.

## Limitaciones

Universo elegido ex post (sesgo de supervivencia); precios de Yahoo ajustados
retroactivamente por dividendos; sin costo de préstamo ni impuestos; vintages de FRED no
usados (series de mercado y CPIAUCNS casi no se revisan).
