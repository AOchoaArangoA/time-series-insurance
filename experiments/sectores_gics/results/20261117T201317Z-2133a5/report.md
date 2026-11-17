# Experimento sectores-gics-rotacion-regimenes

**Hipótesis (pre-registrada)**: H1 (rotación): invertir cada mes en los k sectores SPDR con mayor momentum de 6 o 12 meses
supera a los 9 sectores igual ponderados (mismos costos, rebalanceo mensual) después de
ajustar por todas las pruebas, incluidas las 4 del análisis exploratorio previo.
H2 (ciclo): el exceso de retorno del mes siguiente de los sectores difiere según la curva
invertida, el nivel del VIX o la tendencia del S&P 500.
Expectativa previa: sin evidencia; el periodo 2015-2026 ya se miró, así que es exploratorio.


- Ejecución `20261117T201317Z-2133a5` · experimento sha256 2133a5ed3360… · paquete `sectores_gics` (sha256 e60a270bf66b…) · tsinsurance 0.2.0 · semilla 17
- Supuestos: retraso=1 barra(s), costo=3.0 pb, deslizamiento=2.0 pb, rebalanceo=every_bar, bruto máx.=1.0, cortos=no, financiación=rf+0.0 pb
- Selección y pruebas múltiples sobre datos hasta 2014-12-31; validación única desde 2014-12-31
- Pruebas previas en la bitácora por activo: {'XLB': 8, 'XLE': 8, 'XLF': 8, 'XLI': 8, 'XLK': 8, 'XLP': 8, 'XLU': 8, 'XLV': 8, 'XLY': 8}

## Conclusión automática

- Estado: calibración terminada; validación fuera de muestra PENDIENTE (aún no hay evidencia confirmatoria)
- Ideas con timing significativo (DSR > 1−α y SPA-Holm < α): ninguna
- Modelos econométricos: n/d
- La ganancia CER no tiene inferencia propia; en activos apalancados refleja sobre todo la penalización de varianza, no habilidad.

## Cartera `rotacion_momentum` (cross_sectional_momentum sobre 9 activos)

- Benchmark: igual ponderado de los elegibles (≥ 13 meses), mismos costos, rebalanceo mensual · ventana desde 2000-04-04
- Mejor configuración: idea=rotacion_momentum, lookback_m=6, top_k=4 · Sharpe 0.35 · IR frente al igual ponderado -0.00 · pruebas N=8 (incluye universos parecidos) · DSR 0.286 · SPA p 0.682 · significativa: no

## Régimen `curva_invertida` (spread, clave spread:^TNX-^IRX)

- Justificación: Umbral natural 0: la inversión de la curva anticipa recesiones (Estrella y Mishkin 1998) · variantes previas en el Holm de la familia: 54 · α de la familia de regímenes = 0.010

| Activo | Variante | Meses en / fuera | Exceso anual en / fuera | Dif. | t (HC3) | p | p Holm |
|---|---|---|---|---|---|---|---|
| XLB | {'op': '<', 'value': 0.0} | 14 / 177 | no concluyente | | | | |
| XLE | {'op': '<', 'value': 0.0} | 14 / 177 | no concluyente | | | | |
| XLF | {'op': '<', 'value': 0.0} | 14 / 177 | no concluyente | | | | |
| XLI | {'op': '<', 'value': 0.0} | 14 / 177 | no concluyente | | | | |
| XLK | {'op': '<', 'value': 0.0} | 14 / 177 | no concluyente | | | | |
| XLP | {'op': '<', 'value': 0.0} | 14 / 177 | no concluyente | | | | |
| XLU | {'op': '<', 'value': 0.0} | 14 / 177 | no concluyente | | | | |
| XLV | {'op': '<', 'value': 0.0} | 14 / 177 | no concluyente | | | | |
| XLY | {'op': '<', 'value': 0.0} | 14 / 177 | no concluyente | | | | |

- Seleccionadas para la validación: 0

## Régimen `vix_alto` (threshold, clave threshold:^VIX)

- Justificación: Niveles convencionales de estrés del VIX; se declara la malla completa (el 25 se usó antes en el análisis exploratorio) · variantes previas en el Holm de la familia: 54 · α de la familia de regímenes = 0.010

