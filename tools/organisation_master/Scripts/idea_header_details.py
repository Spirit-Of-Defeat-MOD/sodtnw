"""Details, discussion and references attached to Ideas categories / headings."""

SEP = " › "


def get(data, category, heading):
    return next((row for row in data.get("idea_header_details", [])
                 if row.get("category") == category and row.get("heading", "") == heading), None)


def relocate(data, transform):
    """Keep stable IDs on rename/move; merge discussion and references on a collision."""
    rows = data.get("idea_header_details", [])
    destinations = {}
    for row in list(rows):
        category, heading = transform(row.get("category", ""), row.get("heading", ""))
        row.update(category=category, heading=heading, title=category + (SEP + heading if heading else ""))
        other = destinations.get((category, heading))
        if other is None:
            destinations[category, heading] = row
            continue
        text = row.get("text", "")
        if text and text != other.get("text"):
            other["text"] = "\n\n".join(x for x in (other.get("text"), text) if x)
        if "project" in row and "project" not in other:
            other["project"] = row["project"]
        for key in ("links", "comments"):
            current = other.setdefault(key, [])
            for value in row.get(key, []):
                if value not in current:
                    current.append(value)
        rows.remove(row)

