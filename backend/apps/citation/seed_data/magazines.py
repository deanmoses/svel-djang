"""Seed data for magazine/periodical citation sources.

These are publication-level roots only. Individual issues and articles
will be added as children by contributors.
"""

MAGAZINE_SOURCES: list[dict[str, object]] = [
    # =====================================================================
    # Pinball-dedicated publications
    # =====================================================================
    {
        "name": "PinGame Journal",
        "source_type": "magazine",
        "description": (
            "Hobbyist pinball periodical, active since May 1991. "
            "The longest-running pinball-dedicated print publication."
        ),
        "year": 1991,
        "month": 5,
        "date_note": "First issue May 1991",
        "links": [
            {
                "url": "https://en.wikipedia.org/wiki/PinGame_Journal",
                "label": "Wikipedia",
                "link_type": "reference",
            },
        ],
    },
    {
        "name": "Pinball Magazine",
        "source_type": "magazine",
        "description": (
            "Current print pinball glossy edited by Jonathan Joosten. "
            "High-production-value magazine with in-depth features and "
            "historical articles."
        ),
        "year": 2012,
        "month": 8,
        "date_note": "First issue August 2012",
        "links": [
            {
                "url": "https://www.pinball-magazine.com/",
                "label": "Pinball Magazine",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "Pinhead Classified",
        "source_type": "magazine",
        "description": (
            "Pinball fanzine. Defunct by January 1999 with final issue No. 29."
        ),
        "date_note": "Defunct by January 1999, final issue No. 29",
    },
    # =====================================================================
    # Coin-op trade magazines with regular pinball coverage
    # =====================================================================
    {
        "name": "Play Meter",
        "source_type": "magazine",
        "description": (
            "Major coin-op trade magazine with regular pinball coverage. "
            "Founded 1974, ceased publication 2018."
        ),
        "year": 1974,
        "date_note": "Published 1974–2018",
        "links": [
            {
                "url": "https://en.wikipedia.org/wiki/Play_Meter",
                "label": "Wikipedia",
                "link_type": "reference",
            },
        ],
    },
    {
        "name": "RePlay",
        "source_type": "magazine",
        "description": (
            "Major coin-op trade magazine with regular pinball coverage. "
            "Founded October 1975, still active."
        ),
        "year": 1975,
        "month": 10,
        "date_note": "Founded October 1975, still active",
        "links": [
            {
                "url": "https://www.replaymag.com/",
                "label": "RePlay Magazine",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "GameRoom Magazine",
        "source_type": "magazine",
        "description": (
            "General gameroom hobbyist magazine with steady pinball "
            "coverage. Published January 1989 to July 2016."
        ),
        "year": 1989,
        "month": 1,
        "date_note": "Published January 1989 – July 2016",
        "links": [
            {
                "url": "https://en.wikipedia.org/wiki/Gameroom_magazine",
                "label": "Wikipedia",
                "link_type": "reference",
            },
        ],
    },
    {
        "name": "Coin Slot",
        "source_type": "magazine",
        "description": (
            "Enthusiast coin-op magazine with pinball coverage. Published "
            "from September 1974 into at least the late 1990s."
        ),
        "year": 1974,
        "month": 9,
        "date_note": "Published September 1974 – late 1990s",
        "links": [
            {
                "url": "https://library.arcade-museum.com/magazine/coin-slot",
                "label": "Arcade Museum library",
                "link_type": "reference",
            },
        ],
    },
    {
        "name": "Canadian Coin Box",
        "source_type": "magazine",
        "description": (
            "Long-running Canadian coin-op trade magazine with pinball coverage."
        ),
        "year": 1953,
        "date_note": "Published 1953–2000",
        "links": [
            {
                "url": "https://library.arcade-museum.com/magazine/canadian-coin-box",
                "label": "Arcade Museum library",
                "link_type": "reference",
            },
        ],
    },
    {
        "name": "Coin-Op Newsletter",
        "source_type": "magazine",
        "description": ("Hobbyist coin-op publication with some pinball relevance."),
        "date_note": "Active late 1980s–early 1990s",
        "links": [
            {
                "url": "https://library.arcade-museum.com/magazine/coin-op-newsletter",
                "label": "Arcade Museum library",
                "link_type": "reference",
            },
        ],
    },
    {
        "name": "Pinball Trader Newsletter",
        "source_type": "magazine",
        "description": ("Earlier collector publication that predates PinGame Journal."),
        "date_note": "Active late 1980s–early 1990s",
        "links": [
            {
                "url": "https://library.arcade-museum.com/magazine/pinball-trader",
                "label": "Arcade Museum library",
                "link_type": "reference",
            },
        ],
    },
    {
        "name": "Coin Drop International",
        "source_type": "magazine",
        "description": (
            "Electromechanical coin-op magazine with coverage of older "
            "and pre-flipper pinball."
        ),
    },
]
