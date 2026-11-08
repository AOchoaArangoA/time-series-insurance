# Estacionariedad y orden de integración

Módulo: `tsinsurance.diagnostics.stationarity` · Requisitos: FR-004, FR-005 · SC-001, SC-003

## Por qué importa

Los modelos ARMA/GARCH y las métricas de riesgo suponen series estacionarias. Modelar una
serie con raíz unitaria en niveles produce regresiones espurias, intervalos de pronóstico
subestimados y VaR mal calibrado. Diferenciar de más introduce una raíz unitaria en el
componente MA y pérdida de eficiencia. Por eso el orden de integración se decide con
pruebas formales y una regla explícita y auditable.

## Pruebas

| Prueba | H0 | Implementación | Especificación por defecto |
|--------|----|----------------|----------------------------|
| ADF (Dickey-Fuller aumentada) | raíz unitaria | `statsmodels.adfuller` | rezagos por AIC hasta `12·(n/100)^{1/4}`; valores p de MacKinnon |
| Phillips-Perron (Z-tau) | raíz unitaria | `arch.unitroot.PhillipsPerron` | kernel Bartlett, ancho `12·(n/100)^{1/4}` |
| KPSS | estacionariedad | `statsmodels.kpss` | ancho de banda automático (Hobijn et al. 1998) |
| Zivot-Andrews | raíz unitaria sin quiebre | `statsmodels.zivot_andrews` | quiebre en intercepto (`trend="c"`) o en intercepto y tendencia (`trend="ct"`), recorte 15 %, rezagos por AIC |

Mínimos: 25 observaciones (ADF, PP, KPSS) y 50 (Zivot-Andrews); por debajo se lanza
`InsufficientDataError` con el mínimo requerido. El valor p de KPSS está acotado a
[0,01; 0,10] por la tabla original; cuando cae fuera se registra una nota.

## Regla de decisión (jerárquica: ADF/PP deciden, KPSS desempata y confirma)

En cada diferencia `d = 0, 1, …, max_d`:

1. **ADF y PP rechazan** → estacionaria en `d` ⇒ `I(d)`. Si KPSS también rechaza se
   registra la discrepancia (posible memoria larga o quiebre).
2. **ADF y PP no rechazan y KPSS rechaza** → raíz unitaria: se diferencia y se repite
   (solo con constante en las diferencias).
3. **Ninguna rechaza** → datos poco informativos (baja potencia): *inconcluso*.
4. **ADF y PP discrepan** → *inconcluso*.

Niveles α admitidos: 1 %, 2,5 %, 5 % y 10 % (tabla de KPSS). El valor p de KPSS está
acotado a [0,01; 0,10]; cuando cae en el borde (`p_value_bound`), la decisión usa los
valores críticos tabulados.

Zivot-Andrews se ejecuta sobre el nivel y reporta la fecha que minimiza su estadístico
(convención: última observación antes del quiebre) junto con su significancia; si no
rechaza, la fecha es sólo indicativa (bajo la nula el argmin no es consistente). Si
rechaza la raíz unitaria cuando la regla concluye no estacionariedad, se agrega una nota:
la persistencia aparente podría deberse a un cambio estructural.

### Precisión esperada (SC-001)

Con α = 5 % y n = 500 (500 réplicas Monte Carlo, `tests/simulation/`):

| Proceso | Acierto | Conclusión incorrecta |
|---------|---------|-----------------------|
| AR(1), φ = 0,5 — I(0) | ≈ 100 % | ≈ 0 % |
| Paseo aleatorio — I(1) | ≈ 89 % | ≈ 5 % |

El techo para I(1) es estructural: la regla exige que ni ADF ni PP rechacen en niveles
(probabilidad entre 1 − 2α y 1 − α según la correlación de sus errores) y que KPSS
rechace (potencia ≈ 94 % con n = 500). En la medición exploratoria inicial (200
réplicas), una regla que exigía acuerdo de las tres pruebas en cada diferencia dio
≈ 84 %; esa cifra no está respaldada por una prueba automatizada.

## Ejemplo con datos reales

`examples/01_diagnostico_tasas_fred.py` (GS10 mensual, 1990-2025): ADF y PP no rechazan
en niveles y KPSS sí ⇒ se diferencia; en la primera diferencia ADF y PP rechazan y KPSS no
⇒ **I(1)**. El estadístico de Zivot-Andrews se minimiza en 2020-08, pero la prueba no
rechaza: la fecha es sólo indicativa.

## Referencias

- Dickey, D. A. & Fuller, W. A. (1979). *JASA*, 74(366), 427-431.
- Phillips, P. C. B. & Perron, P. (1988). *Biometrika*, 75(2), 335-346.
- Kwiatkowski, D., Phillips, P. C. B., Schmidt, P. & Shin, Y. (1992). *Journal of Econometrics*, 54, 159-178.
- Zivot, E. & Andrews, D. W. K. (1992). *JBES*, 10(3), 251-270.
- MacKinnon, J. G. (1996, 2010). Valores críticos y funciones de distribución de pruebas de raíz unitaria.
- Hobijn, B., Franses, P. H. & Ooms, M. (1998). Generalisations of the KPSS-test for stationarity. Econometric Institute Report 9802.
- Maddala, G. S. & Kim, I.-M. (1998). *Unit Roots, Cointegration and Structural Change*. Cambridge University Press (análisis confirmatorio).
- Nelson, C. R. & Plosser, C. I. (1982). *Journal of Monetary Economics*, 10(2), 139-162 (referencia clásica; sus datos aún no se usan en las pruebas, ver T082).
- Dickey, D. A. & Pantula, S. G. (1987). Determining the order of differencing in autoregressive processes. *JBES*, 5(4), 455-461.
- Dolado, J., Jenkinson, T. & Sosvilla-Rivero, S. (1990). Cointegration and unit roots. *Journal of Economic Surveys*, 4(3), 249-273.
- Lee, J. & Strazicich, M. C. (2003). Minimum LM unit root test with two structural breaks. *REStat*, 85(4), 1082-1089.
- Engle, R. F. (1982). *Econometrica*, 50(4), 987-1007 (ARCH-LM sobre residuos).
