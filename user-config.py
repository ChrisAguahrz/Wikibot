# -*- coding: utf-8 -*-
import os

family = 'wikipedia'
mylang = 'sw'

# Get credentials from environment
username = os.getenv('WIKI_USERNAME', 'Gayle157')
password = os.getenv('WIKI_PASSWORD', 'CiteBot@fp5d4lfqvjrgi8d4e84s8burfovakba9')

usernames = {}
usernames['wikipedia'] = {}
usernames['wikipedia']['sw'] = username

# Create a bot password file
import os as _os
_bot_pw_dir = _os.path.join(_os.path.expanduser('~'), '.pywikibot')
_os.makedirs(_bot_pw_dir, exist_ok=True)
_bot_pw_file = _os.path.join(_bot_pw_dir, 'botpassword')
with open(_bot_pw_file, 'w') as f:
    f.write(f'("{username}", "{password}")\n')

authenticate = {}
authenticate['wikipedia'] = {}
authenticate['wikipedia']['sw'] = (username, password)
