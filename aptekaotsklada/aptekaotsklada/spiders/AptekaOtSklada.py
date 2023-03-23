import re
from collections import defaultdict
from datetime import datetime

import scrapy
from bs4 import BeautifulSoup
from scrapy import Request
from scrapy.http.response.html import HtmlResponse
from w3lib.url import add_or_replace_parameters, url_query_parameter


class AptekaotskladaSpider(scrapy.Spider):
    name = "AptekaOtSklada"
    allowed_domains = ["apteka-ot-sklada.ru"]
    start_urls = [
        "https://apteka-ot-sklada.ru/catalog/sredstva-gigieny/uhod-za-polostyu-rta/zubnye-niti_-ershiki",
        "https://apteka-ot-sklada.ru/catalog/sredstva-gigieny/vlazhnye-salfetki/vlazhnye-salfetki-dlya-detey",
        "https://apteka-ot-sklada.ru/catalog/sredstva-gigieny/mylo/mylo-zhidkoe",
        "https://apteka-ot-sklada.ru/catalog/medikamenty-i-bady/vitaminy-i-mikroelementy/vitaminy-drugie",
    ]
    city_cookies = {"city": 92}
    api_catalog_format = "https://apteka-ot-sklada.ru/api/catalog/search?slug={slug}&offset=0&limit=12"
    api_item_format = "https://apteka-ot-sklada.ru/api/catalog/{id_item}"
    url_item_format = "https://apteka-ot-sklada.ru/catalog/{slug}_{id}"

    def start_requests(self):
        for url in self.start_urls:
            slug = url.split('catalog/')[1]
            url = self.api_catalog_format.format(slug=slug)
            yield Request(url=url, callback=self.parse_pages, cookies=self.city_cookies)

    def parse_pages(self, response: HtmlResponse):
        json_data = response.json()
        items = json_data["goods"]
        for item in items:
            url = self.api_item_format.format(id_item=item['id'])
            yield Request(url=url, callback=self.parse_item_product, cookies=self.city_cookies)
        if items:
            offset = int(url_query_parameter(response.url, 'offset', 0))
            offset += 12
            url = add_or_replace_parameters(response.url, {'offset': offset})
            yield Request(url=url, callback=self.parse_pages, cookies=self.city_cookies)

    def parse_item_product(self, response: HtmlResponse):
        item = response.json()
        result = {}
        result["timestamp"] = datetime.timestamp(datetime.now())
        result["RPC"] = item["id"]
        result["url"] = self.url_item_format.format(slug=item["slug"], id=item["id"])
        result["title"] = item["name"]
        result["marketing_tags"] = self.get_marketing_tags(response)
        result["brand"] = item["producer"] or ""
        result["section"] = self.get_section(response)
        result["price_data"] = self.get_price_data(response)
        result["stock"] = self.get_stock(response)
        result["assets"] = self.get_assets(response)
        result["metadata"] = self.get_metadata(response)
        result["variants"] = 1

        yield result

    def get_metadata(self, response):
        description = response.json()["description"]
        metadata = defaultdict(str)
        metadata["__description"] = ""
        metadata["АРТИКУЛ"] = response.json()["id"]
        metadata["СТРАНА ПРОИЗВОДИТЕЛЬ"] = response.json()["country"]
        if description:
            description_soup = BeautifulSoup(description, features="html.parser")
            re_keys = re.compile(
                "противопоказания|состав|оболочка|область|показания|описание|форма|характеристика|дозировка|предосторожности")
            key = None
            for desc in description_soup:
                desc = self.normal_form(str(desc).lower())
                if re_keys.search(desc):
                    key = desc
                elif key:
                    metadata[key] += desc
                metadata['__description'] += f' {desc}'

        return metadata

    def normal_form(self, data):
        if data:
            data = re.sub('[<p>:</p><h2></h2>\n\r\t \" ­strong]', '', data).strip()
            data = re.sub('[ ]{2,}', ' ', data)
        return data

    def get_section(self, response):
        parents_sections = response.json()["category"]["parents"]
        section = response.json()["category"]["name"]
        list_section = ["Главная", "Каталог"]
        for parent in parents_sections:
            list_section.append(parent["name"])
        list_section.append(section)
        return list_section

    def get_price_data(self, response):
        old_cost = response.json()["oldCost"]
        cost = response.json()["cost"]
        if cost and old_cost:
            sale_tag = f"Скидка {100.0 - (cost / old_cost) * 100}%"
        else:
            sale_tag = ""
        if old_cost is None:
            old_cost = cost
        result = {}
        result["current"] = cost or 0.0
        result["original"] = old_cost or 0.0
        result["sale_tag"] = sale_tag
        return result

    def get_marketing_tags(self, response):
        marketing_tags = response.json()["stickers"]
        result = []
        for tag in marketing_tags:
            result.append(tag["name"])
        return result

    def get_stock(self, response):
        result = {}
        result["in_stock"] = response.json()['inStock']
        result["count"] = 0
        return result

    def get_assets(self, response):
        images = response.json()["images"]
        result_images = []
        for image in images:
            result_images.append('https://apteka-ot-sklada.ru' + image)
        result = {}
        result["main_image"] = result_images[0] or ''
        result["set_images"] = result_images or []
        result["view360"] = []
        result["video"] = []
        return result
