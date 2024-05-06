import asyncio
import requests
from bs4 import BeautifulSoup

async def scrape_search_result_pages_async(search_result_url, semaphore):
    async with semaphore:
        response = requests.get(search_result_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Add a delay between requests
        await asyncio.sleep(1)

        # Get the links to the next pages
        next_page_url = soup.find('a', {'class': 'next'})
        if next_page_url:
            next_page_url = "https://ovoko.pl" + next_page_url['href']

        # Get the product information
        product_info_list = soup.find_all('div', {'class': 'product-info'})
        for product_info in product_info_list:
            product_name = product_info.find('h2').text
            product_url = "https://ovoko.pl" + product_info.find('a')['href']
            product_image_url = product_info.find('img')['src']
            product_count = int(product_info.find('span', {'class': 'count'}).text)

            product_info = {
                'product_name': product_name,
                'product_url': product_url,
                'product_image_url': product_image_url,
                'product_count': product_count
            }

            product_data.append(product_info)

        if next_page_url:
            await scrape_search_result_pages_async(next_page_url, semaphore)

# List for storing product data
product_data = []

# Semaphore for limiting the number of concurrent requests
semaphore = asyncio.Semaphore(5)

# Start URL
start_url = "https://ovoko.pl/szukaj?man_id=66&cpc=1120&mfi=66;&prs=1"

# File for storing the test output
output_file = open("max_streams_test_output.txt", "a")

# Test the maximum number of parallel parser streams
for i in range(1, 21):
    semaphore.release()
    asyncio.run(scrape_search_result_pages_async(start_url, semaphore))
    print(f"{i} streams: {len(product_data)} products")

output_file.close()