#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
import re
import time

import pywikibot


# Configuration from environment variables
SITE_CODE = os.getenv("SITE_CODE", "sw")
FAMILY = os.getenv("FAMILY", "wikipedia")
CATEGORY_TITLE = os.getenv("CATEGORY_TITLE", "Jamii:Nchi")
PROJECT_PAGE = os.getenv("PROJECT_PAGE", "Wikipedia:Mradi wa Nchi")
MAIN_SECTION = "Takwimu"
EDITORS_SUBSECTION = "Wahariri"
DAYS = int(os.getenv("DAYS", "90"))
VIEWS_DAYS = int(os.getenv("VIEWS_DAYS", "30"))
TOP_N = int(os.getenv("TOP_N", "10"))
TOP_VIEWS = int(os.getenv("TOP_VIEWS", "5"))
MAX_WORKERS = 3
VIEWS_BATCH_SIZE = 20
THROTTLE_DELAY = 1


def fetch_contributors(page, newest, oldest):
    """Fetch contributors for a single page."""
    try:
        return page.contributors(starttime=newest, endtime=oldest)
    except Exception as e:
        return f"ERROR:{page.title()}:{e}"


def fetch_pageviews_batch(pages_batch, site):
    """Fetch page views for a batch of pages using one API call."""
    current_views = {}
    previous_views = {}
    
    if not pages_batch:
        return current_views, previous_views
    
    try:
        from pywikibot.data import api
        
        # Join titles with pipe for batch request
        titles = '|'.join([page.title() for page in pages_batch])
        
        # Request 60 days of data to split into two periods
        req = api.Request(site=site, parameters={
            'action': 'query',
            'format': 'json',
            'titles': titles,
            'prop': 'pageviews',
            'pvipdays': VIEWS_DAYS * 2,
        })
        data = req.submit()
        
        for page_id, page_data in data.get('query', {}).get('pages', {}).items():
            title = page_data.get('title', '')
            if not title:
                continue
                
            views_dict = page_data.get('pageviews', {})
            if views_dict:
                # Sort by date
                sorted_views = sorted(views_dict.items())
                
                if len(sorted_views) > 0:
                    # Split into two periods
                    mid_point = len(sorted_views) // 2
                    
                    # Sum views for each period, handling None values
                    recent_views = sum(v for d, v in sorted_views[mid_point:] if v is not None)
                    older_views = sum(v for d, v in sorted_views[:mid_point] if v is not None)
                    
                    current_views[title] = recent_views
                    previous_views[title] = older_views
                else:
                    current_views[title] = 0
                    previous_views[title] = 0
            else:
                current_views[title] = 0
                previous_views[title] = 0
                
    except Exception as e:
        pywikibot.warning(f"Batch pageview error: {e}")
        for page in pages_batch:
            if page.title() not in current_views:
                current_views[page.title()] = 0
                previous_views[page.title()] = 0
    
    return current_views, previous_views


def get_change_indicator(current, previous):
    """Get change indicator arrow and percentage."""
    if previous == 0:
        if current > 0:
            return "↑ Mpya"
        return "— 0%"
    
    change = ((current - previous) / previous) * 100
    
    if change > 0:
        return f"↑ +{change:.1f}%"
    elif change < 0:
        return f"↓ {change:.1f}%"
    else:
        return "— 0%"


def get_user_link(user):
    """Create a wikilink to user page."""
    return f"[[User:{user}|{user}]]"


