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

**Advertencias:**
- El estado "confirmatorio" del informe es engañoso: los modelos econométricos se
  evaluaron sobre toda la ventana, que es el defecto que corrige la spec 004 (US2).
- Las 49 advertencias de calidad de datos son falsos positivos en caídas reales (2008,
  2020).

```bash
uv run tsinsurance bundle fetch experiments/sectores_gics/recipe.toml experiments/sectores_gics/data
uv run tsinsurance experiment run experiments/sectores_gics/experiment.toml
uv run python experiments/sectores_gics/analisis_exploratorio.py salida.json   # rotación y ciclos (no registrado)
```

Los datos de Yahoo no se versionan (`data/` está ignorado).
