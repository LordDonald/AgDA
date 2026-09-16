# ============================================================
# RANKING LANGUAGE
# ============================================================

RANKING_TERMS = [
    "highest",
    "lowest",
    "most",
    "least",
    "top",
    "rank",
    "best",
    "worst",
    "strongest",
    "weakest",
]


# ============================================================
# GROUPING LANGUAGE
# ============================================================

GROUP_PATTERNS = {
    "crop": [
        "which crops",
        "what crops",
        "by crop",
        "across crops",
    ],

    "state": [
        "which state",
        "which states",
        "what state",
        "what states",
        "by state",
        "across states",
    ],

    "zone": [
        "which zone",
        "which zones",
        "what zone",
        "what zones",
        "by zone",
        "across zones",
    ],

    "sector": [
        "by sector",
        "urban versus rural",
        "urban vs rural",
    ],

    "item": [
        "which foods",
        "which items",
        "what foods",
        "by item",
    ],

    "climate_event": [
        "which climate event",
        "what climate event",
        "which climate risk",
        "what climate risk",
        "by climate event",
    ],
}


# ============================================================
# UNSUPPORTED / SAFETY LANGUAGE
# ============================================================

UNSUPPORTED_LANGUAGE = {
    "profitability": [
        "most profitable",
        "more profitable",
        "profitable",
        "profit",
        "profitability",
        "profit margin",
        "return on investment",
        "roi",
    ],

    "causal": [
        "does extension improve",
        "does extension increase",
        "causes",
        "cause",
        "effect of",
        "impact of",
    ],

    "recommendation": [
        "should i farm",
        "should i grow",
        "should i plant",
        "what should i plant",
        "what should i grow",
        "recommend a crop",
        "recommend planting",
        "best crop for me",
        "good crop for me",
        "good crop to plant",
        "worth planting",
    ],
}


# ============================================================
# CLIMATE ALIASES
# ============================================================

CLIMATE_ALIAS_ADDITIONS = {
    "flooding":
        "Flood",

    "floods":
        "Flood",

    "droughts":
        "Drought",

    "late rains":
        "Late onset of rains",

    "late rain":
        "Late onset of rains",

    "late onset of rain":
        "Late onset of rains",

    "high temperatures":
        "Very high temperatures (>40°C)",

    "very high temperature":
        "Very high temperatures (>40°C)",

    "extreme heat":
        "Very high temperatures (>40°C)",
}


# ============================================================
# METRIC LANGUAGE
# ============================================================

METRIC_LANGUAGE = {

    "household_crop_participation_rate": {
        "phrases": [
            "how many households farm",
            "how many households cultivate",
            "crop participation",
            "crop cultivation participation",
            "households growing crops",
        ],

        "keywords": [
            "participation",
            "cultivate",
        ],
    },


    "median_plot_area_ha": {
        "phrases": [
            "plot size",
            "farm size",
            "land size",
            "land area",
            "cultivated area",
            "how big are farms",
            "how large are plots",
        ],

        "keywords": [
            "hectares",
            "acreage",
        ],
    },


    "crop_grower_share": {
    "phrases": [
        "grower share",
        "crop prevalence",
        "how commonly the crop is grown",
        "most grown crops",
        "most common crops",
        "commonly grown crops",
        "what crops do farmers grow",
        "what crops do people farm",
        "which crops do farmers grow",
        "popular crops",
    ],

    "keywords": [
        "grown",
        "grow",
        "growing",
    ],
},


    "median_completed_yield": {
        "phrases": [
            "crop yield",
            "crop yields",
            "yield per hectare",
            "yields per hectare",
            "median yield",
            "productivity",
            "productive crops",
            "best yields",
            "highest yield",
            "highest yields",
            "lowest yields",
        ],

        "keywords": [
            "yield",
            "yields",
            "productivity",
        ],
    },


    "median_high_confidence_yield": {
        "phrases": [
            "high confidence yield",
            "reliable yield",
            "strongest yield evidence",
            "gps measured yield",
        ],

        "keywords": [
            "high confidence",
        ],
    },


    "harvest_completion_rate": {
        "phrases": [
            "harvest completion rate",
            "completed harvest",
            "finished harvesting",
            "harvest complete",
        ],

        "keywords": [
            "completion",
        ],
    },


    "crop_seller_rate": {
        "phrases": [
            "seller rate",
            "seller participation",
            "market participation",
            "how many farmers sell",
            "what share of farmers sell",
            "what percentage of farmers sell",
            "which crops sell most",
            "most commonly sold",
        ],

        "keywords": [
            "sellers",
            "selling",
        ],
    },


    "median_commercialization_share": {
        "phrases": [
            "share of harvest sold",
            "share of their harvest",
            "share of the harvest",
            "share of harvest",
            "largest share of their harvest",
            "how much of the harvest",
            "percentage of harvest sold",
            "proportion of harvest sold",
            "how much harvest is sold",
            "how much do farmers sell",
            "how much crop do farmers sell",
            "how much harvest do farmers sell",
            "how much of the harvest is sold",
            "how much is sold",
            "commercialization share",
        ],

        "keywords": [
            "commercialization",
            "commercialised",
            "commercialized",
        ],
    },


    "median_household_consumption_share": {
        "phrases": [
            "household consumption share",
            "how much is consumed",
            "share consumed",
            "eat themselves",
            "consumed by household",
        ],

        "keywords": [
            "consumption",
            "consumed",
        ],
    },


    "median_postharvest_loss_share": {
        "phrases": [
            "post harvest loss",
            "postharvest loss",
            "crop losses after harvest",
            "how much is lost after harvest",
        ],

        "keywords": [
            "losses",
            "loss",
        ],
    },


    "pp_food_insecurity_count": {
        "phrases": [
            "food insecurity after planting",
            "post planting food insecurity",
            "food security after planting",
        ],

        "keywords": [],
    },


    "ph_food_insecurity_count": {
        "phrases": [
            "food insecurity after harvest",
            "post harvest food insecurity",
            "food security after harvest",
        ],

        "keywords": [],
    },


    "food_insecurity_change": {
        "phrases": [
            "food security change",
            "food insecurity change",
            "food security better after harvest",
            "food security worse after harvest",
            "food security improve",
            "food insecurity improve",
        ],

        "keywords": [
            "food security",
            "food insecurity",
        ],
    },


    "planting_extension_access_rate": {
        "phrases": [
            "extension access",
            "extension advice",
            "planting extension",
            "agricultural extension",
        ],

        "keywords": [
            "extension",
        ],
    },


    "farm_information_access_rate": {
        "phrases": [
            "farm information access",
            "agricultural information access",
            "farm advice access",
            "receive farm information",
        ],

        "keywords": [
            "information access",
        ],
    },


    "median_same_basis_price_change": {
        "phrases": [
            "price change",
            "prices changed",
            "prices increased",
            "prices decreased",
            "price increase",
            "price decrease",
            "prices rose",
            "prices fell",
        ],

        "keywords": [
            "price",
            "prices",
        ],
    },


    "climate_likely_share": {
        "phrases": [
            "climate risk",
            "climate event",
            "most likely climate",
            "likely climate risk",
            "weather risk",
            "how worried",
            "worried about",
            "communities worried",
            "community concern",
            "climate threat",
            "viewed as the biggest",
        ],

        "keywords": [
            "drought",
            "flood",
            "temperature",
            "climate",
        ],
    },


    "adaptation_no_action_share": {
        "phrases": [
            "no adaptation action",
            "no action on climate",
            "do nothing about climate",
            "taking no action",
        ],

        "keywords": [
            "no action",
        ],
    },
}