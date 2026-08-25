#!/usr/bin/env python3
"""Prove the built wheel is importable before it can reach a consumer.

Why this exists
---------------
On 2026-08-23, commit df51202 landed five Python 2 ``except A, B:`` clauses on
main. That is a SyntaxError on every Python 3, so the affected modules could
not be imported at all -- ``pip install git+...`` produced a package that blew
up on import. Tags v2.1.0 and v2.2.0 both carry the defect.

Nothing in the pipeline stopped it, and the reason is worth recording:

* ``ruff check`` does **not** report it. Ruff's parser accepts the bare tuple
  in an except clause, so it exits 0 on a file CPython refuses to compile.
  Verified against ruff 0.16.4 on a four-line file containing nothing else.
* ``mypy`` does catch it -- and did, on every CI run since -- but mypy stops
  at the first syntax error, and its step had been red for unrelated reasons
  long enough that a red lint job was no longer information.
* Every downstream job (test, architecture, examples, package) ``needs:`` the
  lint job, so once lint went red the test suite and the package check never
  ran at all. The failure that would have been loudest was the one silenced.

So the guard cannot live behind the lint job, and it cannot rely on a linter.
It compiles and imports the *installed artifact*, which is the only thing that
actually answers "can a consumer import this?".

What it does
------------
1. Builds a wheel from the working tree.
2. Creates a throwaway virtualenv that shares nothing with the dev env.
3. Installs the wheel there (plus the runtime requirements, so the import
   sweep exercises real imports rather than tripping over absent third-party
   packages).
4. ``compileall`` over the *installed* package. This needs no dependencies and
   catches every syntax error in shipped bytes -- the hermetic half.
5. Imports every module the wheel ships, via ``pkgutil.walk_packages``.
6. Resolves every ``console_scripts`` entry point the installed distribution
   declares, and checks each one is actually callable.

Steps 4 and 5 are deliberately both present: compileall cannot catch an
import-time failure (a bad top-level call, a circular import), and the import
sweep cannot run at all if a dependency is missing. Together they cover the
"shipped package is unusable" class.

Step 6 covers a class neither of them can reach, and it is not hypothetical:
``TASK-002`` shipped ``sagittarius-audit`` as a documented, ✅-completed
feature while the command could not start at all, and that survived a month.
Three separate faults were involved, and steps 4 and 5 are blind to every one
of them:

* The target module imported ``PySide6`` at module scope while the wheel
  declares no dependencies, so the command died before reaching its own code.
* Its inner imports were bare (``from application...``), resolving only when
  the process happened to start in one specific directory.
* The entry point named ``pkg.module`` where a *function* was required, so
  the generated launcher called a module object.

Steps 4 and 5 miss all three because the script lived in a package the sweep
does not walk, and because importing a module is not the same as resolving
``module:attr`` and confirming the result can be called. An entry point is a
promise printed into the distribution's metadata; nothing else here checks
that the promise is kept.

Step 6 resolves but never *invokes* the target. Running it would launch the
application -- a GUI, a server, a REPL -- which is not something a CI guard
can do meaningfully. Resolution plus a callability check catches all three
faults above without starting anything.

Both sweeps are strict: any failure fails the build. As of this commit every
module in the package imports cleanly under the declared requirements, so
there is no exemption list to maintain -- and adding one should be a
deliberate, argued change rather than a quiet append.

Usage::

    python scripts/verify_wheel_importable.py            # build, then verify
    python scripts/verify_wheel_importable.py --wheel dist/foo.whl

Exit code 0 means a consumer can install and import this package.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "sagittarius_engine"

# Run inside the throwaway venv. Kept as source text rather than a file in the
# repo so the checks cannot accidentally pick up the working tree instead of
# the installed package -- it executes with cwd set outside the repo.
_VERIFY = r"""
import compileall, importlib, pkgutil, sys, traceback
from importlib.metadata import distribution

package = sys.argv[1]
dist_name = sys.argv[2]

try:
    pkg = importlib.import_module(package)
except BaseException:
    print(f"FAIL: cannot import {package!r} at all", flush=True)
    traceback.print_exc()
    sys.exit(1)

root = pkg.__path__[0]
print(f"installed at: {root}", flush=True)

# --- 1. syntax gate over the installed files (no dependencies needed) -------
print("\n[1/3] compileall over the installed package", flush=True)
if not compileall.compile_dir(root, quiet=1, force=True):
    print("FAIL: the installed package contains files that do not compile.")
    sys.exit(1)
print("ok - every shipped module compiles", flush=True)

# --- 2. import every module the wheel ships --------------------------------
print("\n[2/3] importing every shipped module", flush=True)
failures = []
count = 0
for info in pkgutil.walk_packages(pkg.__path__, package + "."):
    count += 1
    try:
        importlib.import_module(info.name)
    except BaseException as exc:
        failures.append((info.name, traceback.format_exc()))
        print(f"  FAIL {info.name}: {type(exc).__name__}: {exc}", flush=True)

if failures:
    print(f"\nFAIL: {len(failures)} of {count} modules failed to import.\n")
    for name, tb in failures:
        print("=" * 70)
        print(name)
        print(tb)
    sys.exit(1)

