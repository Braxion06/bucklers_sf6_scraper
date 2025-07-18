# %%
import asyncio
import json
import logging
import os
from math import ceil

import aiofiles
import dotenv
from asynciolimiter import Limiter
from rnet import Client, Impersonate, Response
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
web_url = "https://www.streetfighter.com/6/buckler/ranking/master"
api_url = "https://www.streetfighter.com/6/buckler/_next/data/{{ buildId }}/en/ranking/master.json"
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Cookie": COOKIE,
    # "Referer": "https://www.streetfighter.com/6/buckler/ranking/league?character_filter=1&character_id=luke&platform=1&user_status=1&home_filter=1&home_category_id=0&home_id=1&league_rank=0&page=1",
}
# Requests per second
limiter = Limiter(2.5)


# %%
def create_client(client_headers: dict) -> Client:
    return Client(
        impersonate=Impersonate.Firefox139, default_headers=client_headers, timeout=10
    )


async def parse_web_request(resp: Response) -> dict:
    html_tree = HTMLParser(await resp.text())
    parsed_data = html_tree.css_first("script#__NEXT_DATA__")
    if parsed_data is None:
        raise ValueError("Couldn't find __NEXT_DATA__ script tag in response")
    parsed_data = parsed_data.text()
    return json.loads(parsed_data)


async def get_url_metadata(rclient: Client, url: str) -> tuple[str, int, int]:
    logging.info("Getting url metadata from %s", url)
    response = await rclient.get(url)
    print(f"Status: {response.status}")
    if response.status == 200:
        json_data = await parse_web_request(response)
        # print(json_data["props"]["pageProps"].keys())
        build_id = json_data["buildId"]
        total_pages = json_data["props"]["pageProps"]["master_rating_ranking"][
            "total_page"
        ]
        total_placements = json_data["props"]["pageProps"]["master_rating_ranking"][
            "total_count"
        ]
        return build_id, total_pages, total_placements
    raise RuntimeError(
        f"Failed to get metadata from {url}\nResponse status: {response.status_code}"
    )


async def fetch_data(rclient: Client, url: str, page_number: int) -> dict:
    # logging.info("Fetching page %d", page_number)
    target_url = f"{url}?page={page_number}"
    response = await rclient.get(target_url)
    print(f"Status: {response.status}")
    if response.status == 200:
        return await response.json()
    raise RuntimeError(f"Failed to fetch data, response status: {response.status_code}")


async def save_json_async(data: dict | list, path: str) -> None:
    async with aiofiles.open(path, "a", encoding="utf-8") as f:
        for item in data:
            json_str = json.dumps(item)
            await f.write(json_str + "\n")
    print(f"Saved {len(data)} lines in {path}")


def choose_batch_size(page_count: int) -> int:
    if page_count < 100:
        return 50
    if page_count < 1000:
        return 150
    if page_count < 10000:
        return 1000
    return 1800


# %%
async def main() -> None:
    with open("data/async_batch.jsonl", "w", encoding="utf-8"):
        pass
    client = create_client(headers)
    current_build_id, total_pages, url_total_placements = await get_url_metadata(
        client, web_url
    )
    f_api_url = api_url.replace("{{ buildId }}", current_build_id)
    logging.info("Working API endpoint: %s", f_api_url)
    logging.info("Total pages in endpoint: %s", total_pages)
    logging.info("Total placements in endpoint: %s", url_total_placements)
    batch_size = choose_batch_size(total_pages)
    # batch_size = 3
    total_pages = 10
    num_batches = ceil(total_pages / batch_size)
    logging.info("Working with %d batches", num_batches)
    for batch in range(num_batches):
        start_page = batch * batch_size + 1
        end_page = min((batch + 1) * batch_size, total_pages)
        logging.info(
            "Processing batch %d/%d, containing pages %d to %d",
            batch,
            batch_size,
            start_page,
            end_page,
        )
        tasks = [
            limiter.wrap(fetch_data(client, f_api_url, page))
            for page in range(start_page, end_page + 1)
        ]
        batch_data = await asyncio.gather(*tasks)
        await save_json_async(batch_data, "data/async_batch.jsonl")
    logging.info("Scraping finished")


if __name__ == "__main__":
    asyncio.run(main())
