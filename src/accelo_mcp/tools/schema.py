"""Accelo object schema tool — on-demand field descriptions for core objects."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient

OBJECT_SCHEMAS: dict[str, str] = {
    "activities": """## Activity Object Fields

Default fields (always returned): **id**, **subject**, **confidential**

| Field | Type | Description |
|-------|------|-------------|
| id | unsigned | Unique identifier |
| subject | string | Title/description of the activity |
| confidential | boolean (0/1) | Whether content is hidden from current user |
| parent_id | unsigned | Parent activity ID ("0" if none) |
| thread | string | Original activity in thread, e.g. "activities/346" |
| thread_id | unsigned | Thread activity ID |
| against_type | string | Object type the activity is against |
| against_id | unsigned | ID of the object it's against |
| against | string | API URI e.g. "request/32" |
| owner_type | string | "staff" or "affiliation" |
| owner_id | unsigned | Owner's ID |
| owner | string | API URI of owner e.g. "staff/14" |
| medium | string | "note", "email", "call", "meeting", or "postal" |
| body | string | Plain text content |
| preview_body | string | First 250 chars of body |
| html_body | string | HTML content (rich text) |
| visibility | string | "private", "confidential", or "all" |
| details | string | Location (meetings), phone number (calls) |
| date_created | unix ts | Creation date |
| date_started | unix ts | When time was logged / meeting start |
| date_ended | unix ts | Meeting end date |
| date_logged | unix ts | Read-only: date_started or date_created |
| date_modified | unix ts | Last modified |
| billable | unsigned | Billable time in SECONDS |
| nonbillable | unsigned | Non-billable time in SECONDS |
| staff | unsigned/object | Staff who logged time |
| activity_class | unsigned/object | Classification (Client Work, Sales, Internal) |
| activity_priority | unsigned/object | Priority (1=Extreme to 5=None) |
| task | unsigned/object | Task the activity is against (null if none) |
| time_allocation | unsigned/object | Time allocation details |
| rate | unsigned/object | Rate charged for billable time |
| rate_charged | unsigned | Hourly rate as decimal |
| tag | array | Tags on the activity |
| scheduled | select | "yes" or "no" |
| standing | select | "unapproved", "approved", "invoiced", "locked", or empty |
| invoice_id | unsigned | Linked invoice ID |
| contract_period_id | unsigned | Linked contract period ID |
| is_billable | bool (0/1) | Whether billable time CAN be logged |
| permissions | object | Current user's permissions on this activity |

### Key Gotchas
- `billable` and `nonbillable` are in **seconds**, not hours (divide by 3600)
- `medium` "note" is the default for internal notes/time logging
- `date_logged` = date_started if set, else date_created (use for timesheets)
- Activities with medium="event_log" are system-generated, not human work
- Use `visibility="all"` when creating activities that log time
- **No subject/text search**: Accelo's GET /activities ignores `_search` and has NO
  `subject` filter, so `accelo_list_activities(search=...)` is rejected (it would return
  unrelated earliest activities upstream, not matches). To find an activity by subject,
  narrow scope first — `accelo_list_thread_activities(thread_id=...)`, or
  `accelo_list_activities` filtered by the against object (e.g.
  `filters={"against": {"prospect": [ID]}}`), or `accelo_run_filter` — then match
  `subject` client-side. There is no global body/subject search.
""",
    "affiliations": """## Affiliation Object Fields

Default fields: **id**, **mobile**, **email**

| Field | Type | Description |
|-------|------|-------------|
| id | unsigned | Unique identifier |
| mobile | string | Mobile number for this role |
| email | string | Email for this role |
| fax | string | Fax number |
| position | string | Job title e.g. "CEO", "Engineer" |
| phone | string | Phone number |
| postal_address | unsigned/object | Postal address ID/object |
| physical_address | unsigned/object | Physical address ID/object |
| company | unsigned/object | Company ID/object |
| contact | unsigned/object | Contact ID/object |
| affiliation_status | unsigned | Status ID |
| standing | string | e.g. "active", "inactive" |
| date_modified | unix ts | Last modified |
| date_last_interacted | unix ts | Last interaction |
| staff_bookmarked | boolean | Bookmarked by current user |
| portal_access | boolean | Has client portal access |
| communication | boolean | Receives newsletters/updates |
| invoice_method | string | "email", "fax", or "postal" |

