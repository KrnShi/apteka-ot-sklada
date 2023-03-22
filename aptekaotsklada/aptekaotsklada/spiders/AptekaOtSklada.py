import scrapy
from scrapy.http.response.html import HtmlResponse
from scrapy import Request, Selector
from datetime import datetime
from w3lib.url import add_or_replace_parameters, url_query_parameter
from bs4 import BeautifulSoup
import re

class AptekaotskladaSpider(scrapy.Spider):
    name = "AptekaOtSklada"
    allowed_domains = ["apteka-ot-sklada.ru"]
    start_urls = [
        "https://apteka-ot-sklada.ru/catalog/sredstva-gigieny/uhod-za-polostyu-rta/zubnye-niti_-ershiki",
        "https://apteka-ot-sklada.ru/catalog/sredstva-gigieny/vlazhnye-salfetki/vlazhnye-salfetki-dlya-detey",
        "https://apteka-ot-sklada.ru/catalog/sredstva-gigieny/mylo/mylo-zhidkoe",
        "https://apteka-ot-sklada.ru/catalog/medikamenty-i-bady/vitaminy-i-mikroelementy/vitaminy-drugie"
    ]
    custom_settings = {

    }
    city_cookies = {"city": 92}
    api_catalog_format = "https://apteka-ot-sklada.ru/api/catalog/search?slug={slug}&offset=0&limit=12"
    api_item_format = "https://apteka-ot-sklada.ru/api/catalog/{id_item}"
    url_item_format = "https://apteka-ot-sklada.ru/catalog/{slug}_{id}"
    def start_requests(self):
        for url in self.start_urls:
            slug = url.split('catalog/')[1]
            url = self.api_catalog_format.format(slug=slug)
            yield Request(url=url, callback=self.parse_pages,
                          cookies=self.city_cookies
                          )


    def parse_pages(self, response: HtmlResponse):
        json_data = response.json()
        items = json_data["goods"]
        for item in items:
            url = self.api_item_format.format(id_item=item['id'])
            # url = f'{self.api_item_format}{item["id"]}'
            yield Request(url=url, callback=self.parse_item_product,
                          cookies=self.city_cookies
                    )
        if items:
            offset = int(url_query_parameter(response.url, 'offset',0))
            offset += 12
            url = add_or_replace_parameters(response.url, {'offset': offset})
            yield Request(url=url, callback=self.parse_pages, cookies=self.city_cookies)



    def parse_item_product(self, response: HtmlResponse):
        item = response.json()
        yield {
            "timestamp": datetime.timestamp(datetime.now()),
            "RPC": item["id"],
            "url": self.url_item_format.format(slug=item["slug"], id=item["id"]),
            "title": item["name"],
            "marketing_tags": self.__get_marketing_tags(response),
            "brand": item["producer"] or "",
            "section": self.__get_section(response),
            "price_data": self.__get_price_data(response),
            "stock": self.__get_stock(response),
            "assets": self.__get_assets(response),
            "metadata": self.__get_metadata(response),
            "variants": 1,
        }


    def __get_metadata(self, response):
        description = response.json()["description"]
        if description:
            soup = BeautifulSoup(description, features="html.parser")
            text_description = soup.get_text()
            text_description = self.__normal_form(text_description)
        else:
            text_description = None

        return  {
            "__description": text_description or "",
            "АРТИКУЛ": response.json()["id"],
            "СТРАНА ПРОИЗВОДИТЕЛЬ": response.json()["country"]
        }

    def __normal_form(self, data):
        if data:
            data = data.replace('\n', '').strip().replace('\r','').replace('\t','').replace(' ','')
            for sp in sorted(re.compile('[ ]{2,}').findall(data))[::-1]:
                data = data.replace(sp, ' ')
        return data

    def __get_section(self, response):
        parents_sections = response.json()["category"]["parents"]
        section = response.json()["category"]["name"]
        list_section = ["Главная", "Каталог"]
        for parent in parents_sections:
            list_section.append(parent["name"])
        list_section.append(section)
        return list_section


    def __get_price_data(self, response):
        old_cost = response.json()["oldCost"]
        cost = response.json()["cost"]
        if cost and old_cost:
            sale_tag = f"Скидка {100.0 - (cost / old_cost) * 100}%"
        else:
            sale_tag = ""
        if old_cost is None:
            old_cost = cost
        return {
            "current": cost or 0.0,
            "original": old_cost or 0.0,
            "sale_tag": sale_tag
        }


    def __get_marketing_tags(self, response):
        marketing_tags = response.json()["stickers"]
        result = []
        if marketing_tags:
            for tag in marketing_tags:
                result.append(tag["name"])
        return result or []


    def __get_stock(self, response):
        return {
            "in_stock": response.json()['inStock'],
            "count": 0
        }


    def __get_assets(self, response):
        images = response.json()["images"]
        result = []
        if images:
            for image in images:
                result.append('https://apteka-ot-sklada.ru' + image)
        return {
            "main_image": result[0] or '',
            "set_images": result or [],
            "view360": [],
            "video": []
        }



