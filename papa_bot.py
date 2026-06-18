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
    
    # Check for both Category:Papa and Jamii:Papa
    if "[[Category:Papa]]" in text:
        page.text = text.replace("[[Category:Papa]]", "[[Jamii:Mapapa]]")
        page.save(summary="Bot: [[Category:Papa]] → [[Jamii:Mapapa]]")
        print(f"  EDITED Category:Papa!")
    elif "[[Jamii:Papa]]" in text:
        page.text = text.replace("[[Jamii:Papa]]", "[[Jamii:Mapapa]]")
        page.save(summary="Bot: [[Jamii:Papa]] → [[Jamii:Mapapa]]")
        print(f"  EDITED Jamii:Papa!")
    elif "Jamii:Papa" in text:
        print(f"  Contains Jamii:Papa but not exact match. Found: {text[text.find('Jamii:Papa')-5:text.find('Jamii:Papa')+20]}")
    elif "Category:Papa" in text:
        print(f"  Contains Category:Papa but not exact match. Found: {text[text.find('Category:Papa')-5:text.find('Category:Papa')+20]}")
    else:
        print(f"  No Jamii:Papa or Category:Papa found")
