# Experimento inverse-treasury-etfs

**Hipótesis (pre-registrada)**: Los ETFs inversos del Tesoro pierden valor en el tiempo (tendencia de tasas, financiamiento y rebalanceo diario), de modo que superar a comprar y mantener es trivial (basta estar menos invertido). Hipótesis: las reglas de tendencia/momentum y un modelo macro tienen habilidad de TIMING, es decir, superan a mantener la misma exposición media constante (retorno de timing > 0), neto de costos y tras el ajuste por pruebas múltiples.

- Ejecución `20261109T155602Z-25596d` · experimento sha256 25596dd66da7… · paquete `inverse_treasury` (sha256 953f4f2a6264…) · tsinsurance 0.0.1 · semilla 20261109
- Supuestos: retraso=1 barra(s), costo=5.0 pb, deslizamiento=2.0 pb, rebalanceo=every_bar, bruto máx.=1.0, cortos=no, financiación=rf+0.0 pb
- Selección y pruebas múltiples sobre datos hasta 2018-12-31; validación única desde 2018-12-31
- Pruebas previas en la bitácora por activo: {}
- Calidad de datos: TBX 2025-05-23: retorno +3.91% y -4.09% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
## Conclusión automática

- Estado: confirmatorio
- Ideas con timing significativo (DSR > 1−α y SPA-Holm < α): ninguna
- Modelos econométricos: macro_tbf → sin_evidencia, macro_tbx → sin_evidencia
- La ganancia CER no tiene inferencia propia; en activos apalancados refleja sobre todo la penalización de varianza, no habilidad.

- Calidad de datos: TLT 2020-03-16: retorno +6.48% y -6.67% al día siguiente (> 8 desviaciones robustas): posible dato erróneo

## Modelo econométrico `macro_tbf` (TBF)

Especificaciones contadas sobre TBF: 1 · benchmark: efectivo (la media histórica es negativa) · anticipación del flujo: Sin anticipación detectada en 15 cortes evaluados (0 omitidos por datos insuficientes).

