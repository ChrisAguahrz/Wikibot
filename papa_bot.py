import os, pywikibot
from pywikibot.login import ClientLoginManager

username = os.getenv('WIKI_USERNAME', 'Gayle-Bot')
password = os.getenv('WIKI_PASSWORD', 'CountryBot@it3ipj55bu65vg6vjq57i8dq4olhsrp2')
site = pywikibot.Site("sw", "wikipedia")
lm = ClientLoginManager(site=site, user=username)
lm.password = password
lm.login()

category = pywikibot.Category(site, "Jamii:Papa")
pages = list(category.articles())
print(f"Found {len(pages)} pages")

for page in pages:
    text = page.text
    print(f"Checking: {page.title()}...")
    if "[[Jamii:Papa]]" in text:
        page.text = text.replace("[[Jamii:Papa]]", "[[Jamii:Mapapa]]")
        page.save(summary="Bot: [[Jamii:Papa]] → [[Jamii:Mapapa]]")
        print(f"  EDITED!")
    elif "Jamii:Papa" in text:
        print(f"  Contains Jamii:Papa but not exact match. Found: {text[text.find('Jamii:Papa')-5:text.find('Jamii:Papa')+20]}")
    else:
        print(f"  No Jamii:Papa found")
