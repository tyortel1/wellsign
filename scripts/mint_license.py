"""CLI for minting WellSign license keys.

Usage::

    python scripts/mint_license.py generate-keypair --out secrets/
    python scripts/mint_license.py mint \\
        --private-key secrets/license_private_key.pem \\
        --customer "Paloma Operating LLC" \\
        --project "Highlander Prospect" \\
        --days 365 \\
        --out secrets/issued/highlander.wslicense

The matching public key must be copied to
``src/wellsign/resources/license_public_key.pem`` (already gitignored if
sensitive).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from wellsign.license_.issue import generate_keypair, mint_license  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(prog="mint_license")
    sub = parser.add_subparsers(dest="cmd", required=True)

    gen = sub.add_parser("generate-keypair", help="Create a fresh RSA keypair (run once)")
    gen.add_argument("--out", type=Path, required=True)
    gen.add_argument("--name", default="license")

    mint = sub.add_parser("mint", help="Mint a signed license file for a project")
    mint.add_argument("--private-key", type=Path, required=True)
    mint.add_argument("--customer", required=True)
    mint.add_argument("--project", required=True)
    mint.add_argument("--days", type=int, default=365)
    mint.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()

    if args.cmd == "generate-keypair":
        priv, pub = generate_keypair(args.out, args.name)
        print(f"Private key (KEEP SECRET): {priv}")
        print(f"Public  key (ship in app): {pub}")
        print(f"Copy {pub.name} to src/wellsign/resources/license_public_key.pem")
        return 0

    if args.cmd == "mint":
        envelope = mint_license(
            private_key_path=args.private_key,
            customer=args.customer,
            project_name=args.project,
            valid_for_days=args.days,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
        print(f"Wrote license file: {args.out}")
        print(f"  customer: {envelope['payload']['customer']}")
        print(f"  project : {envelope['payload']['project_name']}")
        print(f"  expires : {envelope['payload']['expires_at']}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
