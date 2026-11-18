# La metodología, sin el producto

*Versión 2026-11-17.* Explica **qué** se hace y **por qué**,
sin comandos, archivos ni formatos. Distingue entre lo que ya está implementado (v0.1 y
el MVP de la spec 004) y lo que se propone (resto de la spec 004).

---

## 0. La pregunta de fondo

Toda la metodología responde una sola pregunta:

> **¿Esta idea de inversión (una regla o un modelo) tiene capacidad real de mejorar las
> decisiones, o lo que vemos en el backtest es suerte, un error de diseño o un efecto
> que no es lo que creemos?**

Un backtest es un **experimento estadístico** con una muestra pequeña y ruidosa, no una
demostración comercial. Un buen Sharpe histórico no basta, y por eso hay que
controlar cuatro fuentes de engaño:

| # | Fuente de engaño | En qué consiste | Defensa |
|---|---|---|---|
| 1 | **Anticipación** (*look-ahead*) | La regla usa, sin querer, información que no existía en la fecha de la decisión | Datos punto-en-el-tiempo y prueba automática de anticipación (§2, §3) |
| 2 | **Sobreajuste / pruebas múltiples** | Con suficientes intentos, alguno sale bien por azar | Contar **todas** las pruebas y deflactar (§6) |
| 3 | **Fuera de muestra contaminado** | Se mira el periodo de validación y se vuelve a elegir | Calibración y validación separadas, validación una sola vez (§7) |
| 4 | **Comparación equivocada** | Se le gana a una referencia que no mide lo que creemos | Benchmarks correctos: comprar y mantener **y** la misma exposición constante (§4) |

Sobre estas cuatro se monta una quinta capa: **cuantificar la incertidumbre** de cada
número (§5). Un Sharpe de 0,4 con un intervalo [−0,3; 1,1] no dice casi nada.

---

## 1. Diagnóstico de las series antes de modelar

**Por qué.** Si se regresa una serie con tendencia estocástica (raíz unitaria, I(1))
sobre otra igual, aparecen relaciones "significativas" que no existen: la **regresión
espuria** de Granger y Newbold. Por eso, antes de cualquier modelo, hay que establecer el
**orden de integración** de cada serie.

**Cómo (implementado).** Se combinan pruebas con hipótesis nulas opuestas, porque
ninguna es confiable sola:

- **ADF** y **Phillips-Perron**: H0 = raíz unitaria. Una tiene corrección paramétrica y
  la otra no paramétrica de la autocorrelación.
- **KPSS**: H0 = estacionaria. Sirve de contraste con las anteriores.
- **Zivot-Andrews**: raíz unitaria frente a estacionariedad con **un quiebre**. Un
  quiebre no modelado hace parecer persistente a una serie que no lo es.

**Regla jerárquica explícita**, aplicada en niveles y luego en diferencias:
- si ADF y PP rechazan, la serie es estacionaria;
- si no rechazan y KPSS sí, hay raíz unitaria y se diferencia;
- si ninguna rechaza o ADF y PP discrepan, el resultado es **inconcluso** (se dice, no se
  fuerza).

La regla está calibrada por Monte Carlo:
- acierta ≈ 100 % en procesos I(0);
- acierta ≈ 89 % en paseos aleatorios. Ese techo es estructural con α = 5 %.

Los estadísticos coinciden con R hasta 1e-13.

**Además** se revisan residuos (Ljung-Box, Jarque-Bera y ARCH-LM, este último sobre
residuos de un AR y no sobre la serie cruda), porque la inferencia posterior supone algo
sobre ellos.

---

## 2. Datos punto-en-el-tiempo: qué se sabía y cuándo

**Principio.** En la fecha de decisión *t* solo se puede usar lo que un inversionista
tenía en la mano en *t*. Hay tres fuentes sutiles de violación:

1. **Rezago de publicación.** El IPC de marzo no se conoce el 31 de marzo, sino a
   mediados de abril. Cada variable lleva su rezago desde el **fin del periodo** que
   mide, y solo está disponible a partir de esa fecha.
   - *Implementado*: el rezago se declara por serie y los datos mensuales se fechan al
     fin de mes.
