# Contrato: esquema de insumos (versión 1.0)

Fuente de verdad: `tsinsurance.data.schemas`. Este documento describe lo que el usuario
debe entregar para análisis futuros (FR-019b). Definición de campos en
[data-model.md](../data-model.md#insumos-contrato-de-datos-versión-10).

## Archivos esperados

| Insumo | Archivo plantilla | Obligatorio para |
|--------|-------------------|------------------|
| Series de mercado | `market_series.csv` / `.xlsx` | todo análisis |
| Portafolio | `portfolio.csv` / `.xlsx` | VaR/ES de portafolio |
| Nodos de tasas | `rate_nodes.csv` / `.xlsx` | análisis de tasas por plazo; intercambio con paquete de curvas |

## Ejemplo `market_series.csv`

```csv
date,series_id,value,kind,unit,currency,frequency,source
2024-01-02,DGS10,3.95,rate,percent,USD,B,fred:DGS10
2024-01-02,SPX,4742.83,price,level,USD,B,yahoo:^GSPC
```

## Ejemplo `portfolio.csv`

```csv
as_of,asset_id,weight,amount,currency,asset_class
2024-06-30,SPX,0.25,,USD,equity
2024-06-30,AGG,0.70,,USD,fixed_income
2024-06-30,CASH,0.05,,USD,cash
```

## Ejemplo `rate_nodes.csv`

```csv
date,curve_id,tenor_years,rate,unit,compounding,day_count
2024-01-02,USD_TSY,0.25,5.37,percent,annual,ACT/365
2024-01-02,USD_TSY,10,3.95,percent,annual,ACT/365
```

## Reporte de validación

`tsinsurance validate` devuelve una tabla con `row`, `column`, `check`, `failure_case`
para **todos** los errores (validación lazy), y exit code 1 si hay alguno.

## Versionado

`schema_version` se incluye en cada `Snapshot` y reporte. Agregar columnas opcionales es
MINOR; cambiar nombre/tipo/regla de una columna obligatoria es MAJOR.
