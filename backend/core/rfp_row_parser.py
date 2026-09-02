"""Pure parsing rules for the Ariba "Open RFPs" listing table.

This module is deliberately dependency-free — it imports nothing but `re`, and
in particular nothing from `core.common_imports`, `helpers.core_helper` or
`helpers.credentials_provider`. Those build a live `DataverseClient` *at import
time*, which would make the offline selector check
(`Support-Files/verify_open_rfp_selectors.py`) impossible to run without a
network and secrets.

Keeping the rules here means the live Playwright scrape in
`core/common_process.py` and the offline check exercise the *same* code, so the
two cannot drift apart.

Why classes and not ids
-----------------------
Ariba's generated widget ids rotate on every SAP redeploy. The listing table
alone has been `_qml6w` -> `_swbzed` -> `_r5iirb`; each rotation broke the
scrape with a `wait_for_selector` timeout. The CSS class names below have
survived every generation captured in `Support-Files/Analysis-Files/`.

Why direct-child cells and not descendant indices
-------------------------------------------------
Current Ariba markup wraps each cell in a nested `<table class="mls">`, so
`query_selector_all('td')` (which matches *descendants*) returns ~10 elements
per row and the fields land on indices 0/1/3/5/8/9. Older captured markup has
no wrappers and five flat cells, where those same indices silently yield the
wrong fields — no exception, just corrupt rows. Selecting only direct-child
`<td>` gives a stable five columns in both generations.
"""

import re

# ---------------------------------------------------------------------------
# Selectors — anchor on Ariba's semantic classes, never on a generated id.
# ---------------------------------------------------------------------------
RFP_TABLE_SELECTOR = 'table.tableBody'
RFP_ROW_CLASS = 'tableRow1'
RFP_GROUP_ROW_CLASS = 'tableGroupBy'

# Group headers read e.g. "Status: Open (12)", "Status: Pending Selection (1152)".
# The trailing count is the group's advertised size — the scrape uses it to tell
# "the AJAX expand hasn't finished yet" apart from "this group is really empty".
RFP_OPEN_GROUP_RE = re.compile(r'Status:\s*Open\s*\(\d+\)')
RFP_OPEN_GROUP_COUNT_RE = re.compile(r'Status:\s*Open\s*\((\d+)\)')

# Direct-child <td> positions in a listing row. Verified against every capture
# in Support-Files/Analysis-Files/.
COL_TITLE = 0
COL_ID = 1
COL_END_DATE = 2
COL_EVENT_TYPE = 3
COL_PARTICIPATED = 4
EXPECTED_COLUMNS = 5


def norm_text(value) -> str:
    """Collapse whitespace runs to a single space and strip.

    Playwright's `inner_text()` already collapses per CSS rules while
    BeautifulSoup's `get_text()` does not; normalising here makes the live and
    offline paths produce byte-identical values. This also matches what the
    SYNC extractor already does in `automation_logic.extract_rfp_data_from_html`.
    """
    return re.sub(r'\s+', ' ', value or '').strip()


def is_open_group_header(text) -> bool:
    """True when a `tableGroupBy` row is the "Status: Open" header."""
    return bool(RFP_OPEN_GROUP_RE.search(text or ''))


def parse_open_group_count(text):
    """The N from "Status: Open (N)", or None when the header isn't present."""
    match = RFP_OPEN_GROUP_COUNT_RE.search(text or '')
    return int(match.group(1)) if match else None


def parse_open_rfp_row(cell_texts, href='') -> dict:
    """Map one listing row's direct-child cell texts to the scrape's dict shape.

    `cell_texts` must be the text of the row's *direct-child* `<td>` elements,
    in document order. `RFP_End_Date` is returned as the raw portal string;
    callers that persist to Dataverse apply `normalize_date_format` on top
    (that helper lives in `core.log_events`, which is not offline-importable).

    Returns None when the row has too few cells to be a data row — spacer rows
    such as `tr.AWTColAlignRow` land here.
    """
    if len(cell_texts) < EXPECTED_COLUMNS:
        return None

    return {
        "Title": norm_text(cell_texts[COL_TITLE]),
        "Link": norm_text(href),
        "ID": norm_text(cell_texts[COL_ID]),
        "Event Type": norm_text(cell_texts[COL_EVENT_TYPE]),
        "RFP_End_Date": norm_text(cell_texts[COL_END_DATE]),
        "Status": norm_text(cell_texts[COL_PARTICIPATED]),
    }