def build_general_stats_section(total_edits, total_articles, page_views_data):
    """Build the general statistics table."""
    current_views, previous_views = page_views_data
    
    total_current_views = sum(current_views.values())
    total_previous_views = sum(previous_views.values())
    
    edits_per_article = total_edits / total_articles if total_articles > 0 else 0
    view_change = get_change_indicator(total_current_views, total_previous_views)
    
    # Sort pages by current views for top 5
    top_pages = sorted(current_views.items(), key=lambda x: x[1], reverse=True)[:TOP_VIEWS]
    
    lines = [
        f"=={MAIN_SECTION}==",
        "",
        "===Takwimu za Jumla===",
        '{| class="wikitable"',
        "! Vipimo !! Thamani !! Mabadiliko",
        "|-",
        f"| Jumla ya Makala || {total_articles} || —",
        "|-",
        f"| Jumla ya Hariri (siku {DAYS}) || {total_edits} || —",
        "|-",
        f"| Jumla ya Maoni (siku {VIEWS_DAYS}) || {total_current_views} || {view_change}",
        "|-",
        f"| Wastani wa Hariri kwa Makala || {edits_per_article:.1f} || —",
        "|-",
    ]
    
    if total_articles > 0:
        avg_views = total_current_views / total_articles
        lines.append(f"| Wastani wa Maoni kwa Makala || {avg_views:.1f} || —")
    else:
        lines.append("| Wastani wa Maoni kwa Makala || 0 || —")
    
    lines.extend([
        "|}",
        "",
        f"===Makala 5 Zilizotazamwa Zaidi (siku {VIEWS_DAYS})===",
        '{| class="wikitable sortable"',
        "! Nafasi !! Makala !! Maoni !! Mabadiliko",
        "|-"
    ])
    
    for i, (title, views) in enumerate(top_pages, 1):
        prev = previous_views.get(title, 0)
        change = get_change_indicator(views, prev)
        article_link = f"[[{title}]]"
        lines.append(f"| {i} || {article_link} || {views} || {change}")
        lines.append("|-")
    
    lines.append("|}")
    lines.append("")
    
    return "\n".join(lines)


def build_editors_subsection(overall, total_edits):
    """Build the editors wikitable as a subsection."""
    lines = [
        f"===={EDITORS_SUBSECTION}====",
        f"Wahariri kuu wa Mradi wa Nchi wa Wikipedia (siku {DAYS})",
        '{| class="wikitable sortable"',
        "! Namba !! Jina !! Hariri !! Asilimia",
        "|-"
    ]
    
    for i, (user, edits) in enumerate(overall.most_common(TOP_N), start=1):
        share = (edits / total_edits * 100) if total_edits > 0 else 0
        user_link = get_user_link(user)
        lines.append(f"| {i} || {user_link} || {edits} || {share:.1f}%")
        lines.append("|-")
    
    lines.append("|}")
    return "\n".join(lines)


def update_project_page(site, content):
    """Update or create the Takwimu section on the project page."""
    page = pywikibot.Page(site, PROJECT_PAGE)
    
    try:
        text = page.get()
    except pywikibot.exceptions.NoPage:
        pywikibot.output(f"Page {PROJECT_PAGE} does not exist. Creating...")
        page.text = content
        page.save("Ongeza sehemu ya Takwimu", minor=False)
        pywikibot.output("✓ Created new page with Takwimu section")
        return
    except pywikibot.exceptions.IsRedirectPage:
        page = page.getRedirectTarget()
        text = page.get()
        pywikibot.output(f"Following redirect to {page.title()}")
    
    # Find the section using regex
    section_pattern_text = r'^(=+)\s*' + re.escape(MAIN_SECTION) + r'\s*\1\s*$'
    section_pattern = re.compile(section_pattern_text, re.MULTILINE)
    
    match = section_pattern.search(text)
    
    if match:
        pywikibot.output(f"Found existing '{MAIN_SECTION}' section. Replacing content...")
        
        section_level = len(match.group(1))
        
        # Find next section of same or higher level
        next_section_regex = r'^(={1,' + str(section_level) + r'})\s*[^=].*\1\s*$'
        next_section_pattern = re.compile(next_section_regex, re.MULTILINE)
        
        next_match = next_section_pattern.search(text, match.end())
        
        if next_match:
            before_section = text[:match.end()]
            after_section = text[next_match.start():]
            if f"=={MAIN_SECTION}==" in content:
                content_body = content.split(f"=={MAIN_SECTION}==", 1)[1]
            else:
                content_body = content
            new_text = before_section + content_body + after_section
        else:
            before_section = text[:match.end()]
            if f"=={MAIN_SECTION}==" in content:
                content_body = content.split(f"=={MAIN_SECTION}==", 1)[1]
            else:
                content_body = content
            new_text = before_section + content_body
    else:
        pywikibot.output(f"No '{MAIN_SECTION}' section found. Appending to page...")
        if text and not text.endswith("\n"):
            text += "\n"
        new_text = text + "\n" + content
    
    if new_text != text:
        page.text = new_text
        page.save("Sasisha Takwimu za mradi", minor=False)
        pywikibot.output("✓ Updated Takwimu section")
    else:
        pywikibot.output("✓ No changes needed - section already up to date")


