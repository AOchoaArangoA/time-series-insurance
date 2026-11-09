"""Experimentos declarativos (``experiment.toml``) con bitácora permanente.

Ver ``AGENTS.md`` y ``specs/003-experiment-workflow``.
"""

from tsinsurance.experiments.registry import append_trials, prior_information_ratios, read_registry
from tsinsurance.experiments.runner import ExperimentResult, run_experiment
from tsinsurance.experiments.signals import available_signals, get_signal, register_signal
from tsinsurance.experiments.spec import EconometricSpec, ExperimentSpec, IdeaSpec, load_experiment

__all__ = [
    "EconometricSpec",
    "ExperimentResult",
    "ExperimentSpec",
    "IdeaSpec",
    "append_trials",
    "available_signals",
    "get_signal",
    "load_experiment",
    "prior_information_ratios",
    "read_registry",
    "register_signal",
    "run_experiment",
]
