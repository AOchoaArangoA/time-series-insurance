# Experimento sectores-gics-ciclo

**Hipótesis (pre-registrada)**: H1 (timing): en los ETFs sectoriales SPDR, las reglas de tendencia y momentum de serie de
tiempo mejoran el timing frente a la MISMA exposición constante (no sólo frente a comprar y
mantener), después de ajustar por todas las pruebas.
H2 (ciclo): el nivel y el cambio de la tasa a 10 años y el nivel del VIX, conocidos al cierre
de mes, predicen el exceso de retorno del mes siguiente de Financials (XLF), Utilities (XLU) y
Tecnología (XLK) mejor que la media histórica, con valor económico neto de costos.
Expectativa previa: evidencia débil o nula; el ejercicio es exploratorio.


- Ejecución `20261117T192634Z-fc940b` · experimento sha256 fc940be1e2e7… · paquete `sectores_gics` (sha256 e60a270bf66b…) · tsinsurance 0.2.0 · semilla 17
- Supuestos: retraso=1 barra(s), costo=3.0 pb, deslizamiento=2.0 pb, rebalanceo=every_bar, bruto máx.=1.0, cortos=no, financiación=rf+0.0 pb
- Selección y pruebas múltiples sobre datos hasta 2014-12-31; validación única desde 2014-12-31
- Pruebas previas en la bitácora por activo: {'TBF': 15, 'TBX': 15, 'TBT': 14}
- Calidad de datos: XLE 2008-09-29: retorno -11.89% y +6.12% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
## Conclusión automática

- Estado: confirmatorio
- Ideas con timing significativo (DSR > 1−α y SPA-Holm < α): ninguna
- Modelos econométricos: ciclo_financieras → sin_evidencia, ciclo_utilities → sin_evidencia, ciclo_tecnologia → solo_estadistica
- La ganancia CER no tiene inferencia propia; en activos apalancados refleja sobre todo la penalización de varianza, no habilidad.

- Calidad de datos: XLE 2008-11-20: retorno -12.37% y +11.16% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLE 2020-03-12: retorno -12.47% y +9.23% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLB 2020-03-12: retorno -9.63% y +7.02% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLB 2020-03-16: retorno -11.01% y +6.19% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLI 2008-12-01: retorno -8.22% y +4.62% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLI 2020-03-09: retorno -9.22% y +5.18% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLI 2020-03-12: retorno -10.35% y +7.81% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLI 2020-03-13: retorno +7.81% y -11.34% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLY 2008-10-15: retorno -11.62% y +6.60% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLY 2008-12-01: retorno -8.74% y +4.65% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLY 2020-03-12: retorno -10.11% y +6.19% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLP 2020-03-12: retorno -9.40% y +8.51% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLP 2020-03-13: retorno +8.51% y -6.78% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLP 2020-03-16: retorno -6.78% y +8.43% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLV 2008-10-15: retorno -9.78% y +5.22% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLV 2020-03-12: retorno -7.47% y +6.94% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLV 2020-03-13: retorno +6.94% y -9.86% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLV 2020-03-16: retorno -9.86% y +6.28% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2008-09-15: retorno -9.74% y +7.49% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2008-09-17: retorno -9.60% y +7.87% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2008-09-19: retorno +12.92% y -8.18% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2008-09-29: retorno -13.18% y +7.11% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2008-10-09: retorno -10.41% y +10.30% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2009-01-20: retorno -16.53% y +14.73% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2009-01-28: retorno +12.80% y -7.86% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2009-03-18: retorno +10.06% y -7.97% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2009-03-30: retorno -8.64% y +5.51% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2009-04-20: retorno -11.16% y +7.40% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2011-08-08: retorno -9.46% y +7.73% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2020-03-09: retorno -10.72% y +5.87% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2020-03-12: retorno -10.81% y +13.16% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLF 2020-03-13: retorno +13.16% y -13.71% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLK 2020-03-12: retorno -9.76% y +11.73% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLK 2020-03-13: retorno +11.73% y -13.81% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLC 2020-03-12: retorno -9.39% y +8.99% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLC 2020-03-13: retorno +8.99% y -11.28% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLU 2002-07-23: retorno -7.78% y +8.91% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLU 2002-10-09: retorno -8.53% y +6.76% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLU 2020-03-12: retorno -10.09% y +5.45% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLU 2020-03-16: retorno -11.36% y +12.79% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLRE 2020-03-12: retorno -8.59% y +8.78% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: XLRE 2020-03-13: retorno +8.78% y -16.00% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: SPY 2008-09-29: retorno -7.84% y +4.14% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: SPY 2008-11-20: retorno -7.42% y +5.39% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: SPY 2011-08-08: retorno -6.51% y +4.65% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: SPY 2020-03-09: retorno -7.81% y +5.17% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: SPY 2020-03-12: retorno -9.57% y +8.55% al día siguiente (> 8 desviaciones robustas): posible dato erróneo
- Calidad de datos: SPY 2020-03-13: retorno +8.55% y -10.94% al día siguiente (> 8 desviaciones robustas): posible dato erróneo

