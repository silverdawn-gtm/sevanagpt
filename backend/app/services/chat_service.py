"""Chat service orchestrator — handles the full chat pipeline."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.chatbot.fsm import ChatState, get_next_state
from app.chatbot.prompts import (
    closing_prompt,
    disambiguation_prompt,
    greeting_prompt,
    need_extraction_prompt,
    scheme_detail_prompt,
    scheme_search_prompt,
)
from app.models import Conversation, Message, Scheme
from app.schemas.scheme import SchemeListItem
from app.services.mistral_service import chat_complete, chat_configured, classify_intent
from app.services.search_service import hybrid_search

# ── Language-aware suggestions ──────────────────────────────────────

SUGGESTIONS = {
    "en": {
        "greeting": [
            {"text": "Show me education scholarships"},
            {"text": "I'm a farmer looking for schemes"},
            {"text": "Health insurance for my family"},
            {"text": "Housing schemes for low income"},
        ],
        "detail": [
            {"text": "Show me similar schemes"},
            {"text": "Check my eligibility"},
        ],
        "disambiguation": [
            {"text": "Education and scholarships"},
            {"text": "Agriculture and farming"},
            {"text": "Healthcare and insurance"},
        ],
    },
    "hi": {
        "greeting": [
            {"text": "शिक्षा छात्रवृत्ति दिखाओ"},
            {"text": "मैं किसान हूँ, योजनाएँ बताओ"},
            {"text": "परिवार के लिए स्वास्थ्य बीमा"},
            {"text": "कम आय वालों के लिए आवास योजना"},
        ],
        "detail": [
            {"text": "इसी तरह की योजनाएँ दिखाओ"},
            {"text": "मेरी पात्रता जाँचो"},
        ],
        "disambiguation": [
            {"text": "शिक्षा और छात्रवृत्ति"},
            {"text": "कृषि और खेती"},
            {"text": "स्वास्थ्य और बीमा"},
        ],
    },
    "bn": {
        "greeting": [
            {"text": "শিক্ষা বৃত্তি দেখান"},
            {"text": "আমি কৃষক, প্রকল্প বলুন"},
            {"text": "পরিবারের জন্য স্বাস্থ্য বীমা"},
            {"text": "কম আয়ের জন্য আবাসন প্রকল্প"},
        ],
        "detail": [
            {"text": "একই ধরনের প্রকল্প দেখান"},
            {"text": "আমার যোগ্যতা যাচাই করুন"},
        ],
        "disambiguation": [
            {"text": "শিক্ষা ও বৃত্তি"},
            {"text": "কৃষি ও চাষ"},
            {"text": "স্বাস্থ্য ও বীমা"},
        ],
    },
    "ta": {
        "greeting": [
            {"text": "கல்வி உதவித்தொகைகள் காட்டு"},
            {"text": "நான் விவசாயி, திட்டங்கள் சொல்லுங்கள்"},
            {"text": "குடும்பத்திற்கான சுகாதார காப்பீடு"},
            {"text": "குறைந்த வருமானத்தினருக்கான வீட்டுத் திட்டம்"},
        ],
        "detail": [
            {"text": "இதே போன்ற திட்டங்கள் காட்டு"},
            {"text": "என் தகுதியை சரிபார்க்கவும்"},
        ],
        "disambiguation": [
            {"text": "கல்வி மற்றும் உதவித்தொகை"},
            {"text": "வேளாண்மை மற்றும் விவசாயம்"},
            {"text": "சுகாதாரம் மற்றும் காப்பீடு"},
        ],
    },
    "te": {
        "greeting": [
            {"text": "విద్య స్కాలర్‌షిప్‌లు చూపించు"},
            {"text": "నేను రైతును, పథకాలు చెప్పండి"},
            {"text": "కుటుంబానికి ఆరోగ్య బీమా"},
            {"text": "తక్కువ ఆదాయ వర్గానికి గృహ పథకం"},
        ],
        "detail": [
            {"text": "ఇలాంటి పథకాలు చూపించు"},
            {"text": "నా అర్హత తనిఖీ చేయండి"},
        ],
        "disambiguation": [
            {"text": "విద్య మరియు స్కాలర్‌షిప్‌లు"},
            {"text": "వ్యవసాయం మరియు సేద్యం"},
            {"text": "ఆరోగ్యం మరియు బీమా"},
        ],
    },
    "mr": {
        "greeting": [
            {"text": "शिक्षण शिष्यवृत्ती दाखवा"},
            {"text": "मी शेतकरी आहे, योजना सांगा"},
            {"text": "कुटुंबासाठी आरोग्य विमा"},
            {"text": "कमी उत्पन्न असलेल्यांसाठी गृहनिर्माण योजना"},
        ],
        "detail": [
            {"text": "अशाच प्रकारच्या योजना दाखवा"},
            {"text": "माझी पात्रता तपासा"},
        ],
        "disambiguation": [
            {"text": "शिक्षण आणि शिष्यवृत्ती"},
            {"text": "कृषी आणि शेती"},
            {"text": "आरोग्य आणि विमा"},
        ],
    },
    "gu": {
        "greeting": [
            {"text": "શિક્ષણ શિષ્યવૃત્તિ બતાવો"},
            {"text": "હું ખેડૂત છું, યોજનાઓ જણાવો"},
            {"text": "પરિવાર માટે આરોગ્ય વીમો"},
            {"text": "ઓછી આવકવાળા માટે આવાસ યોજના"},
        ],
        "detail": [
            {"text": "આ પ્રકારની યોજનાઓ બતાવો"},
            {"text": "મારી પાત્રતા તપાસો"},
        ],
        "disambiguation": [
            {"text": "શિક્ષણ અને શિષ્યવૃત્તિ"},
            {"text": "કૃષિ અને ખેતી"},
            {"text": "આરોગ્ય અને વીમો"},
        ],
    },
    "kn": {
        "greeting": [
            {"text": "ಶಿಕ್ಷಣ ವಿದ್ಯಾರ್ಥಿವೇತನ ತೋರಿಸಿ"},
            {"text": "ನಾನು ರೈತ, ಯೋಜನೆಗಳನ್ನು ಹೇಳಿ"},
            {"text": "ಕುಟುಂಬಕ್ಕೆ ಆರೋಗ್ಯ ವಿಮೆ"},
            {"text": "ಕಡಿಮೆ ಆದಾಯದವರಿಗೆ ವಸತಿ ಯೋಜನೆ"},
        ],
        "detail": [
            {"text": "ಇದೇ ರೀತಿಯ ಯೋಜನೆಗಳನ್ನು ತೋರಿಸಿ"},
            {"text": "ನನ್ನ ಅರ್ಹತೆ ಪರಿಶೀಲಿಸಿ"},
        ],
        "disambiguation": [
            {"text": "ಶಿಕ್ಷಣ ಮತ್ತು ವಿದ್ಯಾರ್ಥಿವೇತನ"},
            {"text": "ಕೃಷಿ ಮತ್ತು ಬೇಸಾಯ"},
            {"text": "ಆರೋಗ್ಯ ಮತ್ತು ವಿಮೆ"},
        ],
    },
    "ml": {
        "greeting": [
            {"text": "വിദ്യാഭ്യാസ സ്കോളർഷിപ്പുകൾ കാണിക്കൂ"},
            {"text": "ഞാൻ കർഷകനാണ്, പദ്ധതികൾ പറയൂ"},
            {"text": "കുടുംബത്തിനുള്ള ആരോഗ്യ ഇൻഷുറൻസ്"},
            {"text": "കുറഞ്ഞ വരുമാനക്കാർക്കുള്ള ഭവന പദ്ധതി"},
        ],
        "detail": [
            {"text": "സമാനമായ പദ്ധതികൾ കാണിക്കൂ"},
            {"text": "എന്റെ യോഗ്യത പരിശോധിക്കൂ"},
        ],
        "disambiguation": [
            {"text": "വിദ്യാഭ്യാസം, സ്കോളർഷിപ്പ്"},
            {"text": "കൃഷി, കർഷകർ"},
            {"text": "ആരോഗ്യം, ഇൻഷുറൻസ്"},
        ],
    },
    "pa": {
        "greeting": [
            {"text": "ਸਿੱਖਿਆ ਸਕਾਲਰਸ਼ਿਪ ਦਿਖਾਓ"},
            {"text": "ਮੈਂ ਕਿਸਾਨ ਹਾਂ, ਯੋਜਨਾਵਾਂ ਦੱਸੋ"},
            {"text": "ਪਰਿਵਾਰ ਲਈ ਸਿਹਤ ਬੀਮਾ"},
            {"text": "ਘੱਟ ਆਮਦਨ ਵਾਲਿਆਂ ਲਈ ਰਿਹਾਇਸ਼ ਯੋਜਨਾ"},
        ],
        "detail": [
            {"text": "ਇਸ ਤਰ੍ਹਾਂ ਦੀਆਂ ਯੋਜਨਾਵਾਂ ਦਿਖਾਓ"},
            {"text": "ਮੇਰੀ ਯੋਗਤਾ ਜਾਂਚੋ"},
        ],
        "disambiguation": [
            {"text": "ਸਿੱਖਿਆ ਅਤੇ ਸਕਾਲਰਸ਼ਿਪ"},
            {"text": "ਖੇਤੀਬਾੜੀ ਅਤੇ ਕਿਸਾਨ"},
            {"text": "ਸਿਹਤ ਅਤੇ ਬੀਮਾ"},
        ],
    },
    "or": {
        "greeting": [
            {"text": "ଶିକ୍ଷା ବୃତ୍ତି ଦେଖାନ୍ତୁ"},
            {"text": "ମୁଁ ଚାଷୀ, ଯୋଜନା କୁହନ୍ତୁ"},
            {"text": "ପରିବାର ପାଇଁ ସ୍ୱାସ୍ଥ୍ୟ ବୀମା"},
            {"text": "କମ ଆୟ ପାଇଁ ଗୃହ ଯୋଜନା"},
        ],
        "detail": [
            {"text": "ଏହି ପ୍ରକାର ଯୋଜନା ଦେଖାନ୍ତୁ"},
            {"text": "ମୋର ଯୋଗ୍ୟତା ଯାଞ୍ଚ କରନ୍ତୁ"},
        ],
        "disambiguation": [
            {"text": "ଶିକ୍ଷା ଏବଂ ବୃତ୍ତି"},
            {"text": "କୃଷି ଏବଂ ଚାଷ"},
            {"text": "ସ୍ୱାସ୍ଥ୍ୟ ଏବଂ ବୀମା"},
        ],
    },
    "ur": {
        "greeting": [
            {"text": "تعلیمی وظائف دکھائیں"},
            {"text": "میں کسان ہوں، اسکیمیں بتائیں"},
            {"text": "خاندان کے لیے صحت کا بیمہ"},
            {"text": "کم آمدنی والوں کے لیے رہائشی اسکیم"},
        ],
        "detail": [
            {"text": "اسی طرح کی اسکیمیں دکھائیں"},
            {"text": "میری اہلیت جانچیں"},
        ],
        "disambiguation": [
            {"text": "تعلیم اور وظائف"},
            {"text": "زراعت اور کاشتکاری"},
            {"text": "صحت اور بیمہ"},
        ],
    },
}

# Fallback greeting responses per language
FALLBACK_GREETINGS = {
    "en": "Welcome to SevanaGPT! I can help you find government schemes that match your needs. What are you looking for? You can ask about education scholarships, farming schemes, healthcare, housing, or any other topic.",
    "hi": "सेवनाजीपीटी में आपका स्वागत है! मैं आपको सरकारी योजनाएँ खोजने में मदद कर सकता हूँ। आप शिक्षा, कृषि, स्वास्थ्य, आवास या किसी भी विषय पर पूछ सकते हैं।",
    "bn": "সেবনাজিপিটি-তে আপনাকে স্বাগত! আমি আপনাকে সরকারি প্রকল্প খুঁজে পেতে সাহায্য করতে পারি। আপনি কী খুঁজছেন?",
    "ta": "சேவனாஜிபிடி-க்கு வரவேற்கிறோம்! உங்களுக்கு பொருத்தமான அரசு திட்டங்களை கண்டறிய நான் உதவி செய்ய முடியும். நீங்கள் என்ன தேடுகிறீர்கள்?",
    "te": "సేవనాజీపీటీకి స్వాగతం! మీకు సరిపడే ప్రభుత్వ పథకాలను కనుగొనడంలో నేను సహాయం చేయగలను. మీరు ఏమి వెతుకుతున్నారు?",
    "mr": "सेवनाजीपीटीमध्ये आपले स्वागत आहे! मी तुम्हाला सरकारी योजना शोधण्यात मदत करू शकतो. तुम्ही काय शोधत आहात?",
    "gu": "સેવનાજીપીટીમાં આપનું સ્વાગત છે! હું તમને સરકારી યોજનાઓ શોધવામાં મદદ કરી શકું છું. તમે શું શોધી રહ્યા છો?",
    "kn": "ಸೇವನಾಜಿಪಿಟಿಗೆ ಸ್ವಾಗತ! ನಿಮಗೆ ಸರಿಹೊಂದುವ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳನ್ನು ಹುಡುಕಲು ನಾನು ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ನೀವು ಏನು ಹುಡುಕುತ್ತಿದ್ದೀರಿ?",
    "ml": "സേവനാജിപിടിയിലേക്ക് സ്വാഗതം! നിങ്ങൾക്ക് അനുയോജ്യമായ സർക്കാർ പദ്ധതികൾ കണ്ടെത്താൻ എനിക്ക് സഹായിക്കാനാകും. നിങ്ങൾ എന്താണ് തിരയുന്നത്?",
    "pa": "ਸੇਵਨਾਜੀਪੀਟੀ ਵਿੱਚ ਤੁਹਾਡਾ ਸਵਾਗਤ ਹੈ! ਮੈਂ ਤੁਹਾਨੂੰ ਸਰਕਾਰੀ ਯੋਜਨਾਵਾਂ ਲੱਭਣ ਵਿੱਚ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ। ਤੁਸੀਂ ਕੀ ਲੱਭ ਰਹੇ ਹੋ?",
    "or": "ସେବନାଜିପିଟିରେ ଆପଣଙ୍କୁ ସ୍ୱାଗତ! ମୁଁ ଆପଣଙ୍କୁ ସରକାରୀ ଯୋଜନା ଖୋଜିବାରେ ସାହାଯ୍ୟ କରିପାରିବି। ଆପଣ କ'ଣ ଖୋଜୁଛନ୍ତି?",
    "ur": "سیوناجی پی ٹی میں خوش آمدید! میں آپ کو سرکاری اسکیمیں تلاش کرنے میں مدد کر سکتا ہوں۔ آپ کیا ڈھونڈ رہے ہیں؟",
}

FALLBACK_SEARCH = {
    "en": "I found some relevant schemes: {names}. Would you like to know more about any of these? I can provide details on eligibility, benefits, and how to apply.",
    "hi": "मुझे कुछ संबंधित योजनाएँ मिलीं: {names}। क्या आप इनमें से किसी के बारे में और जानना चाहेंगे?",
    "bn": "কিছু প্রাসঙ্গিক প্রকল্প পাওয়া গেছে: {names}। এগুলোর কোনো একটি সম্পর্কে আরও জানতে চান?",
    "ta": "சில தொடர்புடைய திட்டங்கள் கிடைத்தன: {names}. இவற்றில் ஏதாவது ஒன்றைப் பற்றி மேலும் அறிய விரும்புகிறீர்களா?",
    "te": "కొన్ని సంబంధిత పథకాలు దొరికాయి: {names}. వీటిలో ఏదైనా గురించి మరింత తెలుసుకోవాలనుకుంటున్నారా?",
    "mr": "काही संबंधित योजना सापडल्या: {names}. यापैकी कोणत्याही बद्दल अधिक जाणून घ्यायचे आहे?",
    "gu": "કેટલીક સંબંધિત યોજનાઓ મળી: {names}. આમાંથી કોઈ વિશે વધુ જાણવા માંગો છો?",
    "kn": "ಕೆಲವು ಸಂಬಂಧಿತ ಯೋಜನೆಗಳು ಸಿಕ್ಕಿವೆ: {names}. ಇವುಗಳಲ್ಲಿ ಯಾವುದಾದರೂ ಬಗ್ಗೆ ಹೆಚ್ಚು ತಿಳಿಯಲು ಬಯಸುವಿರಾ?",
    "ml": "ചില ബന്ധപ്പെട്ട പദ്ധതികൾ കണ്ടെത്തി: {names}. ഇവയിലേതെങ്കിലും കൂടുതൽ അറിയാൻ ആഗ്രഹിക്കുന്നുവോ?",
    "pa": "ਕੁਝ ਸੰਬੰਧਿਤ ਯੋਜਨਾਵਾਂ ਮਿਲੀਆਂ: {names}। ਕੀ ਤੁਸੀਂ ਇਹਨਾਂ ਵਿੱਚੋਂ ਕਿਸੇ ਬਾਰੇ ਹੋਰ ਜਾਣਨਾ ਚਾਹੋਗੇ?",
    "or": "କିଛି ସମ୍ପୃକ୍ତ ଯୋଜନା ମିଳିଲା: {names}। ଏଥିମଧ୍ୟରୁ କୌଣସି ବିଷୟରେ ଅଧିକ ଜାଣିବାକୁ ଚାହୁଁଛନ୍ତି?",
    "ur": "کچھ متعلقہ اسکیمیں ملیں: {names}۔ کیا آپ ان میں سے کسی کے بارے میں مزید جاننا چاہیں گے؟",
}

FALLBACK_CLOSING = {
    "en": "Thank you for using SevanaGPT! Feel free to come back anytime. You can also browse schemes on our website.",
    "hi": "सेवनाजीपीटी का उपयोग करने के लिए धन्यवाद! आप कभी भी वापस आ सकते हैं।",
    "bn": "সেবনাজিপিটি ব্যবহার করার জন্য ধন্যবাদ! যে কোনো সময় ফিরে আসুন।",
    "ta": "சேவனாஜிபிடி பயன்படுத்தியதற்கு நன்றி! எப்போது வேண்டுமானாலும் திரும்பி வாருங்கள்.",
    "te": "సేవనాజీపీటీని ఉపయోగించినందుకు ధన్యవాదాలు! ఎప్పుడైనా తిరిగి రావచ్చు.",
    "mr": "सेवनाजीपीटी वापरल्याबद्दल धन्यवाद! कधीही परत या.",
    "gu": "સેવનાજીપીટી વાપરવા બદલ આભાર! ગમે ત્યારે પાછા આવો.",
    "kn": "ಸೇವನಾಜಿಪಿಟಿ ಬಳಸಿದ್ದಕ್ಕಾಗಿ ಧನ್ಯವಾದಗಳು! ಯಾವಾಗ ಬೇಕಾದರೂ ಹಿಂತಿರುಗಿ.",
    "ml": "സേവനാജിപിടി ഉപയോഗിച്ചതിന് നന്ദി! എപ്പോൾ വേണമെങ്കിലും തിരികെ വരൂ.",
    "pa": "ਸੇਵਨਾਜੀਪੀਟੀ ਵਰਤਣ ਲਈ ਧੰਨਵਾਦ! ਕਦੇ ਵੀ ਵਾਪਸ ਆਓ।",
    "or": "ସେବନାଜିପିଟି ବ୍ୟବହାର କରିଥିବାରୁ ଧନ୍ୟବାଦ! ଯେକୌଣସି ସମୟରେ ଫେରି ଆସନ୍ତୁ।",
    "ur": "سیوناجی پی ٹی استعمال کرنے کا شکریہ! کبھی بھی واپس آئیں۔",
}

FALLBACK_DEFAULT = {
    "en": "I'd be happy to help you find government schemes. Could you tell me what you're looking for? For example, your state, age, or the type of support you need (education, healthcare, housing, agriculture, etc.).",
    "hi": "मैं आपको सरकारी योजनाएँ खोजने में मदद करने में खुशी होगी। क्या आप बता सकते हैं कि आप क्या खोज रहे हैं? उदाहरण के लिए, आपका राज्य, उम्र, या आवश्यक सहायता का प्रकार।",
    "bn": "আমি আপনাকে সরকারি প্রকল্প খুঁজে পেতে সাহায্য করতে পারি। আপনি কী খুঁজছেন বলবেন? যেমন, আপনার রাজ্য, বয়স, বা কোন ধরনের সাহায্য দরকার।",
    "ta": "அரசு திட்டங்களை கண்டறிய நான் உதவ மகிழ்ச்சி. நீங்கள் என்ன தேடுகிறீர்கள் என்று சொல்ல முடியுமா?",
    "te": "ప్రభుత్వ పథకాలను కనుగొనడంలో మీకు సహాయం చేయడానికి నేను సంతోషిస్తాను. మీరు ఏమి వెతుకుతున్నారో చెప్పగలరా?",
    "mr": "सरकारी योजना शोधण्यात मदत करण्यात मला आनंद होईल. तुम्ही काय शोधत आहात ते सांगाल?",
    "gu": "સરકારી યોજનાઓ શોધવામાં મદદ કરવામાં મને ખુશી થશે. તમે શું શોધી રહ્યા છો તે કહી શકશો?",
    "kn": "ಸರ್ಕಾರಿ ಯೋಜನೆಗಳನ್ನು ಹುಡುಕಲು ನಿಮಗೆ ಸಹಾಯ ಮಾಡಲು ನನಗೆ ಸಂತೋಷವಾಗುತ್ತದೆ. ನೀವು ಏನು ಹುಡುಕುತ್ತಿದ್ದೀರಿ ಎಂದು ಹೇಳಬಹುದೇ?",
    "ml": "സർക്കാർ പദ്ധതികൾ കണ്ടെത്താൻ നിങ്ങളെ സഹായിക്കാൻ എനിക്ക് സന്തോഷമേയുള്ളൂ. നിങ്ങൾ എന്താണ് തിരയുന്നത് എന്ന് പറയാമോ?",
    "pa": "ਸਰਕਾਰੀ ਯੋਜਨਾਵਾਂ ਲੱਭਣ ਵਿੱਚ ਤੁਹਾਡੀ ਮਦਦ ਕਰਕੇ ਮੈਨੂੰ ਖੁਸ਼ੀ ਹੋਵੇਗੀ। ਤੁਸੀਂ ਕੀ ਲੱਭ ਰਹੇ ਹੋ ਦੱਸ ਸਕਦੇ ਹੋ?",
    "or": "ସରକାରୀ ଯୋଜନା ଖୋଜିବାରେ ଆପଣଙ୍କୁ ସାହାଯ୍ୟ କରିବାରେ ମୁଁ ଖୁସି ହେବି। ଆପଣ କ'ଣ ଖୋଜୁଛନ୍ତି ତାହା କହିପାରିବେ?",
    "ur": "سرکاری اسکیمیں تلاش کرنے میں آپ کی مدد کرکے مجھے خوشی ہوگی۔ آپ کیا ڈھونڈ رہے ہیں بتا سکتے ہیں؟",
}

# ── Fallback intent keywords for all languages ─────────────────────

GREETING_WORDS = {
    "en": ["hi", "hello", "hey", "namaste", "good morning", "good evening"],
    "hi": ["नमस्ते", "हैलो", "नमस्कार", "प्रणाम"],
    "bn": ["নমস্কার", "হ্যালো", "নমস্তে"],
    "ta": ["வணக்கம்", "ஹலோ"],
    "te": ["నమస్కారం", "హలో", "నమస్తే"],
    "mr": ["नमस्कार", "हॅलो"],
    "gu": ["નમસ્તે", "હેલો"],
    "kn": ["ನಮಸ್ಕಾರ", "ಹಲೋ"],
    "ml": ["നമസ്കാരം", "ഹലോ"],
    "pa": ["ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "ਹੈਲੋ", "ਨਮਸਤੇ"],
    "or": ["ନମସ୍କାର", "ହେଲୋ"],
    "ur": ["السلام علیکم", "ہیلو", "نمستے"],
}

GOODBYE_WORDS = {
    "en": ["bye", "thanks", "thank you", "goodbye", "see you"],
    "hi": ["धन्यवाद", "शुक्रिया", "अलविदा", "बाय"],
    "bn": ["ধন্যবাদ", "বিদায়", "বাই"],
    "ta": ["நன்றி", "போய் வருகிறேன்"],
    "te": ["ధన్యవాదాలు", "బై"],
    "mr": ["धन्यवाद", "बाय"],
    "gu": ["આભાર", "બાય"],
    "kn": ["ಧನ್ಯವಾದ", "ಬೈ"],
    "ml": ["നന്ദി", "ബൈ"],
    "pa": ["ਧੰਨਵਾਦ", "ਬਾਏ"],
    "or": ["ଧନ୍ୟବାଦ", "ବାଏ"],
    "ur": ["شکریہ", "الوداع", "بائے"],
}

DETAIL_WORDS = {
    "en": ["tell me more", "details", "how to apply", "explain", "more info"],
    "hi": ["विस्तार", "बताओ", "और बताइए", "कैसे आवेदन करें"],
    "bn": ["বিস্তারিত", "আরও বলুন", "কীভাবে আবেদন করব"],
    "ta": ["விரிவாக", "மேலும் சொல்லுங்கள்", "எப்படி விண்ணப்பிப்பது"],
    "te": ["వివరంగా", "మరింత చెప్పండి", "ఎలా దరఖాస్తు చేయాలి"],
    "mr": ["तपशील", "अधिक सांगा", "अर्ज कसा करायचा"],
    "gu": ["વિગતવાર", "વધુ જણાવો", "કેવી રીતે અરજી કરવી"],
    "kn": ["ವಿವರವಾಗಿ", "ಹೆಚ್ಚು ಹೇಳಿ", "ಹೇಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸುವುದು"],
    "ml": ["വിശദമായി", "കൂടുതൽ പറയൂ", "എങ്ങനെ അപേക്ഷിക്കാം"],
    "pa": ["ਵਿਸਤਾਰ", "ਹੋਰ ਦੱਸੋ", "ਅਰਜ਼ੀ ਕਿਵੇਂ ਦੇਣੀ ਹੈ"],
    "or": ["ବିସ୍ତାର", "ଅଧିକ କୁହନ୍ତୁ", "କିପରି ଆବେଦନ କରିବି"],
    "ur": ["تفصیل", "مزید بتائیں", "درخواست کیسے دیں"],
}

ELIGIBILITY_WORDS = {
    "en": ["eligible", "eligibility", "qualify", "am i eligible", "can i get"],
    "hi": ["पात्रता", "योग्यता", "पात्र", "क्या मैं"],
    "bn": ["যোগ্যতা", "পাত্র"],
    "ta": ["தகுதி", "நான் தகுதியானவனா"],
    "te": ["అర్హత", "నేను అర్హుడినా"],
    "mr": ["पात्रता", "मी पात्र आहे का"],
    "gu": ["પાત્રતા", "હું પાત્ર છું?"],
    "kn": ["ಅರ್ಹತೆ", "ನಾನು ಅರ್ಹನೇ"],
    "ml": ["യോഗ്യത", "ഞാൻ യോഗ്യനാണോ"],
    "pa": ["ਯੋਗਤਾ", "ਕੀ ਮੈਂ ਯੋਗ ਹਾਂ"],
    "or": ["ଯୋଗ୍ୟତା", "ମୁଁ ଯୋଗ୍ୟ କି"],
    "ur": ["اہلیت", "کیا میں اہل ہوں"],
}


def _flatten_keywords(word_dict: dict[str, list[str]]) -> list[str]:
    """Flatten all language keyword lists into one list."""
    all_words = []
    for words in word_dict.values():
        all_words.extend(words)
    return all_words


# Pre-computed flat lists for fallback intent detection
_ALL_GREETING = _flatten_keywords(GREETING_WORDS)
_ALL_GOODBYE = _flatten_keywords(GOODBYE_WORDS)
_ALL_DETAIL = _flatten_keywords(DETAIL_WORDS)
_ALL_ELIGIBILITY = _flatten_keywords(ELIGIBILITY_WORDS)


def _get_suggestions(language: str, key: str) -> list[dict]:
    """Get language-appropriate suggestions, falling back to English."""
    lang_sugg = SUGGESTIONS.get(language, SUGGESTIONS["en"])
    return lang_sugg.get(key, SUGGESTIONS["en"].get(key, []))


def _get_fallback(mapping: dict, language: str) -> str:
    """Get a fallback response in the user's language."""
    return mapping.get(language, mapping["en"])


