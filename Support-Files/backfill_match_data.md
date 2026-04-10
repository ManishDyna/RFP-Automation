# Plan: New `cr673_bahra_rfps_v2` Table + Backfill + Code Migration

## Context

The current `bahra_rfps` table is messy (mixed manual multi-rows + automation single-rows, unused columns, columns that don't exist). We're creating a clean `cr673_bahra_rfps_v2` table with only needed columns (19 vs 30+), using `Matched_Data` JSON as the single source of truth for all material match data.

## New Table: `cr673_bahra_rfps_v2`

### 19 Columns (only what the system actually reads):

#

Display Name

Type

Purpose

1

RunID (Primary)

String

Run identifier

2

RFP_ID

String

RFP unique ID

3

Company_Name

String

Company filter

4

RFP_End_Date

String

Deadline

5

owner_name

String

RFP owner

6

publish_time

Date and time

Publication time

7

participated

String

Status

8

Link

String

Portal link

9

**Matched_Data**

**Memo**

**JSON of ALL materials — single source of truth**

10

Email_Status

String

Email tracking

11

Email_To

Email

Recipient

12

Email_Sent_At

String

Send timestamp

13

Downloaded_At

Date and time

Download timestamp

14

Reminder_1Day_Sent

String

Reminder flag

15

Reminder_3Day_Sent

String

Reminder flag

16

response_count

String

Response tracking

17

first_response_at

String

Response tracking

18

all_responses_at

String

Response tracking

19

rfp_type

String

RFP type

### Removed columns (11 columns eliminated):

-   `Material_Matched` — derived from `Matched_Data` JSON at query time
-   `Keyword_Matched` — derived from `Matched_Data` JSON at query time
-   `Material_Code` — never written by code, derive from JSON
-   `Material_Description` — never written by code, derive from JSON
-   `Matched_Keywords` — never written by code, derive from JSON
-   `match_rate_pct` — never read by any route/frontend
-   `exact_match_count` — never read
-   `keyword_match_count` — never read
-   `total_line_items` — never read
-   `file_size_bytes` — never read
-   `no_of_matched_materials` / `no_of_matched_keywords` — don't exist in table

## Matched_Data JSON Format (per item):

```json
{  "Material": "123456789",  "Material Description": "Cable 3x150mm",  "SourceFile": "RFP_file.xls",  "RFP_Title": "DOC123456",  "RFP_End_Date": "3/15/2026",  "RowNumber": 5,  "ColumnName": "Items",  "ExtractedMaterial": "123456789",  "MatchMethod": "exact" | "keyword" | null,  "is_matched": true | false,  "ExcelName": "Cable 3x150mm",  "ExcelDescription": "Power cable..."}
```

## Derived Values (computed at query time, not stored):

-   `Material_Matched` = "Yes" if any item has `is_matched: true`
-   `Keyword_Matched` = "Yes" if any item has `MatchMethod: "keyword"` and `is_matched: true`

## Backfill Script Flow:

1.  Copy existing data from old table (one row per unique RFP_ID)
2.  For RFPs with empty `Matched_Data`: find Excel → match → populate JSON
3.  Idempotent (skips existing RFP_IDs in new table)

## Migration: Old table stays untouched until new table + code is verified.

## Files: See plan file for complete list.