## Modelo econométrico `ciclo_financieras` (XLF)

Especificaciones contadas sobre XLF: 1 · benchmark: regla con media histórica · anticipación del flujo: Sin anticipación detectada en 17 cortes evaluados (0 omitidos por datos insuficientes).

```text
----------------------------------------------------------------------------------------
Veredicto: sin evidencia [DIAGNÓSTICOS NO SUPERADOS]
  Evidencia estadística (Pesaran-Timmermann, α=0.05): no
  Valor económico (Sharpe neto vs regla con media histórica, α=0.05): no
  Ni evidencia estadística ni valor económico frente al benchmark.
  Regla: estadística = Pesaran-Timmermann rechaza H0 al nivel α; económica = prueba unilateral de diferencia de Sharpe (bootstrap estacionario) neto de costos y en exceso de rf frente a la misma regla aplicada a la media histórica rechaza al nivel α; no concluyente si hay menos de 60 pronósticos fuera de muestra; exploratorio si se probó más de una especificación o hay variables no punto-en-el-tiempo.
----------------------------------------------------------------------------------------
(a) VALIDACIÓN ESTADÍSTICA
Walk-forward expanding: 273 pronósticos (2004-02-27 a 2026-10-30), 273 re-estimaciones, min_train=60, refit_every=1
Evaluación fuera de muestra (272 pronósticos): R²_OS=-4.55%  aciertos de signo=54.4%
  Clark-West             estad.=  -0.003  p=0.5014
  Pesaran-Timmermann     estad.=  -0.075  p=0.5298
  Diebold-Mariano (HLN)  estad.=  -0.745  p=0.4566
    Nota: No válida para modelos anidados (subdimensionada); la prueba principal es Clark-West.
Validación del modelo (muestra completa, n=332, descriptiva ex post): R²=0.011  R² ajustado=0.002  HAC rezagos=5
         coef  se_hac       t       p
const  0.0227  0.0171  1.3242  0.1854
^TNX  -0.0043  0.0022 -1.9087  0.0563
d_TNX  0.0114  0.0133  0.8618  0.3888
^VIX  -0.0002  0.0010 -0.1646  0.8692
Estacionariedad de regresores: ^TNX=I(1), d_TNX=I(0), ^VIX=I(0)
Persistencia (ρ AR(1), δ = corr. de innovaciones, sesgo de Stambaugh aprox.):
             rho   delta  sesgo_stambaugh
regresor                                 
^TNX      0.9814  0.1759          -0.0005
d_TNX     0.0278  0.1757          -0.0001
^VIX      0.7867 -0.5901           0.0001
Diagnósticos de residuos:
  Ljung-Box        estad.=  13.3261  p=0.2060
  ARCH-LM          estad.=  75.2016  p=0.0000
  Jarque-Bera      estad.=  91.5167  p=0.0000
  CUSUM (OLS)      estad.=   0.8086  p=0.5302
Diagnósticos superados: no
Advertencia: '^TNX' es I(1): regresión desbalanceada (retorno I(0) sobre regresor no estacionario); inferencia HAC no válida.
Advertencia: '^TNX' es muy persistente (ρ=0.981, δ=0.18): sesgo de Stambaugh ≈ -0.0005 en su coeficiente y t-estadísticos HAC sobredimensionados (IVX pendiente).
Advertencia: Diagnósticos rechazados: ARCH-LM.
----------------------------------------------------------------------------------------
(b) BACKTEST ECONÓMICO (regla 'long_cash')
Backtest 'modelo' — 7000 periodos (1999-01-04 a 2026-10-30)
Supuestos: retraso=1 barra(s), costo=3.0 pb, deslizamiento=2.0 pb, rebalanceo=M, bruto máx.=1.0, cortos=no, financiación=rf+0.0 pb
Fin del calentamiento: 2004-03-02
Métricas sobre retornos en exceso de rf; benchmark = comprar y mantener
Estrategia : ret. anual=+4.20%  vol=19.64%  Sharpe=0.31  Sortino=0.43  máx. caída=-46.46%  Calmar=0.09  aciertos=51.9%  rotación media=0.0056  n=5704
Benchmark  : ret. anual=+4.00%  vol=28.33%  Sharpe=0.28  Sortino=0.40  máx. caída=-83.47%  Calmar=0.05  aciertos=51.9%  rotación media=0.0000  n=5704
Nota: Universo elegido ex post (activos vigentes hoy): posible sesgo de supervivencia y de selección.
Benchmark de la regla (media histórica): ret. anual=+4.27%  vol=18.28%  Sharpe=0.32  Sortino=0.45  máx. caída=-47.80%  Calmar=0.09  aciertos=52.4%  rotación media=0.0004  n=5704
Sharpe 0.308 vs 0.320 (dif. -0.012, p unilateral=0.558); ganancia CER(γ=3)=-0.58% anual
Nota: La decisión de fin de mes se ejecuta al cierre siguiente (retraso 1): el periodo mantenido está desplazado un día respecto del retorno pronosticado.
----------------------------------------------------------------------------------------
```