2. **Revisiones.** Muchas cifras macro se corrigen después. Usar la versión corregida de
   hoy en un backtest de 2010 es usar el futuro.
   - *Propuesto (spec 004)*: usar las versiones históricas (ALFRED) en dos modos.
     - **Primera publicación**: cada dato tal como salió la primera vez, desde su fecha
       real de publicación. Nunca usa el futuro, pero ignora correcciones ya conocidas.
     - **Todas las versiones**: en cada fecha, la versión vigente ese día de cada dato.
       Es lo más fiel, y las transformaciones (variación anual, diferencias) se calculan
       dentro de esa misma versión.
     - Comparar ambos modos mide cuánto depende la conclusión de las revisiones.
   - *Mientras tanto*: una serie revisable en su versión actual se marca **no
     punto-en-el-tiempo** y todo lo que la use queda "exploratorio".
3. **Transformaciones que mezclan fechas.** Una variación anual usa *t* y *t−12*. Su
   disponibilidad es la **más tardía** de las dos publicaciones, no la de *t*.
   - *Propuesto*: regla del máximo.

**Detalle que importa.** La fecha de fin de vigencia que publica ALFRED cuenta como un
día incluido. Tratarla como excluida desplaza las versiones un día. Además, al "cortar"
los datos en una fecha hay que olvidar también *cuándo* fue reemplazada cada versión,
porque saber que un dato se iba a corregir ya es información futura.

---

## 3. La prueba de anticipación

**Idea (implementada).** Si una regla es honesta, su decisión en la fecha *t* no puede
cambiar cuando se borran los datos posteriores a *t*. La prueba hace exactamente eso:
1. calcula la señal con todos los datos;
2. la recalcula con los datos cortados en varias fechas;
3. exige que coincidan hasta cada corte.

- Si algo cambia, la idea se **rechaza** y no se evalúa.
- Si se pueden evaluar pocos cortes, el resultado es **no concluyente**, no "aprobado".

**Mejora propuesta (spec 004).** Para los modelos econométricos, la prueba tiene que
recorrer el proceso **completo**: alineación de fechas, variables derivadas y
re-estimación. Si recibe los datos ya alineados, no prueba nada.

**Límite honesto.** Detecta el uso de datos futuros a través de lo que recibe la regla.
No detecta a alguien que lea el archivo completo por fuera.

---

## 4. El backtest como experimento controlado

**Supuestos explícitos (implementado).** Nada queda implícito:
- **Ejecución**: la decisión de hoy se opera al cierre siguiente. Operar al mismo cierre
  es optimista.
- **Costos** por activo y deslizamiento.
- **Pesos**: derivan con los precios entre rebalanceos.
- **Tasa libre de riesgo**: con su propio rezago.
- **Retornos en exceso** de la tasa libre de riesgo.

El motor propio coincide con la librería `bt` hasta 3e-16 sin costos.

**El benchmark correcto: dos comparaciones, no una.**

- **Contra comprar y mantener**: ¿conviene la regla frente a quedarse invertido?
- **Contra la misma exposición constante**: si la regla estuvo invertida en promedio un
  33 % del tiempo, ¿le gana a estar siempre 33 % invertido? Esta es la medida de
  **habilidad de *timing***: aísla el acierto en el *momento*.

**Ejemplo real.** En los ETFs inversos del Tesoro (TBT, TBX, TBF), las reglas "le
ganaban" a comprar y mantener. Pero esos activos pierden valor con el tiempo, y estar
invertido solo ~1/3 del tiempo ya reduce la pérdida. Contra la exposición constante no
había **ninguna** habilidad. Sin la segunda comparación habríamos concluido lo contrario.

---

## 5. Incertidumbre: cuánto confiar en cada número

**Sharpe con su error (implementado).**
- **EE iid** (Mertens), que corrige por asimetría y curtosis.
- **EE HAC** (Newey-West con método delta), que corrige por autocorrelación. Coincide con
  `sandwich` de R hasta 1e-16.
  - *Propuesto*: **preblanqueo** (Andrews-Monahan), porque el Newey-West subestima el
    error en ≈ 9 % con autocorrelación. Se adopta solo si el Monte Carlo lo respalda.
