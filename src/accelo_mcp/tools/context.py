"""Accelo schema and context tool — provides domain knowledge to the calling LLM."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..client import AcceloClient

ACCELO_CONTEXT = """
# Accelo Object Model & Query Guide

## Core Concepts

Accelo is a professional services CRM. The key domain objects and their relationships:

## Object Hierarchy (how things connect to companies)

```
Company
├── Affiliation (contact-company link, holds email/phone/position)
│   └── Contact (the person)
├── Job (project)
│   └── Milestone (phase within a job)
│       └── Task (work item)
├── Issue (support ticket)
│   └── Task
├── Contract (retainer)
│   └── Contract Period (billing cycle)
├── Prospect (sales opportunity)
└── Invoice
    └── Line Item (Beta — quantity/rate/tax/total lines on the invoice)
```

## The "against" Pattern

Most objects are linked to their parent via `against_type` and `against_id` fields:
- An **Activity** is recorded `against` something (company, job, issue, task, milestone, etc.)
- A **Job** is created `against` a company
- An **Issue** is created `against` a company (or job)
- A **Task** is created `against` a job, milestone, or issue
- An **Expense** is recorded `against` a job, issue, or contract

## Resolving an Activity to its Company

Activities can be against many object types. To find which company an activity belongs to:

| Activity against_type | Path to Company |
|---|---|
| `company` | Direct — against_id IS the company_id |
| `affiliation` | Get affiliation → company_id |
| `job` | Get job → against_id (company_id, since jobs are against companies) |
| `issue` | Get issue → against_id (usually company) or against_type=job → get job → company |
| `task` | Get task → resolve parent (job/milestone/issue) → company |
| `milestone` | Get milestone → job_id → get job → company |
| `contract` | Get contract → against_id (company) |
| `contract_period` | Get contract period → contract_id → get contract → against_id (company) |
| `prospect` | Get prospect → affiliation_id → get affiliation → company_id |
| `staff` | Internal activity, no customer company |

### Efficient Resolution Strategy

1. Use `_fields` to request linked objects inline: e.g. `fields="against()"` on an activity
2. Filter activities by `against_type` to batch-resolve similar paths
3. For contract_period → company: `GET /contracts/periods/{id}` returns `contract_id`,
   then `GET /contracts/{id}` returns `against_id` (the company)
4. For milestones: request `fields="job()"` to get the parent job inline

### Finding an Activity by Subject/Text (IMPORTANT)

There is **no free-text search over activities**. Accelo's `GET /activities` endpoint
does **not** honour the `_search` parameter and exposes **no `subject` (or body) filter** —
so `accelo_list_activities(search="...")` is silently ignored upstream and returns the
deployment's earliest unrelated activities, NOT matches. The MCP tool now rejects a
`search` value with a structured error rather than issuing that misleading query. With
hundreds of thousands of activities on a deployment, blind pagination is not viable.
To locate an activity by its subject, **narrow scope first, then match the subject
client-side over the small returned set**:

1. `accelo_list_thread_activities(thread_id=...)` — every activity in the containing
   email/note thread (best when you know the thread).
2. `accelo_list_activities(filters={"against": {"prospect": [ID]}})` or
   `filters={"against_type": "job", "against_id": ID}` — scope to one object, then read
   `subject` on the results.
3. `accelo_run_filter(filter_id=...)` — a saved activity filter, if one exists on the deployment.

## Key Relationships

### Companies & Contacts
- A **Contact** can be affiliated with multiple companies
- An **Affiliation** is the link between a Contact and a Company (holds the email, phone, position)
- `affiliation.company_id` → Company
- `affiliation.contact_id` → Contact
- Companies have a `default_affiliation` for their main contact

### Jobs (Projects)
- Jobs are always `against` a Company (against_type="company", against_id=company_id)
- Jobs contain **Milestones** (phases) which contain **Tasks**
- Jobs have a `manager_id` (staff), `affiliation_id` (client contact), `status_id`
- Use `fields="manager(),company(),job_type()"` to expand linked objects