| Activo | Variante | Meses en / fuera | Exceso anual en / fuera | Dif. | t (HC3) | p | p Holm |
|---|---|---|---|---|---|---|---|
| XLB | {'op': '>', 'value': 20.0} | 94 / 97 | +11.6% / +4.5% | +7.1% | +0.63 | 0.529 | 1.000 |
| XLB | {'op': '>', 'value': 25.0} | 48 / 143 | +1.0% / +10.4% | -9.4% | -0.56 | 0.578 | 1.000 |
| XLB | {'op': '>', 'value': 30.0} | 21 / 170 | no concluyente | | | | |
| XLE | {'op': '>', 'value': 20.0} | 94 / 97 | +9.6% / +10.7% | -1.1% | -0.10 | 0.920 | 1.000 |
| XLE | {'op': '>', 'value': 25.0} | 48 / 143 | +7.2% / +11.1% | -3.9% | -0.26 | 0.793 | 1.000 |
| XLE | {'op': '>', 'value': 30.0} | 21 / 170 | no concluyente | | | | |
| XLF | {'op': '>', 'value': 20.0} | 94 / 97 | +1.1% / +4.4% | -3.2% | -0.28 | 0.776 | 1.000 |
| XLF | {'op': '>', 'value': 25.0} | 48 / 143 | -0.5% / +3.9% | -4.4% | -0.24 | 0.812 | 1.000 |
| XLF | {'op': '>', 'value': 30.0} | 21 / 170 | no concluyente | | | | |
| XLI | {'op': '>', 'value': 20.0} | 94 / 97 | +7.8% / +6.0% | +1.8% | +0.19 | 0.850 | 1.000 |
| XLI | {'op': '>', 'value': 25.0} | 48 / 143 | +0.0% / +9.2% | -9.1% | -0.62 | 0.537 | 1.000 |
| XLI | {'op': '>', 'value': 30.0} | 21 / 170 | no concluyente | | | | |
| XLK | {'op': '>', 'value': 20.0} | 94 / 97 | +5.6% / -0.1% | +5.7% | +0.45 | 0.651 | 1.000 |
| XLK | {'op': '>', 'value': 25.0} | 48 / 143 | +7.7% / +1.0% | +6.7% | +0.35 | 0.725 | 1.000 |
| XLK | {'op': '>', 'value': 30.0} | 21 / 170 | no concluyente | | | | |
| XLP | {'op': '>', 'value': 20.0} | 94 / 97 | +2.6% / +6.6% | -3.9% | -0.62 | 0.532 | 1.000 |
| XLP | {'op': '>', 'value': 25.0} | 48 / 143 | -0.7% / +6.4% | -7.2% | -0.79 | 0.427 | 1.000 |
| XLP | {'op': '>', 'value': 30.0} | 21 / 170 | no concluyente | | | | |
| XLU | {'op': '>', 'value': 20.0} | 94 / 97 | -0.8% / +12.2% | -13.0% | -1.69 | 0.091 | 1.000 |
| XLU | {'op': '>', 'value': 25.0} | 48 / 143 | -6.7% / +10.0% | -16.6% | -1.58 | 0.114 | 1.000 |
| XLU | {'op': '>', 'value': 30.0} | 21 / 170 | no concluyente | | | | |
| XLV | {'op': '>', 'value': 20.0} | 94 / 97 | +6.5% / +5.7% | +0.8% | +0.11 | 0.913 | 1.000 |
| XLV | {'op': '>', 'value': 25.0} | 48 / 143 | +1.1% / +7.8% | -6.7% | -0.64 | 0.523 | 1.000 |
| XLV | {'op': '>', 'value': 30.0} | 21 / 170 | no concluyente | | | | |
| XLY | {'op': '>', 'value': 20.0} | 94 / 97 | +8.8% / +5.2% | +3.6% | +0.37 | 0.709 | 1.000 |
| XLY | {'op': '>', 'value': 25.0} | 48 / 143 | +7.9% / +6.7% | +1.2% | +0.08 | 0.937 | 1.000 |
| XLY | {'op': '>', 'value': 30.0} | 21 / 170 | no concluyente | | | | |

- Seleccionadas para la validación: 0

## Régimen `mercado_bajista` (trend, clave trend:SPY)

- Justificación: Media móvil de 10 meses (Faber 2007) · variantes previas en el Holm de la familia: 54 · α de la familia de regímenes = 0.010

| Activo | Variante | Meses en / fuera | Exceso anual en / fuera | Dif. | t (HC3) | p | p Holm |
|---|---|---|---|---|---|---|---|
| XLB | {'months': 10} | 56 / 126 | +4.1% / +8.9% | -4.7% | -0.32 | 0.748 | 1.000 |
| XLE | {'months': 10} | 56 / 126 | -8.3% / +17.0% | -25.3% | -1.81 | 0.071 | 1.000 |
| XLF | {'months': 10} | 56 / 126 | -13.6% / +9.6% | -23.2% | -1.47 | 0.143 | 1.000 |
| XLI | {'months': 10} | 56 / 126 | -7.5% / +12.5% | -20.0% | -1.49 | 0.135 | 1.000 |
| XLK | {'months': 10} | 56 / 126 | -16.4% / +10.4% | -26.8% | -1.50 | 0.134 | 1.000 |
| XLP | {'months': 10} | 56 / 126 | -5.7% / +10.5% | -16.2% | -2.11 | 0.035 | 1.000 |
| XLU | {'months': 10} | 56 / 126 | -11.4% / +13.7% | -25.1% | -2.64 | 0.008 | 0.675 |
| XLV | {'months': 10} | 56 / 126 | -2.9% / +10.5% | -13.4% | -1.40 | 0.162 | 1.000 |
| XLY | {'months': 10} | 56 / 126 | +2.9% / +9.2% | -6.3% | -0.48 | 0.629 | 1.000 |

- Seleccionadas para la validación: 0

## Próximo paso: validación única

Las configuraciones quedaron fijadas en la bitácora. Para evaluarlas UNA vez en el periodo posterior a 2014-12-31, confirme los cambios en git y ejecute:

```bash
tsinsurance experiment validate /home/user/time-series-insurance/experiments/sectores_gics/rotacion_regimenes.toml --calibration 20261117T201317Z-2133a5
```

