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
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Cache-Control': 'no-cache'
    }

def generate_wb_card_url(product_id):
    """Генерирует URL для получения карточки товара WB"""
    try:
        # Конвертируем в строку и берем нужные части
        id_str = str(product_id)
        
        # vol - первые 3-4 цифры
        if len(id_str) >= 4:
            vol = id_str[:3]
        else:
            vol = id_str
            
        # part - первые 5-6 цифр
        if len(id_str) >= 6:
            part = id_str[:5]
        elif len(id_str) >= 5:
            part = id_str[:4]
        else:
            part = id_str
        
        # Пробуем разные basket серверы
        basket_servers = ['01', '02', '03', '04', '05']
        
        urls = []
        for server in basket_servers:
            url = f"https://basket-{server}.wbbasket.ru/vol{vol}/part{part}/{product_id}/info/ru/card.json"
            urls.append(url)
            
        return urls
        
    except Exception as e:
        logger.error(f"Ошибка генерации URL для {product_id}: {str(e)}")
        return []

def parse_wb_product(product_id):
    """Парсит товар WB по ID"""
    logger.info(f"Начинаем парсинг товара: {product_id}")
    
    # Метод 1: Новый рабочий API
    api_result = try_new_wb_api(product_id)
    if api_result['success']:
        logger.info(f"Товар {product_id} получен через новый API")
        return api_result
    
    # Метод 2: HTML парсинг как fallback
    html_result = try_html_parsing(product_id)
    if html_result['success']:
        logger.info(f"Товар {product_id} получен через HTML")
        return html_result
    
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

def try_new_wb_api(product_id):
    """Пробует новый рабочий API WB"""
    urls = generate_wb_card_url(product_id)
    
    for url in urls:
        try:
            logger.info(f"Пробуем новый API: {url}")
            
            headers = get_random_headers()
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    # Проверяем что это валидная карточка товара
                    if 'nm_id' in data and data.get('nm_id') == int(product_id):
                        logger.info(f"✅ Товар найден через API: {data.get('imt_name', 'Без названия')}")
                        
                        result = extract_from_new_api(data)
                        if result['name'] and result['name'] != f'Товар {product_id}':
                            return {'success': True, 'data': result}
                
                except json.JSONDecodeError:
                    logger.error(f"Ошибка парсинга JSON: {url}")
                    continue
            else:
                logger.info(f"API {url} ответил: {response.status_code}")
            
            time.sleep(1)  # Пауза между попытками
            
        except Exception as e:
            logger.error(f"Ошибка API {url}: {str(e)}")
            continue
    
    return {'success': False}

def extract_from_new_api(data):
    """Извлекает данные из нового API"""
    try:
        # Основные поля
        name = data.get('imt_name', '')
        description = data.get('description', '')
        
        # Категория и подкатегория
        category = data.get('subj_name', '') or data.get('subj_root_name', '')
        
        # Бренд
        brand = ''
        if 'selling' in data and 'brand_name' in data['selling']:
            brand = data['selling']['brand_name']
        
        # Характеристики
        characteristics = ''
        if 'options' in data:
            chars = []
            for option in data['options']:
                name_char = option.get('name', '')
                value_char = option.get('value', '')
                
                if name_char and value_char:
                    chars.append(f"{name_char} / {value_char}")
            
            characteristics = '::'.join(chars)
        
        # Цена нужно получить отдельно (этот API не содержит цены)
        price = get_product_price(data.get('nm_id', ''))
        
        # Рейтинг (может быть в отдельном API)
        rating = ''
        
        logger.info(f"Извлечены данные: {name[:50]}...")
        
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
        logger.error(f"Ошибка извлечения данных: {str(e)}")
        return {
            'category': '',
            'brand': '',
            'rating': '',
            'price': '',
            'name': '',
            'description': '',
            'characteristics': ''
        }

def get_product_price(product_id):
    """Получает цену товара из API цен"""
    try:
        # API для получения цены
        price_url = f"https://card.wb.ru/cards/detail?appType=1&curr=rub&dest=-1257786&nm={product_id}"
        
        headers = get_random_headers()
        response = requests.get(price_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'data' in data and 'products' in data['data'] and data['data']['products']:
                product = data['data']['products'][0]
                
                if 'salePriceU' in product:
                    return str(round(product['salePriceU'] / 100))
                elif 'priceU' in product:
                    return str(round(product['priceU'] / 100))
        
    except Exception as e:
        logger.error(f"Ошибка получения цены: {str(e)}")
    
    return ''

def try_html_parsing(product_id):
    """Парсит HTML страницу товара (fallback)"""
    url = f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"
    
    try:
        logger.info(f"Загружаем HTML: {url}")
        
        headers = get_random_headers()
        headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Upgrade-Insecure-Requests': '1'
        })
        
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
        
        # Название из title
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
            title = re.sub(r'\s*купить.*$', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*-\s*wildberries.*$', '', title, flags=re.IGNORECASE)
            if len(title) > 10:
                result['name'] = title
        
        # H1 как альтернатива
        if not result['name']:
            h1_tag = soup.find('h1')
            if h1_tag:
                h1_text = h1_tag.get_text().strip()
                if 'unsuccessfulLoad' not in h1_text and len(h1_text) > 5:
                    result['name'] = h1_text
        
        # Описание из meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '').strip()
            if len(description) > 20:
                result['description'] = description
        
        # Если название не найдено
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
        'version': '2.0',
        'status': 'active',
        'api': 'Updated with working WB endpoints',
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
            # Задержка между товарами
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
