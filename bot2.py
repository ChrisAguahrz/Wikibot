import os
import pywikibot
from pywikibot import pagegenerators
import time
import re
import math
from datetime import date

# Force login with env vars
username = os.getenv('WIKI_USERNAME', 'Gayle-Bot')
password = os.getenv('WIKI_PASSWORD', 'CountryBot@it3ipj55bu65vg6vjq57i8dq4olhsrp2')

site = pywikibot.Site("sw", "wikipedia")

from pywikibot.login import ClientLoginManager
login_manager = ClientLoginManager(site=site, user=username)
login_manager.password = password
login_manager.login()

country_categories = [
    "Jamii:Nchi",
    "Jamii:Nchi za Afrika",
    "Jamii:Nchi za Asia",
    "Jamii:Nchi za Ulaya",
    "Jamii:Nchi za Amerika ya Kaskazini",
    "Jamii:Nchi za Amerika ya Kusini",
    "Jamii:Nchi za Australia na Pasifiki"
]

processed = set()
table_page = pywikibot.Page(site, "Wikipedia:Mradi wa Nchi")

CITATION_TEMPLATES = [
    "{{Rejea tovuti", "{{Rejea jarida", "{{Rejea kitabu", "{{Rejea habari",
    "{{Cite web", "{{Cite journal", "{{Cite book", "{{Cite news",
    "{{Rejea ensaiklopedia", "{{Cite encyclopedia"
]

PRESENCE_SECTION_TITLES = {
    "jiografia", "demografia", "historia", "uchumi", "elimu", "sanaa",
    "utamaduni", "utamaduni na sanaa", "utawala", "siasa",
    "serikali na utawala", "serikali", "viungo vya nje", "bibliografia"
}

IGNORED_BODY_SECTIONS = {
    "marejeo", "tazama pia", "viungo vya nje", "bibliografia", "marejeo mengine",
}

def safe_bytes_len(value):
    return len(str(value).encode("utf-8"))

def bounded_log_scale(value, min_val, max_val, min_score, max_score):
    value = int(value)
    if value < min_val:
        return 0
    if value >= max_val:
        return max_score
    return min_score + (math.log(value / min_val) / math.log(max_val / min_val)) * (max_score - min_score)

def linear_score(value, min_val, max_val, min_score, max_score):
    if value < min_val:
        return 0
    if value >= max_val:
        return max_score
    return min_score + ((value - min_val) / (max_val - min_val)) * (max_score - min_score)

def count_unique_refs(text):
    text = str(text)
    refs = re.findall(r"<ref\b[^>/]*>.*?</ref>", text, flags=re.I | re.S)
    refs += re.findall(r"<ref\b[^>/]*/\s*>", text, flags=re.I | re.S)
    normalized = set(re.sub(r"\s+", " ", r.strip().lower()) for r in refs)
    return len(normalized)

def count_citations_in_text(text):
    text = str(text)
    count = count_unique_refs(text)
    count += sum(text.count(t) for t in CITATION_TEMPLATES)
    return count

def find_infobox_start(text):
    text = str(text)
    matches = []
    for pat in [r"\{\{Jedwali la nchi", r"\{\{Infobox country"]:
        m = re.search(pat, text, flags=re.I)
        if m:
            matches.append(m.start())
    return min(matches) if matches else None

def extract_template_block(text, start_index):
    text = str(text)
    i = start_index
    depth = 0
    while i < len(text) - 1:
        pair = text[i:i+2]
        if pair == "{{":
            depth += 1
            i += 2
            continue
        if pair == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return text[start_index:i], i
            continue
        i += 1
    return text[start_index:], len(text)

def get_article_parts(text):
    text = str(text)
    infobox_start = find_infobox_start(text)
    if infobox_start is not None:
        _, infobox_end = extract_template_block(text, infobox_start)
        after_infobox = text[infobox_end:]
    else:
        after_infobox = text
    first_section_match = re.search(r"(?m)^==[^=].*?==\s*$", after_infobox)
    if first_section_match:
        intro_body = after_infobox[:first_section_match.start()]
        body_sections_text = after_infobox[first_section_match.start():]
    else:
        intro_body = after_infobox
        body_sections_text = ""
    return intro_body, body_sections_text

def parse_main_sections(section_text, ignore_titles=None):
    section_text = str(section_text)
    ignore_titles = ignore_titles or set()
    pattern = re.compile(r"(?ms)^==([^=].*?)==\s*\n(.*?)(?=^==[^=].*?==\s*$|\Z)")
    sections = []
    for m in pattern.finditer(section_text):
        title = m.group(1).strip()
        content = m.group(2).strip()
        if title.lower() in ignore_titles:
            continue
        sections.append((title, content))
    return sections

def display_country(country):
    if country == "Jumuiya ya Afrika Mashariki":
        return "[[Jumuiya ya Afrika Mashariki|EAC]]"
    return f"[[{country}]]"

