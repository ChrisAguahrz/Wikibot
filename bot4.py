#!/usr/bin/env python3
"""Pywikibot script for Swahili Wikipedia maintenance on low-revision pages."""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

import pywikibot
from pywikibot.exceptions import NoPageError, IsRedirectPageError

SITE_CODE = "sw"
FAMILY = "wikipedia"
DRY_RUN = False
LIMIT = 50
EDIT_SUMMARY_PREFIX = "Bot: "
MAREJEO_TEMPLATE = "{{Marejeo}}"
NO_SOURCES_TEMPLATE = "{{Kigezo:Vyanzo}}"
NO_SOURCES_TEMPLATES = ["Kigezo:Vyanzo"]
TANBIHI_HEADING = "Tanbihi"
MAREJEO_HEADING = "Marejeo"
VYANZO_HEADING = "Vyanzo"
ADD_IMAGE_FROM_WIKIDATA = False
ADD_REFERENCE_FROM_WIKIDATA = False

HEADING_RE = re.compile(r"^(={2,6})\s*(.*?)\s*\1\s*$", re.MULTILINE)

def normalize_heading_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())

def section_titles(wikitext: str) -> List[str]:
    titles = []
    for m in HEADING_RE.finditer(wikitext):
        titles.append(normalize_heading_text(m.group(2)))
    return titles

def has_section(wikitext: str, title: str) -> bool:
    target = normalize_heading_text(title).casefold()
    return any(t.casefold() == target for t in section_titles(wikitext))

def count_refs(wikitext: str) -> int:
    return len(re.findall(r"<ref\b[^>]*?>", wikitext, flags=re.IGNORECASE))

def top_no_sources_present(wikitext: str) -> bool:
    first_chunk = wikitext[:500]
    for t in NO_SOURCES_TEMPLATES:
        if re.search(r"{{\s*" + re.escape(t) + r"\b", first_chunk, flags=re.IGNORECASE):
            return True
    return False

def rename_tanbihi_to_marejeo(wikitext: str) -> Tuple[str, bool]:
    changed = False
    def repl(match):
        nonlocal changed
        level = match.group(1)
        title = normalize_heading_text(match.group(2))
        if title.casefold() == TANBIHI_HEADING.casefold():
            changed = True
            return f"{level} {MAREJEO_HEADING} {level}"
        return match.group(0)
    new_text = HEADING_RE.sub(repl, wikitext)
    return new_text, changed

def add_marejeo_section_if_needed(wikitext: str) -> Tuple[str, bool]:
    if has_section(wikitext, MAREJEO_HEADING) or has_section(wikitext, VYANZO_HEADING) or has_section(wikitext, TANBIHI_HEADING):
        return wikitext, False
    if count_refs(wikitext) == 0:
        return wikitext, False
    addition = f"\n\n== {MAREJEO_HEADING} ==\n{MAREJEO_TEMPLATE}\n"
    return wikitext.rstrip() + addition, True

def add_no_sources_template_at_top(wikitext: str) -> Tuple[str, bool]:
    if has_section(wikitext, MAREJEO_HEADING) or has_section(wikitext, VYANZO_HEADING) or has_section(wikitext, TANBIHI_HEADING):
        return wikitext, False
    if top_no_sources_present(wikitext):
        return wikitext, False
    return f"{NO_SOURCES_TEMPLATE}\n\n{wikitext}", True

def process_page(page):
    try:
        text = page.get()
    except (NoPageError, IsRedirectPageError):
        return False, "skipped"
    original = text
    changed = False

    text, did_rename = rename_tanbihi_to_marejeo(text)
    changed = changed or did_rename

    text, did_add = add_marejeo_section_if_needed(text)
    changed = changed or did_add

    text, did_nosrc = add_no_sources_template_at_top(text)
    changed = changed or did_nosrc

    if not changed or text == original:
        return False, "no change"

    summary = EDIT_SUMMARY_PREFIX + "fixed references"
    page.text = text
    page.save(summary=summary, minor=False, botflag=True)
    return True, summary

def build_pages_from_report(site):
    from pywikibot.data import api
    req = api.Request(site=site, parameters={
        "action": "query",
        "list": "querypage",
        "qppage": "Fewestrevisions",
        "qplimit": LIMIT
    })
    data = req.submit()
    pages = []
    for result in data.get("query", {}).get("querypage", {}).get("results", []):
        title = result.get("title", "")
        if title:
            pages.append(pywikibot.Page(site, title))
    return pages

def main():
    username = os.getenv('WIKI_USERNAME', 'Gayle-Bot')
    password = os.getenv('WIKI_PASSWORD', 'CountryBot@it3ipj55bu65vg6vjq57i8dq4olhsrp2')
    
    site = pywikibot.Site(SITE_CODE, FAMILY)
    from pywikibot.login import ClientLoginManager
    login_manager = ClientLoginManager(site=site, user=username)
    login_manager.password = password
    login_manager.login()

    pages = build_pages_from_report(site)
    if LIMIT:
        pages = pages[:LIMIT]

    print(f"Loaded {len(pages)} pages")
    done = 0
    for page in pages:
        try:
            changed, status = process_page(page)
            print(f"{page.title()}: {status}")
            if changed:
                done += 1
        except Exception as e:
            print(f"{page.title()}: error: {e}")
    print(f"Finished. Changed {done} pages.")

if __name__ == "__main__":
    main()
