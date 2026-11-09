# Valores de referencia en R para tests/reference/test_against_r.py.
# Uso: Rscript reference_gs10.R <directorio_con_csv> <rezagos_pp>
suppressMessages({library(urca); library(tseries); library(forecast); library(FinTS)})
a <- commandArgs(TRUE)
x <- read.csv(file.path(a[1], "gs10.csv"))$x; d <- read.csv(file.path(a[1], "dgs10.csv"))$d
dm <- read.csv(file.path(a[1], "dm.csv"))
pp_lags <- as.integer(a[2])
out <- list(
 "ADF(c, 3 rezagos fijos)" = ur.df(x, type = "drift", lags = 3)@teststat[1],
 "PP Z-tau (c)" = ur.pp(x, type = "Z-tau", model = "constant", use.lag = pp_lags)@teststat,
 "KPSS nivel (rezagos 5)" = unname(kpss.test(x, null = "Level", lshort = TRUE)$statistic),
 "Ljung-Box(10) dGS10" = unname(Box.test(d, lag = 10, type = "Ljung-Box")$statistic),
 "Jarque-Bera dGS10" = unname(jarque.bera.test(d)$statistic),
 "ARCH-LM(5) dGS10" = unname(ArchTest(d - mean(d), lags = 5, demean = FALSE)$statistic),
 "Diebold-Mariano (HLN) h=1" = unname(dm.test(dm$e1, dm$e2, h = 1, power = 2)$statistic)
)
cat(jsonlite::toJSON(out, auto_unbox = TRUE, digits = 12))
