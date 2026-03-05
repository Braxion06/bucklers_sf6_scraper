# Buckler's bootcamp SF6 scraper

This project aims to download interesting SF6 player data.

Execute guidelines:

- Prepare your Cookies in a .env file
- If using proxies, create a file named reliable_proxies.txt with them and
comment `plist = None` line in main.py
- To save the example request data uncomment `"data/whole_request_example.json", True`
- Build the project dependencies with pyproject.toml and UV
- Run main with a limited amount of pages (~10/100), comment `total_pages = 100`
to scrape all placements
