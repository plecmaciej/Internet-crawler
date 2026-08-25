import time
import os
import json
import threading
from queue import Queue, Empty
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse, urljoin, urlunparse
import requests
from bs4 import BeautifulSoup
import urllib3
import networkx as nx

BASE = "https://stanford.edu/"
DOMAIN = "stanford.edu"
USER_AGENT = "UniversityBot/1.0 (+https://pg.edu.pl/)"

# Disable warnings for unverified HTTPS requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Z1. ROBOTS EXCLUSION PROTOCOL ---
rp = RobotFileParser()
rp.set_url(f"{BASE}robots.txt")
try:
    rp.read()
    print("✅ robots.txt successfully loaded")
except Exception as e:
    print(f"⚠️ Error loading robots.txt: {e}")


def normalize_url(url):
    """
    Normalizes URLs to ensure consistent structure:
    - Enforces HTTPS scheme for ALL links.
    - Strips 'www.' prefix from netloc.
    - Removes trailing slashes and url fragments (#anchor).
    - Preserves query parameters (?key=value) required for dynamic content.
    """
    if not url:
        return ""

    url = str(url).strip()

    # Handle protocol-relative URLs or absolute paths
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith("http://") and not url.startswith("https://"):
        url = urljoin(BASE, url)

    parsed = urlparse(url)

    # Enforce HTTPS scheme
    scheme = "https"

    # Normalize network location (remove www.)
    netloc = parsed.netloc.split(':')[0].lower()
    if netloc.startswith('www.'):
        netloc = netloc[4:]

    # Remove trailing slashes from path
    path = parsed.path.rstrip('/')

    return urlunparse((
        scheme,
        netloc,
        path,
        parsed.params,
        parsed.query,  # Keeps dynamic parameters (e.g. ?tid=All&tid_1=251)
        ""  # Strip fragment identifier (#)
    ))


def is_same_domain(url):
    """Checks whether the target URL belongs to the monitored domain."""
    url_domain = urlparse(url).netloc
    return url_domain == DOMAIN or url_domain.endswith("." + DOMAIN)


def extract_links(html):
    """Parses HTML content to extract anchor tags, ignoring restricted endpoints."""
    links = []
    if not html:
        return links

    try:
        soup = BeautifulSoup(html, 'html.parser')
        for a_tag in soup.find_all('a'):
            href = a_tag.get('href')
            if not href:
                continue

            href_lower = href.lower()
            if any(x in href_lower for x in ['src=', 'aff=', 'redirect']):
                continue
            if any(x in href_lower for x in ['login', 'secure', 'auth', 'signin']):
                continue

            links.append(href)
    except Exception as e:
        pass
    return links


# --- Z2. MULTITHREADED CRAWLER IMPLEMENTATION ---
class FastWebCrawler:
    def __init__(self, domain, base_url, user_agent, max_pages=3000, num_threads=16, log_interval=50):
        self.domain = domain
        self.base_url = base_url
        self.user_agent = user_agent
        self.max_pages = max_pages
        self.num_threads = num_threads
        self.log_interval = log_interval

        self.url_frontier = Queue()
        self.enqueued_urls = set()
        self.visited_urls = set()
        self.successful_urls = set()  # Holds URLs returning HTTP 200 OK

        # Staging set for candidate edges
        self.pending_edges = set()
        self.G = nx.DiGraph()

        self.lock = threading.Lock()
        self.crawled_count = 0
        self.active_workers = 0

    def _add_to_frontier(self, url):
        """Thread-safe URL enqueuing to prevent duplicate network requests."""
        with self.lock:
            if url not in self.enqueued_urls:
                self.enqueued_urls.add(url)
                self.url_frontier.put(url)

    def worker(self, session):
        """Worker thread executing the fetch-parse loop."""
        while True:
            with self.lock:
                if self.crawled_count >= self.max_pages:
                    break

            try:
                current_url = self.url_frontier.get(timeout=0.5)
            except Empty:
                # Proper termination condition: queue is empty and NO threads are currently fetching
                with self.lock:
                    if self.crawled_count >= self.max_pages or (self.url_frontier.empty() and self.active_workers == 0):
                        break
                continue

            with self.lock:
                if current_url in self.visited_urls:
                    self.url_frontier.task_done()
                    continue
                self.visited_urls.add(current_url)
                self.active_workers += 1

            try:
                # Robots Exclusion Protocol check
                if not rp.can_fetch(self.user_agent, current_url):
                    continue

                # Network Request
                try:
                    response = session.get(current_url, verify=False, timeout=3.5)
                except requests.RequestException:
                    continue

                # Content Processing
                if response.status_code == 200 and 'text/html' in response.headers.get('Content-Type', '').lower():
                    with self.lock:
                        self.successful_urls.add(current_url)
                        self.crawled_count += 1
                        current_count = self.crawled_count

                    # Log the first 5 pages to prove the crawler is not stuck, then log periodically
                    if current_count <= 5 or current_count % self.log_interval == 0:
                        print(f"  [Progress: {current_count:5d}/{self.max_pages}] -> {current_url}")

                    found_links = extract_links(response.text)

                    if not found_links and current_count == 1:
                        print(f"  ⚠️ Warning: No links found on the main page. Stanford might be blocking the request.")

                    for link in found_links:
                        # CRITICAL FIX: Try-except scoped to individual links to prevent one bad link from breaking the entire page
                        try:
                            normalized_link = normalize_url(link)

                            if not is_same_domain(
                                    normalized_link) or normalized_link == current_url or '%' in normalized_link:
                                continue

                            with self.lock:
                                self.pending_edges.add((current_url, normalized_link))

                            self._add_to_frontier(normalized_link)
                        except Exception:
                            continue

            except Exception as e:
                pass
            finally:
                with self.lock:
                    self.active_workers -= 1
                self.url_frontier.task_done()

    def run(self):
        start_time = time.time()
        start_url = normalize_url(self.base_url)
        self._add_to_frontier(start_url)

        def thread_main():
            session = requests.Session()
            # Added Accept headers to prevent WAF blocks
            session.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            })
            self.worker(session)

        threads = []
        for _ in range(self.num_threads):
            t = threading.Thread(target=thread_main)
            t.daemon = True
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        elapsed_time = time.time() - start_time

        # --- GRAPH CONSTRUCTION ---
        # 1. Add verified valid nodes (includes sink pages with 0 outgoing links)
        for url in self.successful_urls:
            self.G.add_node(url)

        # 2. Commit edges ONLY if both source and target pages exist and return HTTP 200 OK
        for src, dst in self.pending_edges:
            if src in self.successful_urls and dst in self.successful_urls:
                self.G.add_edge(src, dst)

        return {
            'threads': self.num_threads,
            'time': elapsed_time,
            'crawled': len(self.successful_urls),
            'throughput': len(self.successful_urls) / elapsed_time if elapsed_time > 0 else 0,
            'graph': self.G.copy()
        }


