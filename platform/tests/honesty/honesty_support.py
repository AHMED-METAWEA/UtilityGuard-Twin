"""AST-only guards and recursive contract inspection for honesty tests."""

from __future__ import annotations

import ast
import re
import sys
from contextlib import contextmanager
from dataclasses import fields
from pathlib import Path
from urllib.parse import unquote, urldefrag, urlparse

import pytest
from ug_core.telemetry import TelemetrySeries
from ug_core.truth import TruthEvent, TruthSeries

ROOT = Path(__file__).resolve().parents[3]
# The evaluation harness and a future explicitly authorised "twin truth" endpoint
# are the only places allowed to touch truth, and they are not on this list.
OPERATOR_SIDE = (
    ROOT / "platform/ug_intel/src",
    ROOT / "platform/ug_api/src",
)
sys.path.insert(0, str(ROOT / "platform/tests/contract"))
from contract_support import load_json  # noqa: E402
from contract_support import validator_for as validator_for  # noqa: E402

TRUTH_TYPES = {"TruthSeries", "TruthEvent"}
CONTROL_LIBRARIES = {
    "pymodbus",
    "opcua",
    "asyncua",
    "paho",
    "serial",
    "snap7",
    "bacpypes",
    "pycomm3",
    "minimalmodbus",
}


def imports(tree):
    """Yield qualified import targets, including literal dynamic imports."""
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name] = item.name
                yield node, item.name
        elif isinstance(node, ast.ImportFrom):
            for item in node.names:
                target = f"{node.module or ''}.{item.name}"
                aliases[item.asname or item.name] = target
                yield node, target
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args:
            name = ast.unparse(node.func)
            head, dot, tail = name.partition(".")
            name = aliases.get(head, head) + (dot + tail if dot else "")
            if name in {"importlib.import_module", "__import__", "builtins.__import__"}:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    yield node, arg.value


def truth_violations(source, *, parameters=True, any_truth_import=False):
    """Return line-numbered truth import/parameter violations without execution."""
    tree = ast.parse(source)
    errors = []
    aliases = set(TRUTH_TYPES)
    for node, target in imports(tree):
        parts = target.split(".")
        forbidden = (
            target.startswith(("ug_core.truth", "ug_core.ports"))
            or bool(TRUTH_TYPES.intersection(parts))
            or (any_truth_import and "truth" in parts)
        )
        if forbidden:
            errors.append(f"line {node.lineno}: truth boundary import {target}")
            if isinstance(node, ast.ImportFrom):
                aliases.update(i.asname or i.name for i in node.names)
    if parameters:
        for node in ast.walk(tree):
            if isinstance(node, ast.arg):
                annotation = ast.unparse(node.annotation) if node.annotation else ""
                # Parse quoted and qualified annotations by their identifier tokens.
                tokens = set(re.findall(r"[A-Za-z_]\w*", annotation))
                if node.arg == "truth" or tokens.intersection(aliases):
                    errors.append(
                        f"line {node.lineno}: truth boundary parameter {node.arg}: "
                        f"{annotation}"
                    )
    return errors


def advisory_violations(source):
    tree = ast.parse(source)
    errors = [
        f"line {node.lineno}: advisory-only rule: control import {target}"
        for node, target in imports(tree)
        if target.split(".")[0] in CONTROL_LIBRARIES
    ]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
            node.name.startswith(("write_to_", "actuate", "set_setpoint"))
        ):
            errors.append(f"line {node.lineno}: advisory-only function {node.name}")
    return errors


def finite_violations(source):
    """Conservative syntactic guard; rejection branches remain legitimate."""
    tree = ast.parse(source)
    errors = []
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases.update({i.asname or i.name: i.name for i in node.names})
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func).split(".")[-1]
            name = aliases.get(name, name)
            if name in {"nan_to_num", "fillna"}:
                errors.append(f"line {node.lineno}: P-17 silent replacement via {name}")
        if not isinstance(node, ast.If):
            continue
        checks = any(
            isinstance(test, ast.Call)
            and aliases.get(
                ast.unparse(test.func).split(".")[-1],
                ast.unparse(test.func).split(".")[-1],
            )
            in {"isnan", "isfinite", "isinf"}
            or isinstance(test, ast.Compare)
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.NotEq)
            and ast.dump(test.left) == ast.dump(test.comparators[0])
            for test in ast.walk(node.test)
        )
        if checks:
            for branch in node.body + node.orelse:
                for stmt in ast.walk(branch):
                    if isinstance(stmt, ast.Return | ast.Assign | ast.AnnAssign):
                        value = stmt.value
                        if (
                            isinstance(value, ast.Constant)
                            and type(value.value) in {int, float}
                            and value.value == 0
                        ):
                            errors.append(
                                f"line {stmt.lineno}: P-17 non-finite branch stores zero"
                            )
    return errors