### Key Concept
An affiliation is the JOIN between a Contact and a Company. One person can have
multiple affiliations (e.g. works at Company A as engineer, advises Company B).
Contact info (email, phone) belongs to the affiliation, not the contact directly.
""",
    "companies": """## Company Object Fields

Default fields: **id**, **name**

| Field | Type | Description |
|-------|------|-------------|
| id | unsigned | Unique identifier |
| name | string | Company name |
| custom_id | string | Custom identifier |
| website | string | Company URL |
| phone | string | Phone number |
| fax | string | Fax number |
| date_created | unix ts | Created date |
| date_modified | unix ts | Last modified |
| date_last_interacted | unix ts | Last interaction |
| comments | string | Notes about the company |
| standing | string | From status: "active", "inactive", etc. |
| status | unsigned/object | Status object |
| postal_address | unsigned/object | Postal address |
| staff_bookmarked | bool | Bookmarked by current user |
| default_affiliation | unsigned | Main affiliation ID |

### Key Patterns
- Jobs, issues, and contracts are created "against" a company
- `default_affiliation` links to the main contact person
- Use `fields="postal_address(city,state)"` to expand address inline
""",
    "contacts": """## Contact Object Fields

Default fields: **id**, **firstname**, **surname**, **mobile**, **email**

| Field | Type | Description |
|-------|------|-------------|
| id | unsigned | Unique identifier |
| firstname | string | First name |
| surname | string | Last name |
| mobile | string | DEPRECATED — use affiliation |
| email | string | DEPRECATED — use affiliation |
| username | string | Accelo username |
| middlename | string | Middle name |
| title | string | "Mr", "Ms", "Dr" etc. |
| timezone | string | Timezone |
| date_created | unix ts | Created date |
| date_modified | unix ts | Last modified |
| date_last_interacted | unix ts | Last interaction |
| comments | string | Notes |
| default_affiliation | unsigned | Primary affiliation ID |
| contact_status | unsigned/object | Status |
| standing | string | e.g. "active", "potential" |

### Key Concept
Contact info (email, phone, position) lives on the AFFILIATION, not the contact.
A contact's `default_affiliation` points to their primary company link.
""",
    "contracts": """## Contract Object Fields

Default fields: **id**, **title**, **period_template_id**

| Field | Type | Description |
|-------|------|-------------|
| id | unsigned | Unique identifier |
| title | string | Contract name |
| period_template_id | unsigned | Period template ID |
| date_created | unix ts | Created date |
| date_started | unix ts | Start date |
| date_expires | unix ts | Expiry date |
| date_period_expires | unix ts | Current period end date |
| against | string | API URI e.g. "companies/39" |
| against_id | unsigned | Company ID (contracts are always against companies) |
| against_type | string | Always "company" |
| value | decimal | Total contract value |
| auto_renew | string | "yes" or "no" |
| renew_days | string | Days before expiry to renew |
| send_invoice | string | "none", "email", "fax", "postal" |
| notes | string | Notes |
| staff_bookmarked | bool | Bookmarked |
| owner_affiliation | unsigned/object | Owner affiliation |
| billable_affiliation | unsigned | Billable affiliation ID |
| contract_type | unsigned/object | Contract type |
| manager | unsigned/object | Managing staff member |
| status | unsigned/object | Status |
| standing | string | "active", "cancelled", etc. |
| company | unsigned/object | Company against |

### Contract Periods
Each contract has billing periods. Get them via:
`accelo_list_contract_periods(contract_id=X)`

