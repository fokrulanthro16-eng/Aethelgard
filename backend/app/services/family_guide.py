"""
Family Guide Generator for Aethelgard.

Takes decrypted vault entries and produces a human-readable guide for the
family to navigate accounts, assets, and the vault owner's final wishes.

Architecture:
  Decrypted vault entries
        ↓
  build_guide_context()      ← structures entries into a text block
        ↓
  GUIDE_PROMPT_TEMPLATE      ← wraps context in full Gemini prompt
        ↓
  call_gemini()              ← sends to Gemini (may raise)
        ↓                       if it raises:
  guide text              ← create_fallback_guide()
        ↓
  generate_family_guide()    ← orchestrator; always returns a result

TODO (production):
  - Cache the generated guide keyed by (email, hash(vault contents)) to
    avoid re-billing the same prompt.
  - After RELEASED, send the guide via SES/SendGrid to the nominee's email.
  - Add data minimisation: strip raw passwords from the AI prompt and instead
    describe them as "access credential" to limit PII exposure to Gemini.
"""

from datetime import datetime, timezone
from typing import Any

from app.services.gemini import call_gemini


_ENTRY_TYPE_LABELS: dict[str, str] = {
    "message": "Personal Messages",
    "credentials": "Account Credentials",
    "note": "Important Notes",
    "document": "Documents",
}

_GUIDE_PROMPT = """\
You are helping a bereaved family navigate the digital legacy of a loved one.

You have been provided with the decrypted contents of their secure digital vault.
Transform this information into a compassionate, clear, and practical family guide.

VAULT OWNER: {owner_email}
DATE: {date}

VAULT CONTENTS:
{context}

RULES — follow strictly:
1. NEVER invent, guess, or assume any information not explicitly present in the vault.
2. Write in a warm, empathetic, and professional tone.
3. Address the family directly. Refer to the vault owner as "your loved one" (never by email).
4. If no vault entries exist for a section, omit that section entirely.
5. When listing credentials, note that passwords should be changed immediately after first use.

OUTPUT FORMAT — use plain text with section headers and "===" underlines:

Introduction
============
[Compassionate opening paragraph.]

Important Accounts
==================
[Login credentials and account access information, if present.]

Financial Assets
================
[Banks, insurance, investments, pensions — inferred from credentials/documents, if present.]

Documents
=========
[Legal documents, policies, certificates — if present.]

Digital Assets
==============
[Online services, subscriptions, cloud storage, digital media — if present.]

Personal Messages
=================
[Personal notes, letters, or messages from the vault owner — if present.]

Instructions
============
[Specific wishes, instructions, or guidance from the vault owner — if present.]

Important Notes
===============
[Anything else that does not fit the sections above — if present.]

Closing Message
===============
[Warm, supportive closing paragraph for the family.]

Begin the family guide now. Only include sections that have relevant content.\
"""


def build_guide_context(owner_email: str, entries: list[dict[str, Any]]) -> str:
    """
    Converts decrypted vault entries into a structured plain-text block
    suitable for embedding in the Gemini prompt.
    """
    if not entries:
        return f"Vault owner: {owner_email}\n\nThe vault contains no entries."

    lines: list[str] = [f"Vault owner: {owner_email}", ""]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        t = entry.get("entry_type", "note")
        grouped.setdefault(t, []).append(entry)

    for entry_type, items in grouped.items():
        label = _ENTRY_TYPE_LABELS.get(entry_type, entry_type.title())
        lines.append(f"[{label}]")
        for item in items:
            lines.append(f"  Title: {item.get('title', 'Untitled')}")
            if item.get("sensitive_data"):
                lines.append(f"  Content: {item['sensitive_data']}")
            if item.get("notes"):
                lines.append(f"  Notes: {item['notes']}")
            lines.append("")

    return "\n".join(lines)


def create_fallback_guide(owner_email: str, entries: list[dict[str, Any]]) -> str:
    """
    Generates a deterministic structured guide without AI.
    Always available — used when Gemini is unreachable or not configured.
    """
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    lines: list[str] = [
        "FAMILY LEGACY GUIDE",
        "===================",
        "",
        f"Prepared from the vault of: {owner_email}",
        f"Generated: {date_str}",
        "",
        "Dear Family,",
        "",
        (
            "This guide has been prepared from your loved one's secure digital vault. "
            "Please review each section carefully and keep this document in a safe place."
        ),
        "",
    ]

    if not entries:
        lines += [
            "No vault entries were found.",
            "",
            "If you believe this is an error, please consult a trusted family advisor.",
        ]
        return "\n".join(lines)

    type_order = ["message", "credentials", "note", "document"]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        t = entry.get("entry_type", "note")
        grouped.setdefault(t, []).append(entry)

    ordered = type_order + [t for t in grouped if t not in type_order]

    for entry_type in ordered:
        if entry_type not in grouped:
            continue
        items = grouped[entry_type]
        label = _ENTRY_TYPE_LABELS.get(entry_type, entry_type.title())
        lines += ["", label.upper(), "=" * len(label), ""]
        for item in items:
            lines.append(f"  {item.get('title', 'Untitled')}")
            if item.get("sensitive_data"):
                lines.append(f"    {item['sensitive_data']}")
            if item.get("notes"):
                lines.append(f"    Note: {item['notes']}")
            lines.append("")

    lines += [
        "",
        "─" * 40,
        "",
        "For assistance, consider reaching out to:",
        "  • A trusted family attorney",
        "  • A certified financial advisor",
        "  • The relevant institution's bereavement support team",
        "",
        "This guide was generated automatically by Aethelgard.",
    ]

    return "\n".join(lines)


def generate_family_guide(
    owner_email: str,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Orchestrator: tries Gemini first, falls back to the deterministic guide.

    Returns::

        {
            "generated_at": "<ISO timestamp>",
            "guide":        "<full guide text>",
            "source":       "gemini" | "fallback",
        }
    """
    generated_at = datetime.now(timezone.utc).isoformat()
    context = build_guide_context(owner_email, entries)
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")

    try:
        prompt = _GUIDE_PROMPT.format(
            owner_email=owner_email,
            date=date_str,
            context=context,
        )
        guide = call_gemini(prompt)
        source = "gemini"
    except Exception:
        guide = create_fallback_guide(owner_email, entries)
        source = "fallback"

    return {"generated_at": generated_at, "guide": guide, "source": source}
