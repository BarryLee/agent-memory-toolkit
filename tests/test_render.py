"""Integration tests for `scripts/render.py`.

These run the real script as a subprocess against a temp directory.
The vault path is `.resolve()`-d before being handed to the script
to side-step macOS's `/tmp` -> `/private/tmp` symlink.

The script reads:
  1. `--config` (project-level, default `scripts/config/install.yaml`)
  2. `~/.config/memory-solution/install.yaml` (user-level override)
  3. env vars listed in `ENV_OVERRIDES` (e.g. `MEMORY_VAULT_ROOT`)

To test (2) in isolation we override `HOME` for the subprocess so
`USER_CONFIG` expands to a path under the temp dir that we control.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "render.py"
SKILLS_SRC = REPO_ROOT / "skills"
DEFAULT_CONFIG = REPO_ROOT / "scripts" / "config" / "install.yaml"


# --- helpers ----------------------------------------------------------------


def _run(
    *args: str,
    config: Path | None = None,
    dest: Path | None = None,
    env_extra: dict[str, str] | None = None,
    home: Path | None = None,
) -> subprocess.CompletedProcess:
    """Invoke `render.py` as a subprocess with controlled env.

    - `home`: if set, the subprocess's $HOME; ensures the user-level
      `~/.config/memory-solution/install.yaml` is looked up under this
      directory (and therefore is absent unless we create it).
    - `env_extra`: extra env vars to set on top of the current env.
    """
    cmd: list[str] = [sys.executable, str(SCRIPT)]
    if config is not None:
        cmd += ["--config", str(config)]
    cmd += ["--dest", str(dest)]
    cmd += list(args)

    env = os.environ.copy()
    if home is not None:
        env["HOME"] = str(home)
    if env_extra:
        env.update(env_extra)

    return subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)


# --- happy path -------------------------------------------------------------


def test_happy_path_renders_skills(tmp_path):
    """With the default project config and a temp HOME (so no user
    config exists), render.py runs cleanly and writes one SKILL.md per
    skill under the destination."""
    dest = tmp_path / "out"
    result = _run("--dry-run", dest=dest, home=tmp_path)
    assert result.returncode == 0, result.stderr
    # No files actually written in dry-run.
    assert not dest.exists() or list(dest.rglob("*")) == []


def test_happy_path_actually_writes_when_not_dry_run(tmp_path):
    """Without `--dry-run`, render.py writes one SKILL.md per skill."""
    dest = tmp_path / "out"
    result = _run(dest=dest, home=tmp_path)
    assert result.returncode == 0, result.stderr
    rendered = sorted(p.relative_to(dest) for p in dest.rglob("SKILL.md"))
    # Every skill directory under skills/ should produce a SKILL.md.
    expected = sorted(
        p.name + "/SKILL.md"
        for p in SKILLS_SRC.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file()
    )
    assert rendered == [Path(p) for p in expected]


def test_renders_substitutes_known_vars(tmp_path):
    """The bundled skills use ${VAULT_ROOT}; after rendering, no
    `${...}` placeholder should remain in any rendered SKILL.md."""
    dest = tmp_path / "out"
    result = _run(dest=dest, home=tmp_path)
    assert result.returncode == 0, result.stderr
    placeholder_re = re.compile(r"\$\{[A-Z][A-Z0-9_]*\}")
    for skill_md in dest.rglob("SKILL.md"):
        text = skill_md.read_text()
        assert not placeholder_re.search(text), (
            f"unrendered placeholder in {skill_md}: "
            f"{placeholder_re.findall(text)}"
        )


# --- override precedence ----------------------------------------------------


def test_env_var_overrides_config(tmp_path):
    """MEMORY_VAULT_ROOT=... wins over the YAML value; check the
    rendered SKILL.md contains the override and not the default."""
    dest = tmp_path / "out"
    override = "/tmp/render-test-vault-from-env"
    result = _run(
        dest=dest,
        home=tmp_path,
        env_extra={"MEMORY_VAULT_ROOT": override},
    )
    assert result.returncode == 0, result.stderr
    any_match = False
    for skill_md in dest.rglob("SKILL.md"):
        text = skill_md.read_text()
        if override in text:
            any_match = True
        # The default vault path must not appear (it would mean env
        # override didn't take effect).
        assert "~/Documents/agentstuffs" not in text
    assert any_match, f"env override {override!r} not found in any rendered SKILL.md"


def test_user_config_overrides_project_config(tmp_path):
    """When both project and user config exist, the user one wins.
    We write a user config with a distinctive vault_root and assert
    that value shows up in the rendered SKILL.md files that use the
    var (not every SKILL.md references every var)."""
    dest = tmp_path / "out"
    user_config_dir = tmp_path / ".config" / "memory-solution"
    user_config_dir.mkdir(parents=True)
    user_value = "/tmp/render-test-vault-from-user-config"
    (user_config_dir / "install.yaml").write_text(f"vault_root: {user_value}\n")

    result = _run(dest=dest, home=tmp_path)
    assert result.returncode == 0, result.stderr
    any_match = False
    for skill_md in dest.rglob("SKILL.md"):
        text = skill_md.read_text()
        # The project default must never appear — that would mean the
        # user override didn't win.
        assert "~/Documents/agentstuffs" not in text
        if user_value in text:
            any_match = True
    # At least one rendered skill must contain the user-config value
    # (those that reference ${VAULT_ROOT}).
    assert any_match, f"user override {user_value!r} not found in any rendered SKILL.md"


# --- warning behaviour ------------------------------------------------------


def test_warns_on_unknown_var(tmp_path, capfd):
    """If the config sets only some of the vars a skill needs, the
    script warns per file and leaves the unset placeholder literal.

    We synthesize a SKILL source by pointing --skills-src at a temp
    dir containing one skill that uses a var we don't provide."""
    skills_src = tmp_path / "skills"
    skill = skills_src / "fake"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("vault at ${VAULT_ROOT}\nother ${MISSING_VAR}\n")

    config = tmp_path / "install.yaml"
    config.write_text("vault_root: /some/vault\n")

    dest = tmp_path / "out"
    result = _run(
        "--skills-src", str(skills_src),
        config=config,
        dest=dest,
        home=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    # Warnings go to stderr.
    assert "MISSING_VAR" in result.stderr
    # The known var IS rendered; the unknown one is left literal.
    rendered = (dest / "fake" / "SKILL.md").read_text()
    assert "/some/vault" in rendered
    assert "${MISSING_VAR}" in rendered


# --- fail-loud error behaviour ---------------------------------------------


def test_dies_when_project_config_missing(tmp_path):
    """When --config points to a non-existent file AND there is no
    user-level config to fall back on, render.py must abort with a
    non-zero exit and a message that points at the bundled example."""
    bogus = tmp_path / "no-such-install.yaml"
    assert not bogus.exists()
    dest = tmp_path / "out"
    result = _run(config=bogus, dest=dest, home=tmp_path)
    assert result.returncode != 0, result.stdout
    # The error must name the missing file and point at the example.
    assert "no-such-install.yaml" in result.stderr
    assert "install.example.yaml" in result.stderr
    # Nothing should have been written.
    assert not dest.exists() or list(dest.rglob("*")) == []


def test_dies_when_user_config_does_not_rescue_missing_project(tmp_path):
    """Regression guard: the script must not silently render with an
    empty config. Setting HOME to an empty temp dir means no user
    config exists either, so the script must die."""
    empty_home = tmp_path / "empty-home"
    empty_home.mkdir()
    bogus = tmp_path / "also-missing.yaml"
    dest = tmp_path / "out"
    result = _run(config=bogus, dest=dest, home=empty_home)
    assert result.returncode != 0
    # USER_CONFIG path must appear in the error so the user knows
    # where else they could have provided a config.
    assert ".config/memory-solution/install.yaml" in result.stderr