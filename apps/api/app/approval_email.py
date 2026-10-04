from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
import json
import logging
from typing import Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from app.service import PendingApprovalLinks


class ApprovalEmailProvider(Protocol):
    def send(self, *, recipient: str, subject: str, body: str) -> None: ...


class LogApprovalEmailProvider:
    def __init__(self) -> None:
        self._logger = logging.getLogger("daai.approvals")

    def send(self, *, recipient: str, subject: str, body: str) -> None:
        self._logger.warning(
            "approval email (log provider): recipient=%s subject=%s body=%s",
            recipient,
            subject,
            body,
        )


class ResendApprovalEmailProvider:
    def __init__(self, api_key: str, from_email: str):
        self._api_key = api_key
        self._from_email = from_email
        self._logger = logging.getLogger("daai.approvals")

    def send(self, *, recipient: str, subject: str, body: str) -> None:
        payload = {
            "from": self._from_email,
            "to": [recipient],
            "subject": subject,
            "text": body,
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            url="https://api.resend.com/emails",
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "DAAI-Console/0.1",
            },
        )

        try:
            with urllib_request.urlopen(req, timeout=10) as response:
                if response.status >= 300:
                    self._logger.error(
                        "resend returned unexpected status: %s",
                        response.status,
                    )
        except urllib_error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            self._logger.error(
                "resend http error: status=%s body=%s",
                exc.code,
                message,
            )
        except urllib_error.URLError as exc:
            self._logger.error("resend network error: %s", exc.reason)


@dataclass(frozen=True)
class ApprovalEmailNotifier:
    provider: ApprovalEmailProvider

    def __post_init__(self) -> None:
        object.__setattr__(self, "_logger", logging.getLogger("daai.approvals"))

    def notify_pending_approval(self, links: PendingApprovalLinks) -> None:
        if not links.approval_emails:
            self._logger.warning(
                "pending approval has no configured approval emails: workspace_id=%s action_run_id=%s action=%s",
                links.workspace_id,
                links.action_run_id,
                links.action,
            )
            return

        for approval_email in links.approval_emails:
            self.provider.send(
                recipient=approval_email,
                subject=f"Approval needed: {links.action}",
                body=_build_email_body(links),
            )


def _build_email_body(links: PendingApprovalLinks) -> str:
    workspace_label = links.workspace_client_name or links.workspace_name
    expires_at = links.expires_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return "\n".join(
        [
            f"Workspace: {workspace_label}",
            f"Action: {links.action}",
            f"Governance reason: {links.governance_reason}",
            f"Payload summary: {links.payload_summary}",
            f"Links expire in {links.expires_in_text}.",
            f"Expires at: {expires_at}",
            "",
            f"Approve: {links.approve_url}",
            f"Reject: {links.reject_url}",
            f"Block: {links.block_url}",
        ]
    )