def calculate_intro(text):
    intro_body, _ = get_article_parts(text)
    paragraphs = [p for p in intro_body.split("\n\n") if p.strip()]
    lead_raw = 0
    next_raw = 0
    if paragraphs:
        lead = paragraphs[0]
        lead_size = safe_bytes_len(lead)
        lead_size_score = bounded_log_scale(lead_size, 50, 600, 0.5, 5)
        lead_citations = count_citations_in_text(lead)
        lead_citation_score = linear_score(lead_citations, 1, 2, 0.5, 1.0)
        lead_raw = min(lead_size_score + lead_citation_score, 6)
    continuation = paragraphs[1:]
    continuation.sort(key=lambda x: safe_bytes_len(x), reverse=True)
    top2 = continuation[:2]
    size_score = 0
    citation_score = 0
    for para in top2:
        para_size = safe_bytes_len(para)
        size_score += bounded_log_scale(para_size, 100, 700, 0.25, 3)
        para_citations = count_citations_in_text(para)
        citation_score += linear_score(para_citations, 1, 4, 0.5, 2.0)
    paragraph_count_score = min(len(continuation) * 0.5, 2.0)
    next_raw = size_score + citation_score + paragraph_count_score
    next_final = min((next_raw / 12) * 10, 10) if next_raw else 0
    intro_final = round(min(lead_raw + next_final, 16), 2)
    return intro_final, 16

def calculate_infobox(text):
    text = str(text)
    start = find_infobox_start(text)
    if start is None:
        return 0, 5
    infobox_block, _ = extract_template_block(text, start)
    infobox_citations = count_citations_in_text(infobox_block)
    citation_score = linear_score(infobox_citations, 1, 5, 0.25, 2.5)
    raw = 2.5 + citation_score
    return round(min(raw, 5), 2), 5

def calculate_body_score(text):
    _, body_sections_text = get_article_parts(text)
    sections = parse_main_sections(body_sections_text, IGNORED_BODY_SECTIONS)
    sections.sort(key=lambda x: safe_bytes_len(x[1]), reverse=True)
    top4 = sections[:4]
    top4_score = 0
    for _, content in top4:
        sec_size = safe_bytes_len(content)
        top4_score += bounded_log_scale(sec_size, 300, 2000, 0.5, 4)
    top4_score = min(top4_score, 16)
    extra_score = 0
    for _, content in sections[4:]:
        if safe_bytes_len(content) > 800:
            extra_score += 1.25
    extra_score = min(extra_score, 4)
    subsection_count = 0
    for _, content in sections:
        subsections = re.findall(r"(^===.*?===|^====.*?====)\s*\n(.*?)(?=^===|^====|^==|$)", content, flags=re.M | re.S)
        for _, subcontent in subsections:
            if safe_bytes_len(subcontent) > 250:
                subsection_count += 1
    subsection_score = min(subsection_count, 4)
    body_citation_count = count_citations_in_text(body_sections_text)
    citation_score = linear_score(body_citation_count, 1, 15, 0.5, 10)
    image_score = 0
    for _, content in sections:
        image_count = (content.count("[[File:") + content.count("[[Picha:") + content.count("[[Faili:"))
        if image_count >= 2:
            image_score += 1.5
        elif image_count == 1:
            image_score += 0.75
    image_score = min(image_score, 6)
    raw_total = top4_score + extra_score + subsection_score + citation_score + image_score
    final_score = round(min(raw_total, 40), 2)
    return final_score, 40

def calculate_presence_sections(text):
    _, body_sections_text = get_article_parts(text)
    sections = parse_main_sections(body_sections_text, set())
    present = set()
    for title, _ in sections:
        normalized = title.strip().lower()
        if normalized in PRESENCE_SECTION_TITLES:
            present.add(normalized)
    score = min(len(present) * 0.25, 3)
    return round(score, 2), 3

def calculate_orderly_bonus(text):
    _, body_sections_text = get_article_parts(text)
    sections = parse_main_sections(body_sections_text, IGNORED_BODY_SECTIONS)
    sections.sort(key=lambda x: safe_bytes_len(x[1]), reverse=True)
    top4 = sections[:4]
    score = 0
    for _, content in top4:
        sec_size = safe_bytes_len(content)
        citations_in_sec = count_citations_in_text(content)
        images_in_sec = (content.count("[[File:") + content.count("[[Picha:") + content.count("[[Faili:"))
        if sec_size >= 1000 and citations_in_sec >= 2 and images_in_sec >= 2:
            score += 1.5
    return round(min(score, 3), 2), 3

def calculate_presence_metric(text):
    text = str(text).lower()
    score = 0
    if "wikitable sortable" in text or "wikitable" in text:
        score += 0.45
    if "{{chati ya duara" in text:
        score += 0.45
    if "{{pie chart" in text:
        score += 0.45
    return round(min(score, 1.35), 2), 1.35

def calculate_reference_diversity(text):
    text = str(text)
    types = 0
    if "{{Rejea kitabu" in text or "{{Cite book" in text:
        types += 1
    if "{{Rejea jarida" in text or "{{Cite journal" in text:
        types += 1
    if "{{Rejea tovuti" in text or "{{Cite web" in text:
        types += 1
    if "{{Rejea habari" in text or "{{Cite news" in text:
        types += 1
    if "{{Rejea ensaiklopedia" in text or "{{Cite encyclopedia" in text:
        types += 1
    score = min(types * 0.5, 2.5)
    return round(score, 2), 2.5

