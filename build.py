#!/usr/bin/env python3
"""
Builds partner-branded static sites directly from the main site repo.

This script lives at the ROOT of the medfit-health-website repo, right next
to index.html, employers.html, etc. It treats the repo root as the single
source of truth — there is no separate copy of the site to keep in sync.
When you edit the real site, every partner build picks up the change
automatically on next run.

Usage:
    python build.py --partner nta4me
    python build.py --partner pmd
    python build.py --all

Reads:  .  (repo root)        the real site — same files that serve mfh1.medfit.health
        partners/<slug>.json  per-partner overrides: logo, banner copy, discount code
        partner-banner.html   shared banner component with {{TOKEN}} placeholders
Writes: dist/<slug>/          a full copy of the site with the banner injected into index.html
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE_DIR = ROOT  # the repo root IS the template — no separate copy
PARTNERS_DIR = ROOT / "partners"
BANNER_FILE = ROOT / "partner-banner.html"
DIST_DIR = ROOT / "dist"

# Files/folders at repo root that belong to the partner build system itself,
# not to the actual site — these must never be copied into a partner's dist output.
EXCLUDE_FROM_COPY = {
    "partners", "dist", "build.py", "partner-banner.html", "README.md",
    ".git", ".gitignore", "node_modules", ".netlify",
}

INSERT_BEFORE = '<section class="hero-d2c">'
INSERT_AFTER_MARKER = "</header>"


def load_partner_config(slug):
    path = PARTNERS_DIR / f"{slug}.json"
    if not path.exists():
        sys.exit(f"No config found for partner '{slug}' at {path}")
    with open(path) as f:
        return json.load(f)


def render_banner(config):
    banner_html = BANNER_FILE.read_text()
    tokens = {
        "{{PARTNER_NAME}}": config["partner_name"],
        "{{PARTNER_LOGO_URL}}": config["partner_logo_url"],
        "{{BANNER_HEADLINE}}": config["banner_headline"],
        "{{BANNER_BODY}}": config["banner_body"],
        "{{DISCOUNT_CODE}}": config["discount_code"],
        "{{DISCOUNT_TEXT}}": config["discount_text"],
        "{{BANNER_IMAGE_URL}}": config.get("banner_image_url", "images/placeholder-photo.png"),
    }
    for token, value in tokens.items():
        banner_html = banner_html.replace(token, value)
    return banner_html


def inject_banner(html, banner_html):
    if INSERT_BEFORE not in html:
        sys.exit(f"Could not find insertion point '{INSERT_BEFORE}' in index.html — "
                  f"template may have changed structure; update INSERT_BEFORE in build.py.")
    if INSERT_AFTER_MARKER not in html:
        sys.exit(f"Could not find '{INSERT_AFTER_MARKER}' in index.html.")
    # Insert banner right before the hero section (i.e. right after </header>)
    return html.replace(INSERT_BEFORE, banner_html + "\n" + INSERT_BEFORE, 1)


def patch_meta(html, config):
    if config.get("page_title_suffix"):
        html = re.sub(
            r"(<title>)(.*?)(</title>)",
            lambda m: m.group(1) + m.group(2) + config["page_title_suffix"] + m.group(3),
            html,
            count=1,
            flags=re.DOTALL,
        )
    if config.get("meta_description"):
        html = re.sub(
            r'(<meta name="description" content=")(.*?)(")',
            lambda m: m.group(1) + config["meta_description"] + m.group(3),
            html,
            count=1,
        )
    return html


def copy_source_excluding_build_files(source, dest):
    """Copy the repo root to dest, skipping the partner-build-system's own files."""
    dest.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.name in EXCLUDE_FROM_COPY:
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def build_partner(slug):
    config = load_partner_config(slug)
    out_dir = DIST_DIR / slug

    if out_dir.exists():
        shutil.rmtree(out_dir)
    copy_source_excluding_build_files(SOURCE_DIR, out_dir)

    index_path = out_dir / "index.html"
    html = index_path.read_text()

    banner_html = render_banner(config)
    html = inject_banner(html, banner_html)
    html = patch_meta(html, config)

    index_path.write_text(html)

    placeholder_count = html.count("PLACEHOLDER")
    print(f"[{slug}] built -> {out_dir}")
    if placeholder_count:
        print(f"[{slug}] WARNING: {placeholder_count} unresolved PLACEHOLDER value(s) "
              f"still in partners/{slug}.json — fill these in before deploying.")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--partner", help="Build a single partner site by slug (matches partners/<slug>.json)")
    group.add_argument("--all", action="store_true", help="Build all partner sites found in partners/")
    args = parser.parse_args()

    DIST_DIR.mkdir(exist_ok=True)

    if args.all:
        slugs = [p.stem for p in PARTNERS_DIR.glob("*.json")]
        if not slugs:
            sys.exit("No partner configs found in partners/")
        for slug in slugs:
            build_partner(slug)
    else:
        build_partner(args.partner)


if __name__ == "__main__":
    main()