# ── Core logic ──────────────────────────────────────────────────────

async def get_or_create_conversation(
    session, session_id: str, language: str = "en"
) -> tuple["Conversation", list[dict]]:
    """Get existing conversation and its chat history, or create a new one."""
    conv = (
        await session.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
    ).scalar_one_or_none()

    chat_history: list[dict] = []

    if conv:
        msgs = (
            await session.execute(
                select(Message)
                .where(Message.conversation_id == conv.id)
                .order_by(Message.created_at)
            )
        ).scalars().all()
        chat_history = [
            {"role": m.role, "content": m.content}
            for m in msgs[-10:]
        ]
        # Update language if changed
        if conv.language != language:
            conv.language = language
    else:
        conv = Conversation(
            id=uuid.uuid4(),
            session_id=session_id,
            language=language,
            fsm_state=ChatState.GREETING.value,
            context={},
        )
        session.add(conv)
        await session.flush()

    return conv, chat_history


def format_schemes_for_context(schemes: list[tuple]) -> str:
    """Format scheme results for LLM context."""
    parts = []
    for i, (scheme, score) in enumerate(schemes[:5], 1):
        parts.append(
            f"{i}. {scheme.name}\n"
            f"   Description: {(scheme.description or '')[:200]}\n"
            f"   Benefits: {(scheme.benefits or '')[:200]}\n"
            f"   Eligibility: {(scheme.eligibility_criteria or '')[:200]}"
        )
    return "\n\n".join(parts)


