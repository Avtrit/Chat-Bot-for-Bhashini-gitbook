#!/usr/bin/env python3
import os
import re
import json


def extract_segment_title(raw_text, filename):
    """Extract title from 'TITLE: ...' line, fall back to filename."""
    for line in raw_text.splitlines():
        if line.strip().lower().startswith("title:"):
            # e.g. "TITLE: Pipeline Compute Call | Bhashini APIs"
            # Keep only the part before the pipe for brevity
            title_full = line.strip()[len("title:"):].strip()
            title = title_full.split("|")[0].strip()
            if title:
                return title
    # Fallback: derive from filename
    clean_name = filename.replace(".txt", "").replace("_", " ")
    return clean_name.title()


def clean_text(text):
    """Remove navigation chrome, URL lines, and other GitBook boilerplate."""
    # Words/phrases that are pure navigation noise
    NAV_EXACT = {
        "previous", "next", "copy",
        "bhashini", "bhashini.gov.in",
        "request payload", "response payload",  # common prev/next labels
    }

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        # Drop empty lines (we'll re-join cleanly later)
        if not stripped:
            cleaned_lines.append("")
            continue

        # Drop TITLE and URL header lines
        if lower.startswith("title:") or lower.startswith("url:"):
            continue

        # Drop "Last updated X ago / Last updated on ..."
        if lower.startswith("last updated"):
            continue

        # Drop single-word or short navigation tokens
        if lower in NAV_EXACT:
            continue

        cleaned_lines.append(stripped)

    # Collapse runs of blank lines into a single blank
    result_lines = []
    prev_blank = False
    for line in cleaned_lines:
        if line == "":
            if not prev_blank:
                result_lines.append("")
            prev_blank = True
        else:
            result_lines.append(line)
            prev_blank = False

    return "\n".join(result_lines).strip()


def create_segment_wise_json():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Scanning directory: {current_dir}...")

    # Collect page_X.txt / Page_X.txt files
    all_files = [
        item for item in os.listdir(current_dir)
        if item.lower().startswith("page_") and item.lower().endswith(".txt")
    ]

    if not all_files:
        print(
            "No files found! Make sure this script is placed inside the "
            "folder that contains your page_X.txt files."
        )
        return

    # Natural sort by the numeric index in the filename
    all_files.sort(key=lambda x: int(re.search(r"\d+", x).group()))
    print(f"Found {len(all_files)} pages. Grouping into segments...")

    segmented_data = {}  # title -> { title, pages_combined, combined_text }

    for file_name in all_files:
        file_path = os.path.join(current_dir, file_name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()

            segment_title = extract_segment_title(raw_text, file_name)
            cleaned_body = clean_text(raw_text)

            if segment_title not in segmented_data:
                segmented_data[segment_title] = {
                    "title": segment_title,
                    "pages_combined": [],
                    "combined_text": [],
                }

            segmented_data[segment_title]["pages_combined"].append(file_name)
            segmented_data[segment_title]["combined_text"].append(cleaned_body)

        except Exception as e:
            print(f"Skipping {file_name} due to error: {e}")

    # Build final output list
    final_output = []
    for idx, (title, data) in enumerate(segmented_data.items()):
        full_segment_text = "\n\n--- Next Section ---\n\n".join(data["combined_text"])
        context_header = (
            f"DOCUMENTATION MODULE: {title}\n"
            f"SOURCE FILES: {', '.join(data['pages_combined'])}\n\n"
        )

        final_output.append({
            "id": f"segment_{idx:03d}",
            "segment_name": title,
            "text": context_header + full_segment_text,
            "metadata": {
                "document_topic": title,
                "pages_used": data["pages_combined"],
            },
        })

    output_path = os.path.join(current_dir, "bhashini_segments.json")
    with open(output_path, "w", encoding="utf-8") as out_f:
        json.dump(final_output, out_f, indent=4, ensure_ascii=False)

    print(
        f"Done! Grouped {len(all_files)} pages into {len(final_output)} segments.\n"
        f"Output: {output_path}"
    )


if __name__ == "__main__":
    create_segment_wise_json()