"""Accelo Activities tools."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient, build_params


def register(server: MCPServer, client: AcceloClient):
    """Register activity tools with the MCP server."""

    @server.tool()
    async def accelo_list_activities(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        search: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List activities (notes, emails, calls, meetings) from Accelo.

        Activities track all communication and time logging. Each activity is recorded
        'against' an object (company, job, issue, task, milestone, contract, prospect).
        To find which company an activity belongs to, resolve via against_type:
        - company → direct
        - job/issue → get object → against_id (company)
        - task/milestone → get object → parent job → company
        - contract/contract_period → get contract → against_id (company)
        - affiliation → get affiliation → company_id

        Use fields="against()" to expand the against object inline.

        SUBJECT/TEXT SEARCH IS NOT SUPPORTED. Accelo's GET /activities endpoint does
        NOT honour the _search parameter and exposes NO subject/body filter — passing
        `search` (or a `subject` filter) is silently ignored upstream and returns the
        deployment's earliest unrelated activities, not matches. This tool therefore
        rejects `search` up front rather than issuing a misleading query. To find an
        activity by subject you MUST narrow scope first, then match the subject
        client-side over the (small) returned set:
          1. accelo_list_thread_activities(thread_id=...) — the containing email/note thread
          2. accelo_list_activities(filters={"against": {"prospect": [ID]}}) or
             filters={"against_type": "...", "against_id": ...} — scope to one object
          3. accelo_run_filter(...) — a saved activity filter, if one exists
        There is no global body/subject text search across all activities.

        Args:
            filters: Filter dict. Keys: id, parent_id, thread_id, against_type, against_id,
                owner_id, owner_type, medium, visibility, staff, activity_class,
                activity_priority, task, time_allocation,
                date_created/logged/started/ended_before/after, order_by_asc/desc.
                NOTE: there is no `subject` filter — Accelo does not support one.
            fields: Additional fields, e.g. "body,staff(),medium,interacts"
            search: NOT SUPPORTED — Accelo's /activities endpoint ignores _search.
                Passing a value returns a structured error instead of a silently
                unfiltered result set. See the tool description for the correct
                subject-lookup workflow.
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        if search is not None and str(search).strip():
            return {
                "error": "unsupported_parameter",
                "message": (
                    "Accelo's GET /activities endpoint does not support the _search "
                    "parameter and has no subject/body filter, so 'search' is ignored "
                    "upstream (it returns the deployment's earliest unrelated activities, "
                    "not matches). To find an activity by subject, narrow scope first and "
                    "match the subject client-side: use accelo_list_thread_activities for "
                    "the containing thread, or accelo_list_activities filtered by the "
                    "against object (e.g. filters={'against': {'prospect': [ID]}}), or "
                    "accelo_run_filter with a saved activity filter. There is no global "
                    "subject/body search across all activities."
                ),
                "rejected_search": search,
            }
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/activities", params=params)

    @server.tool()
    async def accelo_get_activity(id: int, fields: str | None = None) -> dict:
        """Get a single activity by ID.

        Args:
            id: Activity ID
            fields: Additional fields to return, e.g. "body,owner(),against()"
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/activities/{id}", params=params)

    @server.tool()
    async def accelo_count_activities(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count activities matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/activities/count", params=params)

    @server.tool()
    async def accelo_create_activity(
        subject: str,
        against_type: str,
        against_id: int,
        body: str | None = None,
        medium: str | None = None,
        priority_id: int | None = None,
        class_id: int | None = None,
        owner_type: str | None = None,
        owner_id: int | None = None,
        billable: int | None = None,
        nonbillable: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Create a new activity (note, email, call, or meeting).

        Args:
            subject: Activity subject (required)
            against_type: Object type to create against (required).
                E.g. company, job, issue, staff, task
            against_id: ID of the object to create against (required)
            body: Activity body/content
            medium: Type — 'note', 'meeting', 'email', or 'call' (default: note)
            priority_id: Priority ID
            class_id: Activity class ID
            owner_type: Owner type ('staff' or 'affiliation')
            owner_id: Owner ID (staff_id or affiliation_id)
            billable: Billable time in seconds
            nonbillable: Non-billable time in seconds
            fields: Additional fields to return
        """
        data: dict[str, Any] = {
            "subject": subject,
            "against_type": against_type,
            "against_id": against_id,
        }
        if body:
            data["body"] = body
        if medium:
            data["medium"] = medium
        if priority_id is not None:
            data["priority_id"] = priority_id
        if class_id is not None:
            data["class_id"] = class_id
        if owner_type:
            data["owner_type"] = owner_type
        if owner_id is not None:
            data["owner_id"] = owner_id
        if billable is not None:
            data["billable"] = billable
        if nonbillable is not None:
            data["nonbillable"] = nonbillable
        if fields:
            data["_fields"] = fields
        return await client.post("/activities", data=data)

    @server.tool()
    async def accelo_update_activity(
        id: int,
        subject: str | None = None,
        body: str | None = None,
        visibility: str | None = None,
        priority_id: int | None = None,
        billable: int | None = None,
        nonbillable: int | None = None,
        fields: str | None = None,
    ) -> dict:
        """Update an existing activity.

        Args:
            id: Activity ID (required)
            subject: New subject (only if owner)
            body: New body (only if owner)
            visibility: New visibility
            priority_id: New priority ID
            billable: Billable time in seconds
            nonbillable: Non-billable time in seconds
            fields: Additional fields to return
        """
        data: dict[str, Any] = {}
        if subject:
            data["subject"] = subject
        if body is not None:
            data["body"] = body
        if visibility:
            data["visibility"] = visibility
        if priority_id is not None:
            data["priority_id"] = priority_id
        if billable is not None:
            data["billable"] = billable
        if nonbillable is not None:
            data["nonbillable"] = nonbillable
        if fields:
            data["_fields"] = fields
        return await client.put(f"/activities/{id}", data=data)

    @server.tool()
    async def accelo_delete_activity(id: int) -> dict:
        """Delete an activity.

        Args:
            id: Activity ID to delete
        """
        return await client.delete(f"/activities/{id}")

    @server.tool()
    async def accelo_list_interactions(id: int, fields: str | None = None) -> dict:
        """List the interactions (senders/recipients) on a single activity.

        An interaction is a sender or recipient of an activity — a staff member or
        contact with a role of creator/from/to/cc/bcc/attendee/did_not_attend.
        The response contains a "staff" array and a "contacts" array; each object
        carries an `interact` sub-object with the interaction id, date_actioned, and type.

        Args:
            id: Activity ID
            fields: Additional fields on the returned staff/contact objects
        """
        params = {"_fields": fields} if fields else {}
        return await client.get(f"/activities/{id}/interacts", params=params)

    @server.tool()
    async def accelo_count_interactions(id: int) -> dict:
        """Count the interactions on a single activity.

        Args:
            id: Activity ID
        """
        return await client.get(f"/activities/{id}/interacts/count")

    @server.tool()
    async def accelo_get_activity_time_allocated(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Get aggregate time allocated across a set of activities.

        Returns the summed billable/nonbillable seconds and total charged for the
        activities matched by the filters. This is an AGGREGATION over a collection
        (endpoint GET /activities/allocations), NOT a single activity's allocation —
        pass the same filters accepted by accelo_list_activities to scope the set
        (e.g. {"staff": 14, "date_logged_after": 1690000000}).

        Args:
            filters: Same filter dict as accelo_list_activities (staff, against_type,
                against_id, date_logged_before/after, etc.)
        """
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/activities/allocations", params=params)

    @server.tool()
    async def accelo_list_activity_threads(
        filters: dict[str, Any] | None = None,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List activity threads from Accelo.

        A thread groups an original activity with the activities sent in response to
        it (e.g. an email and its replies). Each thread carries the original
        activity's id, an event_text, a total_activities count, and the most recent
        activity in the thread.

        Args:
            filters: Filter dict. Keys: against_type + against_id (must be supplied
                together — restrict to threads whose original activity is against that
                object), staff_involved (staff_id), scope ("internal"/"external"),
                date_logged_before/after
            fields: Additional fields on the activities listed in each thread
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(filters=filters, fields=fields, page=page, limit=limit)
        return await client.get("/activities/threads", params=params)

    @server.tool()
    async def accelo_count_activity_threads(
        filters: dict[str, Any] | None = None,
    ) -> dict:
        """Count activity threads matching the given filters."""
        params = build_params(filters=filters)
        params.pop("_page", None)
        params.pop("_limit", None)
        return await client.get("/activities/threads/count", params=params)

    @server.tool()
    async def accelo_list_thread_activities(
        thread_id: int,
        fields: str | None = None,
        page: int = 0,
        limit: int = 10,
    ) -> dict:
        """List all activities within a single thread.

        Args:
            thread_id: The thread's ID (the activity_id of the original activity in
                the thread — see the `thread`/`thread_id` field on any activity)
            fields: Additional fields, e.g. "thread,parent"
            page: Page number (0-indexed)
            limit: Results per page (max 100)
        """
        params = build_params(fields=fields, page=page, limit=limit)
        return await client.get(f"/activities/threads/{thread_id}", params=params)
