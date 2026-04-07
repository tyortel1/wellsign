"""Outlook COM send (Windows-only via pywin32).

The desktop alternative to building our own SMTP / portal: open the operator's
own Outlook profile via COM, build a MailItem with rendered subject + body +
attached PDFs, and either send it immediately or leave it in the Drafts folder
for the operator to review before firing.

Why Drafts-by-default:
  * The operator has full eyes-on review of every email before it goes out
  * No way to "accidentally blast 30 investors" from the app
  * The operator's existing Outlook signature, From address, conversation
    threading, and audit trail all "just work"

Falls back to ``SendError`` (not an exception) if Outlook isn't installed
or COM rejects the call. Callers should always check ``SendResult.success``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# pywin32 is Windows-only and an optional install path on other platforms.
try:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore

    _HAS_OUTLOOK = True
except ImportError:  # pragma: no cover - non-Windows path
    _HAS_OUTLOOK = False


# Outlook MailItem constants — pywin32's makepy normally exports these, but
# we hard-code them so the module imports cleanly even if makepy hasn't run.
_OL_MAIL_ITEM = 0
_OL_FORMAT_HTML = 2


@dataclass
class SendResult:
    success: bool
    message: str
    entry_id: str | None = None  # Outlook's MailItem.EntryID after Save/Send


def outlook_available() -> bool:
    """Best-effort probe — returns False off-Windows or if pywin32 is missing."""
    return _HAS_OUTLOOK


def build_mail_item(
    *,
    to: str,
    subject: str,
    body_html: str,
    attachments: Iterable[Path] | None = None,
    send_immediately: bool = False,
) -> SendResult:
    """Construct an Outlook MailItem, attach files, and Save (or Send).

    Args:
        to: comma-separated recipient list
        subject: rendered email subject (NO `{{merge_variables}}`)
        body_html: rendered HTML body (NO `{{merge_variables}}`)
        attachments: file paths to attach. Missing files are silently skipped.
        send_immediately: True → ``.Send()``. False → ``.Save()`` (Drafts).

    Returns:
        ``SendResult`` with success/failure status and optional EntryID.
        Never raises — caller checks ``.success``.
    """
    if not _HAS_OUTLOOK:
        return SendResult(
            success=False,
            message="Outlook COM not available — pywin32 not installed (Windows only)",
        )

    # Initialise COM for this thread (safe to call from the Qt main thread).
    try:
        pythoncom.CoInitialize()
    except Exception:  # pragma: no cover - already initialised is OK
        pass

    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
    except Exception as e:
        return SendResult(
            success=False,
            message=f"Could not connect to Outlook (is it installed and running?): {e}",
        )

    try:
        mail = outlook.CreateItem(_OL_MAIL_ITEM)
        mail.To = to or ""
        mail.Subject = subject or ""
        mail.BodyFormat = _OL_FORMAT_HTML
        mail.HTMLBody = body_html or ""

        attached_count = 0
        skipped: list[str] = []
        for path in attachments or []:
            try:
                p = Path(path)
                if p.exists():
                    mail.Attachments.Add(str(p.resolve()))
                    attached_count += 1
                else:
                    skipped.append(p.name)
            except Exception as e:  # noqa: BLE001
                skipped.append(f"{Path(path).name} ({e})")

        if send_immediately:
            mail.Send()
            base = "Sent via Outlook"
        else:
            mail.Save()
            base = "Saved to Outlook Drafts"

        details: list[str] = []
        if attached_count:
            details.append(f"{attached_count} attachment(s)")
        if skipped:
            details.append(f"skipped: {', '.join(skipped)}")
        message = base if not details else f"{base} — {' · '.join(details)}"

        # EntryID may not be available until after Save() — wrap in try/except.
        entry_id: str | None
        try:
            entry_id = str(mail.EntryID) if hasattr(mail, "EntryID") else None
        except Exception:
            entry_id = None

        return SendResult(success=True, message=message, entry_id=entry_id)

    except Exception as e:  # noqa: BLE001
        return SendResult(
            success=False,
            message=f"Outlook send failed: {e}",
        )


__all__ = ["SendResult", "outlook_available", "build_mail_item"]
