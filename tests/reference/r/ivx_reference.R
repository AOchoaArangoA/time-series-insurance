# Valores de referencia de la prueba IVX (Kostakis, Magdalinos y Stamatogiannis 2015)
# con el paquete ivx de R. Ejecutar desde la raíz del repositorio:
#   Rscript tests/reference/r/ivx_reference.R
# Escribe tests/data/reference/ivx_*.json, que las pruebas de Python leen sin necesitar R.
suppressPackageStartupMessages({ library(ivx); library(jsonlite) })
dir <- "tests/data/reference"
out <- function(m, file, extra = list()) {
  s <- summary(m)
  res <- c(list(
    r_version = R.version.string,
    ivx_version = as.character(packageVersion("ivx")),
    coefficients = as.list(coef(m)),
    wald_individual = as.list(m$Wald_Ind),
    wald_joint = unname(m$Wald_Joint),
    df = m$df,
    p_individual = as.list(s$coefficients[, "Pr(> chi)"]),
    p_joint = unname(s$pv_waldjoint),
    Rz = as.list(m$AR$Rz),
    Rn = as.list(m$AR$Rn),
    delta = as.list(m$delta),
    n = NROW(m$data$X)
  ), extra)
  write_json(res, file.path(dir, file), auto_unbox = TRUE, digits = NA, pretty = TRUE)
}
sim <- read.csv(file.path(dir, "ivx_sim_input.csv"))
out(ivx(y ~ x1, data = sim), "ivx_sim_one.json", list(input = "ivx_sim_input.csv", formula = "y ~ x1"))
out(ivx(y ~ x1 + x2, data = sim), "ivx_sim_two.json", list(input = "ivx_sim_input.csv", formula = "y ~ x1 + x2"))
gs <- read.csv(file.path(dir, "ivx_gs10_input.csv"))
out(ivx(y ~ x, data = gs), "ivx_gs10.json", list(input = "ivx_gs10_input.csv", formula = "y ~ x"))
cat("ok\n")
