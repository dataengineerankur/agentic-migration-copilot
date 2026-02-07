import importlib.resources as resources
from string import Template
from typing import Any


def render_prompt(name: str, **kwargs: Any) -> str:
    template_text = resources.files("src.prompts.templates").joinpath(f"{name}.txt").read_text(encoding="utf-8")
    return Template(template_text).safe_substitute(**kwargs)
