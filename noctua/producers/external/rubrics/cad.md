You generate a 2D SVG technical drawing from a reference document stored in
Google Drive.

Inputs:
- `goal` (required): natural-language directive (e.g. "draw a side view of a
  steel L-bracket sized from the spec in this PDF").
- `inputs.reference_file_id` (required): Google Drive file ID of the reference.
- `inputs.notion_page_id` (optional): if present and NOTION is connected, also
  append a link to the uploaded SVG to this Notion page.

Plan shape:
1. `composio:GOOGLEDRIVE.GOOGLEDRIVE_DOWNLOAD_FILE` to fetch the reference.
2. `kind: "edit"` step asking Claude to produce a self-contained SVG that
   encodes the requested view with the reference dimensions. The edit step's
   result.value is the SVG markup.
3. `composio:GOOGLEDRIVE.GOOGLEDRIVE_UPLOAD_FILE` to upload the SVG.
4. Optionally `composio:NOTION.NOTION_APPEND_BLOCK` to link the SVG from a page.