print(f"ok - all {count} shipped modules imported", flush=True)

# --- 3. resolve every console script the distribution advertises ------------
# An entry point is a promise written into the metadata: "this command exists
# and can be run". Steps 1 and 2 cannot check it -- the target may live in a
# package the sweep does not walk, and importing a module proves nothing about
# whether `module:attr` resolves to something callable.
print("\n[3/3] resolving declared console scripts", flush=True)
scripts = [ep for ep in distribution(dist_name).entry_points
           if ep.group == "console_scripts"]

if not scripts:
    print("ok - the distribution declares no console scripts", flush=True)
else:
    bad = []
    for ep in sorted(scripts, key=lambda e: e.name):
        try:
            # .load() imports the module and walks to the attribute -- the
            # same two steps the generated launcher performs. It does not
            # call it; invoking a console script would start the application.
            target = ep.load()
        except BaseException as exc:
            bad.append((ep.name, f"{ep.value} -> {type(exc).__name__}: {exc}",
                        traceback.format_exc()))
            print(f"  FAIL {ep.name} = {ep.value}: "
                  f"{type(exc).__name__}: {exc}", flush=True)
            continue

        if not callable(target):
            kind = type(target).__name__
            bad.append((ep.name,
                        f"{ep.value} resolves to a {kind}, which is not callable"
                        " -- the generated launcher would raise TypeError",
                        ""))
            print(f"  FAIL {ep.name} = {ep.value}: resolves to a {kind}, "
                  f"not a callable", flush=True)
            continue

        print(f"  ok   {ep.name} = {ep.value}", flush=True)

    if bad:
        print(f"\nFAIL: {len(bad)} of {len(scripts)} console scripts "
              f"cannot be run by a consumer.\n")
        for name, reason, tb in bad:
            print("=" * 70)
            print(f"{name}: {reason}")
            if tb:
                print(tb)
        sys.exit(1)

    print(f"ok - all {len(scripts)} console scripts resolve to a callable",
          flush=True)

print("\nPASS: the built wheel installs, imports, and every advertised "
      "command resolves.")
"""


def run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a command, echoing it, and abort the guard if it fails."""
    print("$ " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=cwd)


def build_wheel(outdir: Path) -> Path:
    run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(outdir)],
        cwd=REPO_ROOT,
    )
    wheels = glob.glob(str(outdir / "*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one wheel in {outdir}, found {wheels}")
    return Path(wheels[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--wheel",
        help="verify an already-built wheel instead of building one",
    )
    parser.add_argument(
        "--requirements",
        default=str(REPO_ROOT / "requirements.txt"),
        help="runtime requirements installed alongside the wheel",
    )
    args = parser.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="wheel-guard-"))
    try:
        wheel = Path(args.wheel).resolve() if args.wheel else build_wheel(tmp / "dist")
        print(f"\nverifying wheel: {wheel.name}\n", flush=True)

        env_dir = tmp / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        py = (
            env_dir
            / ("Scripts" if os.name == "nt" else "bin")
            / ("python.exe" if os.name == "nt" else "python")
        )

        run([str(py), "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        if Path(args.requirements).exists():
            run([str(py), "-m", "pip", "install", "--quiet", "-r", args.requirements])

        # Installing the wheel is itself a check, not just setup. A
        # requires-python floor above the interpreter a consumer actually runs
        # makes the package uninstallable, which fails "can a consumer use
        # this?" just as surely as a SyntaxError does -- so say so plainly
        # rather than surfacing a CalledProcessError traceback.
        install = subprocess.run(
            [str(py), "-m", "pip", "install", str(wheel)],
            capture_output=True,
            text=True,
        )
        if install.returncode != 0:
            output = install.stdout + install.stderr
            print(output, flush=True)
            if "requires a different Python" in output:
                print(
                    "\nFAIL: the wheel will not install on this interpreter.\n"
                    "  pyproject's requires-python floor excludes it. That is a\n"
                    "  packaging defect in its own right: the artifact is\n"
                    "  uninstallable for anyone below the floor, whether or not\n"
                    "  the code would have run there. Either lower the floor to\n"
                    "  the oldest version actually supported, or run this guard\n"
                    "  on an interpreter that satisfies it.",
                    flush=True,
                )
            else:
                print("\nFAIL: the wheel could not be installed.", flush=True)
            return 1

        script = tmp / "_verify.py"
        script.write_text(_VERIFY, encoding="utf-8")

        # cwd is deliberately outside the repository: run from REPO_ROOT and
        # the local sagittarius_engine/ source directory would shadow the
        # installed one, and the guard would verify the wrong bytes.
        # The distribution name is not the import name -- "sagittarius-engine"
        # vs "sagittarius_engine" -- and step 3 looks up metadata, not a
        # module. Take it from the wheel filename, whose first "-" field is
        # the distribution name by PEP 427, so the guard reads it off the
        # artifact rather than assuming it matches PACKAGE.
        dist_name = wheel.name.split("-")[0]

        result = subprocess.run(
            [str(py), str(script), PACKAGE, dist_name], cwd=str(tmp)
        )
        return result.returncode
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
