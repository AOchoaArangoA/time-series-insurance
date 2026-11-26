# Riesgo de tasa con el Tesoro de EE. UU. — 2026-10-30

Demostración de la spec 007 (procesos estocásticos, simulación y sensibilidades). Mide riesgo; no recomienda asignaciones (FR-017).

- Datos: 7013 días (1998-12-02 a 2026-10-30), Yahoo/CBOE, truncados en la fecha de análisis.
- Nodos cero: ^IRX exacto (descuento act/360 → continuo); 5, 10 y 30 años como par semestral ≈ cero (aproximación sesgada en plazos largos con pendiente; declarada). La calibración ℚ sí valora el bono par.
- ^TYX entre 2002-02 y 2006-02 (1000 días): el bono a 30 años no se emitió; el dato es el publicado por el CBOE y se usa tal cual (M2).

## 1. Tasa corta bajo ℙ (Vasicek, 1998-2026)

```
Vasicek bajo ℙ (n = 7013, Δ = 0.00397)
  kappa = 0.07137 (ee asint. 0.06764; IC 95 % bootstrap [0.03889; 0.72505])
  theta = 0.01874 (ee asint. 0.01904; IC 95 % bootstrap [-0.01141; 0.05083])
  sigma = 0.00713 (ee asint. 0.00006; IC 95 % bootstrap [0.00702; 0.00724])
  κ corregido por jackknife: 0.09320
  Advertencia: κ·T = 2.0 < 50: el MV de κ está sesgado hacia arriba (≈ 4/T_años = 0.144) y sus IC asintóticos no son confiables; use los IC del bootstrap paramétrico.

Diagnósticos de la tasa corta: NO superados
  Estacionariedad de r_t: I(1)
  Ljung-Box: estadístico 214.559, p = 1.4696768794235667e-40
  ARCH-LM: estadístico 1660.428, p = 0.0
  Jarque-Bera: estadístico 2059857.051, p = 0.0
  Pronóstico a 21 pasos frente al paseo aleatorio: ECM modelo 4.046e-06 vs 3.968e-06, DM p = 0.006596991452562944
  Advertencia: r_t no es I(0) según ADF/PP+KPSS (I(1)): la reversión a la media del modelo no está respaldada por los datos.
  Advertencia: Ljung-Box rechaza en los residuos estandarizados (p = 1.47e-40).
  Advertencia: ARCH-LM rechaza en los residuos estandarizados (p = 0): σ constante no captura la volatilidad (esperado).
  Advertencia: Jarque-Bera rechaza en los residuos estandarizados (p = 0).
  Advertencia: El pronóstico del modelo no supera al paseo aleatorio fuera de muestra.
```

- Desde 2009 φ̂ = 1.00009 ≥ 1: en esa muestra la tasa corta se comporta como un paseo aleatorio (κ no identificado). Con toda la muestra κ es pequeño y su IC es muy ancho: la reversión a la media es un supuesto del modelo más que un hecho de los datos.
- CIR no aplica: 7 días con tasa ≤ 0 (2009-2015 y 2020-2021).

## 2. Regímenes de Markov (mensual)

```
Tasa corta con 2 regímenes (estimación hasta 2026-10-31)
  Régimen 0: θ = nan%, κ = nan, σ_Δ = 0.00030, duración esperada 12.4 pasos
  Régimen 1: θ = 2.7450%, κ = 0.187, σ_Δ = 0.00297, duración esperada 14.4 pasos
  AIC -3524.4 vs -3143.4 (1 régimen); BIC -3493.9 vs -3132.0
  Advertencia: Algún régimen sin reversión a la media (φ_s ≥ 1): θ_s y κ_s no definidos.
  Nota: Probabilidades filtradas con parámetros estimados hasta params_estimation_end: antes de esa fecha son pseudo-filtradas (descriptivas), no punto en el tiempo.
```

- Probabilidad filtrada del régimen volátil al cierre: 96.4% (pseudo-filtrada: parámetros estimados con toda la muestra).

## 3. Medida ℚ (Vasicek, 12 meses)

```
Calibración ℚ (vasicek, lambda) con 252 fechas (2025-10-30 a 2026-10-30)
  ℚ: κ = 0.0714, θ = 6.4326%, σ = 0.0071
  λ (precio de mercado del riesgo) = -0.4560 (ee 0.0026)
  RMSE por dato (pb): ^IRX: 2.3, ^FVX: 33.3, ^TNX: 25.7, ^TYX: 20.1
  Nota: σ_ℚ = σ_ℙ por construcción (Girsanov).
  Nota: r_t de cada fecha = tasa corta observada (no se filtra).
  Nota: ee de λ por el jacobiano con errores iid: subestima la incertidumbre con errores persistentes entre fechas.

Calibración ℚ (vasicek, free) con 252 fechas (2025-10-30 a 2026-10-30)
  ℚ: κ = 0.0032, θ = 50.0000%, σ = 0.0071
  RMSE por dato (pb): ^IRX: 1.8, ^FVX: 31.0, ^TNX: 23.6, ^TYX: 17.1
  Nota: σ_ℚ = σ_ℙ por construcción (Girsanov).
  Nota: r_t de cada fecha = tasa corta observada (no se filtra).
  Nota: Parámetros en la cota de la búsqueda ([0.0032, 0.5]): la curva no identifica κ_ℚ y θ_ℚ por separado (casi un paseo aleatorio bajo ℚ).
```

