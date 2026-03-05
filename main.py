# %%
import asyncio
import json
import logging
import os
import random
import time
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
dotenv.load_dotenv()
COOKIE = os.getenv("BUCKLER_COOKIE")
# july 17 build ZPYRiawhkQ08LZvpMzOtP
WEB_URL = "https://www.streetfighter.com/6/buckler/ranking/master"
API_URL = "https://www.streetfighter.com/6/buckler/_next/data/{{ buildId }}/en/ranking/master.json"
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
    with open("reliable_proxies.txt", "r", encoding="utf-8") as f:
        line_list = f.readlines()
        return [line.strip() for line in line_list]


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
    rclient: Client, url: str, path: str | None, save_example: bool = True
) -> tuple[str, int, int]:
    retries = 5
    wait = 40
    for attempt in range(1, retries + 1):
        try:
            logging.info("Getting url metadata from %s", url)
            response = await rclient.get(url)
            print(f"Status: {response.status}")
            if response.status == 200:
                parsed_data = await parse_web_request(response)
                if save_example and path is not None:
                    async with aiofiles.open(path, "w", encoding="utf-8") as f:
                        json_str = json.dumps(parsed_data, indent=2)
                        await f.write(json_str)
                    print(f"Data saved in {path}")
                build_id = parsed_data["buildId"]
                total_pages = parsed_data["props"]["pageProps"][
                    "master_rating_ranking"
                ]["total_page"]
                total_placements = parsed_data["props"]["pageProps"][
                    "master_rating_ranking"
                ]["total_count"]
                print("Metadata: OK")
                return build_id, total_pages, total_placements
            if response.status in (502, 405):
                print("Scraper blocked, waiting")
                logging.error("Scraper blocked, waiting")
                time.sleep(wait)
                wait *= 2
            else:
                raise RuntimeError(
                    f"Failed to get metadata from {url}\nResponse status: {response.status}"
                )
        except Exception as e:
            logging.exception("Failed attempt %d with exception %s", attempt, str(e))
    raise RuntimeError("Failed all retries on fetching metadata")


async def fetch_api_data(
    rclient: Client, url: str, page_number: int, rankings_only: bool
) -> dict:
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
                    return data["pageProps"]["master_rating_ranking"][
                        "ranking_fighter_list"
                    ]
                if not rankings_only:
                    return await response.json()
            if response.status in (405, 502):
                print("Scraper blocked, waiting")
                logging.error("Scraper blocked, waiting")
                time.sleep(wait)
                wait *= 2
        except Exception:
            logging.error("Failed attempt %d with exception", attempt)
    raise RuntimeError("Failed all retries on fetching metadata")


async def save_json_async(data: dict | list, path: str) -> None:
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
    return 500


# %%
async def main() -> None:
    logging.info("Starting buckler_scraper\n------------------------------------------")
    with open("data/async_batch.jsonl", "w", encoding="utf-8"):
        pass
    plist = read_proxies()
    # NOTE: Uncomment to turn off proxies
    # plist = None
    client = create_client(HEADERS, plist)
    current_build_id, total_pages, url_total_placements = await get_url_metadata(
        client, WEB_URL, "data/whole_request_example.json"
    )
    # NOTE: Uncomment to only read 100 pages
    # total_pages = 100  # Hardcoded
    f_api_url = API_URL.replace("{{ buildId }}", current_build_id)
    logging.info("Working API endpoint: %s", f_api_url)
    logging.info("Total pages in endpoint: %s", total_pages)
    logging.info("Total placements in endpoint: %s", url_total_placements)
    batch_size = choose_batch_size(total_pages)
    # batch_size = 3 # Hardcoded
    num_batches = ceil(total_pages / batch_size)
    logging.info("Working with %d batches of %d pages", num_batches, batch_size)
    for batch in range(num_batches):
        start_page = batch * batch_size + 1
        end_page = min((batch + 1) * batch_size, total_pages)
        logging.info(
            "Processing batch %d/%d: pages %d - %d",
            batch,
            num_batches,
            start_page,
            end_page,
        )
        await asyncio.sleep(random.uniform(0.2, 0.5))
        tasks = [
            limiter.wrap(fetch_api_data(client, f_api_url, page, True))
            for page in range(start_page, end_page + 1)
        ]
        batch_data = await asyncio.gather(*tasks)
        await save_json_async(batch_data, "data/async_batch.jsonl")
    logging.info("Scraping finished")


if __name__ == "__main__":
    asyncio.run(main())
