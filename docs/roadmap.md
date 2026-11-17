# Hoja de ruta de especificaciones

Cada fila se convierte en una especificación con `/speckit-specify`.

| # | Especificación | Contenido principal | Estado |
|---|----------------|---------------------|--------|
| 001 | Motor econométrico núcleo | Contrato de datos, conectores replicables, estacionariedad, ARIMA/GARCH, pronóstico, validación temporal, VaR/ES | US1 implementada; US2-US5 pendientes |
| 002 | Backtesting responsable | Señales de tendencia/volatilidad, modelos econométricos con macro punto-en-el-tiempo, anticipación, PSR/DSR/SPA, Clark-West, veredicto doble, ETFs reales | Implementada (v0.1) |
| — | Curvas de rendimiento (paquete hermano) | Nelson-Siegel, Svensson, Smith-Wilson; se comunica vía `RateNodesSchema` | Fuera de este repo |
| 003 | Experimentos registrados, insumo base y entrega a agentes | Paquete de insumos, `experiment.toml`, bitácora, AGENTS.md | Implementada (v0.1) |
| 004 | Integridad del procedimiento y datos en tiempo real | Bitácora a prueba de recortes, validación única en dos fases, huella de señales, ALFRED (primera publicación y todas las versiones), IVX, preblanqueo, varianza del DSR | Especificada (2026-11-17) |
| 005 | Dinámica de tasas por plazo | Diebold-Li dinámico sobre nodos, duración y convexidad del portafolio | Pendiente |
| 006 | Modelos multivariados | VAR/VECM, cointegración de Johansen, funciones impulso-respuesta, DCC-GARCH | Pendiente |
| 007 | Generador de escenarios económicos (ESG) | Simulación conjunta de tasas, inflación, renta variable; escenarios de estrés regulatorios | Pendiente |
| 008 | ALM y asignación estratégica | Calce activo-pasivo, duración de pasivos, optimización media-varianza / CVaR con restricciones regulatorias | Pendiente |
| 009 | Reportes y gobernanza de modelos | Reportes reproducibles para comité, inventario de modelos, validación independiente | Pendiente |
| 010 | (Opcional) Modelos de ML | Benchmarks de ML/DL sólo si superan a los econométricos (Diebold-Mariano) | Pendiente |