## Modelo econométrico `ciclo_utilities` (XLU)

Especificaciones contadas sobre XLU: 1 · benchmark: regla con media histórica · anticipación del flujo: Sin anticipación detectada en 17 cortes evaluados (0 omitidos por datos insuficientes).

```text
----------------------------------------------------------------------------------------
Veredicto: sin evidencia [DIAGNÓSTICOS NO SUPERADOS]
  Evidencia estadística (Pesaran-Timmermann, α=0.05): no
  Valor económico (Sharpe neto vs regla con media histórica, α=0.05): no
  Ni evidencia estadística ni valor económico frente al benchmark.
  Regla: estadística = Pesaran-Timmermann rechaza H0 al nivel α; económica = prueba unilateral de diferencia de Sharpe (bootstrap estacionario) neto de costos y en exceso de rf frente a la misma regla aplicada a la media histórica rechaza al nivel α; no concluyente si hay menos de 60 pronósticos fuera de muestra; exploratorio si se probó más de una especificación o hay variables no punto-en-el-tiempo.
----------------------------------------------------------------------------------------
(a) VALIDACIÓN ESTADÍSTICA
Walk-forward expanding: 273 pronósticos (2004-02-27 a 2026-10-30), 273 re-estimaciones, min_train=60, refit_every=1
Evaluación fuera de muestra (272 pronósticos): R²_OS=-5.95%  aciertos de signo=61.8%
  Clark-West             estad.=   0.871  p=0.1918
  Pesaran-Timmermann     estad.=  -0.473  p=0.6819
  Diebold-Mariano (HLN)  estad.=  -1.145  p=0.2530
    Nota: No válida para modelos anidados (subdimensionada); la prueba principal es Clark-West.
Validación del modelo (muestra completa, n=332, descriptiva ex post): R²=0.006  R² ajustado=-0.003  HAC rezagos=5
         coef  se_hac       t       p
const  0.0167  0.0074  2.2456  0.0247
^TNX  -0.0015  0.0016 -0.8928  0.3720
d_TNX  0.0050  0.0101  0.4979  0.6186
^VIX  -0.0003  0.0003 -1.0794  0.2804
Estacionariedad de regresores: ^TNX=I(1), d_TNX=I(0), ^VIX=I(0)
Persistencia (ρ AR(1), δ = corr. de innovaciones, sesgo de Stambaugh aprox.):
             rho   delta  sesgo_stambaugh
regresor                                 
^TNX      0.9814 -0.1629           0.0003
d_TNX     0.0278 -0.1611           0.0001
^VIX      0.7867 -0.3871           0.0000
Diagnósticos de residuos:
  Ljung-Box        estad.=  12.3876  p=0.2600
  ARCH-LM          estad.=   6.1010  p=0.2965
  Jarque-Bera      estad.=  16.3693  p=0.0003
  CUSUM (OLS)      estad.=   0.5839  p=0.8848
Diagnósticos superados: no
Advertencia: '^TNX' es I(1): regresión desbalanceada (retorno I(0) sobre regresor no estacionario); inferencia HAC no válida.
Advertencia: '^TNX' es muy persistente (ρ=0.981, δ=-0.16): sesgo de Stambaugh ≈ +0.0003 en su coeficiente y t-estadísticos HAC sobredimensionados (IVX pendiente).
----------------------------------------------------------------------------------------
(b) BACKTEST ECONÓMICO (regla 'long_cash')
Backtest 'modelo' — 7000 periodos (1999-01-04 a 2026-10-30)
Supuestos: retraso=1 barra(s), costo=3.0 pb, deslizamiento=2.0 pb, rebalanceo=M, bruto máx.=1.0, cortos=no, financiación=rf+0.0 pb
Fin del calentamiento: 2004-03-02
Métricas sobre retornos en exceso de rf; benchmark = comprar y mantener
Estrategia : ret. anual=+7.44%  vol=14.67%  Sharpe=0.56  Sortino=0.78  máx. caída=-30.12%  Calmar=0.25  aciertos=53.9%  rotación media=0.0035  n=5704
Benchmark  : ret. anual=+7.54%  vol=18.38%  Sharpe=0.49  Sortino=0.69  máx. caída=-47.33%  Calmar=0.16  aciertos=53.9%  rotación media=0.0000  n=5704
Nota: Universo elegido ex post (activos vigentes hoy): posible sesgo de supervivencia y de selección.
Benchmark de la regla (media histórica): ret. anual=+7.07%  vol=18.28%  Sharpe=0.46  Sortino=0.66  máx. caída=-47.33%  Calmar=0.15  aciertos=53.7%  rotación media=0.0002  n=5704
Sharpe 0.563 vs 0.465 (dif. +0.098, p unilateral=0.116); ganancia CER(γ=3)=+1.54% anual
Nota: La decisión de fin de mes se ejecuta al cierre siguiente (retraso 1): el periodo mantenido está desplazado un día respecto del retorno pronosticado.
----------------------------------------------------------------------------------------
```

