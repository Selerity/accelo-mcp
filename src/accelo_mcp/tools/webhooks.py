"""Accelo Webhooks tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient


def register(server: MCPServer, client: AcceloClient):
    """Register webhook tools with the MCP server."""

    @server.tool()
    async def accelo_list_webhook_subscriptions() -> dict:
        """List webhook subscriptions for the current user.

        Returns all webhook subscriptions registered by the authenticated user.
        Each subscription contains: trigger_url, event_id, content_type,
        trigger_table, trigger_type, user_deployment, user_id.
        """
        return await client.get("/webhooks/subscriptions")

    @server.tool()
    async def accelo_list_webhook_subscription_types() -> dict:
        """List available webhook subscription event types.

        Returns the available events you can subscribe to. Events include:
        assign_task, unassign_task, create_task, create_invoice, update_invoice,
        delete_invoice, create_request, update_request_status, create_issue,
        update_issue, create_company, update_company, create_contact,
        update_contact, create_sale, update_sale, delete_activity.
        """
        return await client.get("/webhooks/subscriptions/types")

    @server.tool()
    async def accelo_create_webhook_subscription(
        trigger_url: str,
        event_id: str,
        content_type: str | None = None,
        secret: str | None = None,
    ) -> dict:
        """Create a webhook subscription.

        When the event fires, Accelo POSTs a payload to trigger_url containing
        {id, resource_url}. Headers include X-Accelo-Event and X-Hub-Signature
        (HMAC hex digest if secret is configured).

        Args:
            trigger_url: Callback URL to receive the webhook payload (required)
            event_id: Event to subscribe to (required). One of: assign_task,
                unassign_task, create_task, create_invoice, update_invoice,
                delete_invoice, create_request, update_request_status,
                create_issue, update_issue, create_company, update_company,
                create_contact, update_contact, create_sale, update_sale,
                delete_activity
            content_type: Payload format — 'application/json' or
                'application/x-www-form-urlencoded' (default)
            secret: Optional secret for HMAC signature verification
        """
        data: dict[str, Any] = {
            "trigger_url": trigger_url,
            "event_id": event_id,
        }
        if content_type:
            data["content_type"] = content_type
        if secret:
            data["secret"] = secret
        return await client.post("/webhooks/subscriptions", data=data)

    @server.tool()
    async def accelo_delete_webhook_subscription(id: int) -> dict:
        """Delete a webhook subscription.

        Args:
            id: Subscription ID to delete
        """
        return await client.delete(f"/webhooks/subscriptions/{id}")