def calculate_article_size(text):
    size = safe_bytes_len(text)
    score = bounded_log_scale(size, 2000, 50000, 0.3, 5)
    return round(score, 2), 5

def calculate_total(text):
    intro, intro_max = calculate_intro(text)
    info, info_max = calculate_infobox(text)
    body, body_max = calculate_body_score(text)
    presence, presence_max = calculate_presence_sections(text)
    orderly, orderly_max = calculate_orderly_bonus(text)
    presence_metric, presence_metric_max = calculate_presence_metric(text)
    ref, ref_max = calculate_reference_diversity(text)
    size_score, size_max = calculate_article_size(text)
    total = intro + info + body + presence + orderly + presence_metric + ref + size_score
    max_total = intro_max + info_max + body_max + presence_max + orderly_max + presence_metric_max + ref_max + size_max
    caqi10 = round((total / max_total) * 10, 2) if max_total else 0
    return caqi10

def assign_category(score):
    if score > 8.0:
        return ("Makala Bora", "green")
    elif score >= 7.0:
        return ("Makala Nzuri", "yellow")
    elif score >= 3.5:
        return ("Makala Msingi", "orange")
    elif score >= 2.0:
        return ("Makala ya Chini", "lightblue")
    else:
        return ("Mbegu", "red")

def build_pie_chart(results):
    counts = {"Makala Bora": 0, "Makala Nzuri": 0, "Makala Msingi": 0, "Makala ya Chini": 0, "Mbegu": 0}
    for _, s in results:
        cat, _ = assign_category(s)
        counts[cat] += 1
    return "\n".join([
        "{{Chati ya duara",
        f"| caption= CAQI ({date.today().isoformat()})",
        f"| label1 = Makala Bora",
        f"| value1 = {counts['Makala Bora']}",
        f"| color1= green",
        f"| label2 = Makala Nzuri",
        f"| value2 = {counts['Makala Nzuri']}",
        f"| color2= yellow",
        f"| label3 = Makala Msingi",
        f"| value3 = {counts['Makala Msingi']}",
        f"| color3= orange",
        f"| label4 = Makala ya Chini",
        f"| value4 = {counts['Makala ya Chini']}",
        f"| color4= lightblue",
        f"| label5 = Mbegu",
        f"| value5 = {counts['Mbegu']}",
        f"| color5= red",
        "}}"
    ])

def update_table(results):
    try:
        text = table_page.text
    except:
        text = ""
    results.sort(key=lambda x: x[1], reverse=True)
    date_label = date.today().isoformat()
    table = f'{{| class="wikitable sortable"\n! Nchi\n! CAQI ({date_label})<br />\n'
    current_cat = ""
    for country, score10 in results:
        cat, color = assign_category(score10)
        if cat != current_cat:
            table += f'|-\n| colspan="2" style="background-color:{color}" | {cat}\n'
            current_cat = cat
        table += f'|-\n| {display_country(country)}\n| {score10:.2f}\n'
    table += "|}"
    pie_chart = build_pie_chart(results)
    match = re.search(r"(?m)^==\s*Makala\s*==\s*$", text)
    if match:
        start = match.end()
        next_heading = re.search(r"(?m)^==[^=].*?==\s*$", text[start:])
        if next_heading:
            section_body = text[start:start + next_heading.start()]
            tail = text[start + next_heading.start():]
        else:
            section_body = text[start:]
            tail = ""
        section_body = re.sub(r"\{\{Chati ya duara.*?\}\}", "", section_body, flags=re.S)
        section_body = re.sub(r"\{\| class=\"wikitable sortable\".*?\|\}", "", section_body, flags=re.S)
        section_body = section_body.rstrip()
        new_parts = []
        if section_body.strip():
            new_parts.append(section_body.strip())
        new_parts.append(pie_chart)
        new_parts.append(table)
        new_body = "\n\n".join(new_parts)
        if tail:
            text = text[:start] + "\n\n" + new_body + "\n\n" + tail.lstrip("\n")
        else:
            text = text[:start] + "\n\n" + new_body + "\n"
    else:
        text += "\n\n==Makala==\n\n" + pie_chart + "\n\n" + table + "\n"
    table_page.text = text
    table_page.save(summary="#2.0 CAQI Bot updated with new scoring rules")
    print("Table updated!")

# Main
countries = []
for cat_name in country_categories:
    cat = pywikibot.Category(site, cat_name)
    gen = pagegenerators.CategorizedPageGenerator(cat)
    for page in gen:
        if page.title() not in processed:
            processed.add(page.title())
            countries.append(page)

countries.append(pywikibot.Page(site, "Jumuiya ya Afrika Mashariki"))

results = []
for page in countries:
    try:
        text = page.text
        total_data = calculate_total(text)
        results.append((page.title(), total_data))
        print(f"{page.title()} -> {total_data}")
        time.sleep(0.5)
    except Exception as e:
        print(f"Skipped {page.title()} -> {e}")

update_table(results)
