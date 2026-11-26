"""Curated public-domain parallel translations for bundled Greek sample and Biblical passages.

Corpora that ship their own ``Document.translations`` (such as I.Sicily, Aphrodisias,
IIP, IOSPE, Crete, and IGCyr) always surface those translations directly. This small
offline table supplies parallel English renderings for the bundled offline Greek sample
texts and landmark offline NT/LXX passages (John 1:1–18, Philemon 1:1–25, Genesis 1:1–5,
Psalm 22 [MT 23]:1–6) so interlinear and parallel-translation reading works out of the
box with zero network requests.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ParallelTranslation",
    "lookup_doc_translation",
    "lookup_verse_translations",
]


@dataclass(frozen=True, slots=True)
class ParallelTranslation:
    """Attribution-carrying parallel English translation for a passage or verse map."""

    source: str
    license: str
    document_text: str = ""
    by_ref: dict[str, str] | None = None


# Bundled Greek sample documents (`aegean.load("greek")`).
_SAMPLE_TRANSLATIONS: dict[str, ParallelTranslation] = {
    "iliad-1.1": ParallelTranslation(
        source="A. T. Murray (Loeb 1924, rev. public domain)",
        license="Public Domain",
        document_text="Sing, goddess, the wrath of Achilles, son of Peleus.",
    ),
    "john-1.1": ParallelTranslation(
        source="World English Bible (WEB)",
        license="Public Domain",
        document_text="In the beginning was the Word, and the Word was with God, and the Word was God.",
    ),
    "heraclitus-panta-rhei": ParallelTranslation(
        source="Traditional philosophical rendering (Heraclitus / Plato Cratylus 402a)",
        license="Public Domain",
        document_text="Everything flows (all things are in flux).",
    ),
    "herodotus-1.1": ParallelTranslation(
        source="A. D. Godley (Loeb 1920, public domain)",
        license="Public Domain",
        document_text="This is the display of the inquiry of Herodotus of Halicarnassus.",
    ),
    "sappho-1.1": ParallelTranslation(
        source="H. T. Wharton / literal philological rendering",
        license="Public Domain",
        document_text="Ornate-throned, deathless Aphrodite, wile-weaving child of Zeus.",
    ),
}

# Landmark offline NT verses (World English Bible, Public Domain).
_NT_VERSE_TRANSLATIONS: dict[str, str] = {
    "John.1.1": "In the beginning was the Word, and the Word was with God, and the Word was God.",
    "John.1.2": "The same was in the beginning with God.",
    "John.1.3": "All things were made through him. Without him, nothing was made that has been made.",
    "John.1.4": "In him was life, and the life was the light of men.",
    "John.1.5": "The light shines in the darkness, and the darkness hasn't overcome it.",
    "John.1.6": "There came a man, sent from God, whose name was John.",
    "John.1.7": "The same came as a witness, that he might testify about the light, that all might believe through him.",
    "John.1.8": "He was not the light, but was sent that he might testify about the light.",
    "John.1.9": "The true light that enlightens everyone was coming into the world.",
    "John.1.10": "He was in the world, and the world was made through him, and the world didn't recognize him.",
    "John.1.11": "He came to his own, and those who were his own didn't receive him.",
    "John.1.12": "But as many as received him, to them he gave the right to become God's children, to those who believe in his name:",
    "John.1.13": "who were born, not of blood, nor of the will of the flesh, nor of the will of man, but of God.",
    "John.1.14": "The Word became flesh and lived among us. We saw his glory, such glory as of the only born Son of the Father, full of grace and truth.",
    "John.1.15": "John testified about him. He cried out, saying, 'This was he of whom I said, He who comes after me has surpassed me, for he was before me.'",
    "John.1.16": "From his fullness we all received grace upon grace.",
    "John.1.17": "For the law was given through Moses. Grace and truth were realized through Jesus Christ.",
    "John.1.18": "No one has seen God at any time. The only born Son, who is in the bosom of the Father, has declared him.",
    "Phlm.1.1": "Paul, a prisoner of Christ Jesus, and Timothy our brother, to Philemon, our beloved fellow worker,",
    "Phlm.1.2": "to the beloved Apphia, to Archippus our fellow soldier, and to the assembly in your house:",
    "Phlm.1.3": "Grace to you and peace from God our Father and the Lord Jesus Christ.",
    "Phlm.1.4": "I thank my God always, making mention of you in my prayers,",
    "Phlm.1.5": "hearing of your love and of the faith which you have toward the Lord Jesus and toward all the saints,",
    "Phlm.1.6": "that the fellowship of your faith may become effective in the knowledge of every good thing which is in us in Christ Jesus.",
    "Phlm.1.7": "For we have much joy and comfort in your love, because the hearts of the saints have been refreshed through you, brother.",
    "Phlm.1.8": "Therefore, though I have all boldness in Christ to command you that which is appropriate,",
    "Phlm.1.9": "yet for love's sake I rather appeal to you, being such a one as Paul, the aged, and also a prisoner of Jesus Christ.",
    "Phlm.1.10": "I appeal to you for my child, whom I have become the father of in my chains, Onesimus,",
    "Phlm.1.11": "who once was useless to you, but now is useful to you and to me.",
    "Phlm.1.12": "I am sending him back. Therefore receive him, that is, my own heart,",
    "Phlm.1.13": "whom I desired to keep with me, that on your behalf he might serve me in my chains for the Good News.",
    "Phlm.1.14": "But I was willing to do nothing without your consent, that your goodness would not be as of necessity, but of free will.",
    "Phlm.1.15": "For perhaps he was therefore separated from you for a while, that you would have him forever,",
    "Phlm.1.16": "no longer as a slave, but more than a slave, a beloved brother—especially to me, but how much rather to you, both in the flesh and in the Lord.",
    "Phlm.1.17": "If then you count me a partner, receive him as you would receive me.",
    "Phlm.1.18": "But if he has wronged you at all or owes you anything, put that to my account.",
    "Phlm.1.19": "I, Paul, write this with my own hand: I will repay it (not to mention to you that you owe to me even your own self besides).",
    "Phlm.1.20": "Yes, brother, let me have joy from you in the Lord. Refresh my heart in the Lord.",
    "Phlm.1.21": "Having confidence in your obedience, I write to you, knowing that you will do even beyond what I say.",
    "Phlm.1.22": "Also, prepare a guest room for me, for I hope that through your prayers I will be restored to you.",
    "Phlm.1.23": "Epaphras, my fellow prisoner in Christ Jesus, greets you,",
    "Phlm.1.24": "as do Mark, Aristarchus, Demas, and Luke, my fellow workers.",
    "Phlm.1.25": "The grace of our Lord Jesus Christ be with your spirit. Amen.",
}

# Landmark offline LXX verses (Sir Lancelot C. L. Brenton 1844 Septuagint translation, Public Domain).
_LXX_VERSE_TRANSLATIONS: dict[str, str] = {
    "Gen.1.1": "In the beginning God made the heaven and the earth.",
    "Gen.1.2": "But the earth was unsightly and unfurnished, and darkness was over the deep, and the Spirit of God moved over the water.",
    "Gen.1.3": "And God said, Let there be light, and there was light.",
    "Gen.1.4": "And God saw the light that it was good, and God divided between the light and the darkness.",
    "Gen.1.5": "And God called the light Day, and the darkness he called Night, and there was evening and there was morning, the first day.",
    "Ps.22.1": "A Psalm of David. The Lord tends me as a shepherd, and I shall want nothing.",
    "Ps.22.2": "In a place of green grass, there he has made me dwell: he has nourished me by the water of rest.",
    "Ps.22.3": "He has restored my soul: he has guided me into the paths of righteousness, for his name's sake.",
    "Ps.22.4": "Yea, even if I should walk in the midst of the shadow of death, I will not be afraid of evils: for thou art with me; thy rod and thy staff, these have comforted me.",
    "Ps.22.5": "Thou hast prepared a table before me in presence of them that afflict me: thou hast thoroughly anointed my head with oil; and thy cup cheers me like the best wine.",
    "Ps.22.6": "Surely thy mercy shall follow me all the days of my life: and my dwelling shall be in the house of the Lord for a very long time.",
}


def lookup_doc_translation(
    doc_id: str,
    existing: list[str] | tuple[str, ...] | None = None,
) -> ParallelTranslation | None:
    """Return a known parallel translation for ``doc_id`` or corpus-supplied translations."""
    if existing:
        cleaned = [str(t).strip() for t in existing if str(t).strip()]
        if cleaned:
            return ParallelTranslation(
                source="Corpus edition translation",
                license="See corpus provenance",
                document_text="\n\n".join(cleaned),
            )
    return _SAMPLE_TRANSLATIONS.get(doc_id)


def lookup_verse_translations(
    refs: list[str],
    *,
    is_lxx: bool = False,
) -> ParallelTranslation | None:
    """Return matching verse-keyed translations for NT or LXX references when available."""
    table = _LXX_VERSE_TRANSLATIONS if is_lxx else _NT_VERSE_TRANSLATIONS
    matched = {r: table[r] for r in refs if r in table}
    if not matched:
        return None
    if is_lxx:
        return ParallelTranslation(
            source="Brenton Septuagint Translation (1844)",
            license="Public Domain",
            by_ref=matched,
        )
    return ParallelTranslation(
        source="World English Bible (WEB)",
        license="Public Domain",
        by_ref=matched,
    )
