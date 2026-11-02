# Hoja de ruta de especificaciones

Cada fila se convierte en una especificación con `/speckit-specify`.

| # | Especificación | Contenido principal | Estado |
|---|----------------|---------------------|--------|
| 001 | Motor econométrico núcleo | Contrato de datos, conectores replicables, estacionariedad, ARIMA/GARCH, pronóstico, validación temporal, VaR/ES y backtesting | Spec, plan y tareas listos |
| — | Curvas de rendimiento (paquete hermano) | Nelson-Siegel, Svensson, Smith-Wilson; se comunica vía `RateNodesSchema` | Fuera de este repo |
| 002 | Dinámica de tasas por plazo | Diebold-Li dinámico sobre nodos, duración y convexidad del portafolio | Pendiente |
| 003 | Modelos multivariados | VAR/VECM, cointegración de Johansen, funciones impulso-respuesta, DCC-GARCH | Pendiente |
| 004 | Generador de escenarios económicos (ESG) | Simulación conjunta de tasas, inflación, renta variable; escenarios de estrés regulatorios | Pendiente |
| 005 | ALM y asignación estratégica | Calce activo-pasivo, duración de pasivos, optimización media-varianza / CVaR con restricciones regulatorias | Pendiente |
| 006 | Reportes y gobernanza de modelos | Reportes reproducibles para comité, inventario de modelos, validación independiente | Pendiente |
| 007 | (Opcional) Modelos de ML | Benchmarks de ML/DL sólo si superan a los econométricos (Diebold-Mariano) | Pendiente |
