import ast
import os
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str]


class ValidationAgent:
    def run(self, *, root_path: str, notebook_paths: List[str], utils_paths: List[str], databricks_yml_path: str) -> ValidationResult:
        errors: List[str] = []

        if not os.path.isfile(databricks_yml_path):
            errors.append("databricks.yml missing.")
        else:
            content = _read(databricks_yml_path)
            if "resources:" not in content or "jobs:" not in content:
                errors.append("databricks.yml missing required resources/jobs sections.")

        for path in notebook_paths + utils_paths:
            if not os.path.isfile(path):
                errors.append(f"Missing file: {path}")
                continue
            try:
                ast.parse(_read(path))
            except SyntaxError as exc:
                errors.append(f"Syntax error in {path}: {exc}")

        return ValidationResult(ok=len(errors) == 0, errors=errors)


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()
