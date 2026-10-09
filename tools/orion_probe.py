#!/usr/bin/env python3
"""Read-only probe for the Intergas Orion (ARCH_2_0) cloud API.

Signs in and prints your heaters and zones as JSON, so you can check what the
API returns for your setup (useful when reporting issues). Nothing is written.

Usage:
    python3 orion_probe.py EMAIL            # prompts for the password
    INTERGAS_PASSWORD=... python3 orion_probe.py EMAIL

Ids, serial numbers, names and tokens are redacted by default so the output
is safe to paste into an issue. Use --no-redact to see everything.
"""
import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://app-api.orion.intergas.nl"  # fixed https base, so urlopen schemes are safe

REDACT_KEYS = {
    "jwt", "refresh_token", "access_token", "account_id", "heater_id",
    "gateway_id", "id", "serial_number", "email", "name", "mac", "mac_address",
}


def request(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)  # noqa: S310
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as err:
        return err.code, None


def redact(value):
    if isinstance(value, dict):
        return {
            k: ("<redacted>" if k in REDACT_KEYS and v is not None else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    parser.add_argument("--no-redact", action="store_true")
    args = parser.parse_args()
    show = (lambda x: x) if args.no_redact else redact

    password = os.environ.get("INTERGAS_PASSWORD") or getpass.getpass("Password: ")

    status, data = request("POST", "/v1/accounts/platform_check", body={"email": args.email})
    print("# platform_check:", status, json.dumps(data))
    if not data or data.get("platform") != "ARCH_2_0":
        sys.exit("This account is not on the ARCH_2_0 (Orion) platform.")

    status, auth = request(
        "POST", "/v1/accounts/authenticate",
        body={"email": args.email, "password": password},
    )
    if status != 200 or not auth or not auth.get("jwt"):
        sys.exit(f"authenticate failed: HTTP {status}")
    token, aid = auth["jwt"], auth["account_id"]
    print("# authenticate: OK")

    status, heaters = request("GET", f"/v1/accounts/{aid}/heaters", token)
    print("# heaters:", status)
    print(json.dumps(show(heaters), indent=2))

    for heater in heaters or []:
        hid = heater.get("heater_id")
        status, zones = request("GET", f"/v1/accounts/{aid}/heaters/{hid}/zones", token)
        print("# zones:", status)
        print(json.dumps(show(zones), indent=2))


if __name__ == "__main__":
    main()
