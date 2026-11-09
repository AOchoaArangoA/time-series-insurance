# Experimento registrado: ETFs inversos del Tesoro (TBT, TBX, TBF)

Muestra completa de la funcionalidad: receta → paquete de insumos → experimento
declarativo → ejecución con salvaguardas → bitácora → resultados.

| Archivo | Qué es |
|---------|--------|
| `recipe.toml` | receta de datos (Yahoo + FRED); única parte que depende de la fuente |
| `data/` | paquete de insumos generado (no versionado: datos de Yahoo no redistribuibles) |
| `experiment.toml` | hipótesis, activos, ideas, supuestos, validación y modelos econométricos |
| `results/20261109T155602Z-25596d/result.json` | resultado legible por máquina (para agentes) |
| `results/20261109T155602Z-25596d/report.md` | reporte para humanos |
| `../registry.jsonl` | bitácora permanente encadenada por hash (pre-registro, 42 pruebas de señales, 2 econométricas, 3 validaciones) |

Ejecución registrada **confirmatoria**: código versionado (commit `eb02287`, árbol limpio),
paquete sellado (sha256 `953f4f2a6264…`), bitácora canónica íntegra, hipótesis
pre-registrada antes de ejecutar.

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

## Hipótesis (pre-registrada)

Los ETFs inversos del Tesoro pierden valor en el tiempo, así que superarlos frente a
comprar y mantener es trivial (basta estar menos invertido). La hipótesis evaluada es de
**habilidad de timing**: las reglas de tendencia/momentum y un modelo macro superan a
mantener la **misma exposición media constante**, neto de costos y tras el ajuste por
pruebas múltiples.

## Datos y supuestos

- Precios ajustados de Yahoo: TBT (desde 2008-05), TBF (2009-08), TBX (2011-04); TLT sólo
  como referencia descriptiva (no se prueba).
