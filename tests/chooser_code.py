import langid

langid.set_languages(['fr', 'en'])
langid2iso = {
    'fr': 'fra',
    'en': 'eng'
}

def chooser(message):
    detected_lang, langid_confidence = langid.classify(message)
    detected_lang = langid2iso[detected_lang]
    return (detected_lang, 1)
