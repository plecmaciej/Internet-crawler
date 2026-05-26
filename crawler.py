from urllib.robotparser import RobotFileParser
from collections import deque
from urllib.parse import urlparse, urljoin, urlunparse
import time
import requests
from bs4 import BeautifulSoup
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

BASE = "https://stanford.edu/"
DOMAIN = "stanford.edu"
USER_AGENT = "UniversityBot/1.0 (+https://pg.edu.pl/)"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

rp = RobotFileParser()
rp.set_url(f"{BASE}robots.txt")
try:
    rp.read()
    print("robots.txt loaded")
except Exception as e:
    print(f"Error during loading robots.txt : {e}")


headers = {
    "User-Agent": f"{USER_AGENT}"
}


def normalize_url(url):

    if not url.startswith("http"):
       url = urljoin(BASE, url)

    parsed = urlparse(url)
    normalized_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip('/'),
        parsed.params,
        parsed.query,
        ""
    ))


    return normalized_url

def is_same_domain(url):
    url_domain = urlparse(url).netloc
    return url_domain == DOMAIN or url_domain.endswith("." + DOMAIN)

def extract_links(html, current_url):
    links = []
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for a_tag in soup.find_all('a'):
            href = a_tag.get('href')
            if href:
                links.append(href)
    except Exception as e:
        print(f"Error during parsing : {e}")
    return links


visited_lock = threading.Lock()
frontier_lock = threading.Lock()
stats_lock = threading.Lock()

url_frontier = deque()
visited = set()
crawled_count = 0


def crawl_single_url(session, max_pages):

    global crawled_count

    while True:

        if crawled_count >= max_pages:
            return

        with frontier_lock:
            if not url_frontier:
                return
            current_url = url_frontier.popleft()

        with visited_lock:
            if current_url in visited:
                continue
            visited.add(current_url)

        if not rp.can_fetch( USER_AGENT, current_url):
            continue


        try:
            response = session.get(current_url, verify=False, timeout=5)
            response.raise_for_status()

            with stats_lock:
                crawled_count += 1
                print(f"✅ [{crawled_count:4d}] {current_url}")

            found_links = extract_links(response.text, current_url)

            for link in found_links:
                normalized_link = normalize_url(link)

                if not is_same_domain(normalized_link):
                    continue
                with visited_lock:
                    if normalized_link not in visited:
                        with frontier_lock:
                            url_frontier.append(normalized_link)

            #time.sleep(1)

        except requests.exceptions.SSLError as e:
            print(f"SSL Error: {current_url}")
            continue
        except requests.exceptions.Timeout:
            print(f"Timeout: {current_url}")
            continue
        except requests.exceptions.ConnectionError:
            print(f"Connection Error: {current_url}")
            continue
        except Exception as e:
            print(f"Undefined error: {current_url} - {type(e).__name__}: {e}")
            continue


def crawl_with_threads(num_threads, max_pages = 3000):
    global crawled_count, url_frontier, visited
    crawled_count = 0
    url_frontier.clear()
    visited.clear()

    url_frontier.append(normalize_url(f"https://{DOMAIN}"))

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    start_time = time.time()

    print(f"Crawling with {num_threads} (max {max_pages} stron)\n")

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(crawl_single_url, session, max_pages) for _ in range(num_threads)]

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"Thread error: {e}")

    elapsed_time = time.time() - start_time

    return {
        'threads': num_threads,
        'time': elapsed_time,
        'crawled': crawled_count,
        'throughput': crawled_count / elapsed_time if elapsed_time > 0 else 0,
    }


print("TEST\n")
print(f"{'Threads':<8} {'Time':<10} {'Pages':<8} {'Throughput':<15} {'Speedup':<10}")
print("=" * 70)

results = {}

#for num_threads in [1, 2, 4, 8, 16]:
for num_threads in [8, 16]:
    result = crawl_with_threads(num_threads, max_pages=3000)
    results[num_threads] = result

    print(f"{num_threads:<8} {result['time']:<10.2f} {result['crawled']:<8} "
          f"{result['throughput']:<15.2f}")

print("\n" + "=" * 70)
print(f"{'Threads':<8} {'Time':<10} {'Throughput':<15} {'Speedup':<10}")
print("=" * 70)

baseline_time = results[1]['time']

for num_threads in sorted(results.keys()):
    result = results[num_threads]
    speedup = baseline_time / result['time'] if result['time'] > 0 else 0


    print(f"{num_threads:<8} {result['time']:<10.2f} {result['throughput']:<15.2f} "
          f"{speedup:<10.2f}x")

