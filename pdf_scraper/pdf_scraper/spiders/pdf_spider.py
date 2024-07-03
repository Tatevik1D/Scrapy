import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.http import HtmlResponse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import random

class RandomUserAgentMiddleware:
    user_agent_list = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
        # Add more user agents
    ]

    def process_request(self, request, spider):
        ua = random.choice(self.user_agent_list)
        request.headers.setdefault('User-Agent', ua)

class RotateProxyMiddleware:
    proxy_list = [
        'http://proxy1.com:8000',
        'http://proxy2.com:8000',
        # Add more proxies
    ]

    def process_request(self, request, spider):
        proxy = random.choice(self.proxy_list)
        request.meta['proxy'] = proxy

class SeleniumMiddleware:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=chrome_options)

    def process_request(self, request, spider):
        self.driver.get(request.url)
        try:
            # Wait for the page to load (modify as needed)
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            body = self.driver.page_source
            return HtmlResponse(self.driver.current_url, body=body, encoding='utf-8', request=request)
        except Exception as e:
            spider.logger.error(f"Error loading page with Selenium: {e}")
            return HtmlResponse(request.url, status=500)

class PdfSpider(CrawlSpider):
    name = 'pdf_spider'
    allowed_domains = ['find-and-update.company-information.service.gov.uk']  # Change this to your target domain
    start_urls = ['https://find-and-update.company-information.service.gov.uk/advanced-search/get-results?companyNameIncludes=&companyNameExcludes=&registeredOfficeAddress=&incorporationFromDay=&incorporationFromMonth=&incorporationFromYear=&incorporationToDay=&incorporationToMonth=&incorporationToYear=&status=active&sicCodes=&type=ltd&dissolvedFromDay=&dissolvedFromMonth=&dissolvedFromYear=&dissolvedToDay=&dissolvedToMonth=&dissolvedToYear=']  # Change this to your target start URL

    rules = (
        Rule(LinkExtractor(allow=()), callback='parse_item', follow=True),
    )

    custom_settings = {
        'DOWNLOAD_DELAY': 2,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 5,
        'AUTOTHROTTLE_MAX_DELAY': 60,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
        'AUTOTHROTTLE_DEBUG': True,
        'DOWNLOADER_MIDDLEWARES': {
            'pdf_scraper.middlewares.RandomUserAgentMiddleware': 400,
            'pdf_scraper.middlewares.RotateProxyMiddleware': 410,
            'pdf_scraper.middlewares.SeleniumMiddleware': 420,
        },
    }

    def parse_item(self, response):
        links = response.css('a::attr(href)').getall()
        for link in links:
            if link.endswith('download=0'):
                pdf_url = response.urljoin(link)
                self.logger.info(f'Found PDF URL: {pdf_url}')
                yield scrapy.Request(pdf_url, callback=self.save_pdf)

    def save_pdf(self, response):
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pdf_dir = os.path.join(project_dir, 'pdfs')

        if not os.path.exists(pdf_dir):
            self.logger.info(f'Creating directory: {pdf_dir}')
            os.makedirs(pdf_dir)

        path = os.path.join(pdf_dir, os.path.basename(response.url))
        self.logger.info(f'Saving PDF {path} (Status: {response.status}, Length: {len(response.body)})')

        with open(path, 'wb') as f:
            f.write(response.body)

        self.crawler.stats.inc_value('file_count')