Period fields: id, date_created, date_commenced, date_expires, date_closed,
budget_type ("pre-paid"/"post-paid"), allowance_type, rate_type, standing.
""",
    "prospects": """## Prospect (Sale) Object Fields

Default fields: **id**, **title**

| Field | Type | Description |
|-------|------|-------------|
| id | unsigned | Unique identifier |
| title | string | Sale name |
| date_created | unix ts | Created date |
| date_actioned | unix ts | Actioned date |
| date_due | unix ts | Due date |
| date_last_interacted | unix ts | Last interaction |
| date_modified | unix ts | Last modified |
| weighting | integer | Rating 1-5 (5 = highest) |
| value | decimal | Monetary value |
| success | select | "yes" or "no" |
| comments | string | Description |
| progress | decimal | Progress % as decimal (0.25 = 25%) |
| value_weighted | integer | Weighted value incorporating progress |
| staff_bookmarked | boolean | Bookmarked |
| won_by_id | unsigned | Staff who won (null if not won) |
| cancelled_by_id | unsigned | Staff who cancelled |
| abandoned_by_id | unsigned | Staff who abandoned |
| contact | unsigned/object | Associated contact |
| manager | unsigned/object | Managing staff |
| prospect_type | unsigned/object | Type |
| status | unsigned/object | Status |
| standing | string | e.g. "active", "won" |
| prospect_probability | unsigned/object | Win probability |
| affiliation | unsigned/object | Client affiliation |

### Relationship to Company
Prospect → affiliation_id → get affiliation → company_id
""",
    "quotes": """## Quote Object Fields

Default fields: **id**, **title**

| Field | Type | Description |
|-------|------|-------------|
| id | unsigned | Unique identifier |
| title | string | Quote name |
| against_type | string | Usually "prospect" |
| against_id | unsigned | Prospect/object ID |
| against | string | API URI |
| notes | string | Internal notes |
| portal_access | boolean | Published to client portal |
| affiliation_id | unsigned | Client affiliation |
| affiliation | unsigned/object | Client affiliation object |
| date_created | unix ts | Created date |
| date_expiry | unix ts | Expiry date |
| manager_id | unsigned | Managing staff ID |
| manager | unsigned/object | Managing staff |
| status_id | unsigned | Status ID |
| status | unsigned/object | Status |
| standing | string | "draft", "sent", "accepted", "declined" |
| created_by_staff_id | unsigned | Creator staff ID |
| created_by | unsigned/object | Creator staff |
| introduction | string | HTML introduction |
| conclusion | string | HTML conclusion |
| terms | string | HTML terms and conditions |
| service_price_total | decimal | Total services price |
| service_time_total | integer | Total service time in seconds |
| material_price_total | decimal | Total materials price |
| total_price | decimal | service_price_total + material_price_total |
""",
    "staff": """## Staff Object Fields

Default fields: **id**, **firstname**, **surname**

| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier (note: Accelo docs type this as string, unlike other objects) |
| firstname | string | First name |
| surname | string | Last name |
| standing | select | "active", "inactive", or "lockout" |
| financial_level | select | "none", "time", or "all" |
| title | string | "Mr", "Ms" etc. |
| email | string | Email address |
| mobile | string | Mobile number |
| phone | string | Phone number |
| fax | string | Fax number |
| position | string | Job title |
| username | string | Accelo username |
| timezone | string | Timezone |
| staff_rate | decimal | Billable rate (not in _ALL) |
| staff_cost_rate | decimal | Cost rate (not in _ALL) |

### Notes
- `staff_rate` and `staff_cost_rate` are NOT returned with `_ALL` — request explicitly
- Use `GET /staff/whoami` for current authenticated user
- Timer endpoints only work for the authenticated user (not service apps)
""",
    "tasks": """## Task Object Fields

Default fields: **id**, **title**

