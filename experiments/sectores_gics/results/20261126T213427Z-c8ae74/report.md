# Experimento sectores-gics-panel

**Hipótesis (pre-registrada)**: H1: tras una subida del Tesoro a 10 años en el mes t, los sectores sensibles a tasas
(XLF, XLRE, XLU) rinden MENOS que los demás en el mes t+1.
H2: tras una subida del VIX en el mes t, los sectores defensivos (XLP, XLU, XLV) rinden MÁS
que los demás en el mes t+1.
Expectativa previa: efectos pequeños o nulos con un mes de rezago (la reacción contemporánea
es más plausible que la predictiva).


- Ejecución `20261126T213427Z-c8ae74` · experimento sha256 c8ae741ad949… · paquete `sectores_gics` (sha256 e60a270bf66b…) · tsinsurance 0.2.0 · semilla 17
- Supuestos: retraso=1 barra(s), costo=5.0 pb, deslizamiento=0.0 pb, rebalanceo=every_bar, bruto máx.=1.0, cortos=no, financiación=rf+0.0 pb
- Selección y pruebas múltiples sobre datos hasta 2014-12-31; validación única desde 2014-12-31
- Pruebas previas en la bitácora por activo: {'XLB': 8, 'XLE': 8, 'XLF': 8, 'XLI': 8, 'XLK': 8, 'XLP': 8, 'XLU': 8, 'XLV': 8, 'XLY': 8, 'U:XLB+XLE+XLF+XLI+XLK+XLP+XLU+XLV+XLY': 4}

## Conclusión automática

- Estado: EXPLORATORIO — diagnósticos del panel 'tasas_vix' no superados · validación fuera de muestra PENDIENTE (aún no hay evidencia confirmatoria)
- Ideas con timing significativo (DSR > 1−α y SPA-Holm < α): ninguna
- Modelos econométricos: n/d
- La ganancia CER no tiene inferencia propia; en activos apalancados refleja sobre todo la penalización de varianza, no habilidad.

## Panel `tasas_vix` (TWFE, errores driscoll_kraay, 11 unidades)

- Variable dependiente: exceso de retorno del mes siguiente · justificación: Duración y apalancamiento de los sectores regulados y de bienes raíces (H1); huida a la calidad
hacia sectores de demanda inelástica (H2). Hipótesis y signos fijados antes de estimar el panel.
- Pruebas previas en el Holm (misma memoria): 0 · α de la familia de paneles = 0.0500 · diagnósticos NO superados

| Hipótesis | Estimación | ee | t | p unilateral | p WCR (sensibilidad) | G₁ | p Holm |
|---|---|---|---|---|---|---|---|
| ^TNX:tasas - | +0.0018 | 0.0095 | +0.19 | 0.586 (wild bootstrap DK (rademacher, bloques de 5 periodos; B = 9999)) | 0.723 | 2 | 0.586 |
| ^VIX:defensivo + | +0.0008 | 0.0007 | +1.16 | 0.131 (wild bootstrap DK (rademacher, bloques de 5 periodos; B = 9999)) | 0.016 | 3 | 0.262 |

- Advertencia: Unidades sin datos en esta ventana: ['XLC', 'XLRE']
- Advertencia: Regresores absorbidos y excluidos: ['^TNX', '^VIX']
- Advertencia: WCR de ^TNX:tasas con G₁ = 2: poco confiable (MacKinnon y Webb 2017).
- Advertencia: Dependencia transversal fuerte (CD de Pesaran): los errores agrupados por unidad no son válidos; use Driscoll-Kraay o efectos de tiempo.
- Advertencia: Con efectos de tiempo, la CD clásica no es válida (Juodis y Reese 2022); se reporta la CD sin efectos de tiempo.
- Advertencia: ARCH en los residuos de la mayoría de las unidades.

- Lectura causal: los efectos fijos de unidad quitan confusores constantes en el tiempo, no los que cambian ni la causalidad inversa (Facure, cap. 14); las interacciones estiman efectos diferenciales.

## Próximo paso: validación única

Las configuraciones quedaron fijadas en la bitácora. Para evaluarlas UNA vez en el periodo posterior a 2014-12-31, confirme los cambios en git y ejecute:

```bash
tsinsurance experiment validate /home/user/time-series-insurance/experiments/sectores_gics/panel_sectores.toml --calibration 20261126T213427Z-c8ae74
```

