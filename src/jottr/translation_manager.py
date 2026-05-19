import ast
from pathlib import Path


DEFAULT_LANGUAGE = "en_US"
RTL_LANGUAGES = {
    "ar", "arc", "ckb", "dv", "fa", "he", "ks", "ku", "nqo", "ps", "sd", "ug", "ur", "yi"
}
PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
ARABIC_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_current_language = DEFAULT_LANGUAGE
_messages = {}


def get_translations_dir():
    return Path(__file__).resolve().parents[2] / "translations"


def get_available_languages():
    translations_dir = get_translations_dir()
    if not translations_dir.is_dir():
        return []
    languages = []
    for po_file in sorted(translations_dir.glob("*_*.po")):
        language = po_file.stem
        if language.replace("_", "").replace("-", "").isalnum():
            languages.append(language)
    return languages


def format_language_label(language):
    language_names = {
        "en": "English",
        "fa": "Persian",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "it": "Italian",
        "pt": "Portuguese",
        "ru": "Russian",
        "tr": "Turkish",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean"
    }
    country_names = {
        "US": "United States",
        "GB": "United Kingdom",
        "IR": "Iran",
        "DE": "Germany",
        "FR": "France",
        "ES": "Spain",
        "IT": "Italy",
        "BR": "Brazil",
        "PT": "Portugal",
        "RU": "Russia",
        "TR": "Turkey",
        "CN": "China",
        "JP": "Japan",
        "KR": "South Korea"
    }
    parts = language.replace("-", "_").split("_", 1)
    if len(parts) != 2:
        return language
    language_name = language_names.get(parts[0].lower(), parts[0])
    country_name = country_names.get(parts[1].upper(), parts[1])
    return f"{language_name} ({country_name}) - {language}"


def set_language(language):
    global _current_language, _messages
    _current_language = language or DEFAULT_LANGUAGE
    _messages = load_po_messages(_current_language)


def get_language():
    return _current_language


def is_rtl_language(language=None):
    language = language or _current_language
    language_code = str(language).replace("-", "_").split("_", 1)[0].lower()
    return language_code in RTL_LANGUAGES


def get_language_code(language=None):
    language = language or _current_language
    return str(language).replace("-", "_").split("_", 1)[0].lower()


def localize_digits(value, language=None):
    text = str(value)
    language_code = get_language_code(language)
    if language_code == "fa":
        return text.translate(PERSIAN_DIGITS)
    if language_code == "ar":
        return text.translate(ARABIC_DIGITS)
    return text


def translate(text):
    if not isinstance(text, str):
        return text
    return _messages.get(text, text)


def load_po_messages(language):
    po_path = get_translations_dir() / f"{language}.po"
    if not po_path.is_file():
        return {}

    messages = {}
    msgid = None
    msgstr = None
    active = None

    def flush():
        if msgid and msgstr:
            messages[msgid] = msgstr

    with po_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                flush()
                msgid = None
                msgstr = None
                active = None
                continue
            if line.startswith("#"):
                continue
            if line.startswith("msgid "):
                flush()
                msgid = parse_po_string(line[6:].strip())
                msgstr = None
                active = "msgid"
                continue
            if line.startswith("msgstr "):
                msgstr = parse_po_string(line[7:].strip())
                active = "msgstr"
                continue
            if line.startswith('"') and active == "msgid":
                msgid = (msgid or "") + parse_po_string(line)
                continue
            if line.startswith('"') and active == "msgstr":
                msgstr = (msgstr or "") + parse_po_string(line)

    flush()
    return messages


def parse_po_string(value):
    try:
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return ""


_ = translate
