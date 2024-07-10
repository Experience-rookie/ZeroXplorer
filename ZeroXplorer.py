import scrapy
import json
import re
from urllib.parse import urlparse
from scrapy.crawler import CrawlerProcess
from scrapy.downloadermiddlewares.offsite import OffsiteMiddleware
from scrapy.utils.log import configure_logging

class CustomOffsiteMiddleware(OffsiteMiddleware):
    def should_follow(self, request, spider):
        if not self.host_regex:
            return True
        host = urlparse(request.url).netloc.split(':')[0]
        return bool(self.host_regex.search(host))

class ZeroXplorer(scrapy.Spider):
    name = 'ZeroXplorer'

    def __init__(self, start_url, *args, **kwargs):
        super(ZeroXplorer, self).__init__(*args, **kwargs)
        self.start_urls = [start_url]
        self.allowed_domains = [urlparse(start_url).netloc.split(':')[0]]
        self.visited_urls = set()
        self.results = {
            'emails': set(),
            'links': set(),
            'external_files': set(),
            'js_files': set(),
            'form_fields': set(),
            'images': set(),
            'videos': set(),
            'audio': set(),
            'comments': set(),
        }

    def parse(self, response):
        self.visited_urls.add(response.url)

        if response.headers.get('Content-Type', '').decode('utf-8').startswith('text'):
            self.extract_emails(response)
            self.extract_links(response)
            self.extract_external_files(response)
            self.extract_js_files(response)
            self.extract_form_fields(response)
            self.extract_media(response, 'images', 'img::attr(src)')
            self.extract_media(response, 'videos', 'video::attr(src), source::attr(src)')
            self.extract_media(response, 'audio', 'audio::attr(src), source::attr(src)')
            self.extract_comments(response)
        else:
            self.results['external_files'].add(response.url)

        self.log(f"Processed {response.url}")

    def extract_emails(self, response):
        emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', response.text))
        self.results['emails'].update(emails)

    def extract_links(self, response):
        links = response.css('a::attr(href)').getall()
        for link in links:
            if link.startswith('mailto:'):
                continue
            parsed_link = urlparse(link)
            if not parsed_link.scheme:
                link = response.urljoin(link)
            if urlparse(link).netloc == urlparse(response.url).netloc:
                if link not in self.visited_urls:
                    yield response.follow(link, callback=self.parse)
            self.results['links'].add(link)

    def extract_external_files(self, response):
        external_files = response.css('link::attr(href), a::attr(href)').re(r'.*\.(css|pdf|docx?|xlsx?)$')
        for ext_file in external_files:
            self.results['external_files'].add(response.urljoin(ext_file))

    def extract_js_files(self, response):
        js_files = response.css('script::attr(src)').getall()
        for js_file in js_files:
            self.results['js_files'].add(response.urljoin(js_file))

    def extract_form_fields(self, response):
        form_fields = response.css('input::attr(name), textarea::attr(name), select::attr(name)').getall()
        self.results['form_fields'].update(form_fields)

    def extract_media(self, response, media_type, css_selector):
        media_files = response.css(css_selector).getall()
        for media_file in media_files:
            self.results[media_type].add(response.urljoin(media_file))

    def extract_comments(self, response):
        comments = response.xpath('//comment()').getall()
        self.results['comments'].update(comments)

    def closed(self, reason):
        self.log("Crawl finished, converting results to JSON.")
        for key in self.results:
            self.results[key] = list(self.results[key])
        with open('zeroxer.json', 'w') as f:
            json.dump(self.results, f, indent=4)
        self.log(f"Results saved to zeroxer.json")

def run_crawler(start_url):
    configure_logging()
    process = CrawlerProcess(settings={
        'LOG_LEVEL': 'INFO',
        'DOWNLOADER_MIDDLEWARES': {
            '__main__.CustomOffsiteMiddleware': 500,
        }
    })
    process.crawl(ZeroXplorer, start_url=start_url)
    process.start()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Advanced Web Crawler")
    parser.add_argument("start_url", help="The starting URL for the web crawler")
    args = parser.parse_args()

    run_crawler(args.start_url)
