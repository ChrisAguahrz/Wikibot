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
LIMIT = None
EDIT_SUMMARY_PREFIX = "Bot: "
MAREJEO_TEMPLATE = "{{Marejeo}}"
NO_SOURCES_TEMPLATE = "{{Kigezo:Vyanzo}}"
NO_SOURCES_TEMPLATES = ["Kigezo:Vyanzo"]
TANBIHI_HEADING = "Tanbihi"
MAREJEO_HEADING = "Marejeo"
VYANZO_HEADING = "Vyanzo"
BIBLIOGRAFIA_HEADING = "Bibliografia"
VIUNGO_VYA_NJE_HEADING = "Viungo vya nje"
ADD_IMAGE_FROM_WIKIDATA = True
ADD_REFERENCE_FROM_WIKIDATA = True

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

def has_image_markup(wikitext: str) -> bool:
    return bool(re.search(r"\[\[(?:File|Image|Picha|Faili):", wikitext, flags=re.IGNORECASE))

def top_no_sources_present(wikitext: str) -> bool:
    first_chunk = wikitext[:500]
    for t in NO_SOURCES_TEMPLATES:
        if re.search(r"{{\s*" + re.escape(t) + r"\b", first_chunk, flags=re.IGNORECASE):
            return True
    return False

def remove_existing_no_sources_templates(wikitext: str) -> str:
    for t in NO_SOURCES_TEMPLATES:
        pattern = re.compile(r"{{\s*" + re.escape(t) + r"\b[^}]*}}\n?", re.IGNORECASE)
        wikitext = pattern.sub("", wikitext)
    return wikitext.lstrip()

def find_first_paragraph_end(wikitext: str) -> int:
    """Find the end of the first paragraph (after infobox, before first heading)."""
    # Remove infobox first
    text = str(wikitext)
    infobox_start = None
    for pat in [r"\{\{Jedwali la nchi", r"\{\{Infobox country"]:
        m = re.search(pat, text, flags=re.I)
        if m:
            infobox_start = m.start()
            break
    
    if infobox_start is not None:
        # Skip the infobox
        i = infobox_start
        depth = 0
        while i < len(text) - 1:
            pair = text[i:i+2]
            if pair == "{{": depth += 1; i += 2; continue
            if pair == "}}": depth -= 1; i += 2
            if depth == 0: break
            i += 1
        text = text[i:]
    
    # Find first heading
    first_heading = re.search(r"^==[^=]", text, re.MULTILINE)
    if first_heading:
        # Find the last non-empty line before the heading
        before_heading = text[:first_heading.start()].rstrip()
        return len(wikitext) - len(text) + len(before_heading)
    
    # No heading found, return end of text
    return len(wikitext)

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
    cleaned = remove_existing_no_sources_templates(wikitext)
    return f"{NO_SOURCES_TEMPLATE}\n\n{cleaned}", True

def get_wikidata_item(page):
    try:
        item = pywikibot.ItemPage.fromPage(page)
        item.get()
        return item
    except Exception:
        return None

def add_image_from_wikidata(wikitext: str, item) -> Tuple[str, bool]:
    if not item or has_image_markup(wikitext):
        return wikitext, False
    try:
        claims = item.claims.get("P18")
        if not claims:
            return wikitext, False
        for claim in claims:
            target = claim.getTarget()
            if isinstance(target, str) and target.strip():
                filename = target.strip()
                # Insert after first paragraph
                insert_pos = find_first_paragraph_end(wikitext)
                insertion = f"\n\n[[File:{filename}|thumb|upright=1.1]]\n"
                return wikitext[:insert_pos] + insertion + wikitext[insert_pos:], True
    except Exception:
        return wikitext, False
    return wikitext, False

def get_wikidata_references(item) -> List[str]:
    """Fetch references from Wikidata (P854 - reference URL, P248 - stated in)."""
    refs = []
    if not item:
        return refs
    try:
        # Try to get official website (P856)
        claims = item.claims.get("P856")
        if claims:
            for claim in claims:
                target = claim.getTarget()
                if isinstance(target, str) and target.strip():
                    refs.append(f"* [{target} Tovuti rasmi]")
    except Exception:
        pass
    return refs

def add_reference_from_wikidata(wikitext: str, item) -> Tuple[str, bool]:
    refs = get_wikidata_references(item)
    if not refs:
        return wikitext, False
    
    ref_text = "\n".join(refs)
    
    # Check if using <ref> tags -> add to Marejeo
    if count_refs(wikitext) > 0:
        if has_section(wikitext, MAREJEO_HEADING):
            # Add to existing Marejeo section
            return wikitext + "\n" + ref_text + "\n", True
        elif has_section(wikitext, TANBIHI_HEADING):
            return wikitext + "\n" + ref_text + "\n", True
        else:
            # No Marejeo section, add one
            addition = f"\n\n== {MAREJEO_HEADING} ==\n{ref_text}\n"
            return wikitext.rstrip() + addition, True
    
    # Check if bibliography-style -> add Bibliografia
    has_bib = bool(re.search(r"\* \[https?://", wikitext))
    if has_bib:
        if has_section(wikitext, BIBLIOGRAFIA_HEADING):
            return wikitext + "\n" + ref_text + "\n", True
        elif has_section(wikitext, VIUNGO_VYA_NJE_HEADING):
            return wikitext + "\n" + ref_text + "\n", True
        else:
            # Check if it has external links already
            addition = f"\n\n== {VIUNGO_VYA_NJE_HEADING} ==\n{ref_text}\n"
            return wikitext.rstrip() + addition, True
    
    return wikitext, False

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

    item = None
    if ADD_IMAGE_FROM_WIKIDATA or ADD_REFERENCE_FROM_WIKIDATA:
        item = get_wikidata_item(page)

    if ADD_IMAGE_FROM_WIKIDATA:
        text, did_img = add_image_from_wikidata(text, item)
        changed = changed or did_img

    if ADD_REFERENCE_FROM_WIKIDATA:
        text, did_ref = add_reference_from_wikidata(text, item)
        changed = changed or did_ref

    if not changed or text == original:
        return False, "no change"

    summary = EDIT_SUMMARY_PREFIX + "fixed references and maintenance"
    page.text = text
    page.save(summary=summary, minor=False, botflag=True)
    return True, summary

def build_pages_from_report(site):
    from pywikibot.data import api
    req = api.Request(site=site, parameters={
        "action": "query",
        "list": "querypage",
        "qppage": "Fewestrevisions",
        "qplimit": "max"
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