```text
----------------------------------------------------------------------------------------
Veredicto: sin evidencia [DIAGNÓSTICOS NO SUPERADOS]
  Evidencia estadística (Pesaran-Timmermann, α=0.05): no
  Valor económico (Sharpe neto vs regla con media histórica, α=0.05): no
  Ni evidencia estadística ni valor económico frente al benchmark.
  Regla: estadística = Pesaran-Timmermann rechaza H0 al nivel α; económica = prueba unilateral de diferencia de Sharpe (bootstrap estacionario) neto de costos y en exceso de rf frente a la misma regla aplicada a la media histórica rechaza al nivel α; no concluyente si hay menos de 60 pronósticos fuera de muestra; exploratorio si se probó más de una especificación o hay variables no punto-en-el-tiempo.
----------------------------------------------------------------------------------------
(a) VALIDACIÓN ESTADÍSTICA
Walk-forward expanding: 136 pronósticos (2014-09-30 a 2025-12-31), 136 re-estimaciones, min_train=60, refit_every=1
Evaluación fuera de muestra (135 pronósticos): R²_OS=-9.73%  aciertos de signo=45.2%
  Clark-West             estad.=   0.669  p=0.2516
  Pesaran-Timmermann     estad.=  -1.093  p=0.8628
  Diebold-Mariano (HLN)  estad.=  -1.392  p=0.1662
    Nota: No válida para modelos anidados (subdimensionada); la prueba principal es Clark-West.
Validación del modelo (muestra completa, n=195, descriptiva ex post): R²=0.041  R² ajustado=0.021  HAC rezagos=4
            coef  se_hac       t       p
const    -0.0093  0.0175 -0.5346  0.5929
T10Y2Y   -0.0075  0.0033 -2.2800  0.0226
d_DGS10   0.0160  0.0143  1.1146  0.2650
T10YIE    0.0081  0.0094  0.8619  0.3888
CPIAUCNS -0.1115  0.2280 -0.4888  0.6250
Estacionariedad de regresores: T10Y2Y=I(1), d_DGS10=I(0), T10YIE=I(0), CPIAUCNS=I(1)
Persistencia (ρ AR(1), δ = corr. de innovaciones, sesgo de Stambaugh aprox.):
             rho   delta  sesgo_stambaugh
regresor                                 
T10Y2Y    0.9822  0.5666          -0.0028
d_DGS10   0.0534  0.8949          -0.0009
T10YIE    0.9050  0.5431          -0.0028
CPIAUCNS  0.9673  0.0666          -0.0128
Diagnósticos de residuos:
  Ljung-Box        estad.=   4.4240  p=0.9262
  ARCH-LM          estad.=  11.7206  p=0.0388
  Jarque-Bera      estad.=   3.0559  p=0.2170
  CUSUM (OLS)      estad.=   0.4882  p=0.9710
Diagnósticos superados: no
Advertencia: 'T10Y2Y' es I(1): regresión desbalanceada (retorno I(0) sobre regresor no estacionario); inferencia HAC no válida.
Advertencia: 'T10Y2Y' es muy persistente (ρ=0.982, δ=0.57): sesgo de Stambaugh ≈ -0.0028 en su coeficiente y t-estadísticos HAC sobredimensionados (IVX pendiente).
Advertencia: 'CPIAUCNS' es I(1): regresión desbalanceada (retorno I(0) sobre regresor no estacionario); inferencia HAC no válida.
Advertencia: 'CPIAUCNS' es muy persistente (ρ=0.967, δ=0.07): sesgo de Stambaugh ≈ -0.0128 en su coeficiente y t-estadísticos HAC sobredimensionados (IVX pendiente).
Advertencia: Diagnósticos rechazados: ARCH-LM.
----------------------------------------------------------------------------------------
(b) BACKTEST ECONÓMICO (regla 'long_cash')
Backtest 'modelo' — 4117 periodos (2009-08-20 a 2025-12-31)
Supuestos: retraso=1 barra(s), costo=5.0 pb, deslizamiento=2.0 pb, rebalanceo=M, bruto máx.=1.0, cortos=no, financiación=rf+0.0 pb
Fin del calentamiento: 2014-10-02
Métricas sobre retornos en exceso de rf; benchmark = comprar y mantener
Estrategia : ret. anual=-2.78%  vol=11.27%  Sharpe=-0.19  Sortino=-0.27  máx. caída=-42.07%  Calmar=-0.07  aciertos=46.3%  rotación media=0.0117  n=2829
Benchmark  : ret. anual=-1.63%  vol=14.59%  Sharpe=-0.04  Sortino=-0.06  máx. caída=-47.97%  Calmar=-0.03  aciertos=47.5%  rotación media=0.0000  n=2829
Nota: Universo elegido ex post (activos vigentes hoy): posible sesgo de supervivencia y de selección.
Benchmark de la regla (media histórica): ret. anual=+0.00%  vol=0.00%  Sharpe=0.00  Sortino=nan  máx. caída=0.00%  Calmar=nan  aciertos=nan%  rotación media=0.0000  n=2829
Sharpe -0.194 vs 0.000 (dif. -0.194, p unilateral=0.746); ganancia CER(γ=3)=-4.09% anual
Nota: La decisión de fin de mes se ejecuta al cierre siguiente (retraso 1): el periodo mantenido está desplazado un día respecto del retorno pronosticado.
----------------------------------------------------------------------------------------
```

## Modelo econométrico `macro_tbx` (TBX)

Especificaciones contadas sobre TBX: 1 · benchmark: efectivo (la media histórica es negativa) · anticipación del flujo: Sin anticipación detectada en 15 cortes evaluados (0 omitidos por datos insuficientes).

