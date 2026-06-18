import os, pywikibot, re
from pywikibot.login import ClientLoginManager

username = os.getenv('WIKI_USERNAME', 'Gayle-Bot')
password = os.getenv('WIKI_PASSWORD', 'CountryBot@it3ipj55bu65vg6vjq57i8dq4olhsrp2')
site = pywikibot.Site("sw", "wikipedia")
lm = ClientLoginManager(site=site, user=username)
lm.password = password
lm.login()

category = pywikibot.Category(site, "Jamii:Papa")

# Get articles AND subcategories
pages = list(category.articles()) + list(category.subcategories())
print(f"Found {len(pages)} pages (articles + subcategories)")

for page in pages:
    text = page.text
    print(f"Checking: {page.title()}...")
    edited = False
    
    # Find all category/subcategory links (both [[Category:...]] and [[Jamii:...]])
    pattern = r'\[\[(Jamii|Category):Papa(\|[^\]]*)?\]\]'
    matches = re.findall(pattern, text)
    
    if matches:
        # Replace all occurrences
        new_text = re.sub(pattern, r'[[Jamii:Mapapa\2]]', text)
        if new_text != text:
            page.text = new_text
            page.save(summary="Bot: [[Jamii:Papa]]/[[Category:Papa]] → [[Jamii:Mapapa]]")
            print(f"  EDITED! Replaced {len(matches)} occurrence(s)")
            edited = True
    
    if not edited:
        # Check for loose mentions
        if "Jamii:Papa" in text:
            idx = text.find('Jamii:Papa')
            print(f"  Contains Jamii:Papa but not in brackets. Found: ...{text[max(0,idx-10):idx+20]}...")
        elif "Category:Papa" in text:
            idx = text.find('Category:Papa')
            print(f"  Contains Category:Papa but not in brackets. Found: ...{text[max(0,idx-10):idx+20]}...")
        else:
            print(f"  No Jamii:Papa or Category:Papa found")
