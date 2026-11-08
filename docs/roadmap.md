# Hoja de ruta de especificaciones

Cada fila se convierte en una especificación con `/speckit-specify`.

| # | Especificación | Contenido principal | Estado |
|---|----------------|---------------------|--------|
| 001 | Motor econométrico núcleo | Contrato de datos, conectores replicables, estacionariedad, ARIMA/GARCH, pronóstico, validación temporal, VaR/ES | US1 implementada; US2-US5 pendientes |
| 002 | Backtesting responsable | Señales de tendencia/volatilidad, modelos econométricos con macro punto-en-el-tiempo, anticipación, PSR/DSR/SPA, Clark-West, veredicto doble, ETFs reales | Implementada (v0.1) |
| — | Curvas de rendimiento (paquete hermano) | Nelson-Siegel, Svensson, Smith-Wilson; se comunica vía `RateNodesSchema` | Fuera de este repo |
| 003 | Dinámica de tasas por plazo | Diebold-Li dinámico sobre nodos, duración y convexidad del portafolio | Pendiente |
| 004 | Modelos multivariados | VAR/VECM, cointegración de Johansen, funciones impulso-respuesta, DCC-GARCH | Pendiente |
| 005 | Generador de escenarios económicos (ESG) | Simulación conjunta de tasas, inflación, renta variable; escenarios de estrés regulatorios | Pendiente |
| 006 | ALM y asignación estratégica | Calce activo-pasivo, duración de pasivos, optimización media-varianza / CVaR con restricciones regulatorias | Pendiente |
| 007 | Reportes y gobernanza de modelos | Reportes reproducibles para comité, inventario de modelos, validación independiente | Pendiente |
| 008 | (Opcional) Modelos de ML | Benchmarks de ML/DL sólo si superan a los econométricos (Diebold-Mariano) | Pendiente |