## Modelo econométrico `ciclo_tecnologia` (XLK)

Especificaciones contadas sobre XLK: 1 · benchmark: regla con media histórica · anticipación del flujo: Sin anticipación detectada en 17 cortes evaluados (0 omitidos por datos insuficientes).

```text
----------------------------------------------------------------------------------------
Veredicto: solo estadistica [DIAGNÓSTICOS NO SUPERADOS]
  Evidencia estadística (Pesaran-Timmermann, α=0.05): sí
  Valor económico (Sharpe neto vs regla con media histórica, α=0.05): no
  La prueba estadística indica capacidad predictiva, pero no se traduce en valor económico neto de costos (ajuste sin valor económico). (Pesaran-Timmermann: acierta la dirección más que el azar; no compara contra la media histórica.)
  Regla: estadística = Pesaran-Timmermann rechaza H0 al nivel α; económica = prueba unilateral de diferencia de Sharpe (bootstrap estacionario) neto de costos y en exceso de rf frente a la misma regla aplicada a la media histórica rechaza al nivel α; no concluyente si hay menos de 60 pronósticos fuera de muestra; exploratorio si se probó más de una especificación o hay variables no punto-en-el-tiempo.
----------------------------------------------------------------------------------------
(a) VALIDACIÓN ESTADÍSTICA
Walk-forward expanding: 273 pronósticos (2004-02-27 a 2026-10-30), 273 re-estimaciones, min_train=60, refit_every=1
Evaluación fuera de muestra (272 pronósticos): R²_OS=-6.99%  aciertos de signo=59.6%
  Clark-West             estad.=   0.712  p=0.2381
  Pesaran-Timmermann     estad.=   1.894  p=0.0291
  Diebold-Mariano (HLN)  estad.=  -1.536  p=0.1256
    Nota: No válida para modelos anidados (subdimensionada); la prueba principal es Clark-West.
Validación del modelo (muestra completa, n=332, descriptiva ex post): R²=0.026  R² ajustado=0.017  HAC rezagos=5
         coef  se_hac       t       p
const  0.0184  0.0152  1.2086  0.2268
^TNX  -0.0070  0.0031 -2.2752  0.0229
d_TNX  0.0128  0.0124  1.0372  0.2997
^VIX   0.0007  0.0007  1.0720  0.2837
Estacionariedad de regresores: ^TNX=I(1), d_TNX=I(0), ^VIX=I(0)
Persistencia (ρ AR(1), δ = corr. de innovaciones, sesgo de Stambaugh aprox.):
             rho   delta  sesgo_stambaugh
regresor                                 
^TNX      0.9814  0.1357          -0.0004
d_TNX     0.0278  0.1344          -0.0001
^VIX      0.7867 -0.5854           0.0001
Diagnósticos de residuos:
  Ljung-Box        estad.=  12.2710  p=0.2673
  ARCH-LM          estad.=  84.7614  p=0.0000
  Jarque-Bera      estad.=  26.7898  p=0.0000
  CUSUM (OLS)      estad.=   0.7999  p=0.5443
Diagnósticos superados: no
Advertencia: '^TNX' es I(1): regresión desbalanceada (retorno I(0) sobre regresor no estacionario); inferencia HAC no válida.
Advertencia: '^TNX' es muy persistente (ρ=0.981, δ=0.14): sesgo de Stambaugh ≈ -0.0004 en su coeficiente y t-estadísticos HAC sobredimensionados (IVX pendiente).
Advertencia: Diagnósticos rechazados: ARCH-LM.
----------------------------------------------------------------------------------------
(b) BACKTEST ECONÓMICO (regla 'long_cash')
Backtest 'modelo' — 7000 periodos (1999-01-04 a 2026-10-30)
Supuestos: retraso=1 barra(s), costo=3.0 pb, deslizamiento=2.0 pb, rebalanceo=M, bruto máx.=1.0, cortos=no, financiación=rf+0.0 pb
Fin del calentamiento: 2004-03-02
Métricas sobre retornos en exceso de rf; benchmark = comprar y mantener
Estrategia : ret. anual=+10.17%  vol=20.15%  Sharpe=0.58  Sortino=0.83  máx. caída=-54.42%  Calmar=0.19  aciertos=54.6%  rotación media=0.0030  n=5704
Benchmark  : ret. anual=+12.79%  vol=22.46%  Sharpe=0.65  Sortino=0.93  máx. caída=-53.92%  Calmar=0.24  aciertos=54.8%  rotación media=0.0000  n=5704
Nota: Universo elegido ex post (activos vigentes hoy): posible sesgo de supervivencia y de selección.
Benchmark de la regla (media histórica): ret. anual=+11.74%  vol=18.01%  Sharpe=0.71  Sortino=1.01  máx. caída=-34.28%  Calmar=0.34  aciertos=55.4%  rotación media=0.0002  n=5704
Sharpe 0.582 vs 0.707 (dif. -0.125, p unilateral=0.836); ganancia CER(γ=3)=-2.23% anual
Nota: Pesaran-Timmermann detecta capacidad direccional, pero Clark-West no rechaza y el R² fuera de muestra es -7.0%: el pronóstico no mejora a la media histórica en error cuadrático.
Nota: La decisión de fin de mes se ejecuta al cierre siguiente (retraso 1): el periodo mantenido está desplazado un día respecto del retorno pronosticado.
----------------------------------------------------------------------------------------
```

