# Buckler's bootcamp SF6 scraper

This project aims to download interesting SF6 player data, like MR (Master Rate) and League rankings.

Execute guidelines:

- Choose between `master` or `league` standings by changing the
endpoint variable in main()
- Prepare your Cookies in a .env file with $BUCKLER_COOKIE
- If using proxies, create a file named reliable_proxies.txt with them and
comment `plist = None` line in main.py
- Build the project's dependencies with pyproject.toml and UV
- Run main with a limited amount of pages (~10/100), comment `total_pages = 100`
to scrape all placements, the batch_size variable controls when does the
scraper writes the data
