import os, pywikibot
from pywikibot.login import ClientLoginManager

username = os.getenv('WIKI_USERNAME', 'Gayle-Bot')
password = os.getenv('WIKI_PASSWORD', 'CountryBot@it3ipj55bu65vg6vjq57i8dq4olhsrp2')
site = pywikibot.Site("sw", "wikipedia")
lm = ClientLoginManager(site=site, user=username)
lm.password = password
lm.login()

category = pywikibot.Category(site, "Jamii:Papa")
for page in category.articles():
    text = page.text
    if "[[Jamii:Papa]]" in text:
        page.text = text.replace("[[Jamii:Papa]]", "[[Jamii:Mapapa]]")
        page.save(summary="Bot: [[Jamii:Papa]] → [[Jamii:Mapapa]]")
        print(f"Edited: {page.title()}")