## Idea `tendencia` (sma_crossover, malla {'fast': [50, 100], 'slow': [150, 200]}) — selección hasta 2014-12-31

```text
                                     best  sharpe   psr  ir_vs_bh  exposure  timing_ir  n_trials   dsr  spa_p  spa_p_holm  significant
asset                                                                                                                                 
XLB     idea=tendencia, fast=50, slow=200   0.387 0.933    -0.098     0.685      0.059         8 0.466  0.654       1.000        False
XLE     idea=tendencia, fast=50, slow=200   0.457 0.962    -0.099     0.736      0.056         8 0.291  0.416       1.000        False
XLF    idea=tendencia, fast=100, slow=150   0.519 0.979     0.066     0.627      0.223         9 0.649  0.304       1.000        False
XLI     idea=tendencia, fast=50, slow=150   0.510 0.976    -0.017     0.672      0.166         8 0.637  0.304       1.000        False
XLK    idea=tendencia, fast=100, slow=200   0.495 0.973     0.191     0.631      0.361         9 0.833  0.882       1.000        False
XLP    idea=tendencia, fast=100, slow=150   0.511 0.976    -0.056     0.723      0.126         8 0.625  0.532       1.000        False
XLU    idea=tendencia, fast=100, slow=200   0.732 0.998     0.159     0.735      0.370         9 0.780  0.194       1.000        False
XLV    idea=tendencia, fast=100, slow=200   0.280 0.861    -0.307     0.671     -0.151         8 0.045  0.758       1.000        False
XLY    idea=tendencia, fast=100, slow=200   0.388 0.934    -0.155     0.642      0.019         8 0.293  0.696       1.000        False
```