- FRED: DTB3 (tasa libre de riesgo), T10Y2Y, DGS10, T10YIE (rezago 1 día hábil) y
  CPIAUCNS (variación anual, rezago 20 días). Sin BAA10Y (derechos de Moody's).
- Decisión al cierre, ejecución al cierre siguiente; costo 5 pb + deslizamiento 2 pb; sin
  cortos; retornos en exceso de la tasa libre de riesgo. Modelos macro con rebalanceo
  mensual.
- **Selección y ajuste por pruebas múltiples sólo con 2008-2018**; validación única
  2019-2025 para todas las ideas (registrada en la bitácora).
- Calidad de datos: el paquete marca picos con reversión en TBX (2025-05-23) y TLT
  (2020-03-16, crisis COVID: dato real). No se modificaron.

## Comprar y mantener (2008-2025)

| ETF | Retorno anual | Volatilidad | Máxima caída |
|-----|---------------|-------------|--------------|
| TBT (−2x 20+ años) | −10,4 % | 30,1 % | −95,0 % |
| TBF (−1x 20+ años) | −3,3 % | 14,8 % | −70,4 % |
| TBX (−1x 7-10 años) | −1,4 % | 7,2 % | −41,0 % |
| TLT (referencia) | +2,6 % | 15,4 % | −48,4 % |

## Resultados (calibración 2008-2018)

Ratio vs C&M = retorno activo frente a comprar y mantener (descriptivo, **confundido** por
el decaimiento); ratio de timing = frente a la misma exposición media constante (la
prueba). Pruebas = todas las del activo, incluidos los modelos macro. Significativo exige
DSR > 0,95 y SPA-Holm < 0,05.

| Idea | Activo | Mejor configuración | Sharpe propio | Ratio vs C&M | Exposición media | Ratio de timing | Pruebas | DSR | SPA p | ¿Signif.? |
|------|--------|---------------------|---------------|--------------|------------------|-----------------|---------|-----|-------|-----------|
| Tendencia | TBT | 100/200 | −0,34 | +0,36 | 35 % | −0,01 | 14 | 0,22 | 0,87 | no |
| Tendencia | TBX | 20/200 | −0,14 | +0,49 | 34 % | +0,19 | 15 | 0,25 | 0,78 | no |
| Tendencia | TBF | 20/150 | −0,22 | +0,50 | 34 % | +0,15 | 15 | 0,35 | 0,66 | no |
| Momentum | TBT | 252, salto 21 | −0,37 | +0,44 | 31 % | +0,02 | 14 | 0,25 | 0,87 | no |
| Momentum | TBX | 126, salto 0 | −0,16 | +0,52 | 34 % | +0,17 | 15 | 0,24 | 0,78 | no |
| Momentum | TBF | 63, salto 0 | −0,31 | +0,36 | 34 % | −0,03 | 15 | 0,19 | 0,66 | no |
| Momentum + vol. | TBT | 252/21, 12 % | −0,40 | +0,50 | 18 % | +0,01 | 14 | 0,24 | 0,87 | no |
| Momentum + vol. | TBX | 252/21, 8 % | −0,72 | +0,16 | 38 % | −0,41 | 15 | 0,01 | 0,78 | no |
| Momentum + vol. | TBF | 252/21, 12 % | −0,52 | +0,29 | 30 % | −0,18 | 15 | 0,09 | 0,66 | no |

**Validación única 2019-2025** (configuración elegida en calibración; Sharpe en exceso de
rf; diferencia frente a la misma exposición constante con su valor p):

| Idea | TBT | TBX | TBF |
|------|-----|-----|-----|
| Tendencia | +0,10 (dif. −0,04, p 0,55) | +0,13 (+0,19, p 0,17) | +0,22 (+0,11, p 0,31) |
| Momentum | +0,18 (+0,04, p 0,39) | −0,09 (−0,03, p 0,59) | −0,02 (−0,13, p 0,66) |
| Momentum + vol. | +0,12 (−0,02, p 0,48) | −0,02 (+0,04, p 0,40) | +0,05 (−0,06, p 0,56) |

Todos los intervalos de confianza al 95 % del Sharpe fuera de muestra incluyen 0.

**Modelos macro** (pendiente, cambio de la tasa a 10 años, inflación implícita, inflación
del IPC; regla largo/efectivo; la regla con la media histórica es siempre efectivo porque
la media de los inversos es negativa):

| Modelo | Pronósticos | R² fuera de muestra | Clark-West p | Pesaran-Timmermann p | Sharpe modelo vs efectivo | Ratio de timing | Veredicto |
|--------|-------------|---------------------|--------------|----------------------|---------------------------|-----------------|-----------|
| TBF | 135 | −9,7 % | 0,25 | 0,86 | −0,19 vs 0,00 (p 0,75) | −0,26 | sin evidencia, diagnósticos no superados |
| TBX | 115 | −8,0 % | 0,34 | 0,72 | −0,25 vs 0,00 (p 0,77) | −0,32 | sin evidencia, diagnósticos no superados |

## Conclusión

- **No hay evidencia de habilidad de timing** en ningún ETF inverso ni con ninguna idea
  (ninguna configuración significativa; DSR máximo 0,35).
- La aparente mejora frente a comprar y mantener (ratio +0,16 a +0,52) se explica por
  **estar invertido sólo ~1/3 del tiempo** en activos que decaen: mantener esa exposición
  constante da lo mismo o más. Con el benchmark ingenuo el experimento habría concluido lo
  contrario; por eso la nula se definió frente a la exposición media.
- Incluso con timing, el Sharpe propio en calibración fue negativo: los inversos sólo
  tienen sentido como cobertura táctica de corto plazo, no como inversión.
- Los modelos macro no anticipan los ciclos de tasas (peor que la media histórica).

## Limitaciones

Universo elegido ex post; precios de Yahoo ajustados retroactivamente; sin costo de
préstamo ni impuestos; el benchmark de timing usa la exposición media realizada (no una
beta estimada); sin vintages de FRED (series de mercado y CPIAUCNS casi no se revisan).