### Issues (Tickets)
- Issues are `against` a Company or a Job
- If against a Job: follow job → company to find the customer
- Issues have `assignee` (staff_id), `affiliation_id` (client contact)
- Issues have a `class_id`, `type_id`, `priority_id`

### Contracts (Retainers)
- Contracts are `against` a Company (against_type="company")
- Contracts contain **Contract Periods** (billing cycles)
- `GET /contracts/{id}/periods` lists periods for a contract
- Period has `contract_id` linking back to its parent contract
- Use `fields="company()"` on contracts to get the company inline

### Tasks
- Tasks are `against` a Job, Milestone, or Issue
- Tasks have `assignee_id` (staff), `manager_id` (staff)
- To find company: resolve parent (job/milestone/issue) → company

### Activities (Notes/Emails/Calls/Meetings)
- Activities track ALL communication and time logging
- `against_type` + `against_id` = what the activity is about
- `owner_type` + `owner_id` = who owns it (usually staff)
- `staff` field = who logged time (if time was logged)
- `billable` + `nonbillable` = time in seconds
- `medium` = 'note', 'email', 'call', or 'meeting'
- Use `fields="interacts"` to see all recipients/senders
- Sub-resources: `accelo_list_interactions(id)` for one activity's senders/recipients
  (staff + contacts, each with an interact type: creator/from/to/cc/bcc/attendee);
  `accelo_get_activity_time_allocated(filters=...)` for aggregate billable/nonbillable/
  charged summed over a filtered set of activities (an aggregation, not per-activity)
- Threads group an original activity with its replies:
  `accelo_list_activity_threads(filters={"against_type","against_id"})` finds threads on
  an object; `accelo_list_thread_activities(thread_id)` lists the activities in one thread
  (a thread_id is the activity_id of the thread's original activity — see an activity's
  `thread`/`thread_id` field)

### Prospects (Sales)
- Linked to a company via `affiliation_id` → affiliation → company
- Have a `manager_id` (staff), `value` (monetary), `weighting` (0-5)

### Staff
- Staff are users of the Accelo deployment
- `GET /staff/whoami` returns the currently authenticated user
- Staff have `firstname`, `surname`, `email`

### Invoices & Line Items
- An **Invoice** is created `against` a Company (or job/etc.); `amount` is the
  ex-tax value, `tax` the tax total, `outstanding` the unpaid balance
- An invoice is made up of **Line Items** (Beta) — the individual charge lines
- A **Line Item** has `invoice_id` (parent), `quantity`, `rate` (per-unit price),
  `total` (line total incl. tax), `tax`, `ordering`, and a `description`
- `line_item.ledger_id` → the **Ledger** the line posts to; `line_item.tax_id`
  → the **Tax** code. Expand both inline with
  `fields="line_item_ledger(),line_item_tax()"`
- Line items are NOT nested under `/invoices/{id}` — they are a top-level
  sub-resource. To get one invoice's lines, filter the list endpoint by invoice:
  `accelo_list_invoice_line_items(filters={"invoice_id": invoice_id})`
- Line item create/update/delete are NOT available in the API (read-only, Beta)

## Field Selection (`_fields` parameter)

Request additional fields with comma-separated names:
- Simple: `"website,phone"`
- Linked objects: `"manager(),company()"` — returns the full linked object
- Nested fields: `"postal_address(city,state)"` — specific fields from linked object
- All optional: `"_ALL"` — returns every optional field

## Filtering

Filters are passed as a dict:
- Basic: `{"standing": "active", "status": 1}`
- Date: `{"date_created_after": 1690000000}` (unix timestamp)
- Multi-value: `{"status": [1, 2, 3]}`
- Object: `{"owner": {"staff": [17, 13]}}`
- Ordering: `{"order_by_desc": "date_modified"}`
- Negation: append `_not` to any filter key

