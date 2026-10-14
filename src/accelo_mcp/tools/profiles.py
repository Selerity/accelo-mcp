"""Accelo Profile Fields tools."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from ..client import AcceloAPIError, AcceloClient
from ..models import format_error


def _value_matches(field_type: str, row: dict, value: str) -> bool:
    """Confirm a read-back value row matches the submitted value.

    Comparison is keyed on the field type so the read-back verify never flags a
    genuine write as a no-op. Date fields are compared leniently (presence only)
    because Accelo may normalise the stored date format.
    """
    if field_type == "integer":
        # Guard the int() coercion so the helper stays total (never raises).
        # FINDING 1 rejects non-integer values before any write, so a
        # non-integer here should never occur — but if it somehow does, treat
        # it as a non-match rather than letting ValueError escape the tool's
        # (AcceloAPIError-only) except block.
        try:
            expected = str(int(value))
        except ValueError:
            return False
        return str(row.get("value_int", row.get("value"))) == expected
    if field_type in ("date", "date_time"):
        # Accelo may normalise the stored format, so assert the date is present
        # rather than string-equal — a tighter check would raise false failures.
        return bool(row.get("value_date", row.get("value")))
    if field_type == "lookup":
        return str(row.get("value_id")) == str(value)
    # hyperlink, text, decimal, currency, select, multi_select, structure.
    return str(row.get("value")) == str(value)


def register(server: MCPServer, client: AcceloClient):
    """Register profile tools with the MCP server."""

    @server.tool()
    async def accelo_list_profile_fields(
        object_type: str,
        fields: str | None = None,
    ) -> dict:
        """List profile fields available for an object type.

        Args:
            object_type: The object type — affiliations, companies, contacts, contracts,
                invoices, issues, jobs, milestones, prospects, staff
            fields: Additional fields to return
        """
        params = {}
        if fields:
            params["_fields"] = fields
        return await client.get(f"/{object_type}/profiles/fields", params=params)

    @server.tool()
    async def accelo_get_profile_values(
        object_type: str,
        object_id: int,
        fields: str | None = None,
    ) -> dict:
        """Get profile field values for a specific object.

        Args:
            object_type: The object type (e.g. "companies", "issues")
            object_id: The object's ID
            fields: Additional fields to return
        """
        params = {}
        if fields:
            params["_fields"] = fields
        return await client.get(f"/{object_type}/{object_id}/profiles/values", params=params)

    @server.tool()
    async def accelo_set_profile_value(
        object_type: str,
        object_id: int,
        profile_field_id: int,
        value: str,
        value_type: str | None = None,
    ) -> dict:
        """Set a profile field value on an object and verify it persisted.

        The write goes through Accelo's dedicated profile-value endpoint,
        ``POST /{object_type}/{object_id}/profiles/fields/{profile_field_id}``
        ("Set a Profile Field Value"). The older
        ``PUT /{object_type}/{object_id}`` + ``profile.{id}`` form is only the
        create-company shortcut, not a general profile-value write, so it
        silently no-ops for hyperlink fields — that was the bug behind this
        tool reporting a false success.

        The request body is shaped by the field's ``field_type``, which is
        resolved first via ``GET /{object_type}/profiles/fields``:

        - ``integer`` -> ``value_int`` (the string ``value`` is coerced to int)
        - ``date`` / ``date_time`` -> ``value_date`` (unix timestamp or ISO8601
          string, passed through as given)
        - ``lookup`` -> ``value_id`` (the object id in ``value``) plus
          ``value_type`` (the lookup object type, e.g. ``company``)
        - everything else, including ``hyperlink``, ``text``, ``decimal``,
          ``currency``, ``select``, ``multi_select`` and ``structure`` ->
          ``value`` (a bare string; for a hyperlink that is the plain URL and
          Accelo stores ``value_type`` as null)

        After the write, the value is read back via
        ``GET /{object_type}/{object_id}/profiles/values`` (with
        ``_fields=_ALL`` so custom fields are returned) and compared against
        what was submitted. If no matching row is found, or the persisted value
        does not match, an error is returned (``status`` ``verify_failed``)
        rather than a success — the tool can never report a silent no-op as
        success. Date comparison is deliberately lenient (presence/non-empty)
        because Accelo may normalise the stored date format.

        Values are validated before any write, so a bad input returns a
        structured error (``error`` true) rather than failing mid-write:

        - ``invalid_value`` — an ``integer`` field was given a value that is
          not a valid integer.
        - ``value_type_required`` — a ``lookup`` field was given no
          ``value_type``; it is mandatory for lookup writes.
        - ``field_not_found`` — the ``profile_field_id`` does not exist for the
          object type.

        Args:
            object_type: The object type (e.g. "companies", "issues")
            object_id: The object's ID
            profile_field_id: The profile field's ID
            value: The value to set, as a string. For hyperlink/text fields this
                is the raw value; for integer/date fields it is coerced; for a
                lookup field it is the target object's id.
            value_type: Required for a lookup field — the lookup object type
                (e.g. "company"). A lookup write with no value_type returns a
                value_type_required error. Ignored for other field types.
        """
        try:
            # Resolve the field's type so the body can be shaped correctly.
            # Request the max page size (_limit=100, Accelo's documented
            # maximum) so the target field is not missed when an object type
            # has more than the default page of 10 profile fields. A single
            # _limit=100 request is used deliberately: >100 custom profile
            # fields on one object type is implausible, so paging past 100 is
            # not worth the extra round trips.
            fields_result = await client.get(
                f"/{object_type}/profiles/fields", params={"_limit": 100}
            )
            field_type = None
            for entry in fields_result.get("response") or []:
                if str(entry.get("id")) == str(profile_field_id):
                    field_type = entry.get("field_type")
                    break
            if field_type is None:
                return {
                    "error": True,
                    "status": "field_not_found",
                    "message": (
                        f"Profile field {profile_field_id} not found for "
                        f"object type '{object_type}'."
                    ),
                }

            # Shape the write body by field type.
            if field_type == "integer":
                # Guard the coercion: a non-integer string would raise
                # ValueError, which the surrounding except (AcceloAPIError only)
                # would not catch, surfacing as an unhandled exception. Reject
                # it as a structured error before any write happens.
                try:
                    value_int = int(value)
                except ValueError:
                    return {
                        "error": True,
                        "status": "invalid_value",
                        "message": (
                            f"Profile field {profile_field_id} is an integer "
                            f"field but value '{value}' is not a valid integer."
                        ),
                    }
                body: dict = {"value_int": value_int}
            elif field_type in ("date", "date_time"):
                body = {"value_date": value}
            elif field_type == "lookup":
                # A lookup write needs value_type (the lookup object type). If
                # it is missing, form-encoding would send None as the literal
                # string "None" — an invalid payload — so reject it up front.
                if not value_type:
                    return {
                        "error": True,
                        "status": "value_type_required",
                        "message": (
                            f"Profile field {profile_field_id} is a lookup "
                            f"field; value_type (the lookup object type, e.g. "
                            f"'company') is required."
                        ),
                    }
                body = {"value_id": value, "value_type": value_type}
            else:
                # hyperlink, text, decimal, currency, select, multi_select,
                # structure — a bare string value.
                body = {"value": value}

            write_result = await client.post(
                f"/{object_type}/{object_id}/profiles/fields/{profile_field_id}",
                data=body,
            )

            # Read back and verify the value actually persisted. Accelo value
            # rows may key the field id as "field_id" or "id", so match both.
            values_result = await client.get(
                f"/{object_type}/{object_id}/profiles/values",
                params={"_fields": "_ALL"},
            )
            row = None
            for candidate in values_result.get("response") or []:
                row_id = candidate.get("field_id", candidate.get("id"))
                if str(row_id) == str(profile_field_id):
                    row = candidate
                    break

            if row is None:
                return {
                    "error": True,
                    "status": "verify_failed",
                    "message": (
                        f"Profile field {profile_field_id} was not returned on "
                        f"read-back; the write may have silently no-opped."
                    ),
                }

            if not _value_matches(field_type, row, value):
                return {
                    "error": True,
                    "status": "verify_failed",
                    "message": (
                        f"Profile field {profile_field_id} did not persist the "
                        f"submitted value; the write silently no-opped."
                    ),
                }

            return write_result
        except AcceloAPIError as error:
            # Surface the real Accelo error (status, message, http_code,
            # more_info) to the caller instead of an opaque "Error executing
            # tool" — profile-value writes are a common failure point and the
            # typed-value handling differs by field type.
            return format_error(error)