def format_scheme_detail(scheme: Scheme) -> str:
    """Format a single scheme for detailed view."""
    parts = [f"Scheme: {scheme.name}"]
    if scheme.description:
        parts.append(f"Description: {scheme.description}")
    if scheme.benefits:
        parts.append(f"Benefits: {scheme.benefits}")
    if scheme.eligibility_criteria:
        parts.append(f"Eligibility: {scheme.eligibility_criteria}")
    if scheme.application_process:
        parts.append(f"How to Apply: {scheme.application_process}")
    if scheme.documents_required:
        parts.append(f"Documents Required: {scheme.documents_required}")
    return "\n\n".join(parts)


async def process_message(
    session,
    session_id: str,
    user_message: str,
    language: str = "en",
) -> dict:
    """Process a user message and return AI response with scheme cards."""
    conversation, chat_history = await get_or_create_conversation(session, session_id, language)
    context = conversation.context or {}
    current_state = ChatState(conversation.fsm_state)

    # Save user message
    session.add(Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="user",
        content=user_message,
        content_original=user_message,
    ))

    # Classify intent
    intent_data = {"intent": "other", "entities": {}}
    try:
        intent_data = await classify_intent(user_message, str(context))
    except Exception:
        # Fallback: multilingual keyword-based classification
        msg_lower = user_message.lower()
        if any(w in msg_lower for w in _ALL_GREETING):
            intent_data["intent"] = "greeting"
        elif any(w in msg_lower for w in _ALL_GOODBYE):
            intent_data["intent"] = "goodbye"
        elif any(w in msg_lower for w in _ALL_DETAIL):
            intent_data["intent"] = "ask_detail"
        elif any(w in msg_lower for w in _ALL_ELIGIBILITY):
            intent_data["intent"] = "check_eligibility"
        else:
            intent_data["intent"] = "search_scheme"

    # Update context with extracted entities
    entities = intent_data.get("entities", {})
    for key in ["age", "gender", "state", "category", "occupation", "income"]:
        if entities.get(key):
            context[key] = entities[key]
    conversation.context = context

    # FSM transition
    intent = intent_data["intent"]
    next_state = get_next_state(current_state, intent)
    conversation.fsm_state = next_state.value

    # Build response based on state
    schemes_result = []
    scheme_cards = []
    suggestions = []

    if next_state == ChatState.GREETING:
        system_prompt = greeting_prompt(language)
        suggestions = _get_suggestions(language, "greeting")

    elif next_state == ChatState.NEED_EXTRACTION:
        system_prompt = need_extraction_prompt(context, language)

    elif next_state == ChatState.SCHEME_SEARCH:
        search_query = user_message
        if context.get("category"):
            search_query += f" {context['category']}"

        try:
            schemes_result = await hybrid_search(
                session=session,
                query=search_query,
                limit=5,
                use_semantic=True,
            )
        except Exception:
            schemes_result = await hybrid_search(
                session=session,
                query=search_query,
                limit=5,
                use_semantic=False,
            )

        schemes_context = format_schemes_for_context(schemes_result)
        system_prompt = scheme_search_prompt(schemes_context, user_message, context, language)
        scheme_cards = [
            SchemeListItem.model_validate(scheme)
            for scheme, _ in schemes_result[:5]
        ]
        if schemes_result:
            suggestions = [
                {"text": f"Tell me more about {schemes_result[0][0].name}"}
            ]
        else:
            suggestions = _get_suggestions(language, "greeting")

    elif next_state == ChatState.SCHEME_DETAIL:
        scheme = None
        try:
            search_results = await hybrid_search(
                session=session,
                query=user_message,
                limit=1,
                use_semantic=False,
            )
            if search_results:
                scheme = search_results[0][0]
                full = (
                    await session.execute(
                        select(Scheme)
                        .options(
                            selectinload(Scheme.category),
                            selectinload(Scheme.tags),
                        )
                        .where(Scheme.id == scheme.id)
                    )
                ).unique().scalar_one_or_none()
                if full:
                    scheme = full
        except Exception:
            pass

        if scheme:
            system_prompt = scheme_detail_prompt(format_scheme_detail(scheme), language)
            scheme_cards = [SchemeListItem.model_validate(scheme)]
        else:
            system_prompt = need_extraction_prompt(context, language)

        suggestions = _get_suggestions(language, "detail")

    elif next_state == ChatState.DISAMBIGUATION:
        system_prompt = disambiguation_prompt(context, "category or specific need", language)
        suggestions = _get_suggestions(language, "disambiguation")

    elif next_state == ChatState.CLOSING:
        system_prompt = closing_prompt(language)

    else:
        system_prompt = need_extraction_prompt(context, language)

    # Generate response
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history[-6:])
    messages.append({"role": "user", "content": user_message})

    try:
        reply = await chat_complete(messages, temperature=0.7, max_tokens=512)
    except Exception:
        # Fallback responses when no LLM API key is configured
        if next_state == ChatState.GREETING:
            reply = _get_fallback(FALLBACK_GREETINGS, language)
        elif next_state == ChatState.SCHEME_SEARCH and scheme_cards:
            names = ", ".join(s.name for s in scheme_cards[:3])
            template = _get_fallback(FALLBACK_SEARCH, language)
            reply = template.format(names=names)
        elif next_state == ChatState.CLOSING:
            reply = _get_fallback(FALLBACK_CLOSING, language)
        else:
            reply = _get_fallback(FALLBACK_DEFAULT, language)

    # Save assistant message
    session.add(Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content=reply,
    ))

    await session.commit()

    return {
        "reply": reply,
        "schemes": scheme_cards,
        "suggestions": suggestions,
        "session_id": session_id,
        "fsm_state": next_state.value,
    }


async def get_chat_history(session, session_id: str) -> list[dict]:
    conv = (
        await session.execute(
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.session_id == session_id)
        )
    ).scalar_one_or_none()

    if not conv:
        return []

    return [
        {
            "role": msg.role,
            "content": msg.content,
            "content_original": msg.content_original,
        }
        for msg in sorted(conv.messages, key=lambda m: m.created_at)
    ]


async def reset_conversation(session, session_id: str) -> bool:
    conv = (
        await session.execute(
            select(Conversation).where(Conversation.session_id == session_id)
        )
    ).scalar_one_or_none()

    if conv:
        await session.delete(conv)
        await session.commit()
        return True
    return False
