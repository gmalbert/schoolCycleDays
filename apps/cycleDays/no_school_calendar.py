def fix_and_extract_no_school_events():
    input_file = "calendar.ics"
    output_file = "no_school_clean.ics"

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print("❌ Failed to read file:", e)
        return

    inside_event = False
    event_lines = []
    matching_events = []

    for line in lines:
        stripped = line.strip()

        if stripped == "BEGIN:VEVENT":
            inside_event = True
            event_lines = [line]
            continue

        if inside_event:
            event_lines.append(line)

            if stripped.startswith("SUMMARY:") and stripped[8:].startswith("No School"):
                pass  # We'll decide to keep it at END

            if stripped == "END:VEVENT":
                inside_event = False
                # Check if it's a "No School" event
                if any(l.strip().startswith("SUMMARY:No School") for l in event_lines):
                    matching_events.append(list(event_lines))
                event_lines = []

    # Handle final event if file ends without END:VEVENT
    if inside_event and event_lines:
        print("⚠️ Auto-fixing event missing END:VEVENT")
        event_lines.append("END:VEVENT\n")
        if any(l.strip().startswith("SUMMARY:No School") for l in event_lines):
            matching_events.append(list(event_lines))

    if not matching_events:
        print("😕 No 'No School' events found.")
        return

    # Build new .ics content
    header = [
        "BEGIN:VCALENDAR\n",
        "VERSION:2.0\n",
        "PRODID:-//Greg's Clean Calendar//EN\n",
        "CALSCALE:GREGORIAN\n",
        "METHOD:PUBLISH\n"
    ]
    footer = ["END:VCALENDAR\n"]

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(header)
            for event in matching_events:
                f.writelines(event)
            f.writelines(footer)
        print(f"✅ Created clean .ics file with {len(matching_events)} 'No School' event(s): {output_file}")
    except Exception as e:
        print("❌ Failed to write output file:", e)

fix_and_extract_no_school_events()