"""Accelo Signoffs tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register signoff tools with the MCP server."""

    @server.tool()
    async def accelo_list_signoffs(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List signoffs from Accelo.

        Signoffs allow clients to approve work and comment on attachments. They are
        created against jobs or milestones. Standing: 'draft', 'sent', 'approved',
        or 'declined'.

        Args:
            filters: Filter dict. Keys: id, created_by, standing, requires,
                against_type, against_id,
                date_created/expires/updated_before/after,
                order_by_asc/desc (id, date_created, date_expires, date_updated,
                standing, subject)
            fields: Additional fields, e.g. "html_body,permissions"
            search: Search over subject
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, search=search, page=page, limit=limit)
        return await client.get("/signoffs", params=params)

    @server.tool()
    async def accelo_get_signoff(id: int, fields: str | None = None) -> dict:
        """Get a single signoff by ID.

        Args:
            id: Signoff ID
            fields: Additional fields to return
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/signoffs/{id}", params=params)

    @server.tool()
    async def accelo_count_signoffs(
        filters: dict[str, Any] | None = None,
        search: str | None = None,
    ) -> dict:
        """Count signoffs matching the given filters."""
        params = build_params(filters=filters, search=search)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/signoffs/count", params=params)

    @server.tool()
    async def accelo_update_signoff(
        id: int,
        body: str,
        fields: str | None = None,
    ) -> dict:
        """Update a signoff's body.

        Only the `body` field is updatable via this endpoint.

        Args:
            id: Signoff ID (required)
            body: New body content (required)
            fields: Additional fields to return
        """
        data: dict[str, Any] = {"body": body}
        if fields:
            data["_fields"] = fields
        return await client.put(f"/signoffs/signoff/{id}", data=data)

    @server.tool()
    async def accelo_redraft_signoff(id: int) -> dict:
        """Redraft a signoff — return a sent signoff to draft standing.

        Args:
            id: Signoff ID
        """
        return await client.post(f"/signoffs/{id}/redraft")

    @server.tool()
    async def accelo_send_signoff(id: int) -> dict:
        """Send a signoff to its recipients.

        CLIENT-FACING WRITE — this dispatches an approval request to the signoff's
        recipients (typically clients). Confirm with the user before calling.

        Args:
            id: Signoff ID
        """
        return await client.post(f"/signoffs/{id}/send")

    @server.tool()
    async def accelo_create_signoff_recipient(
        signoff_id: int,
        recipient_id: int,
        recipient_type: str,
        approver: bool | None = None,
        fields: str | None = None,
    ) -> dict:
        """Add a recipient to a signoff.

        Args:
            signoff_id: The signoff to add the recipient to (required)
            recipient_id: ID of the recipient object (required)
            recipient_type: Object type of the recipient — "affiliation" or "staff"
                (required)
            approver: Whether this recipient can approve the signoff
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "signoff_id": signoff_id,
            "recipient_id": recipient_id,
            "recipient_type": recipient_type,
        }
        if approver is not None:
            data["approver"] = "yes" if approver else "no"
        if fields:
            data["_fields"] = fields
        return await client.post("/signoffs/recipients", data=data)

    @server.tool()
    async def accelo_update_signoff_recipient(
        recipient_id: int,
        approver: bool | None = None,
        response: str | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update a signoff recipient.

        A recipient can only be edited while the signoff is in draft; `response`
        may only be updated for your own recipient record and only if you are an
        approver. Only non-None fields are sent.

        Args:
            recipient_id: The recipient record's ID (required)
            approver: Whether the recipient can approve
            response: The recipient's response
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if approver is not None:
            data["approver"] = "yes" if approver else "no"
        if response:
            data["response"] = response
        if fields:
            data["_fields"] = fields
        return await client.put(f"/signoffs/recipients/{recipient_id}", data=data)

    @server.tool()
    async def accelo_delete_signoff_recipient(recipient_id: int) -> dict:
        """Delete a signoff recipient.

        Args:
            recipient_id: The recipient record's ID
        """
        return await client.delete(f"/signoffs/recipients/{recipient_id}")

    @server.tool()
    async def accelo_update_signoff_attachment(
        attachment_id: int,
        standing: str,
    ) -> dict:
        """Update a signoff attachment's standing.

        Only the `standing` field ("active"/"inactive") is updatable.

        Args:
            attachment_id: The attachment's ID (required)
            standing: New standing — "active" or "inactive" (required)
        """
        data: dict[str, Any] = {"standing": standing}
        return await client.put(f"/signoffs/attachments/{attachment_id}", data=data)
