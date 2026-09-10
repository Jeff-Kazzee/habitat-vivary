#!/usr/bin/env python3
"""Exercise habitat.sh with a recording Docker stub."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def find_bash() -> Path:
    if os.name != "nt":
        found = shutil.which("bash")
        if found:
            return Path(found).resolve()
    else:
        for path in (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/usr/bin/bash.exe",
        ):
            if path.is_file():
                return path.resolve()
    raise RuntimeError("Git for Windows Bash or Linux Bash is required")


def shell_path(path: Path) -> str:
    path = path.resolve()
    if os.name != "nt":
        return str(path)
    return f"/{path.drive[0].lower()}/{path.as_posix()[3:]}"


def main() -> int:
    try:
        bash = find_bash()
    except RuntimeError as error:
        print(f"FAIL: test harness: {error}", file=sys.stderr)
        print("test-cli: passed 0 of 0 tests", file=sys.stderr)
        return 1
    token = uuid.uuid4().hex
    work = SCRIPTS / f".test-cli-{token}"
    checkouts = work / "case"
    mock_bin = work / "bin"
    failures: list[str] = []
    passed = 0
    tests = 0

    def check(name: str, condition: bool, detail: str) -> None:
        nonlocal tests, passed
        tests += 1
        if condition:
            passed += 1
        else:
            failures.append(f"{name}: {detail}")

    try:
        work.mkdir()
        checkouts.mkdir()
        mock_bin.mkdir()
        owner = work / "owner"
        owner.write_text(token + "\n", encoding="utf8", newline="\n")
        wrapper = checkouts / "habitat.sh"
        shutil.copyfile(ROOT / "habitat.sh", wrapper)
        wrapper.chmod(0o755)
        docker = mock_bin / "docker"
        docker.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\nprintf '%s\\0' \"$@\" > \"$HABITAT_DOCKER_LOG\"\n",
            encoding="utf8", newline="\n",
        )
        docker.chmod(0o755)

        environment = os.environ.copy()
        environment.pop("BASH_ENV", None)
        environment.pop("ENV", None)
        environment["PATH"] = str(mock_bin) + os.pathsep + environment.get("PATH", "")

        def invoke(*arguments: str, env_file: bool = True):
            log = work / "docker-argv"
            log.unlink(missing_ok=True)
            marker = checkouts / "SOURCED"
            marker.unlink(missing_ok=True)
            dot_env = checkouts / ".env"
            dot_env.unlink(missing_ok=True)
            if env_file:
                dot_env.write_text(
                    "COMPOSE_PROJECT_NAME=habitat-test\n"
                    "HABITAT_PROJECT_DIR=/home/test/project\n"
                    'HABITAT_SENTINEL=$(touch "$repo_dir/SOURCED")\n',
                    encoding="utf8", newline="\n",
                )
            run_env = environment.copy()
            run_env["HABITAT_DOCKER_LOG"] = shell_path(log)
            result = subprocess.run(
                [str(bash), "--noprofile", "--norc", shell_path(wrapper), *arguments], cwd=checkouts,
                env=run_env, stdin=subprocess.DEVNULL, capture_output=True,
                text=True, timeout=15, check=False,
            )
            argv = log.read_bytes().split(b"\0")[:-1] if log.is_file() else []
            return result, [item.decode() for item in argv], marker.exists()

        result, argv, _ = invoke("bogus")
        check("invalid action", result.returncode == 2 and not argv, "must refuse before Docker")
        result, argv, _ = invoke("status", "extra")
        check("extra arguments", result.returncode == 2 and not argv, "must refuse before Docker")
        result, argv, _ = invoke("status", env_file=False)
        check("missing env", result.returncode == 2 and not argv, "must refuse before Docker")
        result, argv, sourced = invoke("check")
        check("config", result.returncode == 0 and argv[-2:] == ["config", "--quiet"] and not sourced,
              "must render config without sourcing .env")
        result, argv, _ = invoke("start")
        check("start", result.returncode == 0 and argv[-3:] == ["up", "-d", "--no-build"],
              "must start without building")
        result, argv, _ = invoke("stop")
        check("stop", result.returncode == 0 and argv[-3:] == ["down", "--timeout", "10"]
              and "-v" not in argv and "--volumes" not in argv, "must preserve volumes")
        result, argv, _ = invoke("shell")
        check("shell", result.returncode == 0 and argv[-3:] == ["exec", "dev", "/bin/bash"]
              and "up" not in argv, "must not start services")
        result, argv, _ = invoke("status")
        check("status", result.returncode == 0 and argv[-2:] == ["ps", "--all"]
              and "up" not in argv, "must not start services")
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        failures.append(f"test harness: {type(error).__name__}: {error}")
    finally:
        expected_parent = SCRIPTS.resolve()
        if work.exists():
            if work.is_symlink() or work.resolve().parent != expected_parent or work.name != f".test-cli-{token}":
                failures.append("refused cleanup outside the owned test directory")
            elif not (work / "owner").is_file() or (work / "owner").is_symlink():
                failures.append("refused cleanup without the ownership marker")
            elif (work / "owner").read_text(encoding="utf8") != token + "\n":
                failures.append("refused cleanup after ownership marker changed")
            else:
                shutil.rmtree(work)

    if tests == 0:
        failures.append("no tests ran")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"test-cli: passed {passed} of {tests} tests", file=sys.stderr)
        return 1
    print(f"test-cli: passed {passed} of {tests} tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
