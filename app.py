from flask import Flask, request, jsonify
import os
from flask_cors import CORS
import requests
import time
import random
import re
import json
from bs4 import BeautifulSoup
import logging
import brotli

app = Flask(__name__)
CORS(app)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_basket_url(product_id):
    """Генерирует URL для basket API на основе ID товара"""
    try:
        id_str = str(product_id)
        
        # Список серверов для попытки - добавлены basket-11 и basket-12
        servers = ['basket-01', 'basket-02', 'basket-03', 'basket-04', 'basket-05', 'basket-11', 'basket-12']
        
        urls = []
        
        for server in servers:
            # Вариант 1: стандартный (первые 3 и 5 цифр)
            if len(id_str) >= 5:
                vol1 = id_str[:3]
                part1 = id_str[:5]
                url1 = f"https://{server}.wbbasket.ru/vol{vol1}/part{part1}/{product_id}/info/ru/card.json"
                urls.append(url1)
            
            # Вариант 2: для длинных ID (первые 4 и 6 цифр)
            if len(id_str) >= 6:
                vol2 = id_str[:4]
                part2 = id_str[:6]
                url2 = f"https://{server}.wbbasket.ru/vol{vol2}/part{part2}/{product_id}/info/ru/card.json"
                urls.append(url2)
            
            # Вариант 3: альтернативная логика (первые 2 и 4 цифры)
            if len(id_str) >= 4:
                vol3 = id_str[:2]
                part3 = id_str[:4]
                url3 = f"https://{server}.wbbasket.ru/vol{vol3}/part{part3}/{product_id}/info/ru/card.json"
                urls.append(url3)
        
        return urls
        
    except Exception as e:
        logger.error(f"Ошибка генерации URL для {product_id}: {e}")
        return []

def fetch_product_data(product_id):
    """Получает данные товара через basket API"""
    urls = generate_basket_url(product_id)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.wildberries.ru/',
        'Origin': 'https://www.wildberries.ru'
    }
    
    for url in urls:
        try:
            logger.info(f"Пробуем новый API: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    content_encoding = response.headers.get('content-encoding', '').lower()
                    logger.info(f"✅ Получен ответ 200 от {url}, размер: {len(response.content)}")
                    logger.info(f"Кодировка: {content_encoding}")
                    
                    # Альтернативный подход - отключаем сжатие в headers
                    if content_encoding == 'br':
                        logger.info("Обнаружен Brotli, делаем новый запрос без сжатия")
                        
                        simple_headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Accept': 'application/json',
                            'Referer': 'https://www.wildberries.ru/'
                        }
                        
                        simple_response = requests.get(url, headers=simple_headers, timeout=10)
                        
                        if simple_response.status_code == 200:
                            response_text = simple_response.text
                            logger.info(f"✅ Получен несжатый ответ, размер: {len(response_text)}")
                        else:
                            logger.error(f"Несжатый запрос неудачен: {simple_response.status_code}")
                            continue
                    else:
                        response_text = response.text
                        logger.info(f"✅ Обработано как {content_encoding or 'несжатое'}")
                    
                    logger.info(f"Первые 100 символов: {response_text[:100]}")
                    
                    data = json.loads(response_text)
                    logger.info(f"✅ Успешно получен и распарсен JSON от {url}")
                    return parse_product_data(data)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга JSON: {url} - {e}")
                    continue
                except Exception as e:
                    logger.error(f"Общая ошибка обработки: {url} - {e}")
                    continue
            else:
                logger.info(f"API {url} ответил: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка запроса {url}: {e}")
            continue
    
    return None

def parse_product_data(data):
    """Парсит данные товара из JSON ответа basket API"""
    try:
        name = data.get('imt_name', '')
        category = data.get('subj_name', '')
        description = data.get('description', '')
        
        selling = data.get('selling', {})
        brand = selling.get('brand_name', '')
        
        characteristics = []
        options = data.get('options', [])
        for option in options:
            name_char = option.get('name', '')
            value_char = option.get('value', '')
            if name_char and value_char:
                characteristics.append(f"{name_char}: {value_char}")
        
        characteristics_str = " | ".join(characteristics[:10])
        
        logger.info(f"✅ Распарсены данные: название='{name}', бренд='{brand}', категория='{category}'")
        
        return {
            'name': name,
            'brand': brand,
            'category': category,
            'description': description,
            'characteristics': characteristics_str,
            'price': '',
            'rating': ''
        }
        
    except Exception as e:
        logger.error(f"Ошибка парсинга данных товара: {e}")
        return None

