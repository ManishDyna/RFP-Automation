import requests
import logging
from msal import ConfidentialClientApplication
from typing import Dict, Any, List
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

logger = logging.getLogger(__name__)


def _is_retryable_error(exc: Exception) -> bool:
    """Only retry on server errors (5xx) or throttling (429), not client errors."""
    if isinstance(exc, requests.exceptions.ConnectionError):
        return True
    if isinstance(exc, requests.exceptions.Timeout):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        status = exc.response.status_code if exc.response is not None else 0
        return status == 429 or status >= 500
    return False


def _retry_request(method, url, **kwargs):
    """Execute an HTTP request with retry logic for transient failures."""
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(_is_retryable_error),
        reraise=True,
    )
    def _do_request():
        resp = method(url, **kwargs)
        if resp.status_code == 429 or resp.status_code >= 500:
            resp.raise_for_status()
        return resp

    try:
        return _do_request()
    except Exception:
        # Final fallback: return the last response without raising
        return method(url, **kwargs)

class DataverseClient:
    def __init__(self, tenant_id, client_id, client_secret, resource_url):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.resource_url = resource_url.rstrip("/")
        self.api_url = f"{self.resource_url}/api/data/v9.2/"
        self.token: str | None = None
        self.token_expiry: datetime | None = None
        # Cache for column mappings (table_logical_name -> {display_name: logical_name})
        # Column mappings rarely change, so we cache them for the lifetime of the client
        self._column_mapping_cache: Dict[str, dict] = {}
        self._refresh_token()

    def _get_access_token(self) -> tuple[str, datetime]:
        authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        scope = f"{self.resource_url}/.default"
        app = ConfidentialClientApplication(
            self.client_id,
            authority=authority,
            client_credential=self.client_secret
        )
        token_result = app.acquire_token_for_client(scopes=[scope])
        access_token = token_result.get("access_token")
        if not access_token:
            raise Exception("Failed to get access token")
        expires_in_seconds = int(token_result.get("expires_in", 3600))
        # Refresh a bit early (5 minutes) to avoid edge-expiry during requests
        expiry_time = datetime.now() + timedelta(seconds=max(0, expires_in_seconds - 300))
        return access_token, expiry_time

    def _refresh_token(self) -> None:
        token, expiry = self._get_access_token()
        self.token = token
        self.token_expiry = expiry

    def _ensure_valid_token(self) -> None:
        if self.token is None or self.token_expiry is None or datetime.now() >= self.token_expiry:
            self._refresh_token()

    def _headers(self, content_type: str = "application/json", extra: dict | None = None):
        self._ensure_valid_token()
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": content_type,
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
        }
        if extra:
            headers.update(extra)
        return headers

    def _request(self, method, url, retryable=True, **kwargs):
        """Centralized HTTP request with optional retry for transient failures."""
        if retryable:
            return _retry_request(method, url, **kwargs)
        return method(url, **kwargs)

    def count_rows(self, table_api_name: str, filter_expr: str = None, table_logical_name: str = None, use_display_names: bool = True) -> int:
        """Get the total count of rows in a Dataverse table using $count."""
        url = f"{self.api_url}{table_api_name}"
        params = {"$count": "true", "$top": "0"}

        if filter_expr and use_display_names and table_logical_name:
            column_map = self.get_column_mapping(table_logical_name)
            for display_name, logical_name in column_map.items():
                filter_expr = filter_expr.replace(display_name, logical_name)

        if filter_expr:
            params["$filter"] = filter_expr

        resp = self._request(requests.get, url, headers=self._headers(), params=params)
        if resp.status_code != 200:
            raise Exception(f"[ERROR] Count failed for '{table_api_name}': {resp.status_code}")
        return resp.json().get("@odata.count", 0)

    def get_all_rows(self, table_api_name: str, select_columns: List[str] = None, table_logical_name: str = None, use_display_names: bool = True, page_size: int = 5000) -> List[dict]:
        """Fetch ALL rows from a Dataverse table using @odata.nextLink pagination."""
        url = f"{self.api_url}{table_api_name}"
        params = {}  # No $top — let Dataverse paginate naturally via @odata.nextLink

        select_expr = None
        if select_columns:
            select_expr = ",".join(select_columns)

        if use_display_names and table_logical_name and select_expr:
            column_map = self.get_column_mapping(table_logical_name)
            select_fields = [column_map.get(f.strip(), f.strip()) for f in select_expr.split(",")]
            select_expr = ",".join(select_fields)

        if select_expr:
            params["$select"] = select_expr

        all_rows = []
        page_num = 0
        while url:
            page_num += 1
            resp = self._request(requests.get, url, headers=self._headers(), params=params)
            if resp.status_code != 200:
                error_text = resp.text.encode('ascii', 'replace').decode('ascii')
                raise Exception(f"[ERROR] Query failed for '{table_api_name}': {resp.status_code}, {error_text}")
            data = resp.json()
            page_rows = data.get("value", [])
            all_rows.extend(page_rows)
            next_link = data.get("@odata.nextLink")
            print(f"[Page {page_num}] fetched {len(page_rows)} rows (total so far: {len(all_rows)}, has next: {bool(next_link)})")
            url = next_link
            params = {}  # nextLink URL already contains query params

        # Remap to display names if needed
        if use_display_names and table_logical_name:
            try:
                column_map = self.get_column_mapping(table_logical_name)
                logical_to_display = {logical: display for display, logical in column_map.items()}
                display_rows = []
                for row in all_rows:
                    display_row = {}
                    for logical_col, value in row.items():
                        display_col = logical_to_display.get(logical_col, logical_col)
                        display_row[display_col] = value
                    display_rows.append(display_row)
                return display_rows
            except Exception:
                return all_rows

        return all_rows

    # ---------------- Get rows with filters and select columns ----------------
    def get_rows_from_dataverse(
        self,
        table_api_name: str,
        filter_by: dict = None,          # e.g., {"RFP_ID": "12345"}
        select_columns: List[str] = None, # e.g., ["RunID", "RFP_ID"]
        top: int = 10,
        skip: int = 0,                   # For pagination: skip first N rows
        order_by: str | None = None,     # e.g., "created_at desc"
        table_logical_name: str = None,
        use_display_names: bool = True
        ) -> List[dict]:
        """
        Retrieve rows from a Dataverse table with optional filtering, column selection, and pagination.

        Args:
            table_api_name: API name of the table
            filter_by: Dict of column->value filters
            select_columns: List of column names to retrieve
            top: Maximum rows to return (default 10)
            skip: Number of rows to skip for pagination (default 0)
            order_by: Sort order (e.g., "created_at desc")
            table_logical_name: Logical name for display name mapping
            use_display_names: Whether to use display names
        """
        filter_expr = None
        select_expr = None

        # Construct filter expression
        if filter_by:
            filter_parts = []
            for col, val in filter_by.items():
                if isinstance(val, str):
                    val = val.replace("'", "''")  # Escape single quotes
                    filter_parts.append(f"{col} eq '{val}'")
                else:
                    filter_parts.append(f"{col} eq {val}")
            filter_expr = " and ".join(filter_parts)

        # Construct select expression
        if select_columns:
            select_expr = ",".join(select_columns)

        # Use the query_rows method
        result = self.query_rows(
            table_api_name=table_api_name,
            filter_expr=filter_expr,
            select=select_expr,
            top=top,
            skip=skip,
            order_by=order_by,
            table_logical_name=table_logical_name,
            use_display_names=use_display_names
        )
        rows = result.get("value", [])

        # If caller asked for display names, remap returned rows' keys from logical -> display
        if use_display_names and table_logical_name:
            try:
                column_map = self.get_column_mapping(table_logical_name)  # display -> logical
                logical_to_display = {logical: display for display, logical in column_map.items()}

                display_rows: List[dict] = []
                for row in rows:
                    display_row = {}
                    for logical_col, value in row.items():
                        display_col = logical_to_display.get(logical_col, logical_col)
                        display_row[display_col] = value
                    display_rows.append(display_row)
                return display_rows
            except Exception:
                # If mapping fails for any reason, fall back to original rows
                return rows

        return rows

    # Query rows from a Dataverse table
    def query_rows(self, table_api_name: str, filter_expr: str = None, select: str = None, top: int = 1, skip: int = 0, order_by: str | None = None, table_logical_name: str = None, use_display_names: bool = True):
        """
        Query rows from Dataverse table with pagination support.
        If use_display_names=True, filter_expr and select can use display names.

        Args:
            skip: Number of rows to skip (for pagination via OData $skip)
        """
        url = f"{self.api_url}{table_api_name}"
        params = {}

        # Map display names to logical names if needed
        if use_display_names and table_logical_name:
            column_map = self.get_column_mapping(table_logical_name)
            if filter_expr:
                for display_name, logical_name in column_map.items():
                    filter_expr = filter_expr.replace(display_name, logical_name)
            if select:
                select_fields = [column_map.get(f.strip(), f.strip()) for f in select.split(",")]
                select = ",".join(select_fields)
            if order_by:
                # support "col desc" or "col asc"
                parts = [p.strip() for p in order_by.split(",")]
                mapped_parts = []
                for p in parts:
                    tokens = p.split()
                    col = tokens[0]
                    direction = tokens[1] if len(tokens) > 1 else None
                    logical = column_map.get(col, col)
                    mapped_parts.append(f"{logical} {direction}".strip())
                order_by = ",".join(mapped_parts)

        if filter_expr:
            params["$filter"] = filter_expr
        if select:
            params["$select"] = select
        if top:
            params["$top"] = str(top)
        if skip and skip > 0:
            params["$skip"] = str(skip)
        if order_by:
            params["$orderby"] = order_by

        resp = self._request(requests.get, url, headers=self._headers(), params=params)
        if resp.status_code != 200:
            error_text = resp.text.encode('ascii', 'replace').decode('ascii')
            raise Exception(f"[ERROR] Query failed for '{table_api_name}': {resp.status_code}, {error_text}")
        result = resp.json()

        # Remap logical column names back to display names if needed
        if use_display_names and table_logical_name:
            try:
                column_map = self.get_column_mapping(table_logical_name)
                logical_to_display = {logical: display for display, logical in column_map.items()}
                rows = result.get("value", []) if isinstance(result, dict) else result if isinstance(result, list) else []
                display_rows = []
                for row in rows:
                    display_row = {}
                    for logical_col, value in row.items():
                        display_col = logical_to_display.get(logical_col, logical_col)
                        display_row[display_col] = value
                    display_rows.append(display_row)
                if isinstance(result, dict):
                    result["value"] = display_rows
                else:
                    result = display_rows
            except Exception:
                pass

        return result


    # Get display name -> logical name mapping for a table (cached)
    def get_column_mapping(self, table_logical_name: str, force_refresh: bool = False) -> dict:
        """
        Get column mapping from display names to logical names.
        Results are cached to avoid repeated API calls - column metadata rarely changes.
        Use force_refresh=True to bypass cache if needed.
        """
        # Return cached mapping if available
        if not force_refresh and table_logical_name in self._column_mapping_cache:
            return self._column_mapping_cache[table_logical_name]

        url = f"{self.api_url}EntityDefinitions(LogicalName='{table_logical_name}')/Attributes?$select=LogicalName,DisplayName"
        response = self._request(requests.get, url, headers=self._headers())
        if response.status_code != 200:
            error_text = response.text.encode('ascii', 'replace').decode('ascii')
            raise Exception(f"Failed to get metadata for '{table_logical_name}': {response.status_code}, {error_text}")

        mapping = {}
        for attr in response.json().get("value", []):
            display_labels = attr.get("DisplayName", {}).get("LocalizedLabels", [])
            if display_labels:
                mapping[display_labels[0]["Label"]] = attr.get("LogicalName")

        # Cache the result
        self._column_mapping_cache[table_logical_name] = mapping
        return mapping

    def clear_column_mapping_cache(self, table_logical_name: str = None):
        """Clear column mapping cache. If table_logical_name is provided, only clear that table's cache."""
        if table_logical_name:
            self._column_mapping_cache.pop(table_logical_name, None)
        else:
            self._column_mapping_cache.clear()

    def get_choice_options(self, table_logical_name: str, attribute_logical_name: str) -> dict:
        """
        Return a dict with keys:
          - label_to_value: {"Label": 123}
          - value_to_label: {123: "Label"}
        """
        # Metadata path for attribute with options
        url = (
            f"{self.api_url}EntityDefinitions(LogicalName='{table_logical_name}')"
            f"/Attributes(LogicalName='{attribute_logical_name}')/Microsoft.Dynamics.CRM.PicklistAttributeMetadata?$select=LogicalName&$expand=OptionSet"
        )
        resp = requests.get(url, headers=self._headers())
        if resp.status_code != 200:
            raise Exception(
                f"Failed to get choice options for {table_logical_name}.{attribute_logical_name}: {resp.status_code} {resp.text}"
            )
        data = resp.json()
        options = data.get("OptionSet", {}).get("Options", [])
        label_to_value = {}
        value_to_label = {}
        for opt in options:
            value = opt.get("Value")
            labels = opt.get("Label", {}).get("LocalizedLabels", [])
            if labels:
                label = labels[0].get("Label")
                label_to_value[label] = value
                value_to_label[value] = label
        return {"label_to_value": label_to_value, "value_to_label": value_to_label}

    # Insert row into Dataverse
    def insert_row(self, table_api_name: str, data: Dict[str, Any], table_logical_name: str = None, use_display_names: bool = True):
        if use_display_names and table_logical_name:
            column_map = self.get_column_mapping(table_logical_name)
            data = {column_map.get(k, k): v for k, v in data.items()}

        url = f"{self.api_url}{table_api_name}"
        # response = requests.post(url, json=data, headers=self._headers())
       
        response = requests.post(
            url,
            json=data,
            headers=self._headers("application/json;IEEE754Compatible=true"),
        )
        if response.status_code in [200, 201, 204]:
            print(f"[OK] Row inserted into '{table_api_name}'")
            return True
        else:
            error_text = response.text.encode('ascii', 'replace').decode('ascii')
            print(f"[ERROR] Insert into '{table_api_name}' failed: {response.status_code} {error_text}")
            return False

    # Update row in Dataverse
    def update_row(self, table_api_name: str, record_id: str, data: Dict[str, Any], table_logical_name: str = None, use_display_names: bool = True):
        if use_display_names and table_logical_name:
            column_map = self.get_column_mapping(table_logical_name)
            data = {column_map.get(k, k): v for k, v in data.items()}
        url = f"{self.api_url}{table_api_name}({record_id})"
        response = self._request(
            requests.patch, url,
            json=data,
            headers=self._headers("application/json;IEEE754Compatible=true"),
        )
        if response.status_code in [200, 204]:
            print(f"[OK] Row updated in '{table_api_name}'")
            return True
        else:
            error_text = response.text.encode('ascii', 'replace').decode('ascii')
            raise Exception(f"[ERROR] Update failed for '{table_api_name}': {response.status_code}, {error_text}")

    def delete_row(self, table_api_name: str, record_id: str):
        """Delete a single row from a Dataverse table by record ID."""
        url = f"{self.api_url}{table_api_name}({record_id})"
        response = self._request(requests.delete, url, headers=self._headers())
        if response.status_code in [200, 204]:
            print(f"[OK] Row deleted from '{table_api_name}'")
            return True
        else:
            error_text = response.text.encode('ascii', 'replace').decode('ascii')
            raise Exception(f"[ERROR] Delete failed for '{table_api_name}': {response.status_code}, {error_text}")

    def batch_delete(self, table_api_name: str, record_ids: List[str]) -> int:
        """
        Delete multiple rows using Dataverse $batch API.
        Returns count of successfully deleted rows.
        Falls back to one-by-one delete if batch fails.
        """
        import uuid as _uuid

        if not record_ids:
            return 0

        batch_id = str(_uuid.uuid4())
        changeset_id = str(_uuid.uuid4())
        boundary = f"batch_{batch_id}"
        changeset_boundary = f"changeset_{changeset_id}"

        # Build multipart batch body
        body_parts = [f"--{boundary}", f"Content-Type: multipart/mixed; boundary={changeset_boundary}", ""]
        for i, rid in enumerate(record_ids):
            body_parts.extend([
                f"--{changeset_boundary}",
                f"Content-Type: application/http",
                f"Content-Transfer-Encoding: binary",
                f"Content-ID: {i + 1}",
                "",
                f"DELETE {self.api_url}{table_api_name}({rid}) HTTP/1.1",
                "Content-Type: application/json",
                "",
                "",
            ])
        body_parts.append(f"--{changeset_boundary}--")
        body_parts.append(f"--{boundary}--")
        batch_body = "\r\n".join(body_parts)

        try:
            resp = requests.post(
                f"{self.api_url}$batch",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": f"multipart/mixed; boundary={boundary}",
                    "OData-MaxVersion": "4.0",
                    "OData-Version": "4.0",
                },
                data=batch_body,
            )
            if resp.status_code in [200, 204]:
                return len(record_ids)
            else:
                logger.warning(f"Batch delete failed ({resp.status_code}), falling back to one-by-one")
        except Exception as e:
            logger.warning(f"Batch delete error: {e}, falling back to one-by-one")

        # Fallback: delete one by one
        deleted = 0
        for rid in record_ids:
            try:
                self.delete_row(table_api_name, rid)
                deleted += 1
            except Exception:
                pass
        return deleted

