#!/usr/bin/env python3
"""Render SKILL.md files for installation by substituting ${VAR} placeholders.

Reads a YAML config (default: `scripts/config/install.yaml`), merges in
any user-level overrides from `~/.config/memory-solution/install.yaml`,
applies env-var overrides (e.g. `MEMORY_VAULT_ROOT`), and writes the
rendered files into a destination directory.

This is invoked by `scripts/install.sh` and is also runnable directly
for testing: `python3 scripts/render.py --dry-run`.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts._lib.config import load_yaml
    from scripts._lib.paths import die
else:
    from _lib.config import load_yaml
    from _lib.paths import die


# Mapping from env var name -> config key. Any env var in this map, if
# set, overrides the YAML value.
ENV_OVERRIDES = {
    "MEMORY_VAULT_ROOT": "vault_root",
}

# User-level override path. If it exists, it wins over the project-level
# config.
USER_CONFIG = Path("~/.config/memory-solution/install.yaml").expanduser()

DEFAULT_CONFIG = Path(__file__).resolve().parent / "config" / "install.yaml"
DEFAULT_SKILLS_SRC = Path(__file__).resolve().parent.parent / "skills"


_VAR_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def _merge_configs(base: dict, override: dict) -> dict:
    """Shallow merge; later wins."""
    out = dict(base)
    for k, v in override.items():
        if v is not None:
            out[k] = v
    return out


def _load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = load_yaml(path)
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        print(f"warning: {path} root is not a mapping; ignoring", file=sys.stderr)
        return {}
    return {str(k): str(v) if v is not None else "" for k, v in raw.items()}


def _apply_env(cfg: dict) -> dict:
    out = dict(cfg)
    for env_key, cfg_key in ENV_OVERRIDES.items():
        val = os.environ.get(env_key)
        if val:
            out[cfg_key] = val
    return out


def _require_config(cfg: dict, project_config: Path) -> None:
    """Die if no config could be loaded from anywhere.

    Order of precedence: project config, user config, env vars. If the
    merged result is empty, neither the project config nor the user
    config existed (or both were empty). Fail loud so the user copies
    the bundled example instead of silently rendering empty values —
    this matches the behaviour of `init_vault.py` and `sync_raw.py`.
    """
    if cfg:
        return
    die(
        f"no config found (tried {project_config} and {USER_CONFIG}).\n"
        f"Copy scripts/config/install.example.yaml to {project_config} "
        f"(or to {USER_CONFIG}) and edit it."
    )


def _substitute(text: str, vars: dict[str, str]) -> tuple[str, list[str]]:
    """Replace ${VAR} with vars[VAR]. Returns (text, list of missing vars).

    Variable names are case-insensitive — `${VaultRoot}`, `${vault_root}`,
    and `${VAULT_ROOT}` are all treated as the same key. Config keys may
    use any case; the lookup uppercases both sides.
    """
    upper = {k.upper(): v for k, v in vars.items()}
    missing: list[str] = []

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name.upper() in upper and upper[name.upper()] != "":
            return upper[name.upper()]
        missing.append(name)
        return m.group(0)

    out = _VAR_RE.sub(repl, text)
    return out, missing


def _render_file(src: Path, dest: Path, vars: dict[str, str], apply: bool) -> tuple[list[str], int]:
    text = src.read_text()
    rendered, missing = _substitute(text, vars)
    if missing:
        unique = sorted(set(missing))
        print(f"warning: {src.relative_to(src.parent.parent)} has unset vars: {unique}", file=sys.stderr)
    if apply:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered)
    return missing, len(rendered)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=f"Base config (default: {DEFAULT_CONFIG}).")
    parser.add_argument("--skills-src", type=Path, default=DEFAULT_SKILLS_SRC, help=f"Skills source dir (default: {DEFAULT_SKILLS_SRC}).")
    parser.add_argument("--dest", type=Path, required=True, help="Destination root (e.g. ~/.agents/skills).")
    parser.add_argument("--dry-run", action="store_true", help="Don't write; just show what would be rendered.")
    args = parser.parse_args()

    if not args.skills_src.exists():
        print(f"error: skills source not found: {args.skills_src}", file=sys.stderr)
        return 1

    cfg = _merge_configs(_load_config(args.config), _load_config(USER_CONFIG))
    cfg = _apply_env(cfg)
    _require_config(cfg, args.config)

    print(f"Config: {args.config} + user overrides + env")
    for k, v in sorted(cfg.items()):
        print(f"  {k} = {v}")
    print(f"Source: {args.skills_src}")
    print(f"Dest:   {args.dest}{' (dry-run)' if args.dry_run else ''}")
    print()

    if not args.dry_run:
        args.dest.mkdir(parents=True, exist_ok=True)

    total = 0
    for skill_dir in sorted(p for p in args.skills_src.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        dest_skill = args.dest / skill_dir.name
        dest_file = dest_skill / "SKILL.md"
        missing, size = _render_file(skill_md, dest_file, cfg, apply=not args.dry_run)
        # Also copy any non-SKILL.md files (assets, references) verbatim.
        for child in skill_dir.rglob("*"):
            if not child.is_file() or child == skill_md:
                continue
            rel = child.relative_to(skill_dir)
            target = dest_skill / rel
            if not args.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                # Use a simple copy: these files don't contain vars.
                target.write_bytes(child.read_bytes())
        action = "would render" if args.dry_run else "rendered  "
        print(f"  {action} {skill_dir.name}/SKILL.md ({size} bytes)")
        total += 1

    print(f"\nProcessed {total} skill(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
