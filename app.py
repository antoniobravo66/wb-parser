"""
Новый упрощенный WB парсер - только HTML текст
Заменяет сложный basket API на простой HTML парсинг
"""

from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import unquote

app = Flask(__name__)

# Браузерные headers для обхода блокировок
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
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

def clean_text(text):
    """Очистка HTML текста для лучшего анализа"""
    if not text:
        return ""
    
    # Убираем лишние пробелы и переносы
    text = ' '.join(text.split())
    
    # Убираем JS код и CSS
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Убираем HTML комментарии
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Ограничиваем размер (первые 50000 символов должно хватить)
    if len(text) > 50000:
        text = text[:50000] + "... [обрезано]"
    
    return text

def extract_product_html(product_id):
    """
    Простой HTML парсинг страницы товара WB
    Возвращает весь текст страницы для дальнейшего анализа
    """
    try:
        url = f"https://www.wildberries.ru/catalog/{product_id}/detail.aspx"
        print(f"🌐 Загружаем HTML: {url}")
        
        # Простой GET запрос
        response = requests.get(url, headers=BROWSER_HEADERS, timeout=15)
        
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}",
                "product_id": product_id
            }
        
        # Извлекаем весь текст из HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Получаем чистый текст
        page_text = soup.get_text(separator=' ', strip=True)
        
        # Очищаем текст
        clean_page_text = clean_text(page_text)
        
        if len(clean_page_text) < 100:
            return {
                "success": False,
                "error": "Слишком мало текста - возможно страница заблокирована",
                "product_id": product_id
            }
        
        print(f"✅ HTML текст получен: {len(clean_page_text)} символов")
        
        return {
            "success": True,
            "product_id": product_id,
            "html_text": clean_page_text,
            "url": url,
            "text_length": len(clean_page_text)
        }
        
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Таймаут загрузки страницы",
            "product_id": product_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Ошибка парсинга: {str(e)}",
            "product_id": product_id
        }

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка работоспособности сервиса"""
    return jsonify({
        "status": "OK",
        "message": "WB HTML Parser Service",
        "version": "2.0 - HTML Text Only",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/parse/<product_id>', methods=['GET'])
def parse_single_product(product_id):
    """
    Парсинг одного товара - возвращает HTML текст
    GET /parse/12345678
    """
    if not product_id or not product_id.isdigit():
        return jsonify({
            "success": False,
            "error": "Неверный ID товара"
        }), 400
    
    print(f"📦 Парсинг товара: {product_id}")
    
    # Получаем HTML текст
    result = extract_product_html(product_id)
    
    return jsonify(result)

@app.route('/parse', methods=['POST'])
def parse_multiple_products():
    """
    Массовый парсинг товаров - возвращает HTML текст для каждого
    POST /parse
    {"product_ids": ["12345678", "87654321"]}
    """
    try:
        data = request.get_json()
        
        if not data or 'product_ids' not in data:
            return jsonify({
                "success": False,
                "error": "Требуется массив product_ids"
            }), 400
        
        product_ids = data['product_ids']
        
        if not isinstance(product_ids, list) or len(product_ids) == 0:
            return jsonify({
                "success": False,
                "error": "product_ids должен быть непустым массивом"
            }), 400
        
        if len(product_ids) > 10:
            return jsonify({
                "success": False,
                "error": "Максимум 10 товаров за запрос"
            }), 400
        
        print(f"📦 Массовый парсинг: {len(product_ids)} товаров")
        
        results = []
        for i, product_id in enumerate(product_ids):
            print(f"🔄 Обработка {i+1}/{len(product_ids)}: {product_id}")
            
            # Валидация ID
            if not str(product_id).isdigit():
                results.append({
                    "product_id": product_id,
                    "success": False,
                    "error": "Неверный формат ID"
                })
                continue
            
            # Парсинг HTML
            result = extract_product_html(str(product_id))
            results.append(result)
            
            # Задержка между запросами (кроме последнего)
            if i < len(product_ids) - 1:
                time.sleep(2)
        
        successful = sum(1 for r in results if r.get('success'))
        failed = len(results) - successful
        
        print(f"✅ Завершено: {successful} успешно, {failed} ошибок")
        
        return jsonify({
            "success": True,
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "results": results
        })
        
    except Exception as e:
        print(f"❌ Ошибка массового парсинга: {e}")
        return jsonify({
            "success": False,
            "error": f"Внутренняя ошибка: {str(e)}"
        }), 500

@app.route('/test', methods=['GET'])
def test_parsing():
    """Тест парсинга на известном товаре"""
    test_product_id = "18671335"  # Тестовый товар из проекта
    
    print(f"🧪 ТЕСТ парсинга товара: {test_product_id}")
    
    result = extract_product_html(test_product_id)
    
    if result.get('success'):
        # Добавляем краткий анализ для теста
        text = result.get('html_text', '')
        
        # Ищем ключевые слова
        has_price = 'руб' in text.lower() or '₽' in text
        has_brand = 'бренд' in text.lower() or 'производитель' in text.lower()
        has_description = len(text) > 1000
        
        result['analysis'] = {
            "has_price_indicators": has_price,
            "has_brand_indicators": has_brand, 
            "has_sufficient_content": has_description,
            "text_preview": text[:300] + "..." if len(text) > 300 else text
        }
    
    return jsonify(result)

@app.route('/', methods=['GET'])
def root():
    """Главная страница сервиса"""
    return jsonify({
        "service": "WB HTML Parser",
        "version": "2.0",
        "description": "Упрощенный парсер товаров Wildberries через HTML",
        "endpoints": {
            "/health": "Проверка работоспособности",
            "/parse/<product_id>": "Парсинг одного товара",
            "/parse": "POST массовый парсинг (product_ids array)",
            "/test": "Тест на образце товара"
        },
        "advantages": [
            "⚡ Быстро - 1 запрос вместо 45",
            "🎯 Надежно - HTML всегда доступен", 
            "🔧 Просто - без сложных алгоритмов",
            "📄 Полно - весь текст страницы"
        ]
    })

if __name__ == '__main__':
    print("🚀 Запуск WB HTML Parser Service v2.0")
    print("📋 Новый подход: HTML текст вместо JSON полей")
    app.run(host='0.0.0.0', port=10000, debug=True)