def forbidden_property(name):
    truth_fields = {f.name for cls in (TruthSeries, TruthEvent) for f in fields(cls)}
    shared = {f.name for f in fields(TelemetrySeries)}
    stems = {"truth", "fault_tag", "faulttag", "hidden", "injected", "ground_truth"}
    return name.casefold() in {n.casefold() for n in truth_fields - shared} or any(
        stem in name.casefold() for stem in stems
    )


def payload_violations(value, where="$", *, schema=False, path=None, seen=None):
    """Inspect all payload keys or schema property names and local ref targets."""
    errors = []
    seen = set() if seen is None else seen
    if isinstance(value, dict):
        names = value.get("properties", {}) if schema else value
        for name in names:
            if forbidden_property(name):
                errors.append(f"{where}.{name}: P-01/P-02 forbidden truth property")
        if schema and "$ref" in value:
            document, fragment = urldefrag(value["$ref"])
            target_path = path
            if document:
                # Contract IDs resolve locally; never fetch a remote reference.
                target_path = path.parent / Path(urlparse(document).path).name
            identity = (target_path, fragment)
            if identity not in seen:
                seen.add(identity)
                target = load_json(target_path)
                for part in fragment.lstrip("/").split("/") if fragment else []:
                    target = target[unquote(part).replace("~1", "/").replace("~0", "~")]
                errors += payload_violations(
                    target,
                    f"{target_path}#{fragment}",
                    schema=True,
                    path=target_path,
                    seen=seen,
                )
        for key, child in value.items():
            errors += payload_violations(
                child, f"{where}.{key}", schema=schema, path=path, seen=seen
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors += payload_violations(
                child, f"{where}[{index}]", schema=schema, path=path, seen=seen
            )
    return errors


def labelled_numbers(value, labels, where="$", inherited=None, residual=False):
    errors = []
    if isinstance(value, dict):
        label = value.get("label", inherited)
        for key, child in value.items():
            here = f"{where}.{key}"
            if (
                type(child) in {int, float}
                and (
                    key in {"value", "score", "p10", "p50", "p90", "residuals"}
                    or residual
                )
                and label not in labels
            ):
                errors.append(
                    f"{here}: P-14 displayed number lacks valid label: {label}"
                )
            errors += labelled_numbers(
                child, labels, here, label, residual or key == "residuals"
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if residual and type(child) in {int, float} and inherited not in labels:
                errors.append(f"{where}[{index}]: P-14 unlabelled residual")
            errors += labelled_numbers(
                child, labels, f"{where}[{index}]", inherited, residual
            )
    return errors


def money_violations(value, where="$"):
    allowed = {
        "CALCULATED",
        "ASSUMPTION",
        "OBSERVED",
        "BENCHMARK",
        "INSUFFICIENT_EVIDENCE",
    }
    errors = []
    if isinstance(value, dict):
        if value.get("unit") in {"EGP", "EGP/year", "EGP/month", "EGP/day"}:
            if value.get("label") not in allowed:
                errors.append(
                    f"{where}: P-14 money has invalid label {value.get('label')}"
                )
        for key, child in value.items():
            errors += money_violations(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors += money_violations(child, f"{where}[{index}]")
    return errors


@contextmanager
def rejects(expected, where, match=None):
    """Require rejection with a diagnostic identifying the honesty rule and API."""
    try:
        yield
    except expected as exc:
        if match is not None and re.search(match, str(exc)) is None:
            pytest.fail(f"{where}: rejected for the wrong reason: {exc}")
    except Exception as exc:
        pytest.fail(f"{where}: unexpected rejection {type(exc).__name__}: {exc}")
    else:
        pytest.fail(f"{where}: forbidden input was accepted instead of rejected")