- **Intervalo por bootstrap estacionario**: remuestrea bloques para respetar la
  dependencia temporal.

**PSR (Probabilistic Sharpe Ratio).** Es la probabilidad de que el Sharpe verdadero
supere un umbral, dada la longitud de la muestra y la forma de la distribución:

```text
PSR(SR*) = Φ( (SR − SR*) · √(T−1) / √(1 − γ₃·SR + (γ₄−1)/4 · SR²) )
```

Muestras cortas y colas gordas reducen la confianza.

---

## 6. Pruebas múltiples: el corazón del problema

**El fenómeno.** Si se prueban 100 configuraciones sin ninguna habilidad, la mejor tendrá
un Sharpe alto **por azar**. Elegir la mejor y reportarla como si fuera la única es la
forma más común de engañarse.

**Defensa 1: Sharpe deflactado, DSR (implementado).** Se calcula el Sharpe **máximo
esperado por azar** entre N pruebas sin habilidad, dada la dispersión V entre sus
Sharpe:

```text
SR₀ ≈ √V · [ (1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)) ]     (γ ≈ 0,5772)
DSR = PSR(SR₀)
```

La mejor configuración debe superar ese umbral, no cero. Está calibrado:
- **tamaño**: 1,6 % de falsos positivos;
- **potencia**: 88 %.

Un hallazgo: el "número efectivo de pruebas" por autovalores **subestima** N y llevó la
tasa de falsos positivos al 22 %. Por eso se usa el N bruto.

**Defensa 2: prueba SPA de Hansen (implementado).** Pregunta directamente si *alguna*
configuración de la familia le gana al benchmark, teniendo en cuenta que se eligió la
mejor. Se aplica Holm entre activos.

**Regla de significancia**: una idea es significativa solo si **DSR > 1 − α y SPA < α**.
Ambas condiciones.

**La memoria de lo probado (implementado).** N no son solo las pruebas de hoy: son
**todas las que se han hecho** sobre ese activo, en cualquier experimento. Por eso existe
una bitácora permanente, y cada prueba nueva hereda el castigo de las anteriores. Esa es
la razón metodológica de que la bitácora no se pueda editar ni recortar.
- *MVP de la spec 004, ya implementado*: borrar las últimas líneas para "olvidar" pruebas
  fallidas ahora se detecta.

**Corrección propuesta a la varianza V (spec 004).** Las pruebas previas tienen ventanas
de distinto largo, y un Sharpe medido en 3 años es más ruidoso que uno de 15.
- **Error descartado.** "Restar el ruido de muestreo" es *incorrecto*: bajo la hipótesis
  de que nadie tiene habilidad, la dispersión entre los Sharpe estimados **es** ese ruido,
  y es justamente lo que genera el máximo esperado. Restarlo dejaría el umbral en cero.
- **Propuesta: estandarizar.** Primero se compara cada prueba en la misma escala,
  `zᵢ = SRᵢ·√Tᵢ`. Después se calcula el umbral y se reescala al largo de la prueba
  actual.
- **Evidencia preliminar.** Con pruebas muy correlacionadas y de largo distinto, la regla
  actual es tan conservadora que casi nunca detectaría habilidad real (tamaño ≈ 0 %). La
  estandarizada queda en 3-4 %.
- **Criterio de adopción.** Solo si un Monte Carlo amplio muestra tamaño acotado y
  potencia mayor o igual que la regla actual. Toda regla que haga el ajuste menos
  conservador necesita esa evidencia.

---

## 7. Fuera de muestra intocable

**Principio.** Los parámetros se eligen **solo** con el periodo de calibración (hasta una
fecha de corte). El periodo posterior se evalúa **una vez**, con la configuración ya
fijada, y se reporta tal cual.

**Walk-forward (implementado).** Los modelos se re-estiman en cada fecha con los datos
hasta esa fecha. Así cada pronóstico es genuinamente fuera de muestra.

