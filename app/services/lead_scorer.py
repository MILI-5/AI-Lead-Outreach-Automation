from typing import Optional


# ---------------------------------------------------------
# Ideal Customer Profile
# ---------------------------------------------------------

TARGET_INDUSTRIES = {
    "saas",
    "software",
    "technology",
    "fintech",
    "ecommerce",
    "edtech",
    "healthtech",
    "ai",
    "artificial intelligence",
    "marketing",
    "sales",
}


TARGET_DESIGNATIONS = {
    "founder",
    "co-founder",
    "ceo",
    "chief executive officer",
    "cto",
    "chief technology officer",
    "head of sales",
    "sales director",
    "head of growth",
    "growth manager",
    "vp sales",
    "vp growth",
}


TARGET_LOCATIONS = {
    "india",
    "united states",
    "usa",
    "uk",
    "united kingdom",
    "canada",
    "australia",
}


TARGET_REQUIREMENTS = {
    "lead generation",
    "lead qualification",
    "sales automation",
    "outreach automation",
    "client outreach",
    "crm automation",
    "ai automation",
    "sales automation",
    "chatbot",
    "ai chatbot",
    "customer acquisition",
}


def normalize(value: Optional[str]) -> str:
    """
    Normalize text before comparison.
    """

    if not value:
        return ""

    return value.lower().strip()


def contains_keyword(
    text: str,
    keywords: set[str]
) -> bool:
    """
    Check whether any target keyword exists
    inside the provided text.
    """

    normalized_text = normalize(text)

    return any(
        keyword in normalized_text
        for keyword in keywords
    )


def calculate_icp_score(lead) -> int:
    """
    Calculate an explainable ICP score from 0 to 100.
    """

    score = 0

    # -----------------------------------------------------
    # 1. Industry
    # -----------------------------------------------------

    if contains_keyword(
        lead.industry,
        TARGET_INDUSTRIES
    ):
        score += 25

    # -----------------------------------------------------
    # 2. Decision-maker designation
    # -----------------------------------------------------

    if contains_keyword(
        lead.designation,
        TARGET_DESIGNATIONS
    ):
        score += 25

    # -----------------------------------------------------
    # 3. Location
    # -----------------------------------------------------

    if contains_keyword(
        lead.location,
        TARGET_LOCATIONS
    ):
        score += 10

    # -----------------------------------------------------
    # 4. Business requirement
    # -----------------------------------------------------

    if contains_keyword(
        lead.business_requirement,
        TARGET_REQUIREMENTS
    ):
        score += 25

    # -----------------------------------------------------
    # 5. Company size
    # -----------------------------------------------------

    if lead.company_size:

        if lead.company_size >= 10:
            score += 15

    return min(score, 100)


def categorize_lead(score: int) -> str:
    """
    Convert ICP score into a business category.
    """

    if score >= 60:
        return "Qualified"

    if score >= 40:
        return "Potential"

    return "Not Qualified"