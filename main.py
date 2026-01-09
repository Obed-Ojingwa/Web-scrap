"""
Professional Web Scraper for JavaScript-Heavy Websites
Scrapes skincare products from Qudo Beauty and exports to Excel
"""

import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QudobeautyScraper:
    """Scraper class for Qudo Beauty website"""
    
    def __init__(self, headless=True):
        """Initialize the scraper with Chrome driver"""
        self.base_url = "https://qudobeauty.com"
        self.products = []
        self.driver = self._setup_driver(headless)
        
    def _setup_driver(self, headless):
        """Configure and return Chrome WebDriver"""
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument('--headless=new')
        
        # Performance and stability options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # User agent to avoid detection
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        
        return driver
    
    def _wait_for_page_load(self, timeout=15):
        """Wait for page to fully load"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(2)  # Additional wait for dynamic content
        except TimeoutException:
            logger.warning("Page load timeout, continuing anyway")
    
    def _safe_find_element(self, by, value, parent=None):
        """Safely find element and return text or None"""
        try:
            element = parent.find_element(by, value) if parent else self.driver.find_element(by, value)
            return element.text.strip() if element.text else None
        except NoSuchElementException:
            return None
    
    def _safe_get_attribute(self, by, value, attribute, parent=None):
        """Safely get element attribute or None"""
        try:
            element = parent.find_element(by, value) if parent else self.driver.find_element(by, value)
            return element.get_attribute(attribute)
        except NoSuchElementException:
            return None
    
    def navigate_to_skincare(self):
        """Navigate to skincare products section"""
        logger.info("Navigating to Qudo Beauty...")
        self.driver.get(self.base_url)
        self._wait_for_page_load()
        
        try:
            # Look for skincare category link
            skincare_selectors = [
                "//a[contains(text(), 'Skincare')]",
                "//a[contains(text(), 'SKINCARE')]",
                "//a[contains(@href, 'skincare')]",
                "//nav//a[contains(text(), 'Skin')]"
            ]
            
            for selector in skincare_selectors:
                try:
                    skincare_link = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    logger.info("Found skincare category, clicking...")
                    skincare_link.click()
                    self._wait_for_page_load()
                    return True
                except TimeoutException:
                    continue
            
            # If no category found, try to find product links directly
            logger.warning("Skincare category not found, searching for products on main page")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to skincare: {e}")
            return False
    
    def extract_product_links(self, max_products=30):
        """Extract product page URLs"""
        logger.info("Extracting product links...")
        
        # Scroll to load more products
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        max_scrolls = 5
        
        while scroll_attempts < max_scrolls:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                break
            
            last_height = new_height
            scroll_attempts += 1
        
        # Find product links using multiple selectors
        product_links = set()
        link_selectors = [
            "//a[contains(@href, '/products/')]",
            "//a[@class and contains(@class, 'product')]",
            "//div[contains(@class, 'product')]//a",
            "//article//a"
        ]
        
        for selector in link_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for elem in elements:
                    href = elem.get_attribute('href')
                    if href and '/products/' in href and 'skincare' in href.lower() or len(product_links) < max_products:
                        product_links.add(href)
                        if len(product_links) >= max_products:
                            break
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
            
            if len(product_links) >= max_products:
                break
        
        logger.info(f"Found {len(product_links)} product links")
        return list(product_links)[:max_products]
    
    def scrape_product_page(self, url):
        """Scrape individual product page"""
        logger.info(f"Scraping: {url}")
        
        try:
            self.driver.get(url)
            self._wait_for_page_load()
            
            product_data = {
                'product_name': None,
                'brand': 'Qudo Beauty',
                'category': None,
                'ingredients': None,
                'size': None,
                'image_url': None,
                'product_url': url
            }
            
            # Product name
            name_selectors = [
                (By.CSS_SELECTOR, "h1.product-title"),
                (By.CSS_SELECTOR, "h1.product__title"),
                (By.XPATH, "//h1[contains(@class, 'product')]"),
                (By.TAG_NAME, "h1")
            ]
            
            for by, selector in name_selectors:
                product_data['product_name'] = self._safe_find_element(by, selector)
                if product_data['product_name']:
                    break
            
            # Category/Type
            category_selectors = [
                (By.CSS_SELECTOR, ".product-type"),
                (By.CSS_SELECTOR, ".breadcrumb a:last-child"),
                (By.XPATH, "//span[contains(@class, 'category')]"),
                (By.XPATH, "//a[contains(@href, 'collections')]")
            ]
            
            for by, selector in category_selectors:
                product_data['category'] = self._safe_find_element(by, selector)
                if product_data['category']:
                    break
            
            # Ingredients
            ingredient_selectors = [
                (By.XPATH, "//*[contains(text(), 'Ingredients')]/following-sibling::*"),
                (By.XPATH, "//*[contains(text(), 'INGREDIENTS')]/following-sibling::*"),
                (By.CSS_SELECTOR, ".ingredients"),
                (By.CSS_SELECTOR, "[class*='ingredient']")
            ]
            
            for by, selector in ingredient_selectors:
                product_data['ingredients'] = self._safe_find_element(by, selector)
                if product_data['ingredients']:
                    break
            
            # Size/Packaging
            size_selectors = [
                (By.CSS_SELECTOR, ".product-size"),
                (By.CSS_SELECTOR, ".variant-option"),
                (By.XPATH, "//*[contains(text(), 'Size')]/following-sibling::*"),
                (By.CSS_SELECTOR, "select option[selected]")
            ]
            
            for by, selector in size_selectors:
                product_data['size'] = self._safe_find_element(by, selector)
                if product_data['size']:
                    break
            
            # Product Image
            image_selectors = [
                (By.CSS_SELECTOR, ".product-image img"),
                (By.CSS_SELECTOR, ".product__media img"),
                (By.XPATH, "//img[contains(@class, 'product')]"),
                (By.CSS_SELECTOR, "img[src*='product']")
            ]
            
            for by, selector in image_selectors:
                product_data['image_url'] = self._safe_get_attribute(by, selector, 'src')
                if product_data['image_url']:
                    # Ensure full URL
                    if product_data['image_url'].startswith('//'):
                        product_data['image_url'] = 'https:' + product_data['image_url']
                    elif product_data['image_url'].startswith('/'):
                        product_data['image_url'] = self.base_url + product_data['image_url']
                    break
            
            # Extract additional info from meta tags if needed
            if not product_data['product_name']:
                product_data['product_name'] = self._safe_get_attribute(
                    By.CSS_SELECTOR, 
                    "meta[property='og:title']", 
                    'content'
                )
            
            if not product_data['image_url']:
                product_data['image_url'] = self._safe_get_attribute(
                    By.CSS_SELECTOR, 
                    "meta[property='og:image']", 
                    'content'
                )
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error scraping product {url}: {e}")
            return None
    
    def scrape_products(self, max_products=30):
        """Main scraping method"""
        try:
            # Navigate to skincare section
            self.navigate_to_skincare()
            
            # Get product links
            product_links = self.extract_product_links(max_products)
            
            if not product_links:
                logger.warning("No product links found, trying alternative approach")
                # Try direct URL if available
                product_links = [f"{self.base_url}/collections/skincare"]
            
            # Scrape each product
            for i, link in enumerate(product_links, 1):
                logger.info(f"Progress: {i}/{len(product_links)}")
                product_data = self.scrape_product_page(link)
                
                if product_data and product_data['product_name']:
                    self.products.append(product_data)
                    logger.info(f"Successfully scraped: {product_data['product_name']}")
                
                # Be respectful - add delay between requests
                time.sleep(1)
            
            logger.info(f"Scraping complete! Collected {len(self.products)} products")
            
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
        
        finally:
            self.driver.quit()
    
    def export_to_excel(self, filename="qudo_beauty_skincare_products.xlsx"):
        """Export scraped data to Excel"""
        if not self.products:
            logger.warning("No products to export")
            return
        
        df = pd.DataFrame(self.products)
        
        # Reorder columns
        column_order = [
            'product_name', 'brand', 'category', 
            'ingredients', 'size', 'image_url', 'product_url'
        ]
        df = df[column_order]
        
        # Export to Excel with formatting
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Skincare Products')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Skincare Products']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
        
        logger.info(f"Data exported to {filename}")
        print(f"\n✓ Successfully exported {len(self.products)} products to {filename}")


def main():
    """Main execution function"""
    print("=" * 60)
    print("Qudo Beauty Skincare Scraper")
    print("=" * 60)
    
    # Initialize scraper
    scraper = QudobeautyScraper(headless=True)
    
    # Scrape products
    scraper.scrape_products(max_products=30)
    
    # Export to Excel
    scraper.export_to_excel("qudo_beauty_skincare_products.xlsx")
    
    print("\n" + "=" * 60)
    print("Scraping Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()