- Un factor no reproduce bien la curva entera: el RMSE por nodo mide cuánto. Para valorar se usa la curva observada (revaluación completa), no el modelo.

## 4. Factores de la curva (3 años de cambios diarios)

```
Factores (pca) de cambios de la curva, 2023-10-26 a 2026-10-30
  nivel: cargas [+0.06, +0.62, +0.59, +0.51] · varianza explicada 91.4%
  pendiente: cargas [-0.43, -0.58, +0.06, +0.69] · varianza explicada 5.7%
  curvatura: cargas [-0.90, +0.31, +0.02, -0.30] · varianza explicada 2.8%

Factores (diebold_li) de cambios de la curva, 2023-10-26 a 2026-10-30
  nivel: cargas [+1.00, +1.00, +1.00, +1.00] · varianza explicada 109.9%
  pendiente: cargas [+0.91, +0.27, +0.14, +0.05] · varianza explicada 36.0%
  curvatura: cargas [+0.08, +0.24, +0.14, +0.05] · varianza explicada 29.6%
  Advertencia: Diebold-Li con 4 nodos y 3 factores: 1 grado(s) de libertad; el ajuste por fecha es casi exacto y el residuo por nodo es poco informativo.
  Advertencia: Las cargas de Nelson-Siegel no son ortogonales: las varianzas por factor no son aditivas (su suma puede superar 100 %). R² conjunto = 99.8%.
  Advertencia: λ fija = 0.0609 (meses⁻¹): no se optimiza (frontera con el paquete de curvas).
```

## 5. Cartera y sensibilidades

- Cartera: 2000 × Bono 2a, cupón 4.000% (2/año); 3000 × Bono 5a, cupón 4.200% (2/año); 3000 × Bono 10a, cupón 4.500% (2/año); 1500 × Bono 25a, cupón 4.700% (2/año)

```
PV 921,189.4250 · DV01 609.8793 · duración efectiva (Fisher-Weil) 6.6206 · convexidad 75.459
  KRD: 0.25: 0.407, 5: 1.964, 10: 3.099, 30: 1.152
```

## 6. VaR y ES a 10 días (revaluación completa)

| Motor | VaR 99 % | ES 97,5 % | IC 95 % del ES |
|---|---|---|---|
| histórica (3 años) | 19,205 | 18,965 | [16,760; 20,280] |
| histórica filtrada EWMA | 24,759 | 25,091 | [24,028; 26,172] |
| MC de factores t₅ | 24,103 | 25,980 | [23,718; 28,371] |
| MC de la tasa corta (ℙ→ℚ λ) | 13,969 | 14,183 | [13,709; 14,675] |

- El MC de un factor mueve toda la curva con r_T: subestima el riesgo de pendiente. Los IC de Monte Carlo miden sólo el error de simulación.

## 7. Backtesting del VaR 99 % a 1 día (FHS EWMA, 4237 días)

```
Backtesting VaR 0.99 (n = 4237)
  Excepciones 51 (1.20% vs 1.00%); Kupiec p = 0.197
  Christoffersen: independencia p = 0.265, cobertura condicional p = 0.233
  Duraciones (Christoffersen-Pelletier) p = 0.43541273287321913
```

- Pérdidas realizadas y pronosticadas con la aproximación ΔΓ (sensibilidades re-estimadas cada mes con la curva del día previo): mide el modelo de escenarios, no el error de la aproximación.

## 8. Estrés e inmunización

```
Estrés (PV base 921,189.4250)
  paralelo +: ΔPV -57,694.0261
  paralelo −: ΔPV +64,664.6735
  empinamiento: ΔPV -12,386.5417
  aplanamiento: ΔPV +13,921.7933
  curvatura +: ΔPV -23,872.6356
  nivel +3σ: ΔPV -8,915.2255
  nivel −3σ: ΔPV +9,070.6388
  pendiente +3σ: ΔPV +204.6448
  pendiente −3σ: ΔPV -199.3384
  curvatura +3σ: ΔPV +16.8349
  curvatura −3σ: ΔPV -16.3177
  Nota: σ de los factores de la ventana ('2023-10-26', '2026-10-30') (cambios diarios).

Cobertura NO factible (residual mínimo): cantidades [-4586.186808, -4672.313377, -1713.208938]; exposición residual 0.25: +3.745e+05, 5: +4.657e-10, 10: +0.000e+00, 30: +0.000e+00
```

- Con 3 coberturas cupón cero para 4 nodos no se anula la exposición del nodo de 13 semanas: se reporta el residual mínimo (M5).

_Tiempo de ejecución: 33.4 s · tsinsurance 0.2.0_
