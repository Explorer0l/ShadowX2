import os
import sys

# Ensure project root is on path when running directly
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils import filters as F


PHRASES = [
    "Они все там долбоебы",
    "давайте жестко ебаться",
    "сука блять",
    "хуйня вопрос",
    "ахуенно красиво",
    "просто обычное сообщение",
    "hello friend",
    "п и з д е ц",
    "Мою мать сожрал Айбек",
    "хyй",  # latin y
]


def run_suite(backend: str):
    # Override backend for this run
    F.AI_PROFANITY_BACKEND = backend
    # Reset internal flags for a clean load attempt per backend
    F._ai_available = False
    F._hf_model = None
    F._hf_tokenizer = None
    F._detoxify_available = False
    F._detoxify_model = None
    F._langid_available = False
    F._langid_fn = None

    print(f"\n=== Backend: {backend} ===")
    F._ensure_ai_loaded()
    print(
        "loaded:",
        {
            "hf": bool(F._hf_model is not None),
            "detoxify": bool(F._detoxify_model is not None),
            "langid": bool(F._langid_fn is not None),
        },
    )

    for text in PHRASES:
        try:
            manual = F.contains_banned_words(text)
            masked = F.filter_profanity(text)
            score = F.ai_profanity_score(text)
            ai_hit = score >= float(F.AI_PROFANITY_THRESHOLD)
            print(
                f"- {text}\n  manual={manual} ai_score={score:.3f} ai_hit={ai_hit} -> masked='{masked}'"
            )
        except Exception as e:
            print(f"- {text}\n  ERROR: {e}")

    # Spam suite (backend-agnostic)
    SPAM_TEXTS = [
        "ПОДПИШИСЬ НА НАС @channel и ЖМИ СЮДА https://t.me/test !!!",
        "Скидка 50% только сегодня! t.me/sale +992 90 123 45 67",
        "🔥🔥🔥 Переходи на сайт www.example.com и выиграй приз!",
        "Привет! Просто обычный текст без ссылок",
        "https://t.me/onlylink",  # low-content link-only
        "купи купи купи купи",
    ]
    print("\n--- Spam detection ---")
    for s in SPAM_TEXTS:
        try:
            s_score = F.spam_score(s)
            s_flag = F.contains_spam(s)
            print(f"- {s}\n  spam_score={s_score:.3f} spam_flag={s_flag}")
        except Exception as e:
            print(f"- {s}\n  ERROR: {e}")

    # Domain detection suite (ads moderation trigger)
    DOMAIN_TEXTS = [
        "Заходи на example.com прямо сейчас!",
        "Наш сайт exaмple.com",  # Cyrillic м in domain label
        "Переходи на example[dot]org",
        "Мы на xn--80asehdb (пример.рф)",
        "Без доменов тут",
        "Магазин my-shop.ru скидки",
        "Обфускация g o o g l e . com",
    ]
    print("\n--- Domain detection (ads flag) ---")
    for s in DOMAIN_TEXTS:
        try:
            ad_flag = F.contains_ad_words(s)
            print(f"- {s}\n  contains_ad_words={ad_flag}")
        except Exception as e:
            print(f"- {s}\n  ERROR: {e}")

    # Hard cases: mixed scripts, obfuscation, separators, zero-widths, long noisy texts
    HARD_TEXTS = [
        # Profanity with separators and leet
        "с у к а, б л*я т ь!!!",
        "пи3д@ц, вот это да",
        "о-х-у-е-н-н-о красиво",
        "П И З Д Е Ц?",
        "х*y*й вопрос",
        "ебатъ уже хватит",
        "пид0р и пидорасы",
        "сос@л? нет, не сосал",
        "охуе\u2060нно" ,  # with word joiner
        # Domains obfuscated
        "Заходи на exаmple.com прямо сейчас!",  # Cyrillic 'а'
        "example(dot)org и example[dot]net",
        "пример.рф и xn--e1afmkfd.xn--p1ai",
        "g o o g l e . com - поехали",
        "cool\u200B.\u200Bsite",  # zero-width around dot
        # Spammy ads
        "СРОЧНО ПОДПИШИСЬ И ВЫИГРАЙ!!! 💥💥💥 СКИДКА 70% только сегодня",
        "+992 (90) 123-45-67 дешевле не бывает!!!",
        "цена 150 сомони — акция 20%",
        "только сегодня промокод 25% www.shop.com",
        # Low-content link-only
        "https://t.me/onlylink",
        # Repeats and emojis
        "купи купи купи купи купи",
        "🔥🔥🔥🔥🔥 ЖМИ ЖМИ ЖМИ",
        # Clean text baseline
        "рассказ о природе и людях без ссылок и мата",
    ]

    print("\n=== HARD CASES ===")
    for s in HARD_TEXTS:
        try:
            prof = F.contains_banned_words(s)
            masked = F.filter_profanity(s)
            ad = F.contains_ad_words(s)
            s_score = F.spam_score(s)
            s_flag = F.contains_spam(s)
            print(
                f"- {s}\n"
                f"  profanity={prof} masked='{masked}'\n"
                f"  contains_ad_words={ad} spam_score={s_score:.3f} spam_flag={s_flag}"
            )
        except Exception as e:
            print(f"- {s}\n  ERROR: {e}")


def main():
    # Run local first (always available)
    run_suite("local")
    # Then HF-only to compare
    run_suite("hf")
    # Finally ensemble
    run_suite("ensemble")


if __name__ == "__main__":
    main()


