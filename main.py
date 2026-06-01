# %%
import asyncio
import json
import logging
import os
import random
import time
from datetime import date
from math import ceil

import aiofiles
import dotenv
from asynciolimiter import Limiter
from rnet import Client, Impersonate, Proxy, Response
from selectolax.parser import HTMLParser

# %%
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s",
    filename="logs/buckler_scraper.log",
)
# Prepare environment
dotenv.load_dotenv()
os.makedirs("data", exist_ok=True)
COOKIE = os.getenv("BUCKLER_COOKIE")
WEB_URL = "https://www.streetfighter.com/6/buckler/ranking/{{ ranking_type }}"
API_URL = "https://www.streetfighter.com/6/buckler/_next/data/{{ buildId }}/en/ranking/{{ ranking_type }}.json"
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Cookie": COOKIE,
    "Referer": "https://www.streetfighter.com/6/buckler/ranking/master?character_filter=1&character_id=luke&platform=1&user_status=1&home_filter=1&home_category_id=0&home_id=1&league_rank=0&page=1",
    "Priority": "u=0, i",
    "Sec-Ch-Ua": '"Not)A;Brand";v="8", "Chromium";v="137", "Google Chrome";v="137"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Linux"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
}
# Requests per second
limiter = Limiter(1.2)


# %%
def read_proxies():
    if os.path.exists("reliable_proxies.txt"):
        with open("reliable_proxies.txt", "r", encoding="utf-8") as f:
            line_list = f.readlines()
            return [line.strip() for line in line_list]
    else:
        print("Did not found reliable_proxies.txt")


def create_client(client_headers: dict, proxy_list: None | list = None) -> Client:
    proxies = None
    if proxy_list is not None:
        proxies = [Proxy.http(proxy) for proxy in proxy_list]
    return Client(
        impersonate=Impersonate.Chrome137,
        default_headers=client_headers,
        timeout=30,
        proxies=proxies,
    )


async def parse_web_request(resp: Response) -> dict:
    html_tree = HTMLParser(await resp.text())
    parsed_data = html_tree.css_first("script#__NEXT_DATA__")
    if parsed_data is None:
        raise ValueError("Couldn't find __NEXT_DATA__ script tag in response")
    parsed_data = parsed_data.text()
    return json.loads(parsed_data)


async def get_url_metadata(
    rclient: Client,
    url: str,
    ranking_endpoint: str,
    path: str | None = None,
    save_file: bool = False,
) -> tuple[str, int, int]:
    if ranking_endpoint not in ("master", "league"):
        raise ValueError("Ranking type must be either ranking or league")
    if ranking_endpoint == "master":
        ladder = "master_rating_ranking"
    else:
        ladder = "league_point_ranking"
    url = url.replace("{{ ranking_type }}", ranking_endpoint)
    retries = 5
    wait = 40
    for attempt in range(1, retries + 1):
        try:
            logging.info("Getting url metadata from %s", url)
            response = await rclient.get(url)
            print(f"Status: {response.status}")
            if response.status == 200:
                print(f"Mode: {ranking_endpoint} - Metadata: OK")
                parsed_data = await parse_web_request(response)
                if save_file and path is not None:
                    async with aiofiles.open(path, "w", encoding="utf-8") as f:
                        json_str = json.dumps(parsed_data, indent=2)
                        await f.write(json_str)
                    print(f"Metadata saved in {path}")
                build_id = parsed_data["buildId"]
                total_pages = parsed_data["props"]["pageProps"][ladder]["total_page"]
                total_placements = parsed_data["props"]["pageProps"][ladder][
                    "total_count"
                ]
                return build_id, total_pages, total_placements
            if response.status in (502, 405):
                print(f"Scraper blocked, waiting for {wait} seconds")
                logging.error("Scraper blocked, waiting for %d seconds", wait)
                time.sleep(wait)
                wait *= 2
            else:
                raise RuntimeError(
                    f"Failed to get metadata from {url}\nResponse status: {response.status}"
                )
        except Exception as e:
            logging.exception(
                "Failed metadata attempt %d with exception %s", attempt, str(e)
            )
    raise RuntimeError("Failed all retries on fetching metadata")


