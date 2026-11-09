# Política de datos y publicación del repositorio

## Estado actual (2026-11-09)

| Punto | Estado |
|-------|--------|
| Visibilidad del repositorio en GitHub | **público** |
| Rama `main` | integra todo el trabajo (v0.1.0) en un commit limpio, sin datos de terceros no redistribuibles |
| Licencia del código | MIT (`LICENSE`) |
| Credenciales en el repositorio | ninguna (verificado) |

## Datos de terceros versionados

| Ubicación | Contenido | ¿Redistribuible? |
|-----------|-----------|------------------|
| `examples/data/yahoo_etfs/` | precios de 8 ETFs (Yahoo Finance) | **No**: no se versiona; `examples/fetch_data.py` |
| `examples/data/fred_daily/` | DTB3, DGS10, T10Y2Y y **BAA10Y** (Moody's) | **No** (por BAA10Y): no se versiona; `examples/fetch_data.py` |
| `examples/data/fred_monthly/` | CPIAUCNS (BLS, dominio público) | Sí |
| `examples/data/fred_gs10/` | GS10 (Federal Reserve, dominio público) | Sí |
| `experiments/*/data/` | paquetes con datos de Yahoo | No se versionan (`.gitignore`) |

Los datos de los paquetes nuevos declaran `license` y `redistributable` por serie; un
paquete es redistribuible sólo si todas sus series lo son (`Bundle.redistributable`).

## Publicación realizada

1. Datos no redistribuibles retirados del árbol y reemplazados por recetas/scripts
   (`examples/fetch_data.py`, `experiments/*/recipe.toml`); las pruebas que los necesitan
   se omiten si no se descargaron, y las cifras publicadas sólo se comparan cuando la
   huella coincide (`examples/data/expected_sha256.json`).
2. `main` recibe el trabajo en un único commit desde una rama limpia (los datos retirados
   no están en su historial).
3. Pendiente del dueño: la rama de desarrollo `ccr-d4f6f6a0-bg0992` conserva en su
   historial las instantáneas de Yahoo/BAA10Y; eliminarla deja `main` como única fuente.
4. Opcional: publicar en PyPI (`uv build` + `uv publish`); mientras tanto se instala desde
   GitHub.
5. Rotar la clave de FRED compartida en la conversación de desarrollo.
