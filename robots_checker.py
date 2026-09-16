import asyncio
from bs4 import BeautifulSoup
import httpx
import pandas as pd

# --- SETTINGS ---
INPUT_FILE = "urls.csv"
OUTPUT_FILE = "robots_results.csv"
CONCURRENCY_LIMIT = 25
TIMEOUT_SECONDS = 10.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}


async def check_url(client, url, semaphore, index, total):
    async with semaphore:
        url = str(url).strip()
        if not url.startswith("http"):
            url = "https://" + url

        try:
            response = await client.get(
                url,
                headers=HEADERS,
                follow_redirects=True,
                timeout=TIMEOUT_SECONDS,
            )

            x_robots = response.headers.get("x-robots-tag", "None")
            meta_robots = "None"
            googlebot = "None"

            soup = BeautifulSoup(response.text, "lxml")

            meta_tag = soup.find(
                "meta", attrs={"name": lambda x: x and x.lower() == "robots"}
            )
            if meta_tag and meta_tag.has_attr("content"):
                meta_robots = meta_tag["content"].strip()

            gbot_tag = soup.find(
                "meta", attrs={"name": lambda x: x and x.lower() == "googlebot"}
            )
            if gbot_tag and gbot_tag.has_attr("content"):
                googlebot = gbot_tag["content"].strip()

            print(
                f"[{index + 1}/{total}] Checked: {url} | Status: {response.status_code}"
            )

            return {
                "Original URL": url,
                "Final URL": str(response.url),
                "Status Code": response.status_code,
                "Meta Robots": meta_robots,
                "X-Robots-Tag": x_robots,
                "Googlebot Tag": googlebot,
                "Error": None,
            }

        except Exception as e:
            print(f"[{index + 1}/{total}] Failed: {url} | Error: {e}")
            return {
                "Original URL": url,
                "Final URL": "N/A",
                "Status Code": "Error",
                "Meta Robots": "None",
                "X-Robots-Tag": "None",
                "Googlebot Tag": "None",
                "Error": str(e),
            }


async def main():
    try:
        df = pd.read_csv(INPUT_FILE)
        url_col = next((c for c in df.columns if c.lower() == "url"), None)
        if not url_col:
            print("Error: Could not find a 'url' column in your CSV.")
            return
        urls = df[url_col].dropna().tolist()
    except Exception as e:
        print(f"Failed to read CSV: {e}")
        return

    total = len(urls)
    print(f"Loaded {total} URLs. Starting checks...\n")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    limits = httpx.Limits(
        max_keepalive_connections=50, max_connections=CONCURRENCY_LIMIT
    )

    async with httpx.AsyncClient(
        verify=False, limits=limits, http2=True
    ) as client:
        tasks = [
            check_url(client, u, semaphore, idx, total)
            for idx, u in enumerate(urls)
        ]
        results = await asyncio.gather(*tasks)

    output_df = pd.DataFrame(results)
    output_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nDone! Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())