async def fetch_api_data(
    rclient: Client,
    url: str,
    ranking_endpoint: str,
    page_number: int,
    rankings_only: bool,
) -> dict:
    if ranking_endpoint not in ("master", "league"):
        raise ValueError("Ranking type must be either ranking or league")
    if ranking_endpoint == "master":
        ladder = "master_rating_ranking"
    else:
        ladder = "league_point_ranking"
    url = url.replace("{{ ranking_type }}", ranking_endpoint)
    retries = 5
    wait = 40
    for attempt in range(1, retries + 1):
        try:
            target_url = f"{url}?page={page_number}"
            response = await rclient.get(target_url)
            print(f"Page: {page_number} - Status: {response.status}")
            if response.status == 200:
                if rankings_only:
                    data = await response.json()
                    return data["pageProps"][ladder]["ranking_fighter_list"]
                else:
                    return await response.json()
            if response.status in (405, 502):
                print(f"Scraper blocked, waiting for {wait} seconds")
                logging.error("Scraper blocked, waiting for %d seconds", wait)
                # NOTE: Pause the entire script
                time.sleep(wait)
                wait = min(wait * 2, 300)
        except Exception:
            logging.error("Failed api_data attempt %d with exception", attempt)
    raise RuntimeError("Failed all retries on fetching metadata")


async def save_json_async(data: list, path: str) -> None:
    async with aiofiles.open(path, "a", encoding="utf-8") as f:
        for item in data:
            json_str = json.dumps(item)
            await f.write(json_str + "\n")
    print(f"Saved {len(data)} lines in {path}")


def choose_batch_size(page_count: int) -> int:
    if page_count < 100:
        return 60
    if page_count < 1000:
        return 180
    return 300


# %%
async def main() -> None:
    process_date = date.today()
    # NOTE: Should be either "master" for master rate or "league" for league points
    endpoint = "master"
    if endpoint not in ("master", "league"):
        raise ValueError("Endpoint must be either ranking or league")
    logging.info("---------------- Starting buckler_sf6_scraper ---------------")
    logging.info("Endpoint chosen: %s", endpoint)
    print("----- Starting bucklers_sf6_scraper -----")
    print(f"Endpoint chosen: {endpoint}")
    plist = read_proxies()
    # NOTE: Comment to to use proxies
    plist = None
    client = create_client(HEADERS, plist)
    # NOTE: Call both endpoints but only use the last one
    master_build_id, master_pages, master_placements = await get_url_metadata(
        client,
        WEB_URL,
        "master",
        f"data/full-response-master-{process_date}.json",
        True,
    )
    league_build_id, league_pages, league_placements = await get_url_metadata(
        client,
        WEB_URL,
        "league",
        f"data/full-response-league-{process_date}.json",
        True,
    )
    if endpoint == "master":
        current_build_id = master_build_id
        total_pages = master_pages
        url_total_placements = master_placements
    else:
        current_build_id = league_build_id
        total_pages = league_pages
        url_total_placements = league_placements
    # NOTE: Comment to (unlock) read more than 100 pages
    total_pages = 100  # Hardcoded
    api_url_w_build = API_URL.replace("{{ buildId }}", current_build_id)
    logging.info(
        "Working API %s endpoint: %s",
        endpoint,
        api_url_w_build.replace("{{ ranking_type }}", endpoint),
    )
    logging.info("Total pages in %s endpoint: %s", endpoint, total_pages)
    logging.info("Total placements in %s endpoint : %s", endpoint, url_total_placements)
    batch_size = choose_batch_size(total_pages)
    # NOTE: Comment to unlock batch size
    batch_size = 50  # Hardcoded
    num_batches = ceil(total_pages / batch_size)
    logging.info("Working with %d batches of %d pages", num_batches, batch_size)
    for batch in range(num_batches):
        # NOTE: Taking into account zero indexing, adding 1 to batch
        start_page = batch * batch_size + 1
        end_page = min((batch + 1) * batch_size, total_pages)
        logging.info(
            "Processing batch %d/%d: pages %d - %d",
            batch + 1,
            num_batches,
            start_page,
            end_page,
        )
        # NOTE: Pause the current task
        await asyncio.sleep(random.uniform(0.2, 0.6))
        tasks = [
            limiter.wrap(fetch_api_data(client, api_url_w_build, endpoint, page, True))
            for page in range(start_page, end_page + 1)
        ]
        batch_data = await asyncio.gather(*tasks)
        await save_json_async(
            batch_data, f"data/bucklers-data-{endpoint}-{process_date}.jsonl"
        )
    logging.info("Scraping finished")


if __name__ == "__main__":
    asyncio.run(main())
