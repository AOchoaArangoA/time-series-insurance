"""Veredicto doble: evidencia estadística y valor económico (Principio VIII)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tsinsurance.results import ResultMixin

__all__ = ["MIN_OOS_FORECASTS", "Quadrant", "Verdict", "make_verdict"]

Quadrant = Literal["estadistica_y_economica", "solo_estadistica", "solo_economica", "sin_evidencia"]
MIN_OOS_FORECASTS = 60

_EXPLAIN = {
    "estadistica_y_economica": "El modelo pronostica mejor que la media histórica y la señal "
    "agrega valor económico neto de costos frente a la misma regla con la media histórica.",
    "solo_estadistica": "Hay capacidad predictiva estadística, pero no se traduce en valor "
    "económico neto de costos (ajuste sin valor económico).",
    "solo_economica": "La señal mejora el desempeño sin respaldo estadístico del pronóstico: "
    "posible suerte, no linealidad o dependencia del periodo; no apta sin más evidencia.",
    "sin_evidencia": "Ni evidencia estadística ni valor económico frente al benchmark.",
}


@dataclass(frozen=True, slots=True)
class Verdict(ResultMixin):
    """Veredicto doble con sus condiciones de validez."""

    statistical: bool
    economic: bool
    quadrant: Quadrant
    diagnostics_passed: bool
    n_specifications: int
    exploratory: bool
    inconclusive: bool
    alpha: float
    statistical_test: str
    rule: str
    explanation: str

    def summary(self) -> str:
        """Veredicto legible para comité."""
        flags = []
        if self.inconclusive:
            flags.append("NO CONCLUYENTE")
        if self.exploratory:
            flags.append("EXPLORATORIO")
        if not self.diagnostics_passed:
            flags.append("DIAGNÓSTICOS NO SUPERADOS")
        head = f"Veredicto: {self.quadrant.replace('_', ' ')}"
        if flags:
            head += " [" + ", ".join(flags) + "]"
        return "\n".join(
            [
                head,
                f"  Evidencia estadística ({self.statistical_test}, α={self.alpha:g}): "
                f"{'sí' if self.statistical else 'no'}",
                f"  Valor económico (Sharpe neto vs regla con media histórica, α={self.alpha:g}): "
                f"{'sí' if self.economic else 'no'}",
                f"  {self.explanation}",
                f"  Regla: {self.rule}",
            ]
        )


def make_verdict(
    *,
    statistical: bool,
    economic: bool,
    diagnostics_passed: bool,
    n_specifications: int,
    point_in_time: bool,
    n_forecasts: int,
    alpha: float,
    statistical_test: str,
) -> Verdict:
    """Construye el veredicto aplicando la regla documentada."""
    quadrant: Quadrant
    if statistical and economic:
        quadrant = "estadistica_y_economica"
    elif statistical:
        quadrant = "solo_estadistica"
    elif economic:
        quadrant = "solo_economica"
    else:
        quadrant = "sin_evidencia"
    exploratory = n_specifications > 1 or not point_in_time
    inconclusive = n_forecasts < MIN_OOS_FORECASTS
    explanation = _EXPLAIN[quadrant]
    if not point_in_time:
        explanation += " Hay variables no punto-en-el-tiempo (revisadas)."
    if n_specifications > 1:
        explanation += f" Se probaron {n_specifications} especificaciones sin ajuste formal."
    rule = (
        f"estadística = {statistical_test} rechaza H0 al nivel α; económica = prueba unilateral "
        "de diferencia de Sharpe (bootstrap estacionario) neto de costos y en exceso de rf frente "
        "a la misma regla aplicada a la media histórica rechaza al nivel α; no concluyente si hay "
        f"menos de {MIN_OOS_FORECASTS} pronósticos fuera de muestra; exploratorio si se probó más "
        "de una especificación o hay variables no punto-en-el-tiempo."
    )
    return Verdict(
        statistical=statistical,
        economic=economic,
        quadrant=quadrant,
        diagnostics_passed=diagnostics_passed,
        n_specifications=n_specifications,
        exploratory=exploratory,
        inconclusive=inconclusive,
        alpha=alpha,
        statistical_test=statistical_test,
        rule=rule,
        explanation=explanation,
    )
