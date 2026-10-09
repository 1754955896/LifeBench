# LifeBench Life Data Viewer

Open `index.html` in this directory directly in Chrome or Edge. Use the folder picker to select a persona directory, for example:

```text
life_bench_data/version2/data/sunyuwei/
```

The browser may describe directory selection as an upload. The viewer only reads files locally through the File API: it has no server, network requests, CDN dependencies, or data uploads. Browsers do not allow pages to read arbitrary disk paths automatically, so select the directory manually and select it again after refreshing.

Expected directory structure:

```text
persona-folder/
  daily_event.json       Required: an array of events
  persona.json           Optional: persona information
  phone_data/            Optional
    sms.json
    calendar.json
    agent_chat.json
    ...                  JSON arrays for each data source
```

## Features

- The calendar marks dates with life events and supports date entry, month navigation, and moving to the previous or next date with data.
- Events are shown chronologically with descriptions, participants, locations, and all time intervals. Events spanning multiple days appear on each covered date.
- Phone records are linked through `phone_data[].daily_event_id` to `daily_event[].event_id`. String and numeric IDs are compared consistently, including the valid ID `0`. The phone record's `event_id` is not used for this join.
- An event can have multiple linked phone records from different sources; arrays of linked IDs are supported. Only linked phone records whose own date matches the selected date are displayed. Records with a different or unrecognized date are excluded from the day's display, counts, search, and type filtering.
- Expand records to inspect all fields and raw JSON for SMS, calls, calendar entries, notes, photo descriptions, notifications, and assistant conversations.
- Search daily events and linked phone content, and filter by phone data type. Matching phone content retains its event context; search does not remove other records of the same type under that event.
- Records with missing or invalid association IDs appear as unlinked records on their own date. Date field priority is `datetime`, `date`, the legacy Chinese date key (JSON escape `\u65e5\u671f`), then `start_time`. Records with neither a date nor a valid association, such as contacts, are noted during loading and are not assigned a date automatically.
- Top-level counts describe the entire day and do not change with search. Linked records are deduplicated for counting. Visible counts are shown separately beside the event heading, and unlinked records are counted separately.
- Invalid individual phone files are reported and skipped. An invalid main event file, missing IDs or dates, or duplicate IDs prevents loading while preserving the previously loaded data.
- The viewer supports narrow screens and requires no build step, dependency installation, or backend.

## Files and Validation

`index.html` is the entry point, `styles.css` defines the styles, and `app.js` handles loading, indexing, and rendering. Keep all three files in the same directory.

Run from the repository root:

```sh
node --test html/viewer.test.cjs
```

Tests cover exact ID matching, events spanning multiple days, unlinked records, malicious HTML escaping, the full Sun Yuwei dataset, and loading, date navigation, search, and type filtering through a simulated browser DOM. Real-browser screenshot and visual validation have not yet been completed.