## Idea `momentum` (tsmom, malla {'lookback': [126, 252], 'skip': [21]}) — selección hasta 2014-12-31

```text
                                       best  sharpe   psr  ir_vs_bh  exposure  timing_ir  n_trials   dsr  spa_p  spa_p_holm  significant
asset                                                                                                                                   
XLB    idea=momentum, lookback=126, skip=21   0.301 0.877    -0.152     0.656     -0.006         8 0.368  0.654       1.000        False
XLE    idea=momentum, lookback=252, skip=21   0.524 0.978    -0.013     0.750      0.169         8 0.458  0.416       1.000        False
XLF    idea=momentum, lookback=126, skip=21   0.367 0.922    -0.024     0.630      0.086         9 0.440  0.304       1.000        False
XLI    idea=momentum, lookback=126, skip=21   0.553 0.983     0.048     0.652      0.270         8 0.774  0.304       1.000        False
XLK    idea=momentum, lookback=126, skip=21   0.312 0.886     0.158     0.623      0.267         9 0.726  0.882       1.000        False
XLP    idea=momentum, lookback=252, skip=21   0.531 0.979    -0.064     0.779      0.107         8 0.596  0.532       1.000        False
XLU    idea=momentum, lookback=252, skip=21   0.610 0.991     0.018     0.747      0.190         9 0.531  0.194       1.000        False
XLV    idea=momentum, lookback=252, skip=21   0.412 0.945    -0.104     0.726      0.056         8 0.189  0.758       1.000        False
XLY    idea=momentum, lookback=252, skip=21   0.285 0.864    -0.210     0.708     -0.101         8 0.157  0.696       1.000        False
```

