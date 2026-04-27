#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
import re
import time
import sys

import pywikibot
from pywikibot.data import api

# Configuration
SITE_CODE = "sw"
FAMILY = "wikipedia"
CATEGORY_TITLE = "Jamii:Nchi"
PROJECT_PAGE = "Wikipedia:Mradi wa Nchi"
MAIN_SECTION = "Takwimu"
EDITORS_SUBSECTION = "Wahariri"
DAYS = 90
VIEWS_DAYS = 30
TOP_N = 10
TOP_VIEWS = 5
MAX_WORKERS = 3
VIEWS_BATCH_SIZE = 20
THROTTLE_DELAY = 1


def fetch_contributors(page, newest, oldest):
    try:
        return page.contributors(starttime=newest, endtime=oldest)
    except Exception as e:
        return f"ERROR:{page.title()}:{e}"


def fetch_pageviews_batch(pages_batch, site):
    current_views = {}
    previous_views = {}
    if not pages_batch:
        return current_views, previous_views
    try:
        titles = '|'.join([page.title() for page in pages_batch])
        req = api.Request(site=site, parameters={
            'action': 'query', 'format': 'json', 'titles': titles,
            'prop': 'pageviews', 'pvipdays': VIEWS_DAYS * 2,
        })
        data = req.submit()
        for page_id, page_data in data.get('query', {}).get('pages', {}).items():
            title = page_data.get('title', '')
            if not title:
                continue
            views_dict = page_data.get('pageviews', {})
            if views_dict:
                sorted_views = sorted(views_dict.items())
                if len(sorted_views) > 0:
                    mid_point = len(sorted_views) // 2
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
        for page in pages_batch:
            if page.title() not in current_views:
                current_views[page.title()] = 0
                previous_views[page.title()] = 0
    return current_views, previous_views


def get_change_indicator(current, previous):
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
    return f"[[User:{user}|{user}]]"


def build_general_stats_section(total_edits, total_articles, page_views_data):
    current_views, previous_views = page_views_data
    total_current_views = sum(current_views.values())
    total_previous_views = sum(previous_views.values())
    edits_per_article = total_edits / total_articles if total_articles > 0 else 0
    view_change = get_change_indicator(total_current_views, total_previous_views)
    top_pages = sorted(current_views.items(), key=lambda x: x[1], reverse=True)[:TOP_VIEWS]
    
    lines = [
        f"=={MAIN_SECTION}==", "",
        "===Takwimu za Jumla===",
        '{| class="wikitable"',
        "! Vipimo !! Thamani !! Mabadiliko", "|-",
        f"| Jumla ya Makala || {total_articles} || —", "|-",
        f"| Jumla ya Hariri (siku {DAYS}) || {total_edits} || —", "|-",
        f"| Jumla ya Maoni (siku {VIEWS_DAYS}) || {total_current_views} || {view_change}", "|-",
        f"| Wastani wa Hariri kwa Makala || {edits_per_article:.1f} || —", "|-",
    ]
    if total_articles > 0:
        avg_views = total_current_views / total_articles
        lines.append(f"| Wastani wa Maoni kwa Makala || {avg_views:.1f} || —")
    else:
        lines.append("| Wastani wa Maoni kwa Makala || 0 || —")
    lines.extend(["|}", "",
        f"===Makala 5 Zilizotazamwa Zaidi (siku {VIEWS_DAYS})===",
        '{| class="wikitable sortable"',
        "! Nafasi !! Makala !! Maoni !! Mabadiliko", "|-"])
    for i, (title, views) in enumerate(top_pages, 1):
        prev = previous_views.get(title, 0)
        change = get_change_indicator(views, prev)
        lines.append(f"| {i} || [[{title}]] || {views} || {change}")
        lines.append("|-")
    lines.append("|}")
    lines.append("")
    return "\n".join(lines)


def build_editors_subsection(overall, total_edits):
    lines = [
        f"===={EDITORS_SUBSECTION}====",
        f"Wahariri kuu wa Mradi wa Nchi wa Wikipedia (siku {DAYS})",
        '{| class="wikitable sortable"',
        "! Namba !! Jina !! Hariri !! Asilimia", "|-"]
    for i, (user, edits) in enumerate(overall.most_common(TOP_N), start=1):
        share = (edits / total_edits * 100) if total_edits > 0 else 0
        user_link = get_user_link(user)
        lines.append(f"| {i} || {user_link} || {edits} || {share:.1f}%")
        lines.append("|-")
    lines.append("|}")
    return "\n".join(lines)


