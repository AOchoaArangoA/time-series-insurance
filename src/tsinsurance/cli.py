"""Interfaz de línea de comandos: plantillas, validación y esquema de insumos.

Uso::

    tsinsurance template market --format csv -o market.csv [--example]
    tsinsurance validate market market.csv
    tsinsurance schema market --format json-schema
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada; devuelve el código de salida (0 válido, 1 errores, 2 uso)."""
    args = _parser().parse_args(argv)
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