| Field | Type | Description |
|-------|------|-------------|
| id | unsigned | Unique identifier |
| title | string | Task name |
| description | string | Description |
| billable | integer | Billable time in SECONDS |
| nonbillable | integer | Non-billable time in SECONDS |
| logged | integer | Total time in seconds (billable + nonbillable) |
| budgeted | integer | Estimated time in seconds |
| remaining | integer | Remaining budget in seconds |
| staff_bookmarked | boolean | Bookmarked |
| date_created | unix ts | Created |
| date_started | unix ts | Scheduled start |
| date_commenced | unix ts | Actually started |
| date_accepted | unix ts | Accepted date |
| date_due | unix ts | Due date |
| date_completed | unix ts | Completed date |
| date_modified | unix ts | Last modified |
| against_type | string | "job", "milestone", or "issue" |
| against_id | unsigned | Parent object ID |
| against | string | API URI |
| creator_type | string | Creator type |
| creator_id | unsigned | Creator ID |
| assignee | unsigned/object | Assigned staff |
| task_type | unsigned/object | Task type |
| task_status | unsigned/object | Status |
| standing | string | "pending", "started", "complete" etc. |
| manager | unsigned/object | Managing staff |
| contact | unsigned/object | Associated contact |
| affiliation | unsigned/object | Associated affiliation |
| company | unsigned/object | Company (if against company) |
| issue | unsigned/object | Issue (if against issue) |
| task_job | unsigned/object | Job (resolved parent) |
| milestone | unsigned/object | Milestone (if against milestone) |
| task_object_budget | unsigned/object | Budget |
| task_object_schedule | unsigned/object | Schedule |
| task_priority | unsigned/object | Priority (1=Critical, 5=None) |
| rate_id | unsigned | Rate ID |
| rate_charged | decimal | Hourly rate |
| ordering | unsigned | Order on parent object |
| skills | array[object] | Assigned skills |

### Key Gotchas
- Time fields (billable, nonbillable, logged, budgeted, remaining) are in SECONDS
- Use `child_of_job` filter to find all tasks under a job (including via milestones)
- `task_job` gives the resolved parent job even when task is against a milestone
""",
}

# Object aliases for convenience
OBJECT_SCHEMAS["activity"] = OBJECT_SCHEMAS["activities"]
OBJECT_SCHEMAS["affiliation"] = OBJECT_SCHEMAS["affiliations"]
OBJECT_SCHEMAS["company"] = OBJECT_SCHEMAS["companies"]
OBJECT_SCHEMAS["contact"] = OBJECT_SCHEMAS["contacts"]
OBJECT_SCHEMAS["contract"] = OBJECT_SCHEMAS["contracts"]
OBJECT_SCHEMAS["prospect"] = OBJECT_SCHEMAS["prospects"]
OBJECT_SCHEMAS["sale"] = OBJECT_SCHEMAS["prospects"]
OBJECT_SCHEMAS["sales"] = OBJECT_SCHEMAS["prospects"]
OBJECT_SCHEMAS["quote"] = OBJECT_SCHEMAS["quotes"]
OBJECT_SCHEMAS["task"] = OBJECT_SCHEMAS["tasks"]


def register(server: MCPServer, client: AcceloClient) -> None:
    """Register the object schema tool."""

    @server.tool()
    async def accelo_describe_object(object_type: str) -> str:
        """Get field descriptions and examples for an Accelo object type.

        Returns detailed field-level documentation including types, descriptions,
        gotchas (e.g. time fields are in seconds), and usage patterns. Call this
        when you need to interpret response data or understand what fields are
        available.

        Supported objects: activities, affiliations, companies, contacts,
        contracts, prospects, quotes, staff, tasks

        Args:
            object_type: The object type to describe (e.g. "activities", "staff")
        """
        key = object_type.lower().strip()
        if key in OBJECT_SCHEMAS:
            return OBJECT_SCHEMAS[key]

        return (
            f"Unknown object type '{object_type}'. "
            f"Available: {', '.join(sorted(OBJECT_SCHEMAS.keys()))}.\n\n"
            f"For objects not listed, use fields='_ALL' on the relevant list/get tool "
            f"to discover available fields from a live response."
        )
