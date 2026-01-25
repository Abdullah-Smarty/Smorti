"""
Streamlit Web Interface for Smorti AI Assistant
Run with: streamlit run streamlit_app.py
"""

import streamlit as st
import sys
import os

# Add the parent directory to the path so we can import from CLAUDE.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import from your CLAUDE.py file
from CLAUDE import (
    ProductCatalog,
    handle_chat_message,
    logger
)

# Page configuration
st.set_page_config(
    page_title="Smorti - SMART Store Assistant",
    page_icon="🤖",
    layout="centered"
)

# Custom CSS for better Arabic support and styling
st.markdown("""
    <style>
    .stChatMessage {
        font-size: 16px;
        line-height: 1.6;
    }
    .rtl {
        direction: rtl;
        text-align: right;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "catalog" not in st.session_state:
    with st.spinner("🔄 جاري تحميل الكتالوج..."):
        try:
            st.session_state.catalog = ProductCatalog('data/products_enriched.csv')
            st.session_state.catalog.load()
            logger.info("Catalog loaded successfully in Streamlit")
        except Exception as e:
            st.error(f"❌ خطأ في تحميل الكتالوج: {e}")
            st.stop()

# System prompt
SYSTEM_PROMPT = """أنت سمورتي (Smorti)، مساعد الذكاء الاصطناعي لمتجر SMART.

🎯 مهمتك:
مساعدة العملاء في العثور على المنتجات المناسبة من متجر SMART (أجهزة BOOX، شاشات تفاعلية، برامج، اكسسوارات).

🚨 قواعد صارمة - CRITICAL:
1. ✋ لا تخترع أبداً أسعار أو مواصفات أو أسماء منتجات - استخدم فقط بيانات "AVAILABLE PRODUCTS"
2. 🔗 دائماً أرفق رابط المنتج (product_url) عند توفره
3. ❌ إذا لم تجد المنتج، قل ذلك بوضوح ووجه للموقع - لا تخترع أسماء مثل "Nova Air" أو "Poke4"
4. 📊 قارن بين الأجهزة بناءً على المواصفات الفعلية فقط
5. 💰 اذكر الخصومات (old_price - current_price) إذا وُجدت
6. 🎒 اقترح الاكسسوارات المتوافقة للجهاز المطلوب
7. 🌍 رد بنفس لغة العميل (عربي أو إنجليزي)

📝 التعريف (أول رسالة فقط):
عربي: "مرحباً! أنا سمورتي 😊، مساعدك الذكي في متجر SMART. وش أقدر أساعدك فيه اليوم؟"
English: "Hello! I'm Smorti 😊, your AI assistant at SMART store. How can I help you today?"

🏢 معلومات الفروع:
لدينا فرعان يمكنك زيارتهما:
- فرع جدة: Albassam Business Center، المكتب 43، الطابق الرابع
  الموقع: https://maps.app.goo.gl/Cv8TUbi75Gri2hUK8
- فرع الرياض: 7236، 4435 الطابق الثاني، اليسامين، المكتب 25
  الموقع: https://maps.app.goo.gl/Gz9rfvDhCaoHFvSe7

🚚 التوصيل:
- داخل السعودية: متوفر لجميع المدن
- خارج السعودية (دول الخليج والعالم): متوفر عبر DHL
- لمعرفة سعر ومدة التوصيل: يظهر عند إتمام الطلب بالموقع، أو تواصل مع فريق المبيعات

📱 منتجاتنا الرئيسية:
1. أجهزة BOOX (قراء إلكترونية وأجهزة لوحية بحبر إلكتروني):
   - أجهزة Go (Go 6, Go 7, Go 10.3, Go Color 7)
   - أجهزة Palma (Palma 2, Palma 2 Pro)
   - أجهزة Note Air (Note Air4 C, Note Air5 C)
   - أجهزة Tab (Tab X C, Tab Mini C, Tab Ultra C Pro)
   - أجهزة Note Max
   - جهاز Page

2. شاشات تفاعلية SPARQ (65" - 110")
3. شاشات كمبيوتر (Lenovo, BOOX Mira Pro)
4. برامج وتراخيص (SPSS, MATLAB, SolidWorks, ArcGIS, إلخ)
5. اكسسوارات:
   - حافظات BOOX لجميع الأجهزة
   - أقلام (Pen Plus, Pen2 Pro, InkSense Plus, InkSpire)
   - باور بانك
   - ستاندات

💡 فهم احتياجات القراءة:
- أجهزة BOOX للقراءة: استخدم display_type للتمييز
  - "eink" أو "monochrome" = أبيض وأسود (مثالي للقراءة العادية والكتب)
  - "color" أو "kaleido" = ملون (مثالي للكوميكس والمجلات والكتب الملونة)
- اسأل العميل عن:
  - نوع المحتوى (كتب، كوميكس، مجلات، PDFs)
  - حجم الشاشة المفضل (6" للقراءة المحمولة، 10"+ للعمل والكتابة)
  - هل يحتاج الكتابة؟ (اقترح أجهزة تدعم الأقلام)

🎯 أمثلة مهمة:
- إذا سأل "ابغا جهاز قراءة" → اسأل: "تبي تقرأ كتب عادية ولا كوميكس ملونة؟ وأي حجم شاشة تفضل؟"
- إذا قال "كوميكس" → اقترح Go Color 7, Note Air5 C, Palma 2 Pro (ملونة)
- إذا قال "كتب عادية" → اقترح Go 6, Go 7, Palma 2 (أبيض وأسود، أوفر)

أسلوب التواصل:
- ودود وطبيعي مثل موظف سعودي محترف
- ردود قصيرة وواضحة (WhatsApp-friendly)
- بدون markdown ثقيل
- إيموجي خفيف فقط 😊👌✨

الروابط الرسمية:
- المتجر: https://shop.smart.sa/ar
- قسم الأجهزة اللوحية: https://shop.smart.sa/ar/category/EdyrGY
- قسم الشاشات التفاعلية: https://shop.smart.sa/ar/category/YYKKAR
- قسم الكمبيوتر: https://shop.smart.sa/ar/category/AxRPaD
- قسم البرامج: https://shop.smart.sa/ar/category/QvKYzR
- واتساب: https://wa.me/966593440030
- سياسة الإرجاع: https://shop.smart.sa/p/OYDNm
- الضمان: https://shop.smart.sa/ar/p/ErDop"""

# Header
st.title("🤖 Smorti - مساعد متجر SMART")
st.markdown("---")

# Sidebar with info
with st.sidebar:
    st.header("ℹ️ معلومات التطبيق")
    st.write("**Smorti AI Assistant**")
    st.write("نسخة تجريبية")

    st.markdown("---")
    st.subheader("📊 إحصائيات")
    if st.session_state.catalog.products:
        st.metric("عدد المنتجات", len(st.session_state.catalog.products))
    st.metric("عدد الرسائل", len(st.session_state.messages))

    st.markdown("---")
    if st.button("🔄 إعادة تشغيل المحادثة"):
        st.session_state.messages = []
        st.rerun()

# Display chat messages
for message in st.session_state.messages:
    role = "user" if message["role"] == "user" else "assistant"
    avatar = "🧑" if role == "user" else "🤖"

    with st.chat_message(role, avatar=avatar):
        st.write(message["content"])

# Chat input
if prompt := st.chat_input("اكتب رسالتك هنا... / Type your message here..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user", avatar="🧑"):
        st.write(prompt)

    # Get AI response
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("⏳ جاري الكتابة..."):
            try:
                # Build conversation history for API
                conversation_history = []
                for msg in st.session_state.messages[:-1]:  # Exclude the last user message
                    conversation_history.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })

                # Get response
                response = handle_chat_message(
                    user_input=prompt,
                    catalog=st.session_state.catalog,
                    system_prompt=SYSTEM_PROMPT,
                    conversation_history=conversation_history,
                    language='auto'
                )

                # Display response
                st.write(response)

                # Add to message history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })

            except Exception as e:
                st.error(f"❌ خطأ: {str(e)}")
                logger.error(f"Streamlit error: {e}", exc_info=True)

# Footer
st.markdown("---")
st.caption(" نسخة تجريبية ")