## Resolving Enum / Status IDs

Filters like `status`, `type`, `class`, `priority`, and `resolution` take numeric
IDs, not names. To discover valid IDs, use the composite enum tools before filtering:
- `accelo_list_enum(object, enum_type)` lists an object's enumeration values.
  Statuses: companies, contacts, affiliations, jobs, issues, milestones, quotes,
  contracts, prospects (enum_type="statuses"). Types: jobs, issues, expenses,
  contracts, contributors, requests, prospects (enum_type="types"). Issues also
  have "classes", "priorities", "resolutions"; tasks have "priorities";
  activities have "classes"; prospects have "probabilities".
- `accelo_get_enum(object, enum_type, id)` / `accelo_count_enum(object, enum_type)`
  for a single value or a count (only where the API offers them; a structured
  error names the alternative otherwise).
- Example: `accelo_list_enum("issues", "statuses")` → find the "Open" status_id →
  `accelo_list_issues(filters={"status": <id>})`.

## Pagination

- `page`: 0-indexed page number
- `limit`: max 100 results per page
- Response includes meta with total count

## Common Patterns

### Find all time by a staff member, grouped by company:
1. List activities filtered by staff ID, requesting against_type, against_id, billable, nonbillable
2. Group by against_type, then resolve each against_id to company (see table above)

### Find all open issues for a company:
1. `accelo_list_issues(filters={"against_type": "company",
   "against_id": company_id, "standing": "open"})`

### Find a company's active jobs:
1. `accelo_list_jobs(filters={"against_type": "company",
   "against_id": company_id, "standing": "active"})`

### Get contract billing for a company:
1. `accelo_list_contracts(filters={"against_type": "company", "against_id": company_id})`
2. For each contract, list periods: `GET /contracts/{id}/periods`

### Get an invoice with its line-item breakdown:
1. `accelo_get_invoice(id=invoice_id)` for the header (amount, tax, outstanding)
2. `accelo_list_invoice_line_items(filters={"invoice_id": invoice_id},
   fields="line_item_ledger(),line_item_tax()")` for the charge lines,
   with ledger and tax code expanded inline
3. Sanity check: the line `total` values should reconcile to the invoice `amount` + `tax`

### Run a saved filter (saved search):
1. `accelo_list_filters()` (or `accelo_list_object_filters(object="companies")`) to
   find a saved filter and its id
2. `accelo_run_filter(id=<filter_id>)` returns the objects it matches (of the
   filter's own object_type)

### Other sub-resource helpers:
- Company managers: `accelo_list_company_managers(company_id)` /
  `accelo_add_company_manager` / `accelo_remove_company_manager` (remove by the
  manager's relationship_id, not staff_id)
- Deactivate (not delete) a contact: `accelo_deactivate_contact(id)` sets standing
  inactive
- Asset links (join an asset to an issue/job/prospect/contract):
  `accelo_list_asset_links` / `accelo_create_asset_link` / `accelo_delete_asset_link`
- Convert an imported calendar appointment to an activity:
  `accelo_convert_time_external_to_activity(id, engagement_table, engagement_id)`
- Move a task's status: `accelo_progress_task_to_start(id)` /
  `accelo_progress_task_to_done(id)`
"""


def register(server: MCPServer, client: AcceloClient):
    """Register the context/schema tool with the MCP server."""

    @server.tool()
    async def accelo_get_context() -> str:
        """Get the Accelo object model, relationships, and query guide.

        Call this FIRST before making complex queries. Returns:
        - Object hierarchy (how companies, jobs, issues, tasks, etc. relate)
        - The 'against' pattern (how objects link to their parents)
        - How to resolve any activity back to its company
        - Field selection syntax (_fields parameter)
        - Filtering and pagination conventions
        - Common query patterns (time by staff, issues by company, etc.)

        This context enables you to correctly traverse relationships and
        construct multi-step queries across the Accelo data model.
        """
        return ACCELO_CONTEXT
