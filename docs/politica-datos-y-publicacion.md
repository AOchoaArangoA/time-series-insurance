# Política de datos y publicación del repositorio

## Estado actual (2026-11-09)

| Punto | Estado |
|-------|--------|
| Visibilidad del repositorio en GitHub | **privado** |
| Rama `main` | sólo el commit inicial; todo el trabajo está en `ccr-d4f6f6a0-bg0992` |
| Licencia del código | MIT (`LICENSE`) |
| Credenciales en el repositorio | ninguna (verificado: la clave de FRED nunca se versionó) |

## Datos de terceros versionados

| Ubicación | Contenido | ¿Redistribuible? |
|-----------|-----------|------------------|
| `examples/data/yahoo_etfs/` | precios de 8 ETFs (Yahoo Finance) | **No** (términos de Yahoo: uso personal) |
| `examples/data/fred_daily/` | DTB3, DGS10, T10Y2Y (dominio público) y **BAA10Y** (Moody's, con derechos de autor) | Parcial: BAA10Y **no** |
| `examples/data/fred_monthly/` | CPIAUCNS (BLS, dominio público) | Sí |
| `examples/data/fred_gs10/` | GS10 (Federal Reserve, dominio público) | Sí |
| `experiments/*/data/` | paquetes con datos de Yahoo | No se versionan (`.gitignore`) |

Los datos de los paquetes nuevos declaran `license` y `redistributable` por serie; un
paquete es redistribuible sólo si todas sus series lo son (`Bundle.redistributable`).

## Pasos para hacer público el repositorio

1. **Retirar datos no redistribuibles**: eliminar `examples/data/yahoo_etfs/` y la serie
   BAA10Y de `examples/data/fred_daily/`, reemplazándolos por recetas
   (`recipe.toml`) que cada usuario ejecuta localmente; las pruebas que dependen de esos
   datos se omiten si el paquete no existe (como `tests/integration/test_inverse_treasury_experiment.py`).
2. **Historial**: esos archivos están en el historial de la rama de trabajo. Para no
   publicarlos, integrar en `main` con un *squash merge* desde una rama limpia y
   eliminar la rama de trabajo (GitHub conserva las referencias de PR; si eso importa,
   crear un repositorio público nuevo a partir de `main` limpio).
3. **Fusionar** la rama de trabajo en `main` mediante un PR revisado.
4. **Cambiar la visibilidad** en GitHub: *Settings → General → Danger Zone → Change
   repository visibility → Public* (sólo el dueño puede hacerlo).
5. **Opcional**: publicar en PyPI (`uv build` + `uv publish`) para que cualquier proyecto
   lo instale con `pip install tsinsurance`; mientras tanto se instala desde GitHub:
   `pip install "tsinsurance @ git+https://github.com/AOchoaArangoA/time-series-insurance"`.
6. Rotar la clave de FRED compartida en la conversación de desarrollo.
