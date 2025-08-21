#!/usr/bin/env python3
"""Paddock Parser Toolkit - Manual Collection Link Helper"""

import sys
import webbrowser
from datetime import date
from pathlib import Path
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader, select_autoescape

from paddock_parser.config import load_config

def create_and_launch_link_helper(config: Dict[str, Any]):
    """
    Generates and opens an HTML file with links to all enabled data sources.
    """
    print("Generating manual collection link helper...")

    output_dir = Path(config.get("DEFAULT_OUTPUT_DIR", "output"))
    output_dir.mkdir(exist_ok=True, parents=True)
    output_path = output_dir / "collector.html"
    template_name = config.get("TEMPLATE_SCANNER", "template_scanner.html")
    data_sources = config.get("DATA_SOURCES", [])
    proxy_viewers = [p for p in config.get("PROXY_VIEWERS", []) if p.get("ENABLED", False)]

    today_str = date.today().strftime("%Y-%m-%d")

    all_sites = []
    for category in data_sources:
        enabled_sites = [
            site for site in category.get("sites", [])
            if site.get("enabled", True) and site.get("url")
        ]
        for site in enabled_sites:
            site["formatted_url"] = site["url"].format(date_str_iso=today_str)

        if enabled_sites:
            all_sites.append({
                "title": category.get("title"),
                "sites": enabled_sites
            })

    try:
        env = Environment(
            loader=FileSystemLoader('.'),
            autoescape=select_autoescape(['html', 'xml'])
        )
        template = env.get_template(template_name)
        html_content = template.render(
            categories=all_sites,
            proxy_viewers=proxy_viewers,
            report_date=today_str
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        print(f"✅ Success! Link helper created at: {output_path.resolve()}")

        try:
            webbrowser.open(output_path.resolve().as_uri())
            print("🚀 Launched in default web browser.")
        except Exception as e:
            print(f"⚠️ Could not automatically open the file in a browser: {e}")
            print("   Please open the file manually.")

    except Exception as e:
        print(f"❌ Error generating link helper: {e}")
        import logging
        logging.basicConfig(level=logging.DEBUG)
        logging.exception("Detailed error trace:")

if __name__ == "__main__":
    print("--- Paddock Parser Link Helper ---")

    cfg = load_config()
    if not cfg:
        sys.exit(1)

    create_and_launch_link_helper(cfg)

    print("\n--- Done ---")