## Idea `momentum_vol` (tsmom_vol_target, malla {'lookback': [252], 'skip': [21], 'target': [0.1, 0.15]}) — selección hasta 2014-12-31

```text
                                                        best  sharpe   psr  ir_vs_bh  exposure  timing_ir  n_trials   dsr  spa_p  spa_p_holm  significant
asset                                                                                                                                                    
XLB    idea=momentum_vol, lookback=252, skip=21, target=0.15   0.321 0.892    -0.207     0.582     -0.049         8 0.308  0.654       1.000        False
XLE    idea=momentum_vol, lookback=252, skip=21, target=0.15   0.607 0.990    -0.155     0.535      0.176         8 0.468  0.416       1.000        False
XLF    idea=momentum_vol, lookback=252, skip=21, target=0.15   0.398 0.937    -0.061     0.564      0.059         9 0.399  0.304       1.000        False
XLI    idea=momentum_vol, lookback=252, skip=21, target=0.15   0.522 0.978    -0.056     0.637      0.146         8 0.607  0.304       1.000        False
XLK    idea=momentum_vol, lookback=252, skip=21, target=0.15   0.344 0.908     0.114     0.565      0.242         9 0.693  0.882       1.000        False
XLP    idea=momentum_vol, lookback=252, skip=21, target=0.15   0.567 0.985    -0.091     0.747      0.100         8 0.586  0.532       1.000        False
XLU     idea=momentum_vol, lookback=252, skip=21, target=0.1   0.662 0.994    -0.111     0.565      0.180         9 0.515  0.194       1.000        False
XLV    idea=momentum_vol, lookback=252, skip=21, target=0.15   0.422 0.949    -0.158     0.669      0.019         8 0.153  0.758       1.000        False
XLY    idea=momentum_vol, lookback=252, skip=21, target=0.15   0.377 0.927    -0.201     0.619     -0.054         8 0.205  0.696       1.000        False
```

## Validación única `tendencia` (desde 2014-12-31)

| Activo | Parámetros | Sharpe fuera de muestra | IC 95 % | p vs efectivo | Sharpe comprar y mantener | Dif. vs exposición constante (p) |
|---|---|---|---|---|---|---|
| XLB | {'fast': 50, 'slow': 200} | +0.12 | [-0.43; +0.65] | 0.338 | +0.42 | -0.30 (0.954) |
| XLE | {'fast': 50, 'slow': 200} | +0.52 | [-0.03; +1.11] | 0.038 | +0.37 | +0.15 (0.284) |
| XLF | {'fast': 100, 'slow': 150} | +0.36 | [-0.14; +0.91] | 0.108 | +0.50 | -0.14 (0.830) |
| XLI | {'fast': 50, 'slow': 150} | +0.13 | [-0.48; +0.81] | 0.324 | +0.55 | -0.42 (0.984) |
| XLK | {'fast': 100, 'slow': 200} | +0.79 | [+0.30; +1.31] | 0.003 | +0.84 | -0.05 (0.660) |
| XLP | {'fast': 100, 'slow': 150} | -0.03 | [-0.50; +0.42] | 0.537 | +0.46 | -0.49 (1.000) |
| XLU | {'fast': 100, 'slow': 200} | +0.30 | [-0.09; +0.80] | 0.149 | +0.43 | -0.12 (0.822) |
| XLV | {'fast': 100, 'slow': 200} | +0.44 | [+0.05; +0.85] | 0.065 | +0.56 | -0.11 (0.796) |
| XLY | {'fast': 100, 'slow': 200} | +0.37 | [-0.14; +0.92] | 0.104 | +0.52 | -0.15 (0.814) |

