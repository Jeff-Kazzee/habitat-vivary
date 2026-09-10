#!/usr/bin/env python3
"""Verify the shareable Habitat source without contacting the Docker daemon."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_FILES = (
    ".env.example", "compose.yaml", "Dockerfile.dev", "Dockerfile.proxy",
    "squid.conf", "habitat.sh", "scripts/verify-source.py", "scripts/test-cli.py",
)
EXPECTED = {
    "proxy": {"cpus": 0.5, "memory": 256 * 1024**2, "pids": 64},
    "dev": {"cpus": 2.0, "memory": 2 * 1024**3, "pids": 256},
}


def integer(value: object) -> int | None:
    try:
        return int(value)  # Compose may encode byte counts as JSON strings.
    except (TypeError, ValueError):
        return None


def main() -> int:
    failures: list[str] = []
    count = 0

    def check(condition: bool, message: str) -> None:
        nonlocal count
        count += 1
        if not condition:
            failures.append(message)

    for name in TEXT_FILES:
        path = ROOT / name
        check(path.is_file() and not path.is_symlink(), f"missing or linked file: {name}")
        if path.is_file() and not path.is_symlink():
            raw = path.read_bytes()
            check(b"\r" not in raw and raw.endswith(b"\n"), f"file must use LF and end with a newline: {name}")

    command = [
        "docker", "compose", "--project-directory", str(ROOT),
        "--env-file", str(ROOT / ".env.example"), "-f", str(ROOT / "compose.yaml"),
        "config", "--format", "json",
    ]
    config = None
    try:
        rendered = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                  text=True, timeout=30, check=False)
        check(rendered.returncode == 0, "docker compose config failed")
        if rendered.returncode == 0:
            config = json.loads(rendered.stdout)
            check(isinstance(config, dict), "Compose output must be a JSON object")
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as error:
        failures.append(f"cannot render Compose config: {type(error).__name__}")

    if isinstance(config, dict):
        services = config.get("services", {})
        networks = config.get("networks", {})
        if not isinstance(services, dict) or not isinstance(networks, dict):
            failures.append("Compose services and networks must be JSON objects")
            services, networks = {}, {}
        check(set(services) == {"dev", "proxy"}, "services must be dev and proxy")
        check(set(networks) == {"egress", "sandbox"}, "networks must be egress and sandbox")
        check(networks.get("sandbox", {}).get("internal") is True, "sandbox network must be internal")
        check(networks.get("egress", {}).get("internal") is not True, "egress network must not be internal")

        binds = []
        for name, service in services.items():
            build = service.get("build", {})
            context = Path(build.get("context", "")).resolve()
            dockerfile = (context / build.get("dockerfile", "")).resolve()
            check(context == ROOT and dockerfile == ROOT / f"Dockerfile.{name}",
                  f"{name} build files must stay in the repository")
            check(service.get("read_only") is True, f"{name} root filesystem must be read-only")
            check(service.get("privileged") is not True, f"{name} must not be privileged")
            check(not service.get("ports") and service.get("network_mode") != "host",
                  f"{name} must not publish ports or use host networking")
            check(service.get("cap_drop") == ["ALL"] and not service.get("cap_add"),
                  f"{name} must drop all capabilities and add none")
            check("no-new-privileges:true" in service.get("security_opt", []),
                  f"{name} must prevent privilege escalation")
            check(service.get("restart") in (None, "", "no"), f"{name} must not restart automatically")
            policy = EXPECTED[name]
            check(float(service.get("cpus", 0)) == policy["cpus"], f"{name} CPU limit differs")
            check(integer(service.get("mem_limit")) == policy["memory"], f"{name} memory limit differs")
            check(integer(service.get("memswap_limit")) == policy["memory"], f"{name} swap limit differs")
            check(integer(service.get("pids_limit")) == policy["pids"], f"{name} PID limit differs")
            for volume in service.get("volumes", []):
                if volume.get("type") == "bind":
                    binds.append((name, volume))
                check("docker.sock" not in (str(volume.get("source", "")) + str(volume.get("target", ""))),
                      f"{name} must not mount the Docker socket")

        check(set(services.get("dev", {}).get("networks", {})) == {"sandbox"},
              "dev must use only the internal sandbox network")
        check(set(services.get("proxy", {}).get("networks", {})) == {"egress", "sandbox"},
              "proxy must bridge sandbox and egress")
        check(len(binds) == 1 and binds[0][0] == "dev", "exactly one project bind is allowed")
        if len(binds) == 1:
            bind = binds[0][1]
            check(bind.get("target") == "/workspace/project", "project bind target differs")
            check(bind.get("bind", {}).get("create_host_path") is False,
                  "project directory must exist before Compose runs")
        check(services.get("dev", {}).get("working_dir") == "/workspace/project",
              "dev working directory differs")
        check(services.get("dev", {}).get("depends_on", {}).get("proxy", {}).get("condition") == "service_healthy",
              "dev must wait for the proxy health check")
        check(bool(services.get("proxy", {}).get("healthcheck", {}).get("test")),
              "proxy must have a health check")

    for name, expected_user in (("Dockerfile.dev", "ubuntu"), ("Dockerfile.proxy", "proxy")):
        users = [line.split(None, 1)[1].strip() for line in (ROOT / name).read_text().splitlines()
                 if line.strip().upper().startswith("USER ")]
        check(users and users[-1] == expected_user, f"{name} must end on non-root user {expected_user}")
    check("COPY squid.conf /etc/squid/squid.conf" in (ROOT / "Dockerfile.proxy").read_text(),
          "proxy Dockerfile must copy the reviewed Squid config")

    if count == 0:
        failures.append("no checks ran")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        print(f"verify-source: failed {len(failures)} of {count} checks", file=sys.stderr)
        return 1
    print(f"verify-source: passed {count} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
