#!/usr/bin/env python3
"""One-run encrypted phone handoff; requires OpenSSL and contents:write."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = "runtime-control"


def run_id(value):
    if not re.fullmatch(r"[0-9]+", str(value)):
        raise SystemExit("run-id must contain only digits")
    return str(value)


def runtime_paths(rid, kind):
    temp = Path(os.environ["RUNNER_TEMP"]).resolve()
    stem = f"rednote-{rid}" + ("-otp" if kind == "otp" else "")
    return temp, stem, temp / f"{stem}.key.pem", temp / f"{stem}.state.json"


def api(method, path, body=None, timeout=20):
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    branch_ref = os.environ.get("GITHUB_REF", "")
    if not re.fullmatch(r"[^/]+/[^/]+", repo) or not token:
        raise SystemExit("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
    if not branch_ref.startswith("refs/heads/"):
        raise SystemExit("workflow must run from a branch ref")
    params = {"ref": branch_ref.removeprefix("refs/heads/")}
    url = f"https://api.github.com/repos/{repo}/contents/{path}?{urlencode(params)}"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
               "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "rednote-private-input"}
    data = json.dumps(body).encode() if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(Request(url, data=data, headers=headers, method=method), timeout=timeout) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        if method == "GET" and exc.code == 404:
            return None
        raise SystemExit(f"GitHub contents API failed ({exc.code})") from None
    except Exception:
        raise SystemExit("GitHub contents API request failed") from None


def secure_write(path, data, exclusive=False):
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


def generate(args):
    rid = run_id(args.run_id)
    temp, stem, key_path, state_path = runtime_paths(rid, args.kind)
    try:
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    except OSError:
        raise SystemExit("ephemeral key path already exists or is unavailable") from None
    try:
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
                        "rsa_keygen_bits:3072", "-out", str(key_path)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        pub = subprocess.run(["openssl", "pkey", "-in", str(key_path), "-pubout"],
                             check=True, capture_output=True).stdout
    except Exception:
        key_path.unlink(missing_ok=True)
        raise SystemExit("OpenSSL RSA key generation failed") from None
    nonce = secrets.token_hex(32)
    pub_path = f"{ROOT}/{stem}.pub.json"
    try:
        secure_write(state_path, json.dumps({"nonce": nonce, "kind": args.kind}).encode(), exclusive=True)
        old = api("GET", pub_path)
        announcement = {"run_id": rid, "nonce": nonce, "kind": args.kind, "public_key_pem": pub.decode("ascii")}
        commit = {"message": f"Add ephemeral Rednote {args.kind} key for run {rid}",
                  "content": base64.b64encode(json.dumps(announcement, separators=(",", ":")).encode()).decode("ascii"),
                  "branch": os.environ["GITHUB_REF"].removeprefix("refs/heads/")}
        if old and old.get("sha"):
            commit["sha"] = old["sha"]
        api("PUT", pub_path, commit)
    except BaseException:
        key_path.unlink(missing_ok=True)
        state_path.unlink(missing_ok=True)
        raise
    print(json.dumps(announcement, separators=(",", ":")))


def wait_for_command(args):
    rid = run_id(args.run_id)
    temp, stem, key_path, state_path = runtime_paths(rid, args.kind)
    output = Path(args.output) if args.output else temp / f"{stem}.{args.kind}.json"
    try:
        output.resolve().relative_to(temp)
    except ValueError:
        raise SystemExit("output must be inside RUNNER_TEMP") from None
    try:
        state = json.loads(state_path.read_text())
        nonce = state["nonce"]
        if state.get("kind", "phone") != args.kind:
            raise ValueError
        if not key_path.is_file():
            raise ValueError
    except Exception:
        raise SystemExit("ephemeral key state is unavailable") from None
    path = f"{ROOT}/{stem}.command.json"
    deadline = time.monotonic() + args.timeout
    try:
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            item = api("GET", path, timeout=max(0.1, min(20, remaining)))
            if item and item.get("content"):
                try:
                    command = json.loads(base64.b64decode(item["content"]))
                except Exception:
                    command = {}
                if command.get("run_id") == rid and secrets.compare_digest(str(command.get("nonce", "")), nonce):
                    if command.get("kind", "phone") != args.kind:
                        raise SystemExit("matching command kind mismatch")
                    try:
                        ciphertext = base64.b64decode(command["ciphertext"], validate=True)
                        if len(ciphertext) != 384:
                            raise ValueError
                        plain = subprocess.run(["openssl", "pkeyutl", "-decrypt", "-inkey", str(key_path),
                            "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
                            "-pkeyopt", "rsa_mgf1_md:sha256"], input=ciphertext,
                            check=True, capture_output=True).stdout
                        payload = json.loads(plain)
                        value = payload["phone"] if args.kind == "phone" else payload["otp"]
                        if payload.get("run_id") != rid or not secrets.compare_digest(str(payload.get("nonce", "")), nonce):
                            raise ValueError
                        if payload.get("kind", "phone") != args.kind:
                            raise ValueError
                        pattern = r"\+86[0-9]{11}" if args.kind == "phone" else r"[0-9]{4,8}"
                        if not isinstance(value, str) or not re.fullmatch(pattern, value):
                            raise ValueError
                    except Exception:
                        raise SystemExit("matching command could not be validated or decrypted") from None
                    print(f"::add-mask::{value}", flush=True)
                    if args.kind == "phone":
                        print(f"::add-mask::{value[3:]}", flush=True)
                    secure_write(output, json.dumps({args.kind: value}).encode(), exclusive=True)
                    print(f"{args.kind} input ready")
                    return
            time.sleep(min(5, max(0, deadline - time.monotonic())))
        raise SystemExit("timed out waiting for encrypted command")
    finally:
        key_path.unlink(missing_ok=True)
        state_path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    pub = sub.add_parser("generate", help="create an ephemeral key and publish its public key")
    pub.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID"), required=os.environ.get("GITHUB_RUN_ID") is None)
    pub.add_argument("--kind", choices=("phone", "otp"), default="phone")
    pub.set_defaults(func=generate)
    wait = sub.add_parser("wait", help="wait up to ten minutes, decrypt one command, then remove the key")
    wait.add_argument("--run-id", default=os.environ.get("GITHUB_RUN_ID"), required=os.environ.get("GITHUB_RUN_ID") is None)
    wait.add_argument("--kind", choices=("phone", "otp"), default="phone")
    wait.add_argument("--timeout", type=int, default=600)
    wait.add_argument("--output", help="JSON path (defaults to the matching phone/OTP file in RUNNER_TEMP)")
    wait.set_defaults(func=wait_for_command)
    args = parser.parse_args()
    if getattr(args, "timeout", 600) < 1 or getattr(args, "timeout", 600) > 600:
        parser.error("--timeout must be between 1 and 600 seconds")
    args.func(args)


if __name__ == "__main__":
    main()
