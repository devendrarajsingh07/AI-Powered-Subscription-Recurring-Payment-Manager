"""Operator-only invitation CLI. Codes are printed once to the operator, never logged."""

import argparse
import uuid

from pydantic import EmailStr, TypeAdapter
from sqlalchemy.orm import Session

from app.account_security import create_invite, revoke_invite
from app.db import get_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "revoke"))
    parser.add_argument("--issuer", type=uuid.UUID, required=True)
    parser.add_argument("--email")
    parser.add_argument("--invite-id", type=uuid.UUID)
    parser.add_argument("--hours", type=int, default=48)
    args = parser.parse_args()
    if args.action == "create" and not args.email:
        parser.error("create requires --email")
    if args.action == "revoke" and not args.invite_id:
        parser.error("revoke requires --invite-id")
    try:
        email = str(TypeAdapter(EmailStr).validate_python(args.email)) if args.email else None
        with Session(get_engine()) as db, db.begin():
            if args.action == "create":
                row, token = create_invite(db, args.issuer, email, hours=args.hours)
                result = (row.id, token)
            else:
                revoke_invite(db, args.issuer, args.invite_id)
                result = None
    except Exception:
        parser.exit(1, "Invite operation failed; check arguments, issuer and database readiness.\n")
    if result:
        print(f"Invite ID: {result[0]}\nSingle-use code (keep private): {result[1]}")
    else:
        print("Invite revoked.")


if __name__ == "__main__":
    main()
