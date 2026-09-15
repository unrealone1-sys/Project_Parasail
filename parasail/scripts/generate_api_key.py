"""Generate an API key + its SHA-256 hash for ParaSail role-based access.

Prints a random key and the hash to paste into config.yaml:

    security:
      api_keys:
        - {name: ops, key_hash: <hash>, role: admin}

Usage:
  python scripts/generate_api_key.py                # random key, admin role
  python scripts/generate_api_key.py --role officer
  python scripts/generate_api_key.py --name survey-boat --role officer
"""
from __future__ import annotations

import argparse
import hashlib
import secrets


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--name", default="ops",
                    help="label for this key (who/what it belongs to)")
    ap.add_argument("--role", default="admin",
                    choices=["officer", "admin"],
                    help="role granted by this key")
    args = ap.parse_args()

    key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(key.encode()).hexdigest()

    print("API key (store securely - shown once):")
    print(f"  {key}")
    print()
    print("Paste into config.yaml -> security.api_keys:")
    print("  api_keys:")
    print(f"    - name: {args.name}")
    print(f"      key_hash: {key_hash}")
    print(f"      role: {args.role}")
    print()
    print("Use it as a header:  X-API-Key: <the key above>")
    print("Roles: officer = read privileged data; admin = officer + model")
    print("switching and the subscriber list. See docs/SECURITY.md.")


if __name__ == "__main__":
    main()