## Validación única `momentum` (desde 2014-12-31)

| Activo | Parámetros | Sharpe fuera de muestra | IC 95 % | p vs efectivo | Sharpe comprar y mantener | Dif. vs exposición constante (p) |
|---|---|---|---|---|---|---|
| XLB | {'lookback': 126, 'skip': 21} | +0.09 | [-0.38; +0.65] | 0.383 | +0.42 | -0.33 (0.962) |
| XLE | {'lookback': 252, 'skip': 21} | +0.43 | [-0.17; +1.04] | 0.070 | +0.37 | +0.06 (0.400) |
| XLF | {'lookback': 126, 'skip': 21} | +0.41 | [-0.12; +0.97] | 0.079 | +0.50 | -0.09 (0.722) |
| XLI | {'lookback': 126, 'skip': 21} | +0.21 | [-0.23; +0.76] | 0.232 | +0.55 | -0.34 (0.974) |
| XLK | {'lookback': 126, 'skip': 21} | +0.55 | [+0.14; +1.01] | 0.030 | +0.84 | -0.29 (0.982) |
| XLP | {'lookback': 252, 'skip': 21} | +0.30 | [-0.14; +0.74] | 0.153 | +0.46 | -0.16 (0.980) |
| XLU | {'lookback': 252, 'skip': 21} | +0.24 | [-0.14; +0.67] | 0.204 | +0.43 | -0.18 (0.920) |
| XLV | {'lookback': 252, 'skip': 21} | +0.24 | [-0.24; +0.74] | 0.207 | +0.56 | -0.32 (0.996) |
| XLY | {'lookback': 252, 'skip': 21} | +0.32 | [-0.22; +0.87] | 0.138 | +0.52 | -0.20 (0.928) |

## Validación única `momentum_vol` (desde 2014-12-31)

| Activo | Parámetros | Sharpe fuera de muestra | IC 95 % | p vs efectivo | Sharpe comprar y mantener | Dif. vs exposición constante (p) |
|---|---|---|---|---|---|---|
| XLB | {'lookback': 252, 'skip': 21, 'target': 0.15} | +0.23 | [-0.31; +0.81] | 0.211 | +0.42 | -0.18 (0.802) |
| XLE | {'lookback': 252, 'skip': 21, 'target': 0.15} | +0.26 | [-0.32; +0.87] | 0.190 | +0.37 | -0.12 (0.670) |
| XLF | {'lookback': 252, 'skip': 21, 'target': 0.15} | +0.20 | [-0.35; +0.72] | 0.249 | +0.50 | -0.30 (0.960) |
| XLI | {'lookback': 252, 'skip': 21, 'target': 0.15} | +0.33 | [-0.21; +0.89] | 0.132 | +0.55 | -0.22 (0.864) |
| XLK | {'lookback': 252, 'skip': 21, 'target': 0.15} | +0.78 | [+0.23; +1.40] | 0.004 | +0.84 | -0.06 (0.642) |
| XLP | {'lookback': 252, 'skip': 21, 'target': 0.15} | +0.27 | [-0.27; +0.88] | 0.174 | +0.46 | -0.19 (0.940) |
| XLU | {'lookback': 252, 'skip': 21, 'target': 0.1} | +0.21 | [-0.29; +0.77] | 0.240 | +0.43 | -0.22 (0.932) |
| XLV | {'lookback': 252, 'skip': 21, 'target': 0.15} | +0.21 | [-0.34; +0.77] | 0.237 | +0.56 | -0.35 (0.988) |
| XLY | {'lookback': 252, 'skip': 21, 'target': 0.15} | +0.33 | [-0.17; +0.92] | 0.131 | +0.52 | -0.19 (0.878) |

