"""Interfaz de línea de comandos: plantillas, validación y esquema de insumos.

Uso::

    tsinsurance template market --format csv -o market.csv [--example]
    tsinsurance validate market market.csv
    tsinsurance schema market --format json-schema
    tsinsurance bundle template|validate|fetch|show ...
    tsinsurance experiment run experiment.toml | list registry.jsonl | signals
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import cast

from tsinsurance import __version__
from tsinsurance.data.schemas import INPUT_KINDS, InputKind
from tsinsurance.data.templates import export_schema, write_template
from tsinsurance.data.validate import read_table, validate
from tsinsurance.errors import TSInsuranceError

__all__ = ["main"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tsinsurance", description="Contrato de datos de insumos de tsinsurance."
    )
    parser.add_argument("--version", action="version", version=f"tsinsurance {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("template", help="Genera una plantilla de insumo.")
    t.add_argument("kind", choices=INPUT_KINDS)
    t.add_argument("--format", choices=["csv", "xlsx"], default="csv")
    t.add_argument("-o", "--output", required=True)
    t.add_argument("--example", action="store_true", help="Incluye una fila de ejemplo.")

    v = sub.add_parser("validate", help="Valida un archivo contra el contrato de datos.")
    v.add_argument("kind", choices=INPUT_KINDS)
    v.add_argument("path")
    v.add_argument("--json", action="store_true", help="Salida en JSON.")

    s = sub.add_parser("schema", help="Exporta el esquema del insumo.")
    s.add_argument("kind", choices=INPUT_KINDS)
    s.add_argument("--format", choices=["json-schema", "frictionless"], default="json-schema")

    b = sub.add_parser("bundle", help="Paquetes de insumos independientes de la fuente.")
    bsub = b.add_subparsers(dest="bundle_command", required=True)
    bt = bsub.add_parser("template", help="Escribe un paquete de ejemplo para llenar.")
    bt.add_argument("directory")
    bv = bsub.add_parser("validate", help="Valida un paquete (datos, manifiesto, huella).")
    bv.add_argument("directory")
    bf = bsub.add_parser("fetch", help="Descarga un paquete según una receta TOML.")
    bf.add_argument("recipe")
    bf.add_argument("directory")
    bz = bsub.add_parser("seal", help="Sella (huella) un paquete escrito a mano.")
    bz.add_argument("directory")
    bs = bsub.add_parser("show", help="Resume un paquete.")
    bs.add_argument("directory")

    e = sub.add_parser("experiment", help="Experimentos declarativos registrados.")
    esub = e.add_subparsers(dest="experiment_command", required=True)
    er = esub.add_parser("run", help="Ejecuta experiment.toml y lo registra en la bitácora.")
    er.add_argument("path")
    er.add_argument("--registry", help="Bitácora alternativa (marca el resultado exploratorio).")
    er.add_argument(
        "--output", help="Carpeta de resultados (por defecto results/ del experimento)."
    )
    ev = esub.add_parser("verify", help="Verifica la integridad de la bitácora (cadena de hashes).")
    ev.add_argument("registry")
    el = esub.add_parser("list", help="Lista las pruebas de la bitácora.")
    el.add_argument("registry")
    esub.add_parser("signals", help="Señales registradas.")
    return parser


def _bundle_command(args: argparse.Namespace) -> int:
    from tsinsurance.data.bundle import (
        Bundle,
        fetch_recipe,
        seal_bundle,
        validate_bundle,
        write_bundle_template,
    )

    if args.bundle_command == "template":
        print(f"Plantilla de paquete escrita en {write_bundle_template(args.directory)}")
        return 0
    if args.bundle_command == "validate":
        issues = validate_bundle(args.directory)
        if not issues:
            print(f"Paquete válido: {args.directory}")
            return 0
        print(f"Paquete inválido: {len(issues)} problema(s)")
        for i in issues:
            print(f"  serie={i.series} campo={i.field}: {i.message}")
        return 1
    if args.bundle_command == "seal":
        print(seal_bundle(args.directory).summary())
        return 0
    if args.bundle_command == "fetch":
        print(fetch_recipe(args.recipe, args.directory).summary())
        return 0
    print(Bundle.load(args.directory).summary())
    return 0


def _experiment_command(args: argparse.Namespace) -> int:
    from tsinsurance.experiments import available_signals, read_registry, run_experiment
    from tsinsurance.experiments.registry import verify_registry

    if args.experiment_command == "run":
        res = run_experiment(args.path, registry=args.registry, output_root=args.output)
        print(res.report)
        print(res.summary())
        return 0
    if args.experiment_command == "verify":
        problems = verify_registry(args.registry)
        print("Bitácora íntegra." if not problems else "\n".join(problems))
        return 0 if not problems else 1
    if args.experiment_command == "list":
        rows = read_registry(args.registry)
        print(f"{len(rows)} prueba(s) registradas")
        for r in rows[-50:]:
            print(
                f"  {r.get('created_at')} {r.get('experiment_id')} {r.get('kind')} "
                f"{r.get('asset')} {r.get('idea')} {r.get('params')}"
            )
        return 0
    for name, doc in available_signals().items():
        print(f"  {name:<18} {doc}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada; devuelve el código de salida (0 válido, 1 errores, 2 uso)."""
    args = _parser().parse_args(argv)
    try:
        if args.command == "bundle":
            return _bundle_command(args)
        if args.command == "experiment":
            return _experiment_command(args)
    except (TSInsuranceError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    kind = cast(InputKind, args.kind)
    try:
        if args.command == "template":
            path = write_template(kind, args.output, args.format, with_example=args.example)
            print(f"Plantilla '{kind}' escrita en {path}")
            return 0
        if args.command == "validate":
            report = validate(read_table(args.path), kind)
            if args.json:
                print(report.to_json())
            else:
                print(report.summary())
                if not report.is_valid and args.path.lower().endswith(".csv"):
                    print("(fila = índice de datos base 0; línea del CSV = fila + 2)")
            return 0 if report.is_valid else 1
        print(json.dumps(export_schema(kind, args.format), indent=2, ensure_ascii=False))
        return 0
    except (TSInsuranceError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
