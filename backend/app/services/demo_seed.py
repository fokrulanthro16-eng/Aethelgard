"""
Demo seed data for Aethelgard hackathon demonstrations.

Creates a realistic demo scenario with:
- A demo user (James Hawthorne / demo@aethelgard.ai)
- 5 encrypted vault entries (bank, insurance, will, crypto wallet, contacts)
- Status advanced to PENDING_RELEASE (simulates an expired Dead Man's Switch)
- A ready-to-use nominee release token

Call setup_demo() to reset and repopulate the scenario from scratch.

TODO (before production): disable or protect the /demo/setup endpoint.
"""

from datetime import datetime, timedelta, timezone

from app.db.dynamodb import (
    delete_all_user_items,
    get_vault_table,
    mark_pending_release,
    put_encrypted_vault_entry,
    put_user_metadata,
)
from app.security.encryption import encrypt_text
from app.services.nominee import create_release_request

DEMO_EMAIL = "demo@aethelgard.ai"
DEMO_NOMINEE_EMAIL = "nominee@aethelgard.ai"

_DEMO_VAULT_ENTRIES = [
    {
        "entry_type": "credentials",
        "title": "Chase Checking Account",
        "sensitive_data": (
            "Bank: Chase Bank NA\n"
            "Account Number: 4782-XXXX-XXXX-1234\n"
            "Online Username: james.hawthorne@email.com\n"
            "Password: ChaseVault2024!@#\n"
            "Customer Service: 1-800-935-9935\n"
            "Branch: 500 Main St, Boston, MA 02101"
        ),
        "notes": "Joint account with Emily. Change the password immediately after accessing.",
    },
    {
        "entry_type": "document",
        "title": "State Farm Life Insurance",
        "sensitive_data": (
            "Provider: State Farm Life Insurance Company\n"
            "Policy Number: LF-789-456-321-HAW\n"
            "Coverage Amount: $500,000\n"
            "Primary Beneficiary: Emily Hawthorne (spouse) — 100%\n"
            "Agent: Michael Chen\n"
            "Agent Phone: 555-0147\n"
            "Claims Hotline: 1-800-SF-CLAIM (1-800-732-5246)\n"
            "Policy Documents: Home office, blue binder on top shelf"
        ),
        "notes": "Premium auto-pays from Chase checking on the 1st of each month.",
    },
    {
        "entry_type": "document",
        "title": "Last Will and Testament",
        "sensitive_data": (
            "Attorney: Johnson & Associates Law Firm\n"
            "Contact: David Johnson, Esq. — 555-0123\n"
            "Office: 220 State St, Suite 400, Boston, MA\n"
            "Document Location: Safety deposit box at Chase Bank (Main St)\n"
            "Key Location: Master bedroom dresser, top right drawer\n\n"
            "SUMMARY:\n"
            "Primary beneficiary: Emily Hawthorne (spouse)\n"
            "Secondary: James Jr. and Sarah in equal shares\n"
            "Charitable: 5% to St. Jude Children's Research Hospital\n"
            "Executor: Robert Hawthorne (brother)"
        ),
        "notes": "Last updated March 2024. Review after any major life event.",
    },
    {
        "entry_type": "credentials",
        "title": "Bitcoin Wallet — Primary",
        "sensitive_data": (
            "Wallet Type: Hardware (Ledger Nano X)\n"
            "Device Location: Top desk drawer, black leather case\n"
            "Device PIN: 7842\n\n"
            "RECOVERY PHRASE (24 words — keep absolutely secret):\n"
            "abandon ability able about above absent absorb abstract absurd\n"
            "abuse access accident account accuse achieve acid acoustic\n"
            "acquire across act action actor actress actual\n\n"
            "Full seed phrase backup: titanium plate in the fireproof safe\n"
            "Exchange: Coinbase — james.hawthorne@email.com\n"
            "Exchange Password: CryptoEx2024!\n"
            "Approximate Balance: ~0.45 BTC (as of January 2024)"
        ),
        "notes": "CRITICAL: Do not share the recovery phrase with anyone except direct heirs.",
    },
    {
        "entry_type": "note",
        "title": "Family Emergency Contacts",
        "sensitive_data": (
            "IMMEDIATE FAMILY:\n"
            "Emily Hawthorne (Spouse): 555-0101\n"
            "James Hawthorne Jr. (Son): 555-0102\n"
            "Sarah Hawthorne (Daughter): 555-0103\n\n"
            "EXTENDED FAMILY:\n"
            "Robert Hawthorne (Brother / Executor): 555-0105\n"
            "Margaret Thornton (Sister): 555-0106\n"
            "Patricia Hawthorne (Mother): 555-0107\n\n"
            "PROFESSIONALS:\n"
            "Dr. Patricia Williams (Family Doctor): 555-0104\n"
            "David Johnson (Attorney): 555-0123\n"
            "Christine Park (Financial Advisor): 555-0145\n"
            "Michael Chen (State Farm Agent): 555-0147\n\n"
            "EMERGENCY: 911\n"
            "Poison Control: 1-800-222-1222"
        ),
        "notes": None,
    },
]