```text
----------------------------------------------------------------------------------------
Veredicto: sin evidencia [DIAGNÓSTICOS NO SUPERADOS]
  Evidencia estadística (Pesaran-Timmermann, α=0.05): no
  Valor económico (Sharpe neto vs regla con media histórica, α=0.05): no
  Ni evidencia estadística ni valor económico frente al benchmark.
  Regla: estadística = Pesaran-Timmermann rechaza H0 al nivel α; económica = prueba unilateral de diferencia de Sharpe (bootstrap estacionario) neto de costos y en exceso de rf frente a la misma regla aplicada a la media histórica rechaza al nivel α; no concluyente si hay menos de 60 pronósticos fuera de muestra; exploratorio si se probó más de una especificación o hay variables no punto-en-el-tiempo.
----------------------------------------------------------------------------------------
(a) VALIDACIÓN ESTADÍSTICA
Walk-forward expanding: 116 pronósticos (2016-05-31 a 2025-12-31), 116 re-estimaciones, min_train=60, refit_every=1
Evaluación fuera de muestra (115 pronósticos): R²_OS=-8.04%  aciertos de signo=47.0%
  Clark-West             estad.=   0.417  p=0.3382
  Pesaran-Timmermann     estad.=  -0.593  p=0.7235
  Diebold-Mariano (HLN)  estad.=  -1.156  p=0.2501
    Nota: No válida para modelos anidados (subdimensionada); la prueba principal es Clark-West.
Validación del modelo (muestra completa, n=175, descriptiva ex post): R²=0.030  R² ajustado=0.007  HAC rezagos=4
            coef  se_hac       t       p
const    -0.0050  0.0087 -0.5752  0.5652
T10Y2Y   -0.0030  0.0018 -1.6174  0.1058
d_DGS10   0.0025  0.0065  0.3877  0.6982
T10YIE    0.0023  0.0046  0.5022  0.6156
CPIAUCNS  0.0269  0.1038  0.2589  0.7957
Estacionariedad de regresores: T10Y2Y=I(1), d_DGS10=I(0), T10YIE=inconclusive, CPIAUCNS=I(1)
Persistencia (ρ AR(1), δ = corr. de innovaciones, sesgo de Stambaugh aprox.):
             rho   delta  sesgo_stambaugh
regresor                                 
T10Y2Y    0.9712  0.4175          -0.0011
d_DGS10   0.0740  0.9394          -0.0005
T10YIE    0.9216  0.4631          -0.0014
CPIAUCNS  0.9825  0.0638          -0.0072
Diagnósticos de residuos:
  Ljung-Box        estad.=   6.8520  p=0.7393
  ARCH-LM          estad.=  12.0083  p=0.0347
  Jarque-Bera      estad.=   0.3211  p=0.8517
  CUSUM (OLS)      estad.=   0.4652  p=0.9820
Diagnósticos superados: no
Advertencia: 'T10Y2Y' es I(1): regresión desbalanceada (retorno I(0) sobre regresor no estacionario); inferencia HAC no válida.
Advertencia: 'T10Y2Y' es muy persistente (ρ=0.971, δ=0.42): sesgo de Stambaugh ≈ -0.0011 en su coeficiente y t-estadísticos HAC sobredimensionados (IVX pendiente).
Advertencia: 'CPIAUCNS' es I(1): regresión desbalanceada (retorno I(0) sobre regresor no estacionario); inferencia HAC no válida.
Advertencia: 'CPIAUCNS' es muy persistente (ρ=0.982, δ=0.06): sesgo de Stambaugh ≈ -0.0072 en su coeficiente y t-estadísticos HAC sobredimensionados (IVX pendiente).
Advertencia: Diagnósticos rechazados: ARCH-LM.
----------------------------------------------------------------------------------------
(b) BACKTEST ECONÓMICO (regla 'long_cash')
Backtest 'modelo' — 3708 periodos (2011-04-05 a 2025-12-31)
Supuestos: retraso=1 barra(s), costo=5.0 pb, deslizamiento=2.0 pb, rebalanceo=M, bruto máx.=1.0, cortos=no, financiación=rf+0.0 pb
Fin del calentamiento: 2016-06-02
Métricas sobre retornos en exceso de rf; benchmark = comprar y mantener
Estrategia : ret. anual=-1.52%  vol=5.48%  Sharpe=-0.25  Sortino=-0.35  máx. caída=-17.98%  Calmar=-0.08  aciertos=47.9%  rotación media=0.0066  n=2410
Benchmark  : ret. anual=-0.69%  vol=7.22%  Sharpe=-0.06  Sortino=-0.08  máx. caída=-22.41%  Calmar=-0.03  aciertos=47.8%  rotación media=0.0000  n=2410
Nota: Universo elegido ex post (activos vigentes hoy): posible sesgo de supervivencia y de selección.
Benchmark de la regla (media histórica): ret. anual=+0.00%  vol=0.00%  Sharpe=0.00  Sortino=nan  máx. caída=0.00%  Calmar=nan  aciertos=nan%  rotación media=0.0000  n=2410
Sharpe -0.252 vs 0.000 (dif. -0.252, p unilateral=0.774); ganancia CER(γ=3)=-1.83% anual
Nota: La decisión de fin de mes se ejecuta al cierre siguiente (retraso 1): el periodo mantenido está desplazado un día respecto del retorno pronosticado.
----------------------------------------------------------------------------------------
```

## Idea `tendencia` (sma_crossover, malla {'fast': [20, 50, 100], 'slow': [150, 200]}) — selección hasta 2018-12-31