# --- GRAPH VALIDATION AND METRICS ---
def validate_graph(G):
    """Analyzes graph connectivity and prints structural statistics."""
    print("\n" + "=" * 70)
    print("📊 GRAPH TOPOLOGY ANALYSIS & VALIDATION")
    print("=" * 70)
    print(f"Total Valid Nodes (HTTP 200 Pages): {G.number_of_nodes()}")
    print(f"Total Valid Directed Edges:         {G.number_of_edges()}")

    if G.number_of_nodes() > 0:
        # Sink nodes: Valid pages with no outgoing links in domain
        sink_nodes = [node for node, out_deg in G.out_degree() if out_deg == 0]
        print(f"Sink Nodes (Dead-ends with out-degree = 0): {len(sink_nodes)}")

        # Isolated nodes
        isolated = list(nx.isolates(G))
        print(f"Isolated Nodes:                           {len(isolated)}")

        # Top in-degree pages
        in_degrees = sorted(G.in_degree(), key=lambda x: x[1], reverse=True)[:5]
        print("\nTop Most Linked Pages (Highest In-Degree):")
        for url, deg in in_degrees:
            print(f"  - [{deg:4d} incoming links] {url}")
    print("=" * 70 + "\n")


# --- EXPERIMENTAL BENCHMARK STAGE ---
def run_benchmarks(thread_variants=[1, 2, 4, 8, 16, 32], sample_pages=500):
    """
    Executes isolated benchmark tests.
    Reduced sample_pages parameter allows faster testing of the thread logic.
    """
    print("\n" + "=" * 70)
    print(f"🚀 BENCHMARK STAGE (Sample Limit: {sample_pages} pages per run)")
    print("=" * 70)
    print(f"{'Threads':<8} {'Time (s)':<12} {'Pages':<8} {'Throughput (p/s)':<18} {'Speedup':<10}")
    print("-" * 70)

    results = {}
    baseline_time = None

    for n_threads in thread_variants:
        crawler = FastWebCrawler(DOMAIN, BASE, USER_AGENT, max_pages=sample_pages, num_threads=n_threads,
                                 log_interval=100)
        res = crawler.run()
        results[n_threads] = res

        if baseline_time is None:
            baseline_time = res['time']

        speedup = baseline_time / res['time'] if res['time'] > 0 else 0
        print(f"{n_threads:<8} {res['time']:<12.2f} {res['crawled']:<8} {res['throughput']:<18.2f} {speedup:<10.2f}x")

    return results


# --- FULL DOMAIN CRAWL STAGE ---
def run_full_domain_crawl(optimal_threads=32, max_pages=10000):
    print("\n" + "=" * 70)
    print(f"🌐 FULL DOMAIN CRAWL STAGE (Threads: {optimal_threads}, Limit: {max_pages})")
    print("=" * 70)

    crawler = FastWebCrawler(DOMAIN, BASE, USER_AGENT, max_pages=max_pages, num_threads=optimal_threads,
                             log_interval=200)
    full_res = crawler.run()

    print(f"\nCrawl execution complete!")
    print(f"Total Execution Time: {full_res['time']:.2f} s")
    print(f"Total Pages Crawled:  {full_res['crawled']}")

    validate_graph(full_res['graph'])

    nx.write_edgelist(full_res['graph'], "graph_cleaned.txt")
    print("💾 Validated graph saved to graph_cleaned.txt")

    return full_res


if __name__ == "__main__":
    # Stage 1: Run multithreading benchmark comparison (e.g. 500 or 3000 pages sample)
    benchmark_results = run_benchmarks(thread_variants=[1, 2, 4, 8, 16, 32], sample_pages=1000)

    print("\n" + "=" * 70)
    print("💾 ZAPISYWANIE DANYCH DO PLIKU RESULTS.JSON")
    print("=" * 70)

    results_data = {}
    for n_threads, res in benchmark_results.items():
        results_data[str(n_threads)] = {
            'time': res['time'],
            'throughput': res['throughput'],
            'crawled': res['crawled']
        }

    OUTPUT_DIR = "graph_analysis_task2"
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    file_path = os.path.join(OUTPUT_DIR, 'results.json')

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(results_data, f, indent=4)

    print("✅ Pomyślnie zapisano plik 'results.json'.")
    print("👉 Możesz teraz uruchomić skrypt generujący statystyki!")

    # Stage 2: Execute full crawl with optimal thread setting (limit up to 10000 pages)
    #full_crawl_results = run_full_domain_crawl(optimal_threads=32, max_pages=200)

