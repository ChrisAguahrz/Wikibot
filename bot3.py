import pywikibot
from pywikibot import pagegenerators

site = pywikibot.Site("sw", "wikipedia")

start = "D"

gen = pagegenerators.AllpagesPageGenerator(start=start, namespace=0, site=site)

replacements = {
    "{{Cite web": "{{Rejea tovuti",
    "{{Cite journal": "{{Rejea jarida",
    "{{Cite book": "{{Rejea kitabu",
    "{{Cite news": "{{Rejea habari"
}

for page in gen:
    try:
        text = page.text
        newtext = text
        count = 0

        for old, new in replacements.items():
            if old in newtext:
                c = newtext.count(old)
                newtext = newtext.replace(old, new)
                count += c

        if count > 0:
            page.text = newtext
            summary = f"#2.0 Boti Replaced Cite web->Rejea tovuti, Cite journal->Rejea jarida, Cite book->Rejea kitabu, Cite news->Rejea habari; {count} template(s) replaced."
            page.save(summary=summary)
            print(f"Edited: {page.title()} ({count} templates replaced)")
    except Exception as e:
        print(f"Skipped {page.title()} because {e}")
