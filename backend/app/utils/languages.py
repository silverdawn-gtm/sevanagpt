"""Language codes and Bhashini pipeline mappings."""

# ISO 639-1 → Bhashini language codes
LANGUAGE_MAP = {
    "en": {"code": "en", "name": "English", "native": "English"},
    "hi": {"code": "hi", "name": "Hindi", "native": "हिन्दी"},
    "bn": {"code": "bn", "name": "Bengali", "native": "বাংলা"},
    "ta": {"code": "ta", "name": "Tamil", "native": "தமிழ்"},
    "te": {"code": "te", "name": "Telugu", "native": "తెలుగు"},
    "mr": {"code": "mr", "name": "Marathi", "native": "मराठी"},
    "gu": {"code": "gu", "name": "Gujarati", "native": "ગુજરાતી"},
    "kn": {"code": "kn", "name": "Kannada", "native": "ಕನ್ನಡ"},
    "ml": {"code": "ml", "name": "Malayalam", "native": "മലയാളം"},
    "pa": {"code": "pa", "name": "Punjabi", "native": "ਪੰਜਾਬੀ"},
    "or": {"code": "or", "name": "Odia", "native": "ଓଡ଼ିଆ"},
    "as": {"code": "as", "name": "Assamese", "native": "অসমীয়া"},
    "ur": {"code": "ur", "name": "Urdu", "native": "اردو"},
    "sa": {"code": "sa", "name": "Sanskrit", "native": "संस्कृतम्"},
    "ne": {"code": "ne", "name": "Nepali", "native": "नेपाली"},
    "sd": {"code": "sd", "name": "Sindhi", "native": "سنڌي"},
    "doi": {"code": "doi", "name": "Dogri", "native": "डोगरी"},
    "mai": {"code": "mai", "name": "Maithili", "native": "मैथिली"},
    "mni": {"code": "mni", "name": "Manipuri", "native": "মৈতৈলোন্"},
    "sat": {"code": "sat", "name": "Santali", "native": "ᱥᱟᱱᱛᱟᱲᱤ"},
    "bodo": {"code": "bodo", "name": "Bodo", "native": "बड़ो"},
    "kok": {"code": "kok", "name": "Konkani", "native": "कोंकणी"},
    "lus": {"code": "lus", "name": "Mizo", "native": "Mizo ṭawng"},
}

SUPPORTED_LANGUAGES = list(LANGUAGE_MAP.keys())
