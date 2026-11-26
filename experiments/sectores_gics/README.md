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

## Panel sectorial con efectos fijos de dos vías (spec 006, `panel_sectores.toml`)

Pregunta: ¿los sectores **sensibles a tasas** (XLF, XLRE, XLU) y los **defensivos** (XLP,
XLU, XLV) reaccionan de forma **diferencial**, en el mes siguiente, a los cambios del
Tesoro a 10 años y del VIX? Con efectos de tiempo, los efectos comunes de las variables
macro quedan absorbidos: sólo se identifican las interacciones (efecto diferencial;
Facure, cap. 14).

- Inferencia principal: t de Driscoll-Kraay con corrección por grados de libertad y wild
  bootstrap por bloques de periodos (B = 9 999).
- Sensibilidad: wild cluster bootstrap por sector, que no es válido con el factor de
  mercado común.
- G₁ ≥ 2 en cada característica. XLRE y XLC nacen después de 2014: en la calibración,
  G₁ = 2 para "tasas".
- Reclasificación GICS de 2016 y 2018: la característica es la del sector actual.

| Hipótesis | Calibración 1999-2014 | Validación 2015-2026 |
|---|---|---|
| ^TNX:tasas (signo −) | +0,0018, p = 0,59 (WCR 0,72) | +0,0075, p = 0,72; MDE 0,031 (poca potencia) |
| ^VIX:defensivo (signo +) | +0,0008, p = 0,13 (WCR **0,016**) | +0,0002, p = 0,36; MDE 0,0022 (poca potencia) |

- Calibración `20261126T213427Z-c8ae74` y validación `20261126T213440Z-c8ae74-val`.
- Ambas son **EXPLORATORIAS**:
  - los diagnósticos no se superan (ARCH en la mayoría de los sectores, dependencia
    transversal fuerte);
  - el periodo 2015-2026 ya se había visto en los experimentos anteriores de esta
    carpeta; la herramienta lo detecta por sector.
- **Lectura**: no hay evidencia de sensibilidad diferencial con un mes de rezago.
- El caso del VIX muestra por qué el WCR es sólo una sensibilidad: con el factor común
  de mercado, el WCR por sector da p = 0,016, mientras que DK con bootstrap por periodos
  da 0,13. El primero ignora la dependencia entre sectores.
