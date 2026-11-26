# Valores de referencia de paneles con plm (spec 006, revisión M1). Ejecutar desde la raíz:
#   Rscript tests/reference/r/plm_reference.R
suppressPackageStartupMessages({ library(plm); library(lmtest); library(jsonlite) })
dir <- "tests/data/reference"
d <- read.csv(file.path(dir, "plm_input.csv"))
p <- pdata.frame(d, index = c("entity", "time"))
fe <- plm(y ~ x, data = p, model = "within", effect = "individual")
tw <- plm(y ~ x, data = p, model = "within", effect = "twoways")
re <- plm(y ~ x, data = p, model = "random", random.method = "swar")
se <- function(m, V) unname(sqrt(diag(V))["x"])
scc_fe <- vcovSCC(fe, type = "HC0", maxlag = 3)
scc_tw <- vcovSCC(tw, type = "HC0", maxlag = 3)
cl_fe <- vcovHC(fe, method = "arellano", type = "HC1", cluster = "group")
cd <- pcdtest(plm(y ~ x, data = p, model = "within", effect = "individual"), test = "cd")
wt <- pwartest(y ~ x, data = p)
wfd <- pwfdtest(y ~ x, data = p, h0 = "fe")
ht <- phtest(fe, re)
res <- list(
  r_version = R.version.string, plm_version = as.character(packageVersion("plm")),
  input = "plm_input.csv",
  fe_coef = unname(coef(fe)["x"]), fe_se_unadjusted = se(fe, vcov(fe)),
  fe_se_scc_hc0_lag3 = se(fe, scc_fe), fe_se_cluster_hc1 = se(fe, cl_fe),
  twfe_coef = unname(coef(tw)["x"]), twfe_se_scc_hc0_lag3 = se(tw, scc_tw),
  re_coef = unname(coef(re)["x"]), re_theta = unname(ercomp(re)$theta),
  pesaran_cd = unname(cd$statistic), pesaran_cd_p = cd$p.value,
  wooldridge_ar_F = unname(wt$statistic), wooldridge_ar_p = wt$p.value,
  wooldridge_fd_F = unname(wfd$statistic), wooldridge_fd_p = wfd$p.value,
  hausman_chisq = unname(ht$statistic), hausman_p = ht$p.value
)
write_json(res, file.path(dir, "plm_reference.json"), auto_unbox = TRUE, digits = NA, pretty = TRUE)
cat("ok\n")
