import ast
from typing import Any, Dict, List, Optional, Tuple

from .airflow_parser import parse_airflow_file


def index_airflow_file(path: str, content: str) -> Dict[str, Any]:
    parsed = parse_airflow_file(path, content)
    tree = ast.parse(content)
    lines = content.splitlines()

    function_defs = _collect_function_defs(tree, lines)
    tasks = _collect_tasks(tree, lines)

    for task in tasks:
        callable_name = task.get("python_callable")
        if callable_name and callable_name in function_defs:
            task["callable_definition"] = function_defs[callable_name]

    operator_summary: Dict[str, int] = {}
    for task in tasks:
        operator = task.get("operator", "Unknown")
        operator_summary[operator] = operator_summary.get(operator, 0) + 1

    dependencies = [{"upstream": u, "downstream": d} for u, d in parsed.dependencies]
    task_graph = {
        "nodes": [{"task_id": t.get("task_id"), "operator": t.get("operator")} for t in tasks],
        "edges": dependencies,
    }

    return {
        "dag_id": parsed.dag_id or path.split("/")[-1].replace(".py", ""),
        "schedule_interval": parsed.schedule_interval,
        "default_args": parsed.default_args,
        "tasks": tasks,
        "dependencies": dependencies,
        "operator_summary": operator_summary,
        "task_graph": task_graph,
        "code_index": {
            "file_path": path,
            "tasks": tasks,
            "function_defs": list(function_defs.values()),
        },
    }


def _collect_function_defs(tree: ast.AST, lines: List[str]) -> Dict[str, Dict[str, Any]]:
    defs: Dict[str, Dict[str, Any]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None) or start
            snippet = _slice_lines(lines, start, end)
            defs[node.name] = {
                "name": node.name,
                "line_start": start,
                "line_end": end,
                "code_snippet": snippet,
            }
    return defs


def _collect_tasks(tree: ast.AST, lines: List[str]) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            operator = _extract_name(node.value.func)
            if not operator or not (operator.endswith("Operator") or operator.endswith("Sensor")):
                continue
            task_id, params = _extract_task_params(node.value)
            if not task_id:
                continue
            start = getattr(node, "lineno", None)
            end = getattr(node, "end_lineno", None) or start
            snippet = _slice_lines(lines, start, end)
            tasks.append(
                {
                    "task_id": task_id,
                    "operator": operator,
                    "params": params,
                    "python_callable": params.get("python_callable"),
                    "bash_command": params.get("bash_command"),
                    "line_start": start,
                    "line_end": end,
                    "code_snippet": snippet,
                }
            )
    return tasks


def _extract_task_params(call: ast.Call) -> Tuple[Optional[str], Dict[str, Any]]:
    params: Dict[str, Any] = {}
    task_id: Optional[str] = None
    for keyword in call.keywords:
        if not keyword.arg:
            continue
        value = _safe_literal(keyword.value)
        if keyword.arg == "task_id":
            task_id = value
        else:
            params[keyword.arg] = value
    return task_id, params


def _safe_literal(node: ast.AST) -> Any:
    try:
        value = ast.literal_eval(node)
    except Exception:
        name = _extract_name(node)
        return name or "<non_literal>"
    return value


def _extract_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _slice_lines(lines: List[str], start: Optional[int], end: Optional[int]) -> str:
    if start is None:
        return ""
    end = end or start
    start_idx = max(start - 1, 0)
    end_idx = min(end, len(lines))
    return "\n".join(lines[start_idx:end_idx])
