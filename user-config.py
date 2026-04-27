import os

family = 'wikipedia'
mylang = 'sw'

# MUST use this exact format
usernames = {}
usernames['wikipedia'] = {}
usernames['wikipedia']['sw'] = os.getenv('WIKI_USERNAME', 'Gayle157')

# Use authenticate with password
authenticate = {}
authenticate['wikipedia'] = {}
authenticate['wikipedia']['sw'] = (
    os.getenv('WIKI_USERNAME', 'Gayle157'),
    os.getenv('WIKI_PASSWORD', 'CiteBot@fp5d4lfqvjrgi8d4e84s8burfovakba9')
)