**Lo que falla hoy y la propuesta (spec 004).**
- Hoy, al ejecutar con fecha de corte, se calibra **y** se ve la validación en el mismo
  paso. Quien itera ve el resultado fuera de muestra en cada vuelta: queda registrado,
  pero lo ve.
- Hoy, los modelos econométricos se evalúan sobre toda la ventana, incluida la
  validación.
- **Propuesta: dos fases separadas.**
  1. La **calibración** recibe los datos cortados en la fecha de corte, así que no puede
     ver el periodo de validación aunque quiera.
  2. La **validación** se abre después, explícitamente y una vez. Exige que la
     calibración esté registrada y que no haya cambiado nada: datos anteriores al corte,
     código ni experimento.
- **Periodo ya visto.** El periodo de validación se identifica por **activo y fechas**,
  no por el nombre del experimento. Si cualquier experimento anterior ya miró ese periodo
  para ese activo, la validación nueva queda **exploratoria** automáticamente.
  - *Consecuencia práctica*: para TLT, TBX y TBF el periodo 2019-2025 ya se miró. Un
    nuevo experimento sobre ellos con ese corte es una demostración, no una
    confirmación.
- **Validación con varias hipótesis.** Si se validan varios activos o modelos a la vez,
  también hay pruebas múltiples: se aplica Holm sobre la familia declarada de antemano.

**Pre-registro.** La hipótesis y la fecha de corte se escriben **antes** de ejecutar, y
quedan sellados en la bitácora.

---

## 8. Modelos econométricos con variables macro: la validación doble

**El modelo (implementado).** Regresión predictiva *walk-forward*: el retorno en exceso
del mes siguiente se explica con variables macro conocidas hoy (pendiente de la curva,
diferencial de crédito, inflación, cambios de tasas). El pronóstico se convierte en una
posición (invertido o en efectivo, largo o corto, o proporcional).

**Primera pregunta, estadística: ¿pronostica?**
- **R² fuera de muestra** frente a la **media histórica**. Si es negativo, el modelo
  pronostica peor que no hacer nada.
- **Clark-West**: prueba si el modelo mejora a la media histórica, corrigiendo que los
  modelos anidados se comparan con ruido de estimación (Diebold-Mariano estaría sesgada).
  Calibrada: potencia 94 %, tamaño 3,5 %.
- **Pesaran-Timmermann**: ¿acierta la **dirección** más que el azar?
- **Diagnósticos**: estacionariedad y persistencia de los regresores, y residuos.

**El problema de los regresores persistentes.** Variables como la pendiente de la curva
se mueven muy despacio (ρ ≈ 0,98). Con ellas, los errores estándar habituales exageran
la significancia (**sesgo de Stambaugh**).
- *Propuesto*: prueba **IVX** (Kostakis, Magdalinos y Stamatogiannis 2015), válida tanto
  si el regresor es estacionario como si es casi una raíz unitaria. Se verificará contra
  el paquete `ivx` de R, con valores ya guardados.

**Segunda pregunta, económica: ¿sirve neto de costos?** Se compara el Sharpe de la regla
basada en el modelo con el de **la misma regla aplicada a la media histórica**. Así el
valor económico mide el aporte del *modelo*, no de la regla.

**Veredicto en cuatro cuadrantes.** Se reporta explícitamente cuál de los cuatro aplica:

| | Valor económico sí | Valor económico no |
|---|---|---|
| **Evidencia estadística sí** | Estadística y económica | Solo estadística (pronostica pero no paga) |
| **Evidencia estadística no** | Solo económica (gana sin respaldo: sospechoso) | Sin evidencia |

A eso se suman las marcas:
- **exploratorio**: se probó más de una especificación o hay datos no
  punto-en-el-tiempo;
- **no concluyente**: hay pocos pronósticos;
- **diagnósticos no superados**.

**Ejemplo real (TLT).** El modelo macro acertó la dirección el 56 % de las veces
(Pesaran-Timmermann p = 0,04), pero su R² fuera de muestra fue −14 % y no generó valor
económico significativo. Veredicto: "solo estadística", exploratorio. Es decir:
**no sirve para decidir**, y el sistema lo dice.

