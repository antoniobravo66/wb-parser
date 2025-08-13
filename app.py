from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import time
import random
import re
import json
from bs4 import BeautifulSoup
import logging

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для Google Apps Script

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Список User-Agent для ротации
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
]

def get_random_headers():
    """Возвращает случайные headers для имитации браузера"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }

def parse_wb_product(product_id):
    """Парсит товар WB по ID"""
    logger.info(f"Начинаем парсинг товара: {product_id}")
    
    # Метод 1: Попробуем API endpoints
    api_result = try_api_endpoints(product_id)
    if api_result['success']:
        logger.info(f"Товар {product_id} получен через API")
        return api_result
    
    # Метод 2: HTML парсинг
    html_result = try_html_parsing(product_id)
    if html_result['success']:
        logger.info(f"Товар {product_id} получен через HTML")
        return html_result
    
    # Метод 3: Поисковый API
    search_result = try_search_api(product_id)
    if search_result['success']:
        logger.info(f"Товар {product_id} получен через поиск")
        return search_result
    
    # Если все методы не сработали
    logger.error(f"Не удалось получить данные товара {product_id}")
    return {
        'success': False,
        'error': 'Не удалось получить данные товара',
        'data': {
            'category': 'Не определена',
            'brand': 'Не определен',
            'rating': '',
            'price': '',
            'name': f'Товар {product_id}',
            'description': 'Не загружено',
            'characteristics': ''
        }
    }

def try_api_endpoints(product_id):
    """Пробует различные API endpoints"""
    endpoints = [
        f"https://card.wb.ru/cards/detail?appType=1&curr=rub&dest=-1257786&nm={product_id}",
        f"https://wbx-content-v2.wbstatic.net/cards/v1/detail?appType=1&curr=rub&dest=-1257786&nm={product_id}"
    ]
    
    for endpoint in endpoints:
        try:
            logger.info(f"Пробуем API: {endpoint}")
            
            headers = get_random_headers()
            headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Origin': 'https://www.wildberries.ru',
                'Referer': 'https://www.wildberries.ru/'
            })
            
            response = requests.get(endpoint, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('data') and data['data'].get('products'):
                    product = data['data']['products'][0]
                    
                    result = extract_from_api_response(product)
                    if result['name'] and result['name'] != f'Товар {product_id}':
                        return {'success': True, 'data': result}
            
            time.sleep(1)  # Пауза между попытками
            
        except Exception as e:
            logger.error(f"Ошибка API {endpoint}: {str(e)}")
            continue
    
    return {'success': False}

def try_html_parsing(product_id):
    """Парсит HTML страницу товара"""
    url = f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"
    
    try:
        logger.info(f"Загружаем HTML: {url}")
        
        headers = get_random_headers()
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            html = response.text
            
            # Проверяем что это не страница ошибки
            if 'unsuccessfulLoad' in html or len(html) < 5000:
                logger.warning(f"Получена страница ошибки для {product_id}")
                return {'success': False}
            
            soup = BeautifulSoup(html, 'html.parser')
            result = extract_from_html(soup, product_id)
            
            if result['name'] and 'unsuccessfulLoad' not in result['name']:
                return {'success': True, 'data': result}
        
    except Exception as e:
        logger.error(f"Ошибка HTML парсинга для {product_id}: {str(e)}")
    
    return {'success': False}

def try_search_api(product_id):
    """Пробует найти товар через поисковый API"""
    search_url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?TestGroup=no_test&TestID=no_test&appType=1&curr=rub&dest=-1257786&query={product_id}&resultset=catalog&sort=popular&spp=24&suppressSpellcheck=false"
    
    try:
        logger.info(f"Поиск через Search API: {product_id}")
        
        headers = get_random_headers()
        headers.update({
            'Accept': 'application/json',
            'Origin': 'https://www.wildberries.ru',
            'Referer': 'https://www.wildberries.ru/'
        })
        
        response = requests.get(search_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('data') and data['data'].get('products'):
                products = data['data']['products']
                
                # Ищем точное совпадение ID
                for product in products:
                    if str(product.get('id', '')) == str(product_id):
                        result = extract_from_api_response(product)
                        return {'success': True, 'data': result}
                
                # Если точное совпадение не найдено, берем первый
                if products:
                    result = extract_from_api_response(products[0])
                    return {'success': True, 'data': result}
        
    except Exception as e:
        logger.error(f"Ошибка Search API для {product_id}: {str(e)}")
    
    return {'success': False}

def extract_from_api_response(product):
    """Извлекает данные из API ответа"""
    try:
        # Базовые поля
        category = product.get('subj_name') or product.get('subj_root_name') or ''
        brand = product.get('brand') or ''
        rating = product.get('rating') or product.get('reviewRating') or ''
        name = product.get('name') or ''
        description = product.get('description') or ''
        
        # Цена
        price = ''
        if product.get('salePriceU'):
            price = str(round(product['salePriceU'] / 100))
        elif product.get('priceU'):
            price = str(round(product['priceU'] / 100))
        
        # Характеристики
        characteristics = ''
        if product.get('characteristics'):
            chars = []
            for char in product['characteristics']:
                name_char = char.get('name', '')
                value_char = ''
                
                if char.get('value'):
                    if isinstance(char['value'], list):
                        value_char = ';'.join(map(str, char['value']))
                    else:
                        value_char = str(char['value'])
                elif char.get('values'):
                    if isinstance(char['values'], list):
                        value_char = ';'.join(map(str, char['values']))
                    else:
                        value_char = str(char['values'])
                
                if name_char and value_char:
                    chars.append(f"{name_char} / {value_char}")
            
            characteristics = '::'.join(chars)
        
        return {
            'category': category,
            'brand': brand,
            'rating': rating,
            'price': price,
            'name': name,
            'description': description,
            'characteristics': characteristics
        }
        
    except Exception as e:
        logger.error(f"Ошибка извлечения данных из API: {str(e)}")
        return {
            'category': '',
            'brand': '',
            'rating': '',
            'price': '',
            'name': '',
            'description': '',
            'characteristics': ''
        }

def extract_from_html(soup, product_id):
    """Извлекает данные из HTML"""
    try:
        result = {
            'category': '',
            'brand': '',
            'rating': '',
            'price': '',
            'name': '',
            'description': '',
            'characteristics': ''
        }
        
        # Название
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
            # Очищаем от лишнего
            title = re.sub(r'\s*купить.*$', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*-\s*wildberries.*$', '', title, flags=re.IGNORECASE)
            if len(title) > 10:
                result['name'] = title
        
        # H1
        h1_tag = soup.find('h1')
        if h1_tag and not result['name']:
            h1_text = h1_tag.get_text().strip()
            if 'unsuccessfulLoad' not in h1_text and len(h1_text) > 5:
                result['name'] = h1_text
        
        # Описание из meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '').strip()
            if len(description) > 20:
                result['description'] = description
        
        # Цена (простой поиск)
        price_patterns = [
            r'(\d+)\s*₽',
            r'₽\s*(\d+)',
            r'"price":\s*(\d+)',
            r'"salePriceU":\s*(\d+)'
        ]
        
        html_text = str(soup)
        for pattern in price_patterns:
            match = re.search(pattern, html_text)
            if match:
                price = int(match.group(1))
                if price > 10000:  # Если в копейках
                    price = round(price / 100)
                if price > 0 and price < 1000000:
                    result['price'] = str(price)
                    break
        
        # Если название не найдено, используем ID
        if not result['name']:
            result['name'] = f'Товар {product_id}'
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка извлечения из HTML: {str(e)}")
        return {
            'category': '',
            'brand': '',
            'rating': '',
            'price': '',
            'name': f'Товар {product_id}',
            'description': '',
            'characteristics': ''
        }

@app.route('/', methods=['GET'])
def home():
    """Главная страница сервиса"""
    return jsonify({
        'service': 'WB Parser',
        'version': '1.0',
        'status': 'active',
        'endpoints': {
            'parse_product': '/parse/{product_id}',
            'parse_multiple': '/parse',
            'health': '/health'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Проверка работоспособности"""
    return jsonify({'status': 'healthy', 'timestamp': time.time()})

