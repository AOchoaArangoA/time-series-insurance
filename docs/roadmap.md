# Hoja de ruta de especificaciones

Cada fila se convierte en una especificación con `/speckit-specify`.

| # | Especificación | Contenido principal | Estado |
|---|----------------|---------------------|--------|
| 001 | Motor econométrico núcleo | Contrato de datos, conectores replicables, estacionariedad, ARIMA/GARCH, pronóstico, validación temporal, VaR/ES | US1 implementada; US2-US5 pendientes |
| 002 | Backtesting responsable | Señales de tendencia/volatilidad, modelos econométricos con macro punto-en-el-tiempo, anticipación, PSR/DSR/SPA, Clark-West, veredicto doble, ETFs reales | Implementada (v0.1) |
| — | Curvas de rendimiento (paquete hermano) | Nelson-Siegel, Svensson, Smith-Wilson; se comunica vía `RateNodesSchema` | Fuera de este repo |
| 003 | Experimentos registrados, insumo base y entrega a agentes | Paquete de insumos, `experiment.toml`, bitácora, AGENTS.md | Implementada (v0.1) |
| 004 | Integridad del procedimiento y datos en tiempo real | Bitácora a prueba de recortes, validación única en dos fases, huella de señales, ALFRED (primera publicación y todas las versiones), IVX, preblanqueo, varianza del DSR | Especificada (2026-11-17) |
| 005 | Ideas de cartera y regímenes del ciclo | Rotación y carteras sobre un universo con memoria de pruebas por universo; estados del ciclo punto-en-el-tiempo con HAC y Holm; dos fases | Especificada (2026-11-17) |
| 006 | Datos de panel con efectos fijos y aleatorios | FE de unidad y tiempo, RE, Hausman/Mundlak, Driscoll-Kraay y wild cluster bootstrap, diferencias en diferencias; panel sectores × meses (Facure cap. 13-14; Wooldridge 2010) | Especificada (2026-11-26) |
| 007 | Procesos estocásticos, simulación y sensibilidades (MVP) | Vasicek/CIR/Hull-White (ℙ y ℚ), regímenes de Markov, simulación histórica/filtrada/Monte Carlo con reducción de varianza, PCA y Diebold-Li (λ fija), Δ/ΔΓ, duración/convexidad/KRD, VaR/ES con backtesting, estrés e inmunización. Absorbe la antigua "dinámica de tasas por plazo" | Especificada (2026-11-26) |
| 008 | Crédito y extensiones estocásticas | Intensidad (hazard), migraciones de Markov, modelos estructurales, afines con saltos, filtraje de estados latentes (Kalman/HMM), importance sampling | Pendiente |
| 009 | Modelos multivariados | VAR/VECM, cointegración de Johansen, funciones impulso-respuesta, DCC-GARCH | Pendiente |
| 010 | Generador de escenarios económicos (ESG) | Simulación conjunta de tasas, inflación, renta variable; escenarios de estrés regulatorios | Pendiente |
| 011 | ALM y asignación estratégica | Calce activo-pasivo, duración de pasivos, optimización media-varianza / CVaR con restricciones regulatorias | Pendiente |
| 012 | Reportes y gobernanza de modelos | Reportes reproducibles para comité, inventario de modelos, validación independiente | Pendiente |
| 013 | (Opcional) Modelos de ML | Benchmarks de ML/DL sólo si superan a los econométricos (Diebold-Mariano) | Pendiente |
