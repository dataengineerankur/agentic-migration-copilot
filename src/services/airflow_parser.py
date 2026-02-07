import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class ParsedTask:
    task_id: str
    operator: str
    params: Dict[str, str] = field(default_factory=dict)
    upstream: Set[str] = field(default_factory=set)
    downstream: Set[str] = field(default_factory=set)


@dataclass
class ParsedDAG:
    dag_id: Optional[str] = None
    schedule_interval: Optional[str] = None
    default_args: Dict[str, str] = field(default_factory=dict)
    tasks: Dict[str, ParsedTask] = field(default_factory=dict)
    dependencies: List[Tuple[str, str]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    has_dag_definition: bool = False


def _safe_literal(node: ast.AST) -> Optional[str]:
    try:
        value = ast.literal_eval(node)
    except Exception:
        return None
    return str(value)


def _extract_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _extract_task_refs(node: ast.AST) -> List[str]:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        refs: List[str] = []
        for element in node.elts:
            refs.extend(_extract_task_refs(element))
        return refs
    name = _extract_name(node)
    return [name] if name else []


class AirflowDagParser(ast.NodeVisitor):
    def __init__(self) -> None:
        self.dag = ParsedDAG()
        self.task_vars: Dict[str, str] = {}

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call):
            func_name = _extract_name(node.value.func)
            if func_name == "DAG":
                self._capture_dag_meta(node.value)
            elif func_name and (
                func_name.endswith("Operator") or func_name.endswith("Sensor")
            ):
                task_id, params = self._capture_task_params(node.value)
                if task_id:
                    for target in node.targets:
                        name = _extract_name(target)
                        if name:
                            self.task_vars[name] = task_id
                    self.dag.tasks[task_id] = ParsedTask(
                        task_id=task_id, operator=func_name, params=params
                    )
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                func_name = _extract_name(item.context_expr.func)
                if func_name == "DAG":
                    self._capture_dag_meta(item.context_expr)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            owner = _extract_name(node.func.value)
            if method in {"set_downstream", "set_upstream"} and owner:
                for arg in node.args:
                    refs = _extract_task_refs(arg)
                    for ref in refs:
                        if method == "set_downstream":
                            self._add_dependency(owner, ref)
                        else:
                            self._add_dependency(ref, owner)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        if isinstance(node.op, ast.RShift):
            left = _extract_task_refs(node.left)
            right = _extract_task_refs(node.right)
            self._wire_dependencies(left, right)
        elif isinstance(node.op, ast.LShift):
            left = _extract_task_refs(node.left)
            right = _extract_task_refs(node.right)
            self._wire_dependencies(right, left)
        self.generic_visit(node)

    def _capture_dag_meta(self, call: ast.Call) -> None:
        self.dag.has_dag_definition = True
        for keyword in call.keywords:
            key = keyword.arg
            if not key:
                continue
            literal = _safe_literal(keyword.value)
            if key == "schedule_interval" and literal:
                self.dag.schedule_interval = literal
            elif key == "dag_id" and literal:
                self.dag.dag_id = literal
            elif key == "default_args" and isinstance(keyword.value, ast.Dict):
                for key_node, value_node in zip(
                    keyword.value.keys, keyword.value.values
                ):
                    arg_key = _safe_literal(key_node)
                    arg_value = _safe_literal(value_node)
                    if arg_key and arg_value:
                        self.dag.default_args[arg_key] = arg_value
        if not self.dag.dag_id and call.args:
            literal = _safe_literal(call.args[0])
            if literal:
                self.dag.dag_id = literal

    def _capture_task_params(self, call: ast.Call) -> Tuple[Optional[str], Dict[str, str]]:
        params: Dict[str, str] = {}
        task_id: Optional[str] = None
        for keyword in call.keywords:
            key = keyword.arg
            if not key:
                continue
            literal = _safe_literal(keyword.value)
            if key == "task_id":
                task_id = literal
            elif literal:
                params[key] = literal
        return task_id, params

    def _resolve_task(self, ref: str) -> str:
        return self.task_vars.get(ref, ref)

    def _add_dependency(self, upstream_ref: str, downstream_ref: str) -> None:
        upstream = self._resolve_task(upstream_ref)
        downstream = self._resolve_task(downstream_ref)
        self.dag.dependencies.append((upstream, downstream))

    def _wire_dependencies(self, left: List[str], right: List[str]) -> None:
        for upstream in left:
            for downstream in right:
                self._add_dependency(upstream, downstream)


def parse_airflow_file(path: str, content: str) -> ParsedDAG:
    parser = AirflowDagParser()
    try:
        parser.visit(ast.parse(content))
    except SyntaxError:
        parser.dag.notes.append(f"Unable to parse {path} with AST; skipped.")
        return parser.dag

    text_deps = re.findall(r"([A-Za-z0-9_]+)\s*>>\s*([A-Za-z0-9_]+)", content)
    for upstream, downstream in text_deps:
        parser._add_dependency(upstream, downstream)

    if not parser.dag.dag_id:
        parser.dag.dag_id = path.split("/")[-1].replace(".py", "")

    return parser.dag