@app.route('/parse/<product_id>', methods=['GET'])
def parse_single_product(product_id):
    """Парсит один товар по ID"""
    try:
        logger.info(f"Запрос на парсинг товара: {product_id}")
        
        # Добавляем случайную задержку
        time.sleep(random.uniform(1, 3))
        
        result = parse_wb_product(product_id)
        
        return jsonify({
            'success': result['success'],
            'product_id': product_id,
            'data': result['data'],
            'error': result.get('error')
        })
        
    except Exception as e:
        logger.error(f"Ошибка в parse_single_product: {str(e)}")
        return jsonify({
            'success': False,
            'product_id': product_id,
            'error': str(e)
        }), 500

@app.route('/parse', methods=['POST'])
def parse_multiple_products():
    """Парсит несколько товаров"""
    try:
        data = request.get_json()
        product_ids = data.get('product_ids', [])
        
        if not product_ids:
            return jsonify({'error': 'product_ids required'}), 400
        
        if len(product_ids) > 10:
            return jsonify({'error': 'Maximum 10 products per request'}), 400
        
        logger.info(f"Запрос на парсинг {len(product_ids)} товаров")
        
        results = []
        for product_id in product_ids:
            # Добавляем задержку между товарами
            time.sleep(random.uniform(2, 4))
            
            result = parse_wb_product(str(product_id))
            results.append({
                'product_id': str(product_id),
                'success': result['success'],
                'data': result['data'],
                'error': result.get('error')
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'total': len(results)
        })
        
    except Exception as e:
        logger.error(f"Ошибка в parse_multiple_products: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