```text
                                     best  sharpe   psr  ir_vs_bh  exposure  timing_ir  n_trials   dsr  spa_p  spa_p_holm  significant
asset                                                                                                                                 
TBT    idea=tendencia, fast=100, slow=200  -0.341 0.144     0.364     0.351     -0.006        14 0.220  0.872       1.000        False
TBX     idea=tendencia, fast=20, slow=200  -0.141 0.356     0.493     0.343      0.188        15 0.250  0.784       1.000        False
TBF     idea=tendencia, fast=20, slow=150  -0.217 0.264     0.501     0.337      0.147        15 0.351  0.660       1.000        False
```

## Idea `momentum` (tsmom, malla {'lookback': [63, 126, 252], 'skip': [0, 21]}) — selección hasta 2018-12-31

```text
                                       best  sharpe   psr  ir_vs_bh  exposure  timing_ir  n_trials   dsr  spa_p  spa_p_holm  significant
asset                                                                                                                                   
TBT    idea=momentum, lookback=252, skip=21  -0.370 0.126     0.442     0.309      0.021        14 0.248  0.872       1.000        False
TBX     idea=momentum, lookback=126, skip=0  -0.164 0.336     0.516     0.344      0.170        15 0.239  0.784       1.000        False
TBF      idea=momentum, lookback=63, skip=0  -0.313 0.185     0.357     0.343     -0.031        15 0.186  0.660       1.000        False
```

## Idea `momentum_vol` (tsmom_vol_target, malla {'lookback': [252], 'skip': [21], 'target': [0.08, 0.12]}) — selección hasta 2018-12-31

```text
                                                        best  sharpe   psr  ir_vs_bh  exposure  timing_ir  n_trials   dsr  spa_p  spa_p_holm  significant
asset                                                                                                                                                    
TBT    idea=momentum_vol, lookback=252, skip=21, target=0.12  -0.402 0.107     0.500     0.181      0.008        14 0.235  0.872       1.000        False
TBX    idea=momentum_vol, lookback=252, skip=21, target=0.08  -0.720 0.031     0.158     0.379     -0.409        15 0.013  0.784       1.000        False
TBF    idea=momentum_vol, lookback=252, skip=21, target=0.12  -0.521 0.067     0.287     0.302     -0.184        15 0.091  0.660       1.000        False
```

## Validación única `tendencia` (desde 2018-12-31)

| Activo | Parámetros | Sharpe fuera de muestra | IC 95 % | p vs efectivo | Sharpe comprar y mantener | Dif. vs exposición constante (p) |
|---|---|---|---|---|---|---|
| TBT | {'fast': 100, 'slow': 200} | +0.10 | [-0.55; +0.81] | 0.394 | +0.14 | -0.04 (0.546) |
| TBX | {'fast': 20, 'slow': 200} | +0.13 | [-0.44; +0.76] | 0.362 | -0.06 | +0.19 (0.172) |
| TBF | {'fast': 20, 'slow': 150} | +0.22 | [-0.46; +0.89] | 0.277 | +0.11 | +0.11 (0.308) |

## Validación única `momentum` (desde 2018-12-31)

| Activo | Parámetros | Sharpe fuera de muestra | IC 95 % | p vs efectivo | Sharpe comprar y mantener | Dif. vs exposición constante (p) |
|---|---|---|---|---|---|---|
| TBT | {'lookback': 252, 'skip': 21} | +0.18 | [-0.58; +0.83] | 0.317 | +0.14 | +0.04 (0.390) |
| TBX | {'lookback': 126, 'skip': 0} | -0.09 | [-0.67; +0.60] | 0.596 | -0.06 | -0.03 (0.590) |
| TBF | {'lookback': 63, 'skip': 0} | -0.02 | [-0.73; +0.65] | 0.520 | +0.11 | -0.13 (0.660) |

## Validación única `momentum_vol` (desde 2018-12-31)

| Activo | Parámetros | Sharpe fuera de muestra | IC 95 % | p vs efectivo | Sharpe comprar y mantener | Dif. vs exposición constante (p) |
|---|---|---|---|---|---|---|
| TBT | {'lookback': 252, 'skip': 21, 'target': 0.12} | +0.12 | [-0.58; +0.84] | 0.373 | +0.14 | -0.02 (0.484) |
| TBX | {'lookback': 252, 'skip': 21, 'target': 0.08} | -0.02 | [-0.65; +0.57] | 0.522 | -0.06 | +0.04 (0.404) |
| TBF | {'lookback': 252, 'skip': 21, 'target': 0.12} | +0.05 | [-0.61; +0.75] | 0.447 | +0.11 | -0.06 (0.562) |

