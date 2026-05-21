from urllib.robotparser import RobotFileParser
from collections import deque
from urllib.parse import urlparse, urljoin, urlunparse
import time
import requests
from bs4 import BeautifulSoup
import threading

BASE = "https://mit.edu/"
DOMAIN = "mit.edu"
USER_AGENT = "UniversityBot/1.0 (+https://pg.edu.pl/)"

rp = RobotFileParser()
rp.set_url(f"{BASE}/robots.txt")
rp.read()

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


headers = {
    "User-Agent": f"{USER_AGENT}"
}

start_time = time.time()

url_frontier = deque()
url_frontier.append(f"https://{DOMAIN}")

visited_lock = threading.Lock()
visited = set()



while url_frontier:
    current_url = url_frontier.popleft()

    if current_url in visited:
        continue
    if rp.can_fetch( USER_AGENT, current_url):
        visited.add(current_url)
    else:
        continue

    time.sleep(2)
    response = requests.get(current_url, headers=headers)
    html = response.text

    soup = BeautifulSoup(html, 'html.parser')

    found_links = []
    for a_tag in soup.find_all('a'):
        href = a_tag.get('href')
        if href:
            found_links.append(href)

    print("==========Found ", len(found_links), " links============")

    for link in found_links:
        link = normalize_url(link)

        if not is_same_domain(link):
            continue

        url_frontier.append(link)

elapsed_time = time.time() - start_time
print(f"Czas: {elapsed_time:.2f} sekund")
print("========Visited Links============")
print(visited)
print(f"\n Visited {len(visited)} pages")