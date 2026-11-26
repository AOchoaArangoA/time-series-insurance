# Riesgo de tasa con el Tesoro de EE. UU. (spec 007, US7)

Demostración de la cadena completa de procesos estocásticos, simulación y sensibilidades
sobre cuatro nodos del Tesoro (CBOE vía Yahoo):

| Serie | Plazo | Convención |
|---|---|---|
| ^IRX | 13 semanas | tasa de descuento act/360 (letra a 91 días) |
| ^FVX | 5 años | rendimiento par semestral |
| ^TNX | 10 años | rendimiento par semestral |
| ^TYX | 30 años | rendimiento par semestral (sin emisión entre 2002 y 2006) |

```bash
uv run --extra yahoo tsinsurance bundle fetch experiments/tesoro_riesgo/recipe.toml experiments/tesoro_riesgo/data
uv run python experiments/tesoro_riesgo/demo.py --asof 2026-10-30
```

Los datos de Yahoo no son redistribuibles: `data/` no se versiona. Los resultados quedan
en `results/<asof>/` (`report.md`, `result.json`).

**Qué hace.**

1. Vasicek bajo ℙ con IC por bootstrap paramétrico, *jackknife* y diagnósticos FR-001b.
2. Regímenes de Markov mensuales (pseudo-filtrados: los parámetros usan toda la muestra).
3. Calibración ℚ: precio de mercado del riesgo λ con σ_ℚ = σ_ℙ, valorando el par
   semestral y la tasa de descuento según su convención.
4. Factores PCA y Diebold-Li (λ fija) de los cambios diarios.
5. Cartera de bonos de una aseguradora: PV, DV01, KRD y duración de Fisher-Weil.
6. VaR y ES a 10 días con cuatro motores de escenarios y revaluación completa.
7. Backtesting del VaR 99 % a 1 día con histórica filtrada EWMA, punto en el tiempo y
   sensibilidades re-estimadas cada mes (Kupiec, Christoffersen y duraciones).
8. Estrés (paralelo, pendiente, curvatura y factores) e inmunización por KRD.

**Qué NO hace.** No recomienda asignaciones. Cualquier regla que use estas salidas
(*tilt* de duración, valor relativo) es una idea y debe pasar por `tsinsurance experiment`
con dos fases, costos y pruebas múltiples (FR-017).

**Lecturas del 2026-10-30.**

- Desde 2009, κ no está identificado (φ̂ ≥ 1). Con toda la muestra, κ ≈ 0,07 con un IC
  [0,04; 0,73] y r_t resulta I(1): la reversión a la media es un supuesto, no un hecho de
  los datos. El pronóstico a 1 mes no supera al paseo aleatorio.
- Vasicek de un factor ajusta la curva con errores de 20 a 33 pb en los nodos largos.
- El Monte Carlo de la tasa corta da un VaR menor que los motores multifactoriales,
  porque mueve la curva rígidamente.
- La histórica filtrada EWMA pasa el backtesting a 1 día (1,2 % de excepciones frente
  al 1 %).
