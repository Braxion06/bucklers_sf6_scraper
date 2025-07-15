# %%
import asyncio
import json
import logging
import os

import aiofiles
import dotenv
from asynciolimiter import Limiter
from rnet import Client, Impersonate
from selectolax.parser import HTMLParser

# %%
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s"
)
dotenv.load_dotenv()
COOKIE = os.getenv("BUCKLER_COOKIE")
base_url = "https://www.streetfighter.com/6/buckler/_next/data/9ef0_Yi1mn5q2sDtFiaTz/en/ranking/master.json"
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Cookie": COOKIE,
    # "Referer": "https://www.streetfighter.com/6/buckler/ranking/league?character_filter=1&character_id=luke&platform=1&user_status=1&home_filter=1&home_category_id=0&home_id=1&league_rank=0&page=1",
}
# Requests per second
limiter = Limiter(3)


def parse_request(resp) -> dict:
    html_tree = HTMLParser(resp.text)
    parsed_data = html_tree.css_first("script#__NEXT_DATA__").text()  # pyright: ignore
    return json.loads(parsed_data)


# %%
def create_client(client_headers: dict) -> Client:
    return Client(
        impersonate=Impersonate.Firefox139, default_headers=client_headers, timeout=10
    )


async def fetch_data(rclient: Client, url: str, page_number: int) -> dict:
    logging.info("Fetching page %d", page_number)
    target_url = f"{url}?page={page_number}"
    response = await rclient.get(target_url)
    print(f"Status: {response.status}")
    if response.status == 200:
        return await response.json()
    raise RuntimeError(f"Failed to fetch data, response status: {response.status_code}")


async def save_json_async(data: dict | list, path: str) -> None:
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        json_str = json.dumps(data, indent=2)
        await f.write(json_str)
    print(f"Data saved in {path}")


# %%
async def main():
    client = create_client(headers)
    j_data = []
    tasks = [limiter.wrap(fetch_data(client, base_url, i)) for i in range(1, 11)]
    j_data = await asyncio.gather(*tasks)
    await save_json_async(j_data, "data/async_output.json")


if __name__ == "__main__":
    asyncio.run(main())

# %%
print(__name__)
