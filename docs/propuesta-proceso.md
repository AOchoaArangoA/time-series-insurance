# Propuesta del proceso completo

De una idea de inversión a una decisión documentada, con humanos y agentes de IA
trabajando sobre el mismo flujo auditable.

## 1. Visión general

```text
 Idea / hipótesis ─▶ Receta de datos ─▶ PAQUETE DE INSUMOS ─▶ experiment.toml ─▶ Ejecución
   (humano o agente)   (única parte que      (formato base,       (ideas, modelos,     │
                        depende de la         independiente        supuestos,          │
                        fuente)               de la fuente)        validación)         ▼
                                                                         ┌──────────────────────┐
                                                                         │ salvaguardas         │
                                                                         │ · anticipación       │
                                                                         │ · punto en el tiempo │
                                                                         │ · costos explícitos  │
                                                                         │ · pruebas múltiples  │
                                                                         │ · validación única   │
                                                                         └─────────┬────────────┘
                                                                                   ▼
  Comité / decisión ◀── report.md (humanos) ◀── result.json (agentes) ◀── registry.jsonl
                                                                         (bitácora permanente:
                                                                          alimenta el DSR de
                                                                          los experimentos
                                                                          siguientes)
```

## 2. Etapas, responsables y artefactos

| # | Etapa | Responsable | Artefacto | Control |
|---|-------|-------------|-----------|---------|
| 1 | Hipótesis | analista o agente | `experiment.toml` → `hypothesis` | escrita antes de ver la validación |
| 2 | Datos | ingeniería de datos / agente | `recipe.toml` o archivos propios | licencia y rezago de publicación por serie |
| 3 | Paquete de insumos | automático | `data/bundle.toml` + `market_series.csv` | `tsinsurance bundle validate` (contrato, manifiesto, huella) |
| 4 | Diseño del experimento | analista o agente | `experiment.toml` | señales registradas, supuestos explícitos, `train_end` fijo |
| 5 | Ejecución | `tsinsurance experiment run` | `results/<run_id>/` | anticipación por idea, DSR/SPA con bitácora, calibración/validación |
| 6 | Registro | automático | `experiments/registry.jsonl` | sólo agregado; identidad = activo + idea + parámetros |
| 7 | Revisión | validador / subagente `econometrics-reviewer` | comentarios en el PR | constitución, principios I-VIII |
| 8 | Decisión | comité de inversiones | `report.md` | veredicto doble y marcas (exploratorio, no concluyente) |

**Entrega a otro agente.** Un agente nuevo necesita sólo `AGENTS.md` (o la habilidad
`.claude/skills/tsinsurance-experiment`) y el repositorio: crea la receta o el paquete,
escribe `experiment.toml`, ejecuta, lee `result.json` y respeta las reglas (no tocar la
bitácora, no mover `train_end`, declarar especificaciones). La bitácora es el mecanismo
por el que "se alimenta del proceso": cada experimento hereda lo probado antes.

## 3. Zoom: cómo se llama hoy la información

### 3.1 Cadena actual

```text
Yahoo Finance ── yfinance.download(ticker, start, end+1d, auto_adjust=True) ── columna Close
FRED ─────────── GET /fred/series            (frecuencia, unidades)
                 GET /fred/series/observations (valores; "." ⇒ faltante)
Archivo propio ─ CSV / Excel leído como texto
        │
        ▼  DataSource.fetch(ids, start, end)          src/tsinsurance/data/sources/*.py
DataFrame en el contrato "market" v1.0 (formato largo)
        │  load(): validación pandera (tipos, dominios, unicidad, monotonía, precio > 0)
        ▼
Snapshot (datos + fuente + consulta + fecha de consulta + SHA-256)   data/snapshot.py
        │  Bundle.from_snapshots(..., declaraciones por serie)
        ▼
PAQUETE DE INSUMOS  bundle.toml + market_series.csv                   data/bundle.py
        │  Bundle.load(): contrato + coherencia manifiesto/datos + huella
        ├─ assets()     → precios anchos por activo (NaN antes del inicio)
        ├─ exogenous()  → Exogenous(disponible = fin de periodo + release_lag, transformación por fecha)
        └─ risk_free()  → tasa por día hábil (convención declarada), disponible con su rezago
        ▼
Señales / modelos → motor de backtesting → inferencia → veredicto
```

### 3.2 Hallazgos del acercamiento

| Punto | Situación | Propuesta |
|-------|-----------|-----------|
| Dependencia de la fuente | Antes los ejemplos leían instantáneas por fuente (`yahoo_etfs`, `fred_daily`) y armaban las variables en código | **Paquete de insumos** como única entrada del análisis; las fuentes sólo aparecen en la receta |
| Semántica de cada serie | Estaba implícita en el código (qué es activo, qué es rf, qué rezago) | Declarada en el manifiesto (`role`, `release_lag`, `transform`, `rf_convention`) |
| Licencias | No se registraban | `license` y `redistributable` obligatorios por serie |
| Precios de Yahoo | `Close` ajustado por dividendos: aproxima retorno total pero **se recalcula hacia atrás** con cada dividendo; una descarga posterior cambia la huella | Versionar la receta y la huella del paquete usado en cada ejecución (queda en `result.json` y la bitácora); para producción, una fuente con precios de retorno total versionados |
| Yahoo no oficial | Límites de tasa (HTTP 429 observado), cambios de API | Tratarla como fuente de exploración; el formato base permite cambiar a Bloomberg/Refinitiv/archivo interno sin tocar el análisis |
| Revisiones (vintages) | FRED entrega la versión actual | Usar series sin revisión o marcar `point_in_time = false`; soporte ALFRED pendiente (T046) |
| Moneda | Los conectores asumen USD por defecto | Declararla en la receta (`[fetch.options] currency = "..."`) |

### 3.3 Formato base propuesto (v1.0)

```text
mi_paquete/
├── bundle.toml          # manifiesto (ver AGENTS.md para los campos)
└── market_series.csv    # date,series_id,value,kind,unit,currency,frequency,source
```

- Cualquier proveedor se integra escribiendo un adaptador `DataSource` (o exportando
  directamente este CSV y su manifiesto).
- El contrato del CSV ya está publicado (`tsinsurance schema market`) y tiene plantillas
  (`tsinsurance template market`, `tsinsurance bundle template`).
- Extensiones previstas (mismo manifiesto): `portfolio.csv` y `rate_nodes.csv` (contratos
  ya definidos) para ALM y para el paquete hermano de curvas.

## 4. Gobernanza

- **Especificación primero** (Spec Kit): cada capacidad nueva pasa por
  `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.
- **Revisión independiente**: el subagente `econometrics-reviewer` revisa diseño e
  implementación antes de integrar (en este proyecto encontró 11 bloqueantes y 35
  importantes en cuatro revisiones; todos corregidos o registrados como tareas).
- **Bitácora**: única fuente de verdad de lo probado; respaldarla junto con el código.
- **Publicación**: ver `docs/politica-datos-y-publicacion.md`.

## 5. Próximos pasos propuestos

1. Confirmar TFT → TBT y la publicación del repositorio (licencia, datos, rama principal).
2. Fusionar la rama de trabajo en `main` mediante un PR revisado.
3. Spec 001 US2-US5 (ARIMA/GARCH, pronóstico, VaR/ES, reportes de comité).
4. Adaptador para la fuente de datos oficial de la aseguradora (precios de retorno total
   versionados) y vintages ALFRED.
5. Ejecutor programado: experimentos re-ejecutados periódicamente con datos nuevos y
   seguimiento de su desempeño fuera de muestra real (*paper trading*).