def main() -> None:
    site = pywikibot.Site(SITE_CODE, FAMILY)
    category = pywikibot.Category(site, CATEGORY_TITLE)

    newest = site.server_time()
    oldest = newest - timedelta(days=DAYS)

    # Collect all pages first
    pages = list(category.articles(recurse=False, namespaces=0))
    total_pages = len(pages)
    
    pywikibot.output(f"Found {total_pages} articles in {CATEGORY_TITLE}")
    pywikibot.output(f"Fetching edits from last {DAYS} days...\n")

    overall = Counter()
    pages_processed = 0
    pages_with_errors = 0

    # Parallel fetching with progress
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_page = {
            executor.submit(fetch_contributors, page, newest, oldest): page
            for page in pages
        }

        for future in as_completed(future_to_page):
            page = future_to_page[future]
            pages_processed += 1
            
            try:
                result = future.result()
                
                if isinstance(result, str) and result.startswith("ERROR:"):
                    _, title, error = result.split(":", 2)
                    pages_with_errors += 1
                    pywikibot.warning(f"Skipped {title}: {error}")
                else:
                    overall.update(result)
            except Exception as e:
                pages_with_errors += 1
                pywikibot.warning(f"Skipped {page.title()}: {e}")

            # Progress bar
            percent = (pages_processed / total_pages) * 100
            bar_length = 30
            filled = int(bar_length * pages_processed / total_pages)
            bar = '█' * filled + '░' * (bar_length - filled)
            
            print(f"\r[{bar}] {percent:5.1f}% ({pages_processed}/{total_pages}) "
                  f"- {len(overall)} unique editors found", end='', flush=True)

    print("\n")
    
    total_edits = sum(overall.values())
    
    pywikibot.output(f"Category: {category.title()}")
    pywikibot.output(f"Articles scanned: {total_pages}")
    pywikibot.output(f"Total edits in period: {total_edits}")
    pywikibot.output(f"Time window: last {DAYS} days")
    pywikibot.output("")

    if not overall:
        pywikibot.output("No edits found in the selected period.")
        return

    # Display top editors
    pywikibot.output(f"Top {min(TOP_N, len(overall))} editors overall:")
    for i, (user, total) in enumerate(overall.most_common(TOP_N), start=1):
        share = (total / total_edits * 100) if total_edits > 0 else 0
        pywikibot.output(f"{i:2}. {user} - {total} ({share:.1f}%)")

    if pages_with_errors:
        pywikibot.output(f"\nPages skipped because of errors: {pages_with_errors}")

    # Fetch page views in batches to avoid overwhelming the server
    pywikibot.output(f"\nFetching page views (last {VIEWS_DAYS} days)...")
    pywikibot.output(f"Processing in batches of {VIEWS_BATCH_SIZE}...")
    
    all_current_views = {}
    all_previous_views = {}
    
    # Split pages into batches
    for i in range(0, len(pages), VIEWS_BATCH_SIZE):
        batch = pages[i:i + VIEWS_BATCH_SIZE]
        batch_num = (i // VIEWS_BATCH_SIZE) + 1
        total_batches = (len(pages) + VIEWS_BATCH_SIZE - 1) // VIEWS_BATCH_SIZE
        
        pywikibot.output(f"  Batch {batch_num}/{total_batches} ({len(batch)} pages)...")
        
        # Add throttle delay between batches
        if i > 0:
            time.sleep(THROTTLE_DELAY)
        
        current_batch, previous_batch = fetch_pageviews_batch(batch, site)
        all_current_views.update(current_batch)
        all_previous_views.update(previous_batch)
    
    page_views_data = (all_current_views, all_previous_views)
    
    # Build all sections
    pywikibot.output(f"\nUpdating {PROJECT_PAGE}...")
    
    # Build complete content with main section and subsections
    general_stats = build_general_stats_section(total_edits, total_pages, page_views_data)
    editors_section = build_editors_subsection(overall, total_edits)
    
    full_content = general_stats + "\n" + editors_section + "\n"
    
    update_project_page(site, full_content)


if __name__ == "__main__":
    main()