def fetch_html_fallback(product_id):
    """Fallback метод - парсинг HTML страницы"""
    try:
        url = f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.wildberries.ru/'
        }
        
        logger.info(f"Загружаем HTML: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            html = response.text
            
            soup = BeautifulSoup(html, 'html.parser')
            
            title_tag = soup.find('title')
            name = ''
            if title_tag:
                title_text = title_tag.get_text().strip()
                name = re.sub(r'\s*купить.*$|.*wildberries.*$', '', title_text, flags=re.IGNORECASE).strip()
            
            price = ''
            price_patterns = [
                r'(\d+)\s*₽',
                r'₽\s*(\d+)',
                r'"price"[:\s]*(\d+)',
                r'"priceU"[:\s]*(\d+)'
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, html)
                if match:
                    price_val = int(match.group(1))
                    if price_val > 10000:
                        price_val = price_val // 100
                    if 1 <= price_val <= 100000:
                        price = str(price_val)
                        break
            
            if name and len(name) > 5:
                logger.info(f"✅ HTML парсинг успешен: {name}")
                return {
                    'name': name,
                    'brand': '',
                    'category': 'Определена через HTML',
                    'description': 'Загружено через HTML парсинг',
                    'characteristics': '',
                    'price': price,
                    'rating': ''
                }
                
    except Exception as e:
        logger.error(f"Ошибка HTML парсинга: {e}")
        
    return None

@app.route('/')
def home():
    return jsonify({
        'service': 'WB Parser Service',
        'version': '2.0',
        'status': 'active',
        'endpoints': {
            '/health': 'Health check',
            '/parse/<product_id>': 'Parse single product',
            '/parse': 'Parse multiple products (POST)'
        }
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time()
    })

@app.route('/parse/<product_id>')
def parse_single_product(product_id):
    """Парсит один товар по ID"""
    logger.info(f"Запрос на парсинг товара: {product_id}")
    
    try:
        logger.info(f"Начинаем парсинг товара: {product_id}")
        
        product_data = fetch_product_data(product_id)
        
        if product_data:
            logger.info(f"✅ Товар {product_id} успешно распарсен через API")
            return jsonify({
                'success': True,
                'product_id': product_id,
                'data': product_data
            })
        
        logger.info(f"API не сработал, пробуем HTML парсинг для {product_id}")
        html_data = fetch_html_fallback(product_id)
        
        if html_data:
            logger.info(f"✅ Товар {product_id} успешно распарсен через HTML")
            return jsonify({
                'success': True,
                'product_id': product_id,
                'data': html_data
            })
        
        logger.error(f"Не удалось получить данные товара {product_id}")
        return jsonify({
            'success': False,
            'product_id': product_id,
            'error': 'Не удалось получить данные товара',
            'data': {
                'name': f'Товар {product_id}',
                'brand': 'Не определен',
                'category': 'Не определена',
                'description': 'Не загружено',
                'characteristics': '',
                'price': '',
                'rating': ''
            }
        })
        
    except Exception as e:
        logger.error(f"Критическая ошибка при парсинге {product_id}: {e}")
        return jsonify({
            'success': False,
            'product_id': product_id,
            'error': str(e),
            'data': {
                'name': f'Товар {product_id}',
                'brand': 'Ошибка сервиса',
                'category': 'Ошибка сервиса',
                'description': 'Ошибка обработки',
                'characteristics': '',
                'price': '',
                'rating': ''
            }
        })

@app.route('/parse', methods=['POST'])
def parse_multiple_products():
    """Парсит несколько товаров за раз (до 10)"""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        
        if not product_ids:
            return jsonify({
                'success': False,
                'error': 'Не указаны ID товаров'
            })
        
        if len(product_ids) > 10:
            return jsonify({
                'success': False,
                'error': 'Максимум 10 товаров за раз'
            })
        
        results = []
        
        for product_id in product_ids:
            logger.info(f"Групповой парсинг товара: {product_id}")
            
            product_data = fetch_product_data(product_id)
            
            if product_data:
                results.append({
                    'product_id': product_id,
                    'success': True,
                    'data': product_data
                })
            else:
                results.append({
                    'product_id': product_id,
                    'success': False,
                    'data': {
                        'name': f'Товар {product_id}',
                        'brand': 'Не определен',
                        'category': 'Не определена', 
                        'description': 'Не загружено',
                        'characteristics': '',
                        'price': '',
                        'rating': ''
                    }
                })
            
            time.sleep(0.5)
        
        success_count = sum(1 for r in results if r['success'])
        
        return jsonify({
            'success': True,
            'total': len(results),
            'successful': success_count,
            'failed': len(results) - success_count,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Ошибка группового парсинга: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
