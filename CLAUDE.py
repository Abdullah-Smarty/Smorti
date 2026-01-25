"""
Smorti AI Agent - Enhanced Error Handling System
Local CLI Testing with Advanced Product Matching & Comparison
Supports: Pandas, Groq (Llama 3.3), Multi-language, Smart Recommendations
"""

import logging
from functools import wraps
from typing import Optional, Dict, Any, List, Tuple
import time
from datetime import datetime
import pandas as pd
import os
from dotenv import load_dotenv
import re

# Load environment variables from .env file
load_dotenv()

# ============================================
# 1. LOGGING CONFIGURATION
# ============================================

def setup_logging():
    """Configure logging for local testing"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        handlers=[
            logging.FileHandler('smorti_errors.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger('Smorti')

logger = setup_logging()


# ============================================
# 2. CUSTOM EXCEPTION CLASSES
# ============================================

class SmortiBaseException(Exception):
    """Base exception for all Smorti errors"""
    def __init__(self, message: str, user_message_ar: str, user_message_en: str):
        self.message = message
        self.user_message_ar = user_message_ar
        self.user_message_en = user_message_en
        super().__init__(self.message)


class GroqAPIError(SmortiBaseException):
    """Groq/Llama API failures"""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.original_error = original_error
        super().__init__(
            message,
            "عذراً، حصل خطأ مؤقت مع النظام 🙏 جرب مرة ثانية",
            "Sorry, a temporary system error occurred 🙏 Please try again"
        )


class GroqRateLimitError(SmortiBaseException):
    """Groq rate limit exceeded"""
    def __init__(self, message: str):
        super().__init__(
            message,
            "عذراً، الطلبات كثيرة حالياً. انتظر ثانية وحاول مرة ثانية 😊",
            "Sorry, too many requests. Wait a moment and try again 😊"
        )


class CatalogLoadError(SmortiBaseException):
    """Product catalog/CSV loading issues"""
    def __init__(self, message: str):
        super().__init__(
            message,
            "ما قدرت أوصل للكتالوج حالياً 😔 راح أوجهك للموقع",
            "Cannot access catalog right now 😔 I'll direct you to the website"
        )


class EmptyInputError(SmortiBaseException):
    """Empty user input"""
    def __init__(self):
        super().__init__(
            "Empty user input",
            "مرحباً! 😊 وش أقدر أخدمك؟",
            "Hello! 😊 How can I help you?"
        )


# ============================================
# 3. RETRY DECORATOR FOR GROQ API
# ============================================

def retry_groq_call(max_attempts=3, delay=2, backoff=2):
    """Retry decorator for Groq API calls with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay
            last_error = None

            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)

                except GroqRateLimitError:
                    logger.warning(f"Rate limit hit on attempt {attempt}")
                    if attempt == max_attempts:
                        raise
                    time.sleep(current_delay * 3)
                    attempt += 1

                except GroqAPIError as e:
                    last_error = e
                    if attempt == max_attempts:
                        logger.error(f"Max retries reached for {func.__name__}")
                        raise

                    logger.warning(f"Attempt {attempt}/{max_attempts} failed. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1

                except Exception as e:
                    logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
                    raise

            if last_error:
                raise last_error

        return wrapper
    return decorator


# ============================================
# 4. GROQ API ERROR HANDLING
# ============================================

@retry_groq_call(max_attempts=3, delay=2)
def call_groq_api(
    prompt: str,
    system_prompt: str,
    conversation_history: Optional[List[Dict]] = None,
    temperature: float = 0.3,
    max_tokens: int = 800
) -> str:
    """Call Groq API with comprehensive error handling"""
    try:
        from groq import Groq

        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise GroqAPIError("GROQ_API_KEY not found in environment variables")

        client = Groq(api_key=api_key)

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": prompt})

        # Call API (using updated model)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1,
            stream=False
        )

        ai_response = response.choices[0].message.content

        if not ai_response or ai_response.strip() == "":
            raise GroqAPIError("Empty response from Groq API")

        logger.info(f"✓ Groq API call successful ({len(ai_response)} chars)")
        return ai_response.strip()

    except Exception as e:
        error_msg = str(e).lower()

        if 'rate_limit' in error_msg or 'rate limit' in error_msg or '429' in error_msg:
            logger.error(f"Rate limit exceeded: {e}")
            raise GroqRateLimitError(str(e))

        elif 'api key' in error_msg or '401' in error_msg or 'unauthorized' in error_msg:
            logger.error(f"Authentication error: {e}")
            raise GroqAPIError(f"Invalid API key: {e}", e)

        elif 'timeout' in error_msg or 'timed out' in error_msg:
            logger.error(f"Groq API timeout: {e}")
            raise GroqAPIError(f"API timeout: {e}", e)

        elif '503' in error_msg or '502' in error_msg or 'service unavailable' in error_msg:
            logger.error(f"Groq service unavailable: {e}")
            raise GroqAPIError(f"Service temporarily unavailable: {e}", e)

        else:
            logger.error(f"Groq API error: {e}")
            raise GroqAPIError(f"API error: {e}", e)


