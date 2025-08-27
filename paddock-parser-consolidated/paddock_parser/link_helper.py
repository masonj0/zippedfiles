#!/usr/bin/env python3
"""
Paddock Parser Toolkit - Integrated Collector Generator (v2.1)

This module generates our interactive data collection dashboard. It has been
updated to be more robust in handling the v2.0 config structure.
"""

import webbrowser
from pathlib import Path
from typing import Dict, List
from datetime import date
from urllib.parse import quote
import sys

# Use the canonical config manager
from .config_manager import config_manager


def create_and_launch_link_helper():
    """
    Generates and opens the interactive `collector.html` dashboard,
    populating it with all enabled V2 and Legacy data sources.
    """
    config = config_manager.get_config()
    print("Generating the Integrated Collector dashboard...")

    output_dir = Path(config.get("DEFAULT_OUTPUT_DIR", "output"))
    output_dir.mkdir(exist_ok=True, parents=True)
    helper_path = output_dir / "collector.html"

    today = date.today()
    date_str_iso = today.strftime("%Y-%m-%d")

    proxy_viewers = config.get("PROXY_VIEWERS", [])

    # --- NEW LOGIC: Combine V2 and Legacy data sources ---
    all_categories: List[Dict] = []

    # 1. Add sites from the new DATA_SOURCES_V2 dictionary
    v2_sources = config.get("DATA_SOURCES_V2", {})
    v2_sites = []
    for key, value in v2_sources.items():
        if value.get("enabled", False):
            # Ensure the site dictionary has a 'name', using the key as a fallback
            if "name" not in value:
                value["name"] = key.replace("_", " ").title()
            v2_sites.append(value)

    if v2_sites:
        all_categories.append({"title": "V2 Data Adapters", "sites": v2_sites})

    # 2. Add sites from the old LEGACY_DATA_SOURCES list
    legacy_categories = config.get("LEGACY_DATA_SOURCES", [])
    for category in legacy_categories:
        enabled_sites = [site for site in category.get("sites", []) if site.get("enabled", True)]
        if enabled_sites:
            all_categories.append({"title": category.get("title"), "sites": enabled_sites})

    # --- Dynamic HTML Generation ---
    sections_html = ""
    for category in all_categories:
        title = category.get("title", "Unknown Category")
        sites_html = ""
        for site in category.get("sites", []):
            # This is now guaranteed to exist because of the logic above
            name = site.get("name")

            url = site.get("url", "#")
            if "{date_str_iso}" in url:
                url = url.format(date_str_iso=date_str_iso)

            source_id = name.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")

            proxy_links_html = ""
            for viewer in proxy_viewers:
                if viewer.get("ENABLED", False):
                    proxy_url_template = viewer.get("TOOL_URL", "")
                    proxy_link_text = viewer.get("LINK_TEXT", "View via Proxy")
                    if proxy_url_template:
                        encoded_url = quote(url, safe=":/")
                        proxy_full_url = proxy_url_template.format(target_url=encoded_url)
                        proxy_links_html += (
                            f' | <a href="{proxy_full_url}" target="_blank">{proxy_link_text}</a>'
                        )

            sites_html += f"""
            <div class="source-item">
                <div class="source-header">
                    <strong>{name}:</strong>
                    <div class="links">
                        <a href="{url}" target="_blank">Direct Link</a>{proxy_links_html}
                    </div>
                </div>
                <textarea id="{source_id}" placeholder="Paste source code for {name} here..."></textarea>
            </div>
            """
        sections_html += f"<h2>{title}</h2>\n<div class='source-grid'>{sites_html}</div>\n"

    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Paddock Parser - Integrated Collector</title>
    <style>
        body {{ font-family: system-ui, sans-serif; margin: 0; padding: 25px; background: #f8f9fa; }}
        /* Basic styles for readability */
        .container {{ max-width: 1200px; margin: auto; }}
        h1, h2 {{ color: #2c3e50; }}
        .source-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }}
        textarea {{ width: 100%; height: 100px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🐎 Integrated Data Collector</h1>
        <p>Paste the source code for each site into the corresponding text box below.</p>
        {sections_html}
    </div>
</body>
</html>
    """

    try:
        helper_path.write_text(html_content, encoding="utf-8")
        print(f"✅ Successfully generated dashboard at: {helper_path.resolve()}", file=sys.stdout)
        webbrowser.open(f"file://{helper_path.resolve()}")
    except Exception as e:
        print(f"❌ Could not create or open the Integrated Collector file: {e}", file=sys.stderr)


if __name__ == "__main__":
    create_and_launch_link_helper()