def update_project_page(site, content):
    page = pywikibot.Page(site, PROJECT_PAGE)
    try:
        text = page.get()
    except pywikibot.exceptions.NoPage:
        page.text = content
        page.save("Ongeza sehemu ya Takwimu", minor=False)
        return
    except pywikibot.exceptions.IsRedirectPage:
        page = page.getRedirectTarget()
        text = page.get()
    
    section_pattern_text = r'^(=+)\s*' + re.escape(MAIN_SECTION) + r'\s*\1\s*$'
    section_pattern = re.compile(section_pattern_text, re.MULTILINE)
    match = section_pattern.search(text)
    
    if match:
        section_level = len(match.group(1))
        next_section_regex = r'^(={1,' + str(section_level) + r'})\s*[^=].*\1\s*$'
        next_section_pattern = re.compile(next_section_regex, re.MULTILINE)
        next_match = next_section_pattern.search(text, match.end())
        if next_match:
            before_section = text[:match.end()]
            after_section = text[next_match.start():]
            content_body = content.split(f"=={MAIN_SECTION}==", 1)[1] if f"=={MAIN_SECTION}==" in content else content
            new_text = before_section + content_body + after_section
        else:
            before_section = text[:match.end()]
            content_body = content.split(f"=={MAIN_SECTION}==", 1)[1] if f"=={MAIN_SECTION}==" in content else content
            new_text = before_section + content_body
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        new_text = text + "\n" + content
    
    if new_text != text:
        page.text = new_text
        page.save("Sasisha Takwimu za mradi", minor=False)


def main():
    # Force login with env vars
    username = os.getenv('WIKI_USERNAME', 'Gayle157')
    password = os.getenv('WIKI_PASSWORD', 'CiteBot@fp5d4lfqvjrgi8d4e84s8burfovakba9')
    
    site = pywikibot.Site(SITE_CODE, FAMILY)
    
    # Login manually
    from pywikibot.login import ClientLoginManager
    login_manager = ClientLoginManager(site=site, user=username)
    login_manager.password = password
    login_manager.login()
    
    category = pywikibot.Category(site, CATEGORY_TITLE)
    newest = site.server_time()
    oldest = newest - timedelta(days=DAYS)
    pages = list(category.articles(recurse=False, namespaces=0))
    total_pages = len(pages)
    
    print(f"Found {total_pages} articles")
    
    overall = Counter()
    pages_processed = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_page = {executor.submit(fetch_contributors, page, newest, oldest): page for page in pages}
        for future in as_completed(future_to_page):
            pages_processed += 1
            try:
                result = future.result()
                if isinstance(result, str) and result.startswith("ERROR:"):
                    continue
                else:
                    overall.update(result)
            except:
                pass
            percent = (pages_processed / total_pages) * 100
            bar_length = 30
            filled = int(bar_length * pages_processed / total_pages)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\r[{bar}] {percent:.1f}% ({pages_processed}/{total_pages}) - {len(overall)} editors", end='', flush=True)
    
    print()
    total_edits = sum(overall.values())
    
    if not overall:
        return
    
    print(f"Total edits: {total_edits}")
    for i, (user, total) in enumerate(overall.most_common(10), start=1):
        share = (total / total_edits * 100) if total_edits > 0 else 0
        print(f"{i}. {user} - {total} ({share:.1f}%)")
    
    print("Fetching page views...")
    all_current_views = {}
    all_previous_views = {}
    for i in range(0, len(pages), VIEWS_BATCH_SIZE):
        batch = pages[i:i + VIEWS_BATCH_SIZE]
        if i > 0:
            time.sleep(THROTTLE_DELAY)
        current_batch, previous_batch = fetch_pageviews_batch(batch, site)
        all_current_views.update(current_batch)
        all_previous_views.update(previous_batch)
    
    page_views_data = (all_current_views, all_previous_views)
    print("Updating project page...")
    general_stats = build_general_stats_section(total_edits, total_pages, page_views_data)
    editors_section = build_editors_subsection(overall, total_edits)
    full_content = general_stats + "\n" + editors_section + "\n"
    update_project_page(site, full_content)
    print("Done!")


if __name__ == "__main__":
    main()