# ============================================
# 5. ENHANCED CATALOG WITH SMART SEARCH
# ============================================

class ProductCatalog:
    """Enhanced product catalog with fuzzy matching and comparisons"""

    def __init__(self, csv_path: str, descriptions_txt_path: Optional[str] = None):
        self.csv_path = csv_path
        self.descriptions_txt_path = descriptions_txt_path
        self.df = None
        self.products = None
        self.product_descriptions = {}
        self.last_loaded = None

    def load(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """Load product catalog from CSV with validation"""
        if self.products is not None and not force_reload:
            logger.info(f"Using cached catalog ({len(self.products)} products)")
            return self.products

        try:
            if not os.path.exists(self.csv_path):
                raise CatalogLoadError(f"Catalog file not found: {self.csv_path}")

            logger.info(f"Loading catalog from {self.csv_path}...")
            self.df = pd.read_csv(self.csv_path, encoding='utf-8')

            if self.df.empty:
                raise CatalogLoadError("Catalog file is empty")

            # Validate required columns
            required_columns = ['name_en', 'name_ar']
            missing = [col for col in required_columns if col not in self.df.columns]

            if missing:
                logger.error(f"Missing required columns: {missing}")
                # Don't fail, just warn
                logger.warning("Continuing with available columns")

            logger.info(f"Catalog columns: {list(self.df.columns)}")

            # Handle null values gracefully (matching your CSV columns)
            fill_values = {
                'price_sar': 0,
                'old_price_sar': 0,
                'product_url': '',
                'category_link': '',
                'short_desc': '',
                'availability': 'unknown',
                'category': 'general',
                'screen_size_in': '',
                'display_type': '',
                'ram_gb': '',
                'storage_gb': '',
                'connectivity': '',
                'item_type': '',
                'resolution_px': '',
                'ppi': '',
                'cpu': '',
                'os': '',
                'bluetooth': '',
                'wifi': '',
                'Battery_mah': '',
                'audio_jack': '',
                'Micro_sd_slot': ''
            }

            for col, default_val in fill_values.items():
                if col in self.df.columns:
                    self.df[col] = self.df[col].fillna(default_val)

            # Remove duplicates based on product_id if exists
            if 'product_id' in self.df.columns:
                original_count = len(self.df)
                self.df = self.df.drop_duplicates(subset=['product_id'], keep='first')
                removed = original_count - len(self.df)
                if removed > 0:
                    logger.warning(f"Removed {removed} duplicate products")

            self.products = self.df.to_dict('records')
            self.last_loaded = datetime.now()

            logger.info(f"✓ Loaded {len(self.products)} products successfully")

            # Load descriptions if available
            if self.descriptions_txt_path and os.path.exists(self.descriptions_txt_path):
                self._load_descriptions()

            return self.products

        except pd.errors.EmptyDataError:
            raise CatalogLoadError("Catalog file is empty or corrupted")

        except pd.errors.ParserError as e:
            raise CatalogLoadError(f"Failed to parse CSV: {e}")

        except UnicodeDecodeError as e:
            raise CatalogLoadError(f"Encoding error (try UTF-8): {e}")

        except Exception as e:
            if isinstance(e, CatalogLoadError):
                raise
            logger.error(f"Unexpected catalog error: {e}")
            raise CatalogLoadError(f"Failed to load catalog: {e}")

    def _load_descriptions(self):
        """Load product descriptions from text file"""
        try:
            with open(self.descriptions_txt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse descriptions (you can adjust this based on your txt format)
            logger.info(f"Loaded product descriptions from {self.descriptions_txt_path}")
            self.product_descriptions_text = content

        except Exception as e:
            logger.warning(f"Could not load descriptions: {e}")

    def search_products(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Enhanced fuzzy search with better matching"""
        try:
            if self.products is None:
                self.load()

            query_lower = query.lower()

            # Extract key search terms
            search_terms = re.findall(r'\w+', query_lower)

            results = []
            scores = []

            for product in self.products:
                score = 0

                # Get searchable fields
                name_en = str(product.get('name_en', '')).lower()
                name_ar = str(product.get('name_ar', '')).lower()
                desc = str(product.get('short_desc', '')).lower()
                keywords = str(product.get('keywords', '')).lower()
                brand = str(product.get('brand', '')).lower()
                series = str(product.get('series', '')).lower()

                # Score matches
                for term in search_terms:
                    if term in name_en: score += 3
                    if term in name_ar: score += 3
                    if term in series: score += 2
                    if term in brand: score += 2
                    if term in keywords: score += 1
                    if term in desc: score += 1

                # Exact series match bonus
                if query_lower in series or series in query_lower:
                    score += 5

                if score > 0:
                    results.append(product)
                    scores.append(score)

            # Sort by score
            if results:
                sorted_results = [x for _, x in sorted(zip(scores, results), key=lambda pair: pair[0], reverse=True)]
                return sorted_results[:limit]

            return []

        except Exception as e:
            logger.error(f"Product search error: {e}")
            return []

    def get_accessories_for_product(self, product_name: str) -> List[Dict[str, Any]]:
        """Find compatible accessories for a product"""
        try:
            if self.products is None:
                self.load()

            accessories = []
            product_name_lower = product_name.lower()

            # Extract series/model info
            series_match = None
            if 'palma 2 pro' in product_name_lower:
                series_match = 'palma 2 pro'
            elif 'palma 2' in product_name_lower:
                series_match = 'palma 2'
            elif 'note air5 c' in product_name_lower or 'note air 5 c' in product_name_lower:
                series_match = 'note air5 c'
            elif 'go 7' in product_name_lower:
                series_match = 'go 7'
            elif 'go 6' in product_name_lower:
                series_match = 'go 6'

            if not series_match:
                return []

            # Search for accessories
            for product in self.products:
                item_type = str(product.get('item_type', '')).lower()
                name_en = str(product.get('name_en', '')).lower()
                name_ar = str(product.get('name_ar', '')).lower()

                # Check if it's an accessory
                if any(acc_type in item_type or acc_type in name_en or acc_type in name_ar
                       for acc_type in ['case', 'cover', 'stylus', 'pen', 'tip', 'remote', 'حافظة', 'جراب', 'قلم']):

                    # Check if compatible with the series
                    if series_match in name_en.lower() or series_match in name_ar.lower():
                        accessories.append(product)

            return accessories

        except Exception as e:
            logger.error(f"Accessory search error: {e}")
            return []


# ============================================
# 6. INPUT VALIDATION
# ============================================

def validate_user_input(user_input: str) -> str:
    """Validate and sanitize user input"""
    if not user_input:
        raise EmptyInputError()

    cleaned = user_input.strip()

    if not cleaned:
        raise EmptyInputError()

    if len(cleaned) > 5000:
        logger.warning(f"Input too long ({len(cleaned)} chars), truncating")
        cleaned = cleaned[:5000]

    return cleaned


# ============================================
# 7. LANGUAGE DETECTION
# ============================================

def detect_language(text: str) -> str:
    """Detect if text is primarily Arabic or English"""
    arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))

    if arabic_chars > english_chars:
        return 'ar'
    return 'en'


# ============================================
# 8. PRODUCT CONTEXT BUILDER
# ============================================

def build_product_context(products: List[Dict], language: str = 'ar', include_accessories: bool = False) -> str:
    """Build detailed product context for AI"""
    if not products:
        if language == 'ar':
            return "\n\n=== لم يتم العثور على منتجات مطابقة ===\nقل للمستخدم أنك لا تملك معلومات دقيقة ووجهه للموقع\n"
        else:
            return "\n\n=== NO MATCHING PRODUCTS FOUND ===\nTell user you don't have exact info and direct to website\n"

    context = "\n\n=== AVAILABLE PRODUCTS (USE ONLY THIS DATA) ===\n"

    for i, product in enumerate(products, 1):
        context += f"\n--- Product {i} ---\n"
        context += f"Name (EN): {product.get('name_en', 'N/A')}\n"
        context += f"Name (AR): {product.get('name_ar', 'N/A')}\n"
        context += f"Brand: {product.get('brand', 'N/A')}\n"
        context += f"Series: {product.get('series', 'N/A')}\n"
        context += f"Price: {product.get('price_sar', 'N/A')} SAR\n"

        if product.get('old_price_sar') and float(product.get('old_price_sar', 0)) > 0:
            context += f"Old Price: {product.get('old_price_sar')} SAR (Discount available!)\n"
            savings = float(product.get('old_price_sar', 0)) - float(product.get('price_sar', 0))
            if savings > 0:
                context += f"You Save: {savings:.2f} SAR\n"

        context += f"Screen Size: {product.get('screen_size_in', 'N/A')} inches\n"
        context += f"Display Type: {product.get('display_type', 'N/A')}\n"
        context += f"RAM: {product.get('ram_gb', 'N/A')} GB\n"
        context += f"Storage: {product.get('storage_gb', 'N/A')} GB\n"
        context += f"Resolution: {product.get('resolution_px', 'N/A')}\n"
        context += f"PPI: {product.get('ppi', 'N/A')}\n"
        context += f"CPU: {product.get('cpu', 'N/A')}\n"
        context += f"OS: {product.get('os', 'N/A')}\n"
        context += f"Bluetooth: {product.get('bluetooth', 'N/A')}\n"
        context += f"WiFi: {product.get('wifi', 'N/A')}\n"
        context += f"Battery: {product.get('Battery_mah', 'N/A')} mAh\n"
        context += f"Audio Jack: {product.get('audio_jack', 'N/A')}\n"
        context += f"MicroSD Slot: {product.get('Micro_sd_slot', 'N/A')}\n"
        context += f"Availability: {product.get('availability', 'N/A')}\n"
        context += f"Product URL: {product.get('product_url', 'N/A')}\n"

    context += "\n=== CRITICAL INSTRUCTIONS ===\n"
    context += "- ONLY use data from products listed above\n"
    context += "- NEVER invent prices, specs, or details\n"
    context += "- Always include product URL when available\n"
    context += "- Compare products if multiple options exist\n"
    context += "- Explain technical specs in simple terms\n"
    context += "- Mention discounts/savings if applicable\n"
    context += "=================================\n"

    return context


# ============================================
# 9. FALLBACK RESPONSE HANDLER
# ============================================

def get_fallback_response(error: SmortiBaseException, language: str = 'ar') -> str:
    """Get user-friendly error message"""
    logger.error(f"Returning fallback for {type(error).__name__}: {error.message}")

    if language == 'ar':
        return error.user_message_ar
    else:
        return error.user_message_en


# ============================================
# 10. MAIN CHAT HANDLER WITH ANTI-HALLUCINATION
# ============================================

def handle_chat_message(
    user_input: str,
    catalog: ProductCatalog,
    system_prompt: str,
    conversation_history: Optional[List[Dict]] = None,
    language: str = 'auto'
) -> str:
    """Main handler with anti-hallucination and smart product matching"""
    try:
        # Validate input
        try:
            cleaned_input = validate_user_input(user_input)
        except EmptyInputError as e:
            return get_fallback_response(e, language)

        # Auto-detect language
        if language == 'auto':
            language = detect_language(cleaned_input)

        logger.info(f"User ({language}): {cleaned_input[:100]}...")

        # Load catalog
        try:
            catalog.load()
        except CatalogLoadError as e:
            logger.error(f"Catalog error: {e.message}")
            logger.warning("Continuing without catalog access")

        # Build enhanced prompt with product context
        catalog_context = ""

        # Detect if user is asking about products
        product_keywords = [
            'جهاز', 'بوكس', 'boox', 'قو', 'go', 'سعر', 'price', 'بكم', 'كم سعر',
            'palma', 'note', 'air', 'tab', 'بالما', 'نوت', 'تابلت', 'قارئ',
            'مواصفات', 'specs', 'specification', 'compare', 'قارن', 'difference',
            'أفضل', 'best', 'recommend', 'اقترح', 'suggest', 'شاشة', 'screen',
            'ذاكرة', 'memory', 'ram', 'storage', 'بطارية', 'battery'
        ]

        is_product_query = any(keyword in cleaned_input.lower() for keyword in product_keywords)

        if is_product_query:
            try:
                search_results = catalog.search_products(cleaned_input, limit=8)

                if search_results:
                    catalog_context = build_product_context(search_results, language)

                    # Check for accessory queries
                    if any(acc in cleaned_input.lower() for acc in ['حافظة', 'جراب', 'قلم', 'case', 'cover', 'stylus', 'pen', 'accessories', 'اكسسوارات']):
                        # Add accessory info
                        catalog_context += "\n=== ACCESSORIES AVAILABLE ===\n"
                        catalog_context += "Check for compatible cases, styluses, and covers for each device.\n"
                        catalog_context += "Mention accessories if user asks about them.\n"

                    logger.info(f"Found {len(search_results)} matching products")
                else:
                    if language == 'ar':
                        catalog_context = "\n\n=== لم يتم العثور على منتجات مطابقة ===\n"
                        catalog_context += "قل للمستخدم بأدب أنك لا تملك معلومات دقيقة عن هذا المنتج\n"
                        catalog_context += "وجّهه لزيارة الموقع: https://shop.smart.sa/ar\n"
                        catalog_context += "أو تصفح الأقسام: https://shop.smart.sa/ar/category/EdyrGY\n"
                        catalog_context += "لا تخترع أي معلومات\n"
                    else:
                        catalog_context = "\n\n=== NO MATCHING PRODUCTS ===\n"
                        catalog_context += "Politely tell user you don't have exact information\n"
                        catalog_context += "Direct to website: https://shop.smart.sa/ar\n"
                        catalog_context += "DO NOT invent any information\n"

                    logger.warning(f"No products found for: {cleaned_input[:50]}")

            except Exception as e:
                logger.error(f"Catalog search error: {e}")

        # Build enhanced prompt
        enhanced_prompt = cleaned_input + catalog_context

        # Call Groq API
        try:
            response = call_groq_api(
                prompt=enhanced_prompt,
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                temperature=0.3,  # Low temp for factual accuracy
                max_tokens=800
            )

            logger.info(f"Smorti: {response[:100]}...")
            return response

        except GroqRateLimitError as e:
            return get_fallback_response(e, language)

        except GroqAPIError as e:
            return get_fallback_response(e, language)

    except Exception as e:
        logger.critical(f"UNEXPECTED ERROR: {e}", exc_info=True)

        if language == 'ar':
            return "عذراً، حصل خطأ غير متوقع 😔 جرب مرة ثانية"
        else:
            return "Sorry, an unexpected error occurred 😔 Try again"


# ============================================
# 11. SYSTEM HEALTH CHECK
# ============================================

def run_health_check(catalog_path: str) -> Dict[str, str]:
    """Check system health"""
    health = {
        'timestamp': datetime.now().isoformat(),
        'groq_api': '❌ Not tested',
        'api_key': '❌ Missing',
        'catalog': '❌ Not loaded',
        'pandas': '❌ Not installed'
    }

    try:
        import pandas as pd
        health['pandas'] = '✓ Installed'
    except ImportError:
        health['pandas'] = '❌ Not installed'

    if os.getenv('GROQ_API_KEY'):
        health['api_key'] = '✓ Found'
    else:
        health['api_key'] = '❌ Missing'

    try:
        catalog = ProductCatalog(catalog_path)
        products = catalog.load()
        health['catalog'] = f'✓ Loaded ({len(products)} products)'
    except Exception as e:
        health['catalog'] = f'❌ Error: {str(e)[:50]}'

    try:
        test_response = call_groq_api(
            prompt="Say 'جاهز' in one word",
            system_prompt="You are a test bot.",
            temperature=0.1,
            max_tokens=10
        )
        health['groq_api'] = f'✓ Working'
    except Exception as e:
        health['groq_api'] = f'❌ Error: {str(e)[:50]}'

    return health


# ============================================
# 12. CLI TEST WITH ENHANCED SYSTEM PROMPT
# ============================================

def main():
    """CLI testing with multi-language support"""

    print("=" * 60)
    print("🤖 SMORTI AI AGENT - LOCAL CLI TEST")
    print("=" * 60)

    # Health check
    print("\n🏥 Running health check...")
    health = run_health_check('data/products_enriched.csv')
    for component, status in health.items():
        print(f"  {component}: {status}")

    # Initialize catalog
    catalog = ProductCatalog('data/products_enriched.csv')

    # Enhanced system prompt with strict anti-hallucination
    system_prompt = """أنت سمورتي (Smorti)، مساعد الذكاء الاصطناعي لمتجر SMART.

🎯 مهمتك:
مساعدة العملاء في اختيار أجهزة BOOX (الأجهزة اللوحية والقراء الإلكترونية) بناءً على احتياجاتهم.

🚨 قواعد صارمة - CRITICAL:
1. ✋ لا تخترع أبداً أسعار أو مواصفات - استخدم فقط بيانات "AVAILABLE PRODUCTS"
2. 🔗 دائماً أرفق رابط المنتج (product_url) عند توفره
3. ❌ إذا لم تجد المنتج، قل ذلك بوضوح ووجه للموقع
4. 📊 قارن بين الأجهزة بناءً على المواصفات الفعلية
5. 💰 اذكر الخصومات (old_price - current_price) إذا وُجدت
6. 🎒 اقترح الاكسسوارات المتوافقة (Cases/Stylus) للجهاز المطلوب
7. 🌍 رد بنفس لغة العميل (عربي أو إنجليزي)

📝 التعريف (أول رسالة فقط):
عربي: "مرحباً! أنا سمورتي 😊، مساعدك الذكي في متجر SMART. وش أقدر أساعدك فيه اليوم؟"
English: "Hello! I'm Smorti 😊, your AI assistant at SMART store. How can I help you today?"

💡 شرح المواصفات بطريقة مبسطة:
- Display Type: eink = حبر إلكتروني (مريح للعين)، color = ملون
- RAM/Storage: كلما زاد = أداء أسرع وتخزين أكثر
- Screen Size: حسب الاستخدام (6" للقراءة، 10"+ للكتابة والعمل)
- Battery (mAh): كلما زاد = بطارية تدوم أطول
- WiFi/Bluetooth: للاتصال بالإنترنت والأجهزة
- MicroSD Slot: لزيادة التخزين
- Audio Jack: لتوصيل سماعات سلكية

🎒 الاكسسوارات المتوافقة:
- Palma 2 Pro → حافظة مغناطيسية Palma 2 Pro
- Note Air5 C → حافظة Note Air5 C + لوحة مفاتيح مغناطيسية
- Go 7 → حافظة Go 7 Series
- معظم الأجهزة → قلم InkSense Plus (للكتابة)

أسلوب التواصل:
- ودود وطبيعي مثل موظف سعودي محترف
- ردود قصيرة وواضحة (WhatsApp-friendly)
- بدون markdown ثقيل
- إيموجي خفيف فقط 😊👌✨

الروابط الرسمية:
- المتجر: https://shop.smart.sa/ar
- قسم الأجهزة: https://shop.smart.sa/ar/category/EdyrGY
- واتساب: https://wa.me/966593440030
- سياسة الإرجاع: https://shop.smart.sa/p/OYDNm
- الضمان: https://shop.smart.sa/ar/p/ErDop"""