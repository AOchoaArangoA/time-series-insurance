# Research: Motor econométrico núcleo (001)

Fase 0 del plan. Cada decisión: **Decision / Rationale / Alternatives considered**.

## R1. Pruebas de raíz unitaria y estacionariedad

- **Decision**: ADF (`statsmodels.tsa.stattools.adfuller`, rezagos por AIC), Phillips-Perron
  (`arch.unitroot.PhillipsPerron`), KPSS (`statsmodels.tsa.stattools.kpss`, rezagos
  automáticos de Hobijn et al.) y Zivot-Andrews (`statsmodels.tsa.stattools.zivot_andrews`).
  Regla de decisión confirmatoria (ADF/PP vs KPSS) con cuatro resultados: `I(0)`, `I(1)`,
  `inconcluso`, y aplicación recursiva sobre la primera diferencia hasta `d_max = 2`.
- **Rationale**: Nulas opuestas reducen el error de decisión (Principio I); librerías
  validadas contra tablas de MacKinnon (1996, 2010).
- **Alternatives considered**: DF-GLS (Elliott-Rothenberg-Stock) — se expone como opción
  adicional, no como default; implementar pruebas propias — rechazado (Principio V).

## R2. Modelos de media (ARIMA/SARIMA)

- **Decision**: `statsmodels.tsa.arima.model.ARIMA` / `SARIMAX` con búsqueda en malla
  acotada (p, q ≤ 5; P, Q ≤ 2) por AIC/BIC/HQIC; orden `d` tomado del diagnóstico R1.
- **Rationale**: Estimación por máxima verosimilitud exacta (filtro de Kalman), errores
  estándar y pronósticos con intervalos analíticos ya disponibles.
- **Alternatives considered**: `pmdarima.auto_arima` — rechazado por mantenimiento
  irregular y porque decide `d` con una sola prueba; `statsforecast` — más rápido pero
  menos diagnósticos; se podrá evaluar como backend opcional.

## R3. Modelos de volatilidad (GARCH)

- **Decision**: `arch.arch_model` para GARCH, EGARCH, GJR-GARCH con distribuciones
  normal, t y t asimétrica de Hansen; media constante, AR o cero. Reintentos con valores
  iniciales alternativos ante no convergencia; errores estándar robustos (Bollerslev-
  Wooldridge) por defecto.
- **Rationale**: Referencia de facto en Python, validada contra literatura.
- **Alternatives considered**: implementación propia — rechazada; `rugarch` vía rpy2 —
  sólo como referencia para pruebas de regresión fuera de CI.

## R4. Diagnósticos de residuos

- **Decision**: Ljung-Box (`acorr_ljungbox`, `model_df = p + q`), ARCH-LM (`het_arch`),
  Jarque-Bera (`scipy.stats.jarque_bera`), CUSUM de residuos OLS
  (`breaks_cusumolsresid`). Para GARCH, Ljung-Box sobre residuos estandarizados y sus
  cuadrados. Indicador global `apto` = ninguna prueba crítica (LB, ARCH-LM) rechaza al 5 %;
  JB informa pero no bloquea cuando la distribución supuesta es de colas pesadas.
- **Rationale**: Cumple Principio I con una regla de aptitud explícita y documentada.

## R5. Validación temporal y comparación de pronósticos

- **Decision**: Motor propio `rolling_origin` (ventana expansiva o móvil, paso
  configurable, re-estimación configurable) que recibe una *fábrica* de modelos y sólo
  pasa datos `<= origen`. Métricas RMSE, MAE, MASE (escala del naive en la muestra de
  entrenamiento). Diebold-Mariano con corrección de Harvey-Leybourne-Newbold y varianza
  HAC; benchmarks: random walk y media histórica.
- **Rationale**: Garantiza ausencia de fuga (Principio II) por construcción, y es
  testeable con un modelo "espía" que falla si ve datos futuros.
