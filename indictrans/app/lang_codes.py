"""ISO 639-1 to IndicTrans2 BCP-47 language code mapping.

SevanaGPT uses ISO 639-1 codes (hi, bn, ta...). IndicTrans2 uses
Flores/BCP-47 codes (hin_Deva, ben_Beng, tam_Taml...).
"""

# ISO 639-1 -> IndicTrans2 BCP-47 code
ISO_TO_INDICTRANS: dict[str, str] = {
    "hi": "hin_Deva",
    "bn": "ben_Beng",
    "ta": "tam_Taml",
    "te": "tel_Telu",
    "mr": "mar_Deva",
    "gu": "guj_Gujr",
    "kn": "kan_Knda",
    "ml": "mal_Mlym",
    "pa": "pan_Guru",
    "or": "ory_Orya",
    "ur": "urd_Arab",
    # Additional Indic languages supported by IndicTrans2
    "as": "asm_Beng",
    "ne": "npi_Deva",
    "sa": "san_Deva",
    "sd": "snd_Arab",
    "mai": "mai_Deva",
    "doi": "doi_Deva",
    "kok": "kok_Deva",
    "sat": "sat_Olck",
    "mni": "mni_Mtei",
    "bodo": "brx_Deva",
    "lus": "lus_Latn",
}

# English source code for IndicTrans2
ENGLISH_CODE = "eng_Latn"

SUPPORTED_TARGETS = set(ISO_TO_INDICTRANS.keys())


def to_indictrans_code(iso_code: str) -> str | None:
    """Convert ISO 639-1 code to IndicTrans2 code. Returns None if unsupported."""
    return ISO_TO_INDICTRANS.get(iso_code)
