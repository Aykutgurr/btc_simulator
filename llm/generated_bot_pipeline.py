# -*- coding: utf-8 -*-
"""
Shared LLM bot generation: extract code, validate, write file, import, registry, sandbox.
Used by web_api and the PyQt desktop app.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from llm.client_ollama import OllamaClient
from llm.prompts import bot_repair_user_prompt, bot_system_prompt, bot_user_prompt

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_REGISTRY_PATH = REPO_ROOT / "generated_bots_registry.json"
GENERATED_DIR = REPO_ROOT / "bots" / "generated"
SANDBOX_RUNNER = REPO_ROOT / "sandbox_runner.py"

VALID_TIMEFRAMES = frozenset({"1m", "5m", "15m", "1h", "4h"})


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def slugify(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^\w\- ]+", "", s, flags=re.UNICODE)
    s = s.replace(" ", "_")
    s = re.sub(r"_+", "_", s)
    return s[:60] or "bot"


def relpath_to_repo(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO_ROOT))
    except Exception:
        return str(p)


def extract_python_codeblock(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r"```python\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if not m:
        return None
    code = m.group(1).strip()
    return code if code else None


def syntax_check(code: str) -> Optional[str]:
    try:
        compile(code, "<generated_bot>", "exec")
        return None
    except Exception as e:
        return str(e)


def validate_generated_bot_code(code: str) -> Optional[str]:
    allowed_engine_methods = {
        "get_position",
        "get_balance_usdt",
        "get_available_balance",
        "open_long",
        "open_short",
        "close_position",
        "close_partial",
        "update_position_parameters",
        "log_message",
    }

    forbidden_import_roots = {
        "os",
        "sys",
        "subprocess",
        "socket",
        "requests",
        "http",
        "urllib",
        "pathlib",
        "shutil",
        "importlib",
    }

    try:
        tree = ast.parse(code)
    except Exception as e:
        return f"AST parse failed: {e}"

    bad_engine_calls: set[str] = set()
    bad_imports: set[str] = set()
    uses_eval_exec = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = (alias.name or "").split(".")[0]
                if root in forbidden_import_roots:
                    bad_imports.add(root)
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0] if node.module else ""
            if root in forbidden_import_roots:
                bad_imports.add(root)

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "__import__"}:
                uses_eval_exec = True

        if isinstance(node, ast.Attribute):
            v = node.value
            if (
                isinstance(v, ast.Attribute)
                and isinstance(v.value, ast.Name)
                and v.value.id == "self"
                and v.attr == "trading_engine"
            ):
                attr = node.attr
                if attr not in allowed_engine_methods:
                    bad_engine_calls.add(attr)

    problems: List[str] = []
    if bad_imports:
        problems.append("Forbidden imports used: " + ", ".join(sorted(bad_imports)))
    if uses_eval_exec:
        problems.append("Forbidden builtins used: eval/exec/__import__")
    if bad_engine_calls:
        problems.append(
            "Invented TradingEngine methods: "
            + ", ".join(sorted(bad_engine_calls))
            + f". Allowed: {', '.join(sorted(allowed_engine_methods))}"
        )
    return "; ".join(problems) if problems else None


def import_generated_bot_with_error(
    path: Path, trading_engine: Any, data_engine: Any = None
) -> tuple[Optional[Any], Optional[str]]:
    """
    Load generated bot file. On failure returns (None, error_message).
    """
    try:
        if not path.is_file():
            return None, f"File not found: {path}"
        spec = importlib.util.spec_from_file_location(f"generated_{path.stem}", str(path))
        if spec is None or spec.loader is None:
            return None, "Could not create importlib module spec"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    except Exception as e:
        tb = traceback.format_exc()
        return None, f"Module exec failed: {type(e).__name__}: {e}\n{tb[-2500:]}"

    cls = getattr(mod, "GeneratedBot", None)
    if cls is None:
        return None, "No class named GeneratedBot in file."
    try:
        return cls(trading_engine, data_engine), None
    except Exception as e:
        tb = traceback.format_exc()
        return None, f"GeneratedBot() constructor failed: {type(e).__name__}: {e}\n{tb[-2000:]}"


def import_generated_bot(path: Path, trading_engine: Any, data_engine: Any = None) -> Optional[Any]:
    bot, _err = import_generated_bot_with_error(path, trading_engine, data_engine)
    return bot


def load_generated_registry() -> Dict[str, Dict[str, Any]]:
    try:
        if GENERATED_REGISTRY_PATH.is_file():
            data = json.loads(GENERATED_REGISTRY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_generated_registry(registry: Dict[str, Dict[str, Any]]) -> None:
    try:
        GENERATED_REGISTRY_PATH.write_text(
            json.dumps(registry, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def sandbox_has_bot_errors(report: Dict[str, Any]) -> Optional[str]:
    try:
        tail = report.get("logsTail") or []
        for line in tail:
            if isinstance(line, str) and "[bot_error]" in line:
                return line
    except Exception:
        pass
    return None


def run_sandbox_report_sync(
    *,
    bot_path: Path,
    bot_id: str,
    df_1m: pd.DataFrame,
    max_steps: int = 800,
    timeout: int = 20,
) -> Dict[str, Any]:
    tmpdir = Path(tempfile.gettempdir())
    csv_path = tmpdir / f"btc_sim_sandbox_{bot_id}.csv"
    try:
        df_out = df_1m.reset_index()
        if "datetime" not in df_out.columns and len(df_out.columns) > 0:
            df_out = df_out.rename(columns={df_out.columns[0]: "datetime"})
        df_out.to_csv(csv_path, index=False, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Failed to write sandbox csv: {e}"}

    max_steps = max(100, min(5000, int(max_steps)))
    timeout = max(5, min(180, int(timeout)))

    cmd = [
        sys.executable,
        str(SANDBOX_RUNNER),
        "--bot-path",
        str(bot_path),
        "--csv-path",
        str(csv_path),
        "--max-steps",
        str(max_steps),
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Sandbox timeout"}
    except Exception as e:
        return {"ok": False, "error": f"Sandbox failed: {e}"}

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:4000]
        return {"ok": False, "error": f"Sandbox error: {err}"}

    try:
        report = json.loads(proc.stdout or "{}")
    except Exception:
        report = {"ok": False, "error": "Invalid sandbox JSON output", "raw": (proc.stdout or "")[:2000]}
    return report


def _llm_chat_sync(client: OllamaClient, user_content: str, system: Optional[str]) -> tuple[str, Dict[str, Any]]:
    return client.chat([{"role": "user", "content": user_content}], system=system)


def generate_and_register_bot(
    trading_engine: Any,
    data_engine: Any,
    *,
    bot_name: str,
    timeframe: str,
    description: str,
    constraints: Optional[Dict[str, str]] = None,
    df_1m_for_sandbox: Optional[pd.DataFrame] = None,
    client: Optional[OllamaClient] = None,
) -> Dict[str, Any]:
    """
    Generate code with Ollama, validate, write under bots/generated, update registry.
    Returns ok, botId, path, compileOk or ok=False, error, raw (truncated).
    """
    name = (bot_name or "").strip()
    if not name:
        return {"ok": False, "error": "name required", "compileOk": False}
    tf = (timeframe or "").strip()
    if tf not in VALID_TIMEFRAMES:
        return {"ok": False, "error": "invalid timeframe", "compileOk": False}

    ollama = client or OllamaClient()
    prompt = bot_user_prompt(
        bot_name=name,
        timeframe=tf,
        description=description,
        constraints=constraints,
    )

    content = ""
    code: Optional[str] = None
    last_error: Optional[str] = None

    for attempt in range(1, 3):
        try:
            content, _raw = _llm_chat_sync(ollama, prompt, bot_system_prompt())
        except Exception as e:
            last_error = f"LLM call failed: {e}"
            break

        code = extract_python_codeblock(content)
        if not code:
            last_error = "No python code block returned by model."
            prompt = bot_repair_user_prompt(previous_code=content[:4000], error=last_error)
            continue

        syn = syntax_check(code)
        if syn:
            last_error = f"Syntax error: {syn}"
            prompt = bot_repair_user_prompt(previous_code=code, error=last_error)
            code = None
            continue

        val = validate_generated_bot_code(code)
        if val:
            last_error = f"Validation error: {val}"
            prompt = bot_repair_user_prompt(previous_code=code, error=last_error)
            code = None
            continue

        last_error = None
        break

    if last_error or not code:
        return {
            "ok": False,
            "compileOk": False,
            "error": last_error or "Generation failed",
            "raw": (content or "")[:2000],
        }

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(name)
    bot_id = f"{slug}_{int(datetime.now().timestamp())}"
    path = GENERATED_DIR / f"{bot_id}.py"
    try:
        path.write_text(code + "\n", encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Failed to write file: {e}", "compileOk": False}

    bot_obj: Optional[Any] = None
    import_err: Optional[str] = None
    bot_obj, import_err = import_generated_bot_with_error(path, trading_engine, data_engine)

    last_failure_detail = import_err

    for _attempt in range(2):
        err: Optional[str] = None
        if bot_obj is None:
            err = import_err or "Import failed (missing GeneratedBot or syntax/runtime error in module)."
        else:
            try:
                df_ok = df_1m_for_sandbox is not None and not df_1m_for_sandbox.empty
                if df_ok:
                    report = run_sandbox_report_sync(
                        bot_path=path,
                        bot_id=bot_id,
                        df_1m=df_1m_for_sandbox,
                        max_steps=800,
                        timeout=20,
                    )
                    bot_err = sandbox_has_bot_errors(report) if isinstance(report, dict) else None
                    if not report.get("ok", False) or bot_err:
                        extra = ""
                        if isinstance(report, dict) and report.get("error"):
                            extra = f" | sandbox: {report.get('error')}"
                        err = f"Sandbox: {bot_err or 'ok=False'}{extra}"
            except Exception as e:
                err = f"Sandbox smoke test failed: {e}\n{traceback.format_exc()[-1500:]}"

        if not err:
            break

        last_failure_detail = err

        try:
            repair_prompt = bot_repair_user_prompt(
                previous_code=path.read_text(encoding="utf-8")[:6000],
                error=err or "unknown",
            )
            content2, _ = _llm_chat_sync(ollama, repair_prompt, bot_system_prompt())
            code2 = extract_python_codeblock(content2) or ""
            syn2 = syntax_check(code2) if code2 else "No code block"
            val2 = validate_generated_bot_code(code2) if (not syn2 and code2) else None
            if syn2 or val2 or not code2:
                bot_obj = None
                import_err = f"Repair code invalid: syntax={syn2!r} validation={val2!r}"
                last_failure_detail = import_err
            else:
                path.write_text(code2 + "\n", encoding="utf-8")
                code = code2
                bot_obj, import_err = import_generated_bot_with_error(path, trading_engine, data_engine)
                last_failure_detail = import_err or err
        except Exception as e:
            bot_obj = None
            import_err = f"Repair loop error: {e}\n{traceback.format_exc()[-1500:]}"
            last_failure_detail = import_err

    if bot_obj is None:
        detail = (last_failure_detail or import_err or "No further detail.")[:4000]
        return {
            "ok": False,
            "error": (
                "Generated code does not run after import or sandbox.\n\n"
                f"Detail:\n{detail}\n\n"
                f"File: {path}"
            ),
            "path": str(path),
            "compileOk": False,
        }

    resolved_name = getattr(bot_obj, "name", name)
    tff = getattr(bot_obj, "timeframe", tf)
    registry = load_generated_registry()
    entry = {
        "id": bot_id,
        "name": resolved_name,
        "timeframe": tff,
        "path": relpath_to_repo(path),
        "enabled": False,
        "createdAt": now_iso(),
        "lastTest": None,
    }
    registry[bot_id] = entry
    save_generated_registry(registry)

    return {
        "ok": True,
        "botId": bot_id,
        "path": str(path),
        "compileOk": True,
        "name": resolved_name,
        "timeframe": tff,
        "code": code[:8000],
        "bot": bot_obj,
        "entry": entry,
    }


def instantiate_registered_bots(trading_engine: Any, data_engine: Any = None) -> List[Any]:
    """Load all registry bots; skip entries that fail to import."""
    out: List[Any] = []
    registry = load_generated_registry()
    for _bot_id, meta in list(registry.items()):
        try:
            p = Path(meta.get("path", ""))
            if not p.is_absolute():
                p = (REPO_ROOT / p).resolve()
            bot = import_generated_bot(p, trading_engine, data_engine)
            if bot is not None:
                out.append(bot)
        except Exception:
            continue
    return out
