from __future__ import annotations


USER_QUESTION_BANK = [

    # ========================================================
    # FARMER / ASPIRING FARMER
    # ========================================================

    {
        "id": "FARMER_001",
        "persona": "farmer",
        "question":
            "What crops do people farm most in Kaduna?",
        "expected_status": "answered",
        "expected_metric": "crop_grower_share",
    },

    {
        "id": "FARMER_002",
        "persona": "farmer",
        "question":
            "How much maize do farmers sell?",
        "expected_status": "answered",
        "expected_metric":
            "median_commercialization_share",
    },

    {
        "id": "FARMER_003",
        "persona": "farmer",
        "question":
            "Which crops have the highest yields in Nigeria?",
        "expected_status": "answered",
        "expected_metric": "median_completed_yield",
    },

    {
        "id": "FARMER_004",
        "persona": "farmer",
        "question":
            "How risky is flooding in the North West?",
        "expected_status": "answered",
        "expected_metric": "climate_likely_share",
    },

    {
        "id": "FARMER_005",
        "persona": "farmer",
        "question":
            "Should I farm maize in Katsina?",
        "expected_status": "reframe_required",
        "expected_metric": None,
    },

    {
        "id": "FARMER_006",
        "persona": "farmer",
        "question":
            "What is the most profitable crop?",
        "expected_status": "unsupported",
        "expected_metric": None,
    },


    # ========================================================
    # GOVERNMENT / POLICY
    # ========================================================

    {
        "id": "GOV_001",
        "persona": "government",
        "question":
            "Which states have the highest grower share for rice?",
        "expected_status": "answered",
        "expected_metric": "crop_grower_share",
    },

    {
        "id": "GOV_002",
        "persona": "government",
        "question":
            "Which states have the highest yields for rice?",
        "expected_status": "answered",
        "expected_metric": "median_completed_yield",
    },

    {
        "id": "GOV_003",
        "persona": "government",
        "question":
            "Which states have the highest seller participation for rice?",
        "expected_status": "answered",
        "expected_metric": "crop_seller_rate",
    },

    {
        "id": "GOV_004",
        "persona": "government",
        "question":
            "Which state looks strongest for rice?",
        "expected_status": "needs_clarification",
        "expected_metric": None,
    },

    {
        "id": "GOV_005",
        "persona": "government",
        "question":
            "Is food security better after harvest?",
        "expected_status": "answered",
        "expected_metric": "food_insecurity_change",
    },


    # ========================================================
    # RESEARCHER
    # ========================================================

    {
        "id": "RESEARCH_001",
        "persona": "researcher",
        "question":
            "Does extension improve yield?",
        "expected_status": "reframe_required",
        "expected_metric": None,
    },

    {
        "id": "RESEARCH_002",
        "persona": "researcher",
        "question":
            "What climate risk is highest?",
        "expected_status": "answered",
        "expected_metric": "climate_likely_share",
    },

    {
        "id": "RESEARCH_003",
        "persona": "researcher",
        "question":
            "Which crops have the highest yields in Nigeria?",
        "expected_status": "answered",
        "expected_metric": "median_completed_yield",
    },


    # ========================================================
    # INVESTOR / STAKEHOLDER
    # ========================================================

    {
        "id": "INVESTOR_001",
        "persona": "investor",
        "question":
            "Which states have the highest commercialization share for rice?",
        "expected_status": "answered",
        "expected_metric":
            "median_commercialization_share",
    },

    {
        "id": "INVESTOR_002",
        "persona": "investor",
        "question":
            "What is the most profitable crop?",
        "expected_status": "unsupported",
        "expected_metric": None,
    },

    {
        "id": "INVESTOR_003",
        "persona": "investor",
        "question":
            "How much maize do farmers sell?",
        "expected_status": "answered",
        "expected_metric":
            "median_commercialization_share",
    },


    # ========================================================
    # GENERAL USER
    # ========================================================

    {
        "id": "GENERAL_001",
        "persona": "general",
        "question":
            "What crops do people farm most in Kaduna?",
        "expected_status": "answered",
        "expected_metric": "crop_grower_share",
    },

    {
        "id": "GENERAL_002",
        "persona": "general",
        "question":
            "Which state looks strongest for rice?",
        "expected_status": "needs_clarification",
        "expected_metric": None,
    },

    {
        "id": "GENERAL_003",
        "persona": "general",
        "question":
            "Should I farm maize in Katsina?",
        "expected_status": "reframe_required",
        "expected_metric": None,
    },


    # ========================================================
    # CONVERSATIONAL FOLLOW-UPS
    # ========================================================

    {
        "id": "CONV_001",
        "persona": "general",
        "conversation": [
            "Which states have the highest grower share for rice?",
            "What about Kaduna?",
        ],
        "expected_final_status": "answered",
        "expected_final_metric": "crop_grower_share",
    },

    {
        "id": "CONV_002",
        "persona": "general",
        "conversation": [
            "Which states have the highest grower share for rice?",
            "Show commercialization instead",
        ],
        "expected_final_status": "answered",
        "expected_final_metric":
            "median_commercialization_share",
    },

    {
        "id": "CONV_003",
        "persona": "general",
        "conversation": [
            "How much maize do farmers sell?",
            "What about rice?",
        ],
        "expected_final_status": "answered",
        "expected_final_metric":
            "median_commercialization_share",
    },

]