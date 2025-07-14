# %%
import asyncio
import json
import os
import time

import dotenv
from asynciolimiter import Limiter
from httpx import Client, Response

# from rnet import Client, Impersonate, Response
from selectolax.parser import HTMLParser

# %%
dotenv.load_dotenv()
COOKIE = os.getenv("BUCKLER_COOKIE")
url_api = "https://www.streetfighter.com/6/buckler/_next/data/9ef0_Yi1mn5q2sDtFiaTz/en/ranking/master.json"
url = "https://www.streetfighter.com/6/buckler/ranking/master"
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Cookie": COOKIE,
    # "Referer": "https://www.streetfighter.com/6/buckler/ranking/league?character_filter=1&character_id=luke&platform=1&user_status=1&home_filter=1&home_category_id=0&home_id=1&league_rank=0&page=1",
}


# %%
def create_client(client_headers: dict) -> Client:
    return Client(headers=client_headers)


#
# def create_client(client_headers: dict) -> Client:
#


def make_request(cl: Client, target_url: str) -> Response:
    response_f = cl.get(target_url)
    # if response_f.status_code == 200:
    return response_f


def parse_request(resp: Response) -> dict:
    html_tree = HTMLParser(resp.text)
    parsed_data = html_tree.css_first("script#__NEXT_DATA__").text()  # pyright: ignore
    return json.loads(parsed_data)


def save_json(data: dict | list, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Data saved in {path}")


def loop_over(client_headers: dict, target_url: str, path: str):  # -> list:
    client = create_client(client_headers)
    j_data = []
    is_api = {target_url.endswith("json")}
    print(f"Target url is an API: {is_api}")
    for i in range(1, 11):
        loop_url = f"{target_url}?page={i}"
        response = make_request(client, loop_url)
        print(i)
        print(loop_url)
        print(response.status_code)
        if response.status_code == 200:
            if is_api:
                # j_data.append(response.json()["pageProps"]["master_rating_ranking"]['ranking_fighter_list'][i])
                j_data.append(response.json())
            else:
                j_data.append(parse_request(response))
        else:
            with open("err_res.txt", "w", encoding="utf-8") as file:
                file.write(response.text)
        time.sleep(0.5)
    if len(j_data) > 0:
        save_json(j_data, path)
    # return j_data


def main():
    loop_over(headers, url_api, "data/list_data.json")


if __name__ == "__main__":
    main()

# %%
# client = create_client(headers)
# response = make_request(client, url_api)
# print(response.status_code)
# print(response.json())
#
# %%