- **Alternatives considered**: `sktime`/`darts` — dependencias pesadas, menor control
  sobre la fuga y los diagnósticos.

## R6. VaR / ES y backtesting

- **Decision**: Métodos histórico, paramétrico (normal/t, con ajuste Cornish-Fisher
  opcional) y condicional al GARCH (cuantil de la distribución estimada). Portafolio por
  agregación de retornos ponderados (v1) y, opcionalmente, varianza-covarianza.
  Backtesting propio: Kupiec POF, Christoffersen independencia y cobertura condicional,
  zonas semáforo de Basilea (binomial acumulada, umbrales 95 % / 99,99 %). ES: prueba
  de Acerbi-Szekely Z2 por simulación.
- **Escalado a horizonte largo**: raíz del tiempo (con advertencia explícita de supuesto
  i.i.d.) o simulación del GARCH ajustado con semilla.
- **Rationale**: No existe una implementación Python consolidada de estas pruebas; son
  fórmulas cerradas cortas que se validan contra ejemplos publicados (Jorion; Christoffersen
  1998) — excepción justificada al Principio V.

## R7. Contrato de datos (esquema de insumos)

- **Decision**: `pandera` (API de `DataFrameModel`) para definir esquemas versionados de
  insumos: `MarketSeriesSchema` (formato largo: fecha, serie_id, valor, unidad, moneda,
  frecuencia), `PortfolioSchema` (activo, peso o monto, moneda, fecha_corte) y
  `RateNodesSchema` (fecha, plazo_años, tasa, convención) para interoperar con el futuro
  paquete de curvas. Validación *lazy* para reportar todos los errores con fila, columna
  y regla (SC-008). Exportación a JSON Schema / Frictionless Table Schema y generación de
  plantillas CSV/Excel.
- **Rationale**: Validación declarativa de DataFrames con reporte de errores detallado;
  el esquema publicado sirve como contrato entre paquetes.
- **Alternatives considered**: `pydantic` (orientado a registros, no a DataFrames);
  validación manual (frágil, sin reporte estructurado).

## R8. Conectores de datos públicos y replicabilidad

- **Decision**: Interfaz `DataSource` (protocolo) con implementaciones `CSVSource`,
  `ExcelSource`, `FredSource` (endpoint REST oficial, clave en `FRED_API_KEY`) y
  `YahooSource` (`yfinance`, extra opcional). Registro de conectores por *entry points*
  (`tsinsurance.sources`) para añadir bancos centrales sin tocar el núcleo. Cada
  descarga produce un `Snapshot` (Parquet + metadatos JSON: fuente, ids, rango, fecha de
  consulta, hash SHA-256) que los ejercicios versionan en `examples/data/`.
- **Rationale**: Cumple FR-019/019a; las pruebas de CI usan snapshots, nunca red.
- **Alternatives considered**: `pandas-datareader` — mantenimiento inactivo y roturas
  frecuentes con Yahoo; descargar sin snapshot — no replicable.

## R9. Perfiles de jurisdicción

- **Decision**: `JurisdictionProfile` (dataclass inmutable, cargable desde TOML) con nivel
  de confianza, horizonte, moneda base, calendario de días hábiles y choques de estrés.
  Perfil `generic` por defecto (99,5 %, 1 año, 252 días). Ningún módulo lee constantes
  regulatorias fuera del perfil.
- **Rationale**: FR-018 (v1 agnóstica); permite añadir perfiles nacionales sin código.

## R10. Reportes reproducibles

- **Decision**: Objeto `AnalysisReport` serializable a JSON (canónico, claves ordenadas)
  y renderizable a Markdown/HTML con plantillas `string.Template` (sin dependencia
  extra); incluye hash de datos, versión del paquete y de dependencias clave, semilla y
  perfil.
- **Alternatives considered**: Jinja2/Quarto — se pueden añadir en la spec 006.
