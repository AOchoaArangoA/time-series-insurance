# Valores de referencia del EE HAC del Sharpe (por periodo) con el paquete sandwich de R.
# HAC sobre la función de influencia escalar psi_t = grad' z_t, z_t = (r_t - m1, r_t^2 - m2)
# (spec 004, revisión I9). Ejecutar desde la raíz del repositorio:
#   Rscript tests/reference/r/prewhite_reference.R
suppressPackageStartupMessages({ library(sandwich); library(jsonlite) })
dir <- "tests/data/reference"
r <- read.csv(file.path(dir, "prewhite_input.csv"))$r
n <- length(r)
m1 <- mean(r); m2 <- mean(r^2); sigma <- sqrt(m2 - m1^2)
grad <- c(m2 / sigma^3, -m1 / (2 * sigma^3))
psi <- grad[1] * (r - m1) + grad[2] * (r^2 - m2)
fit <- lm(psi ~ 1)
L <- floor(4 * (n / 100)^(2 / 9))
nw <- NeweyWest(fit, lag = L, prewhite = FALSE, adjust = FALSE)
pw <- kernHAC(fit, prewhite = 1, kernel = "Quadratic Spectral", bw = bwAndrews,
              adjust = FALSE, ar.method = "ols")
bw <- bwAndrews(fit, kernel = "Quadratic Spectral", prewhite = 1, ar.method = "ols")
res <- list(
  r_version = R.version.string,
  sandwich_version = as.character(packageVersion("sandwich")),
  input = "prewhite_input.csv",
  n = n,
  sharpe_per_period = m1 / sigma,
  newey_west_lags = L,
  se_newey_west = sqrt(nw[1, 1]),
  se_prewhitened_qs = sqrt(pw[1, 1]),
  andrews_bandwidth = bw,
  settings = "kernHAC(prewhite=1, kernel='Quadratic Spectral', bw=bwAndrews, adjust=FALSE, ar.method='ols')"
)
write_json(res, file.path(dir, "prewhite_reference.json"), auto_unbox = TRUE, digits = NA, pretty = TRUE)
cat("ok\n")
