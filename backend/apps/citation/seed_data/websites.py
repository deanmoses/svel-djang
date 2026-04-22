"""Seed data for website citation sources."""

WEBSITE_SOURCES: list[dict[str, object]] = [
    {
        "name": "Internet Pinball Database (IPDB)",
        "source_type": "web",
        "identifier_key": "ipdb",
        "description": (
            "Comprehensive database of pinball machines with specs, photos, "
            "and historical data. Primary reference for machine "
            "identification and production details."
        ),
        "links": [
            {"url": "https://www.ipdb.org/", "label": "IPDB", "link_type": "homepage"}
        ],
    },
    {
        "name": "Online Pinball Database (OPDB)",
        "source_type": "web",
        "identifier_key": "opdb",
        "description": (
            "Machine-readable pinball database with structured data on "
            "titles, manufacturers, and features."
        ),
        "links": [
            {"url": "https://opdb.org/", "label": "OPDB", "link_type": "homepage"}
        ],
    },
    {
        "name": "Pinside",
        "source_type": "web",
        "description": (
            "Pinball community forum and database with market prices, "
            "reviews, and collector discussions."
        ),
        "links": [
            {"url": "https://pinside.com/", "label": "Pinside", "link_type": "homepage"}
        ],
    },
    {
        "name": "PinWiki",
        "source_type": "web",
        "description": (
            "Community-edited wiki focused on pinball machine repair, "
            "maintenance, and technical documentation."
        ),
        "links": [
            {
                "url": "https://www.pinwiki.com/",
                "label": "PinWiki",
                "link_type": "homepage",
            }
        ],
    },
    {
        "name": "Kineticist",
        "source_type": "web",
        "description": (
            "Pinball news and media site. Absorbed This Week in Pinball (TWiP) in 2022."
        ),
        "links": [
            {
                "url": "https://www.kineticist.com/",
                "label": "Kineticist",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "Pinball News",
        "source_type": "web",
        "description": (
            "Long-running pinball news site with in-depth game reviews and "
            "industry coverage. Active since late 1999."
        ),
        "links": [
            {
                "url": "https://www.pinballnews.com/",
                "label": "Pinball News",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "This Week in Pinball (TWiP)",
        "source_type": "web",
        "description": "Weekly pinball news roundup. Now part of Kineticist.",
        "links": [
            {
                "url": "https://twip.kineticist.com/",
                "label": "TWiP",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "Stern Pinball",
        "source_type": "web",
        "description": ("Official site of the largest current pinball manufacturer."),
        "links": [
            {
                "url": "https://www.sternpinball.com/",
                "label": "Stern Pinball",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "Jersey Jack Pinball",
        "source_type": "web",
        "description": (
            "Official site of Jersey Jack Pinball, boutique manufacturer founded 2011."
        ),
        "links": [
            {
                "url": "https://www.jerseyjackpinball.com/",
                "label": "Jersey Jack Pinball",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "American Pinball",
        "source_type": "web",
        "description": (
            "Official site of American Pinball, manufacturer of Houdini, "
            "Oktoberfest, and Hot Wheels."
        ),
        "links": [
            {
                "url": "https://www.american-pinball.com/",
                "label": "American Pinball",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "Spooky Pinball",
        "source_type": "web",
        "description": (
            "Official site of Spooky Pinball, small-batch manufacturer founded 2013."
        ),
        "links": [
            {
                "url": "https://www.spookypinball.com/",
                "label": "Spooky Pinball",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "Multimorphic",
        "source_type": "web",
        "description": (
            "Official site of Multimorphic, maker of the P3 modular pinball "
            "platform. Began as PinballControllers.com in 2009."
        ),
        "links": [
            {
                "url": "https://www.multimorphic.com/",
                "label": "Multimorphic",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "Pinball Brothers",
        "source_type": "web",
        "description": (
            "Official site of Pinball Brothers, European manufacturer formed 2020."
        ),
        "links": [
            {
                "url": "https://www.pinballbrothers.com/",
                "label": "Pinball Brothers",
                "link_type": "homepage",
            },
        ],
    },
    {
        "name": "Chicago Gaming Company",
        "source_type": "web",
        "description": (
            "Official site of Chicago Gaming Company, known for remakes of "
            "classic Bally/Williams titles."
        ),
        "links": [
            {
                "url": "https://www.chicago-gaming.com/",
                "label": "Chicago Gaming Company",
                "link_type": "homepage",
            },
        ],
    },
]