def create_demo_user() -> dict:
    """Resets all demo user data and creates an account backdated 91 days to simulate expiry."""
    delete_all_user_items(DEMO_EMAIL)
    item = put_user_metadata(DEMO_EMAIL, DEMO_NOMINEE_EMAIL)

    # Backdate last_checkin_at and next_check_due_at so the demo user genuinely
    # appears to have missed their 90-day window. Without this, both timestamps
    # sit in the future (fresh creation), contradicting PENDING_RELEASE status.
    now = datetime.now(timezone.utc)
    overdue_checkin = (now - timedelta(days=91)).isoformat()
    overdue_due = (now - timedelta(days=1)).isoformat()

    table = get_vault_table()
    table.update_item(
        Key={"PK": item["PK"], "SK": "METADATA"},
        UpdateExpression="SET last_checkin_at = :checkin, next_check_due_at = :due",
        ExpressionAttributeValues={":checkin": overdue_checkin, ":due": overdue_due},
    )
    return {**item, "last_checkin_at": overdue_checkin, "next_check_due_at": overdue_due}


def create_demo_vault(email: str) -> list[dict]:
    """Creates the five demo vault entries with AES-256-GCM encryption."""
    created = []
    for entry in _DEMO_VAULT_ENTRIES:
        encrypted_sensitive = encrypt_text(entry["sensitive_data"], email)
        encrypted_notes = (
            encrypt_text(entry["notes"], email) if entry.get("notes") else None
        )
        item = put_encrypted_vault_entry(
            email,
            {
                "entry_type": entry["entry_type"],
                "title": entry["title"],
                "sensitive_data": encrypted_sensitive,
                "notes": encrypted_notes,
            },
        )
        created.append(
            {
                "entry_id": item["entry_id"],
                "entry_type": item["entry_type"],
                "title": item["title"],
            }
        )
    return created


def create_demo_release(email: str) -> dict:
    """Advances the demo user to PENDING_RELEASE and creates a nominee token."""
    mark_pending_release(email)
    return create_release_request(email)


def setup_demo() -> dict:
    """
    Full demo setup: reset → user → vault entries → PENDING_RELEASE → token.
    Safe to call multiple times — resets cleanly each run.

    Returns:
        demo_email, nominee_email, vault_entries (metadata only),
        release_token, release_expires_at
    """
    create_demo_user()
    entries = create_demo_vault(DEMO_EMAIL)
    release = create_demo_release(DEMO_EMAIL)
    return {
        "demo_email": DEMO_EMAIL,
        "nominee_email": DEMO_NOMINEE_EMAIL,
        "vault_entries": entries,
        "release_token": release["token"],
        "release_expires_at": release["expires_at"],
    }