---

## 9. Cómo se lee un resultado

Un resultado **sirve para decidir** solo si se cumplen todas estas condiciones:
1. pasó la prueba de anticipación;
2. usa datos punto-en-el-tiempo;
3. supera el ajuste por **todas** las pruebas registradas (DSR y SPA);
4. le gana a la exposición constante, no solo a comprar y mantener;
5. su validación fuera de muestra se abrió una vez, sobre un periodo nunca visto;
6. en los modelos, tiene respaldo estadístico **y** económico, con diagnósticos superados.

Todo lo demás es **exploratorio**: útil para generar hipótesis, no para decidir. La
metodología está diseñada para que esa distinción la haga el sistema, no la memoria ni
el entusiasmo del analista.

---

## 10. Qué no garantiza la metodología

- **El pasado no asegura el futuro.** Una habilidad real en 2003-2018 puede desaparecer
  por cambios de régimen. La validación fuera de muestra lo mitiga, no lo elimina.
- **Sesgo de supervivencia en el universo.** Los ETFs elegidos hoy existen porque
  sobrevivieron; el sistema lo advierte.
- **Precios ajustados de Yahoo.** Se recalculan hacia atrás con cada dividendo.
  Sirven para explorar; para producción hace falta una fuente versionada.
- **Separación lógica, no física.** Quien quiera hacer trampa leyendo los archivos por
  fuera puede. El sistema protege contra el error honesto y deja rastro, no contra el
  fraude deliberado.
- **Muestras cortas.** Con 15-20 años de datos mensuales, la potencia para detectar
  habilidades modestas es baja. "No significativo" a menudo significa "no sabemos", no
  "no existe".

---

## 11. Mapa rápido: implementado o propuesto

| Pieza | Estado |
|---|---|
| Estacionariedad con regla jerárquica, diagnósticos de residuos | Implementado (verificado contra R) |
| Rezago de publicación declarado y fechas de fin de periodo | Implementado |
| Versiones de datos macro (primera publicación / todas las versiones) | Propuesto (spec 004) |
| Prueba de anticipación | Implementada; extenderla al flujo econométrico completo es propuesta |
| Motor con supuestos explícitos y doble benchmark | Implementado (verificado contra `bt`) |
| Sharpe con EE iid/HAC, bootstrap, PSR | Implementado; preblanqueo propuesto |
| DSR + SPA + Holm con memoria de todas las pruebas | Implementado |
| Bitácora a prueba de recortes, un solo escritor | **Implementado (MVP spec 004)** |
| Corrección de la varianza del DSR por largo de ventana | Propuesta, condicionada a Monte Carlo |
| Calibración y validación en dos fases; periodo ya visto | Propuesto (spec 004) |
| Huella del código de cada señal | Propuesta (spec 004) |
| Regresión predictiva walk-forward, Clark-West, PT, R² fuera de muestra, veredicto doble | Implementado |
| IVX para regresores persistentes | Propuesto (spec 004) |
| ARIMA/GARCH, pronóstico, VaR/ES, ALM | Fuera de esta metodología por ahora (hoja de ruta) |

## Referencias principales

- Bailey, D. y López de Prado, M. (2012, 2014): PSR y Sharpe deflactado.
- Hansen, P. R. (2005): prueba SPA.
- Clark, T. y West, K. (2007): comparación de pronósticos anidados.
- Pesaran, M. H. y Timmermann, A. (1992): prueba de dirección.
- Goyal, A. y Welch, I. (2008): R² fuera de muestra frente a la media histórica.
- Kostakis, A., Magdalinos, T. y Stamatogiannis, M. (2015): IVX.
- Stambaugh, R. (1999): sesgo con regresores persistentes.
- Croushore, D. y Stark, T. (2001): datos en tiempo real.
- Andrews, D. (1991); Andrews, D. y Monahan, J. (1992): HAC y preblanqueo.
- Politis, D. y Romano, J. (1994): bootstrap estacionario.
- Granger, C. y Newbold, P. (1974): regresión espuria.
