# -*- coding: utf-8 -*-
import os

family = 'wikipedia'
mylang = 'sw'

username = os.getenv('WIKI_USERNAME', 'Gayle157')
password = os.getenv('WIKI_PASSWORD', 'CiteBot@fp5d4lfqvjrgi8d4e84s8burfovakba9')

usernames = {}
usernames['wikipedia'] = {}
usernames['wikipedia']['sw'] = username

# Store password so pywikibot doesn't prompt
_password = password

authenticate = {}
authenticate['wikipedia'] = {}
authenticate['wikipedia']['sw'] = (username, password)

# CRITICAL: This tells pywikibot not to ask for password
import pywikibot
pywikibot.config.password_file = None
