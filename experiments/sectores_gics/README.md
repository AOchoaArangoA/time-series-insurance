# Experimento exploratorio: ETFs sectoriales GICS y ciclo de mercado

Pre-registrado y ejecutado el 2026-11-17 con `tsinsurance` 0.2.0 (en desarrollo, MVP de
la spec 004).

**Qué se probó:**
- reglas de tendencia y momentum en los 9 ETFs Select Sector SPDR con historia desde
  1999;
- modelos de ciclo (tasa a 10 años y VIX) para XLF, XLU y XLK.

Calibración 1999-2014 y validación 2015-2026.

**Resultado:** ninguna regla tiene habilidad de timing significativa tras el ajuste por
pruebas múltiples. Los modelos de ciclo tienen R² fuera de muestra negativo. XLK sale
"solo estadística": acierta la dirección, pero sin valor económico.

**Advertencias (resultado `20261117T192634Z-fc940b`, previo a US2):**
- El estado "confirmatorio" del informe es engañoso: los modelos econométricos se
  evaluaron sobre toda la ventana. La US2 de la spec 004 ya lo corrige: hoy `run` sólo
  calibra y la validación se abre con `experiment validate`.
- Las 49 advertencias de calidad de datos eran falsos positivos en caídas reales (2008,
  2020). Con la regla nueva (escala local, sin movimientos de todo el mercado) son 0.
- Para estos activos, el periodo 2015-2026 **ya fue visto**: toda validación futura con
  ese corte saldrá exploratoria automáticamente.

```bash
uv run tsinsurance bundle fetch experiments/sectores_gics/recipe.toml experiments/sectores_gics/data
uv run tsinsurance experiment run experiments/sectores_gics/experiment.toml
uv run python experiments/sectores_gics/analisis_exploratorio.py salida.json   # rotación y ciclos (no registrado)
```

Los datos de Yahoo no se versionan (`data/` está ignorado).

## Rotación sectorial y regímenes con el flujo registrado (spec 005)

`rotacion_regimenes.toml` repite lo que el análisis exploratorio hizo fuera de la
bitácora, ahora con las salvaguardas del paquete:

- **Rotación** por momentum relativo (L 6/12 meses, k 3/4) frente a los 9 sectores igual
  ponderados, con los mismos costos y rebalanceo mensual. Las 4 configuraciones del
  script exploratorio se **declaran** (`[[declared_prior_tests]]`), así que N = 8.
- **Regímenes**: curva invertida (^TNX − ^IRX < 0), VIX > 20/25/30 (malla completa
  declarada) y SPY bajo su media de 10 meses, para los 9 sectores. Se usa HC3, y el Holm
  incluye las variantes previas y las 33 pruebas declaradas.

Resultados:
- **Calibración** (`20261117T201317Z-2133a5`, 1999-2014): rotación con IR ≈ 0,00 frente
  al igual ponderado (DSR 0,29; SPA p 0,68). Ningún régimen sobrevive a Holm (la menor p
  sin ajustar es XLU con VIX alto, p ≈ 0,09), así que ninguno pasa a la validación.
- **Validación** (`20261117T201350Z-2133a5-val`, 2015-2026): rotación con Sharpe 0,64
  frente a 0,64 del igual ponderado (diferencia −0,01; p 0,56). Sale **EXPLORATORIA
  automáticamente**: el periodo ya lo vieron el experimento `sectores-gics-ciclo` y el
  análisis declarado.

Nota: las 33 pruebas de régimen se declararon sin clave de memoria, así que cuentan para
cada tipo de régimen. Es conservador (m de Holm mayor).

> **Nota (revisión de implementación, 2026-11-17).** Las ejecuciones `20261117T201317Z-2133a5`
> y `20261117T201350Z-2133a5-val` se hicieron **antes** de corregir dos cosas:
> - la validación usaba una diferencia de Sharpe, que ignora la exposición de la
>   calibración; hoy usa el IR del retorno activo;
> - los cierres de mes ignoraban los feriados de NYSE.
>
> Las conclusiones no cambian (sin evidencia; periodo ya visto), pero las cifras exactas de
> esas dos ejecuciones corresponden al código anterior. Se conservan como registro.
