"""Static scanner for uploaded Skill packages.

Scans:
- SKILL.md (and any other .md): regex for shell injection patterns
- *.py files: AST walk for dangerous calls/imports

Returns a list of finding dicts. Empty list = clean.
"""
from __future__ import annotations
import ast
import re
from pathlib import Path

# Shell-style danger patterns inside markdown / yaml / shell files
_SHELL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("rm_rf",          re.compile(r"\brm\s+-[rf]+(?:\s+/|\s+\*|\s+~)")),
    ("sudo_destruct",  re.compile(r"\bsudo\s+(?:rm|chmod|chown|dd|mkfs)\b")),
    ("chmod_777",      re.compile(r"\bchmod\s+(?:777|\+s)\b")),
    ("redirect_etc",   re.compile(r">\s*/etc/")),
    ("curl_pipe_sh",   re.compile(r"\bcurl\b[^\n]+\|\s*(?:bash|sh|zsh)\b")),
    ("wget_pipe_sh",   re.compile(r"\bwget\b[^\n]+\|\s*(?:bash|sh|zsh)\b")),
    ("rev_shell",      re.compile(r"\b(?:bash|sh)\s+-i\s+>\s*/dev/tcp/")),
    ("read_secrets",   re.compile(r"~/\.ssh/(?:id_rsa|authorized_keys)|/etc/(?:passwd|shadow|sudoers)")),
    ("nc_listen",      re.compile(r"\bnc\b\s+-l(?:vp)?\s+\d+")),
]

# Python AST denylist
_BAD_PY_FUNCS = {"eval", "exec", "compile", "__import__"}
# `os` was previously in this set, but `import os` is too common in legitimate
# skills (path joins, env reads, etc.) — we now police only the actually
# dangerous os APIs via _BAD_PY_ATTRS below.
_BAD_PY_MODULES = {"subprocess", "socket", "ctypes", "marshal", "pickle"}
_BAD_PY_ATTRS = {
    ("os", "system"), ("os", "popen"),
    ("os", "execv"), ("os", "execvp"), ("os", "execve"), ("os", "execvpe"),
    ("os", "spawnv"), ("os", "spawnvp"), ("os", "spawnve"), ("os", "spawnvpe"),
    ("os", "fork"), ("os", "forkpty"),
}


def _scan_text(content: str) -> list[dict]:
    findings = []
    for name, pat in _SHELL_PATTERNS:
        m = pat.search(content)
        if m:
            findings.append({"kind": "shell", "rule": name, "snippet": m.group(0)[:160]})
    return findings


def _scan_python(content: str) -> list[dict]:
    findings: list[dict] = []
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        findings.append({"kind": "py", "rule": "syntax_error", "snippet": str(e)})
        return findings
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in _BAD_PY_FUNCS:
                findings.append({"kind": "py", "rule": f"call:{f.id}",
                                 "snippet": f"{f.id}(...) at line {node.lineno}"})
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                pair = (f.value.id, f.attr)
                if pair in _BAD_PY_ATTRS:
                    findings.append({"kind": "py", "rule": f"call:{f.value.id}.{f.attr}",
                                     "snippet": f"{f.value.id}.{f.attr}(...) at line {node.lineno}"})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BAD_PY_MODULES:
                    findings.append({"kind": "py", "rule": f"import:{alias.name}",
                                     "snippet": f"import {alias.name} at line {node.lineno}"})
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _BAD_PY_MODULES:
                findings.append({"kind": "py", "rule": f"import:{node.module}",
                                 "snippet": f"from {node.module} import ... at line {node.lineno}"})
    return findings


SHELL_EXT = {".md", ".sh", ".bash", ".yml", ".yaml", ".txt"}


def scan_skill_dir(root: Path, max_files: int = 200) -> list[dict]:
    """Walk the skill directory and return all findings (empty = clean)."""
    findings: list[dict] = []
    count = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        count += 1
        if count > max_files:
            break
        if p.stat().st_size > 512 * 1024:  # skip huge files
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        ext = p.suffix.lower()
        rel = str(p.relative_to(root))
        if ext == ".py":
            for f in _scan_python(content):
                f["file"] = rel
                findings.append(f)
        elif ext in SHELL_EXT or p.name.lower() == "skill.md":
            for f in _scan_text(content):
                f["file"] = rel
                findings.append(f)
    return findings
