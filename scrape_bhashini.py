from playwright.sync_api import sync_playwright
import json
import os

START_URL = "https://dibd-bhashini.gitbook.io/bhashini-apis"

visited = set()
documents = []

print("Script started")
def extract_content(page):
    selectors = [
        "main",
        "article",
        "[data-testid='page-content']"
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                text = locator.first.inner_text()
                if text.strip():
                    return text
        except:
            pass

    return page.locator("body").inner_text()

def crawl(page, url):
    if url in visited:
        return

    visited.add(url)

    try:
        page.goto(url, wait_until="networkidle", timeout=60000)

        title = page.title()
        content = extract_content(page)

        documents.append({
            "url": url,
            "title": title,
            "content": content
        })

        print(f"Scraped: {url}")

        links = page.locator("a").evaluate_all(
            "elements => elements.map(e => e.href)"
        )

        for link in links:
            if (
                link.startswith(START_URL)
                and link not in visited
            ):
                crawl(page, link)

    except Exception as e:
        print(f"Error scraping {url}: {e}")

def save_documents():
    os.makedirs("docs", exist_ok=True)

    for i, doc in enumerate(documents):
        filename = f"docs/page_{i+1}.txt"

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"TITLE: {doc['title']}\n")
            f.write(f"URL: {doc['url']}\n\n")
            f.write(doc["content"])

    with open("bhashini_docs.json", "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(documents)} pages")
    print("Created:")
    print("- bhashini_docs.json")
    print("- docs/ folder")

def main():
    print("main")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        crawl(page, START_URL)

        browser.close()

    save_documents()

if __name__ == "__main__":
    main()