from app.schemas.discovery import DiscoveredLead


def get_sample_leads() -> list[DiscoveredLead]:
    return [
        DiscoveredLead(
            name="Rahul Sharma",
            designation="Founder & CEO",
            company_name="TechFlow AI",
            company_website="https://techflow.example.com",
            linkedin_url="https://linkedin.com/in/rahul-sharma",
            instagram_url="https://instagram.com/techflowai",
            industry="AI",
            location="India",
            business_requirement="Lead generation and sales automation",
            company_size=25,
            source="linkedin",
            source_url="https://linkedin.com/in/rahul-sharma",
            discovery_reason="Matches the target ICP: AI company, founder, India."
        ),
        DiscoveredLead(
            name="Priya Mehta",
            designation="Head of Growth",
            company_name="GrowthLabs",
            company_website="https://growthlabs.example.com",
            linkedin_url="https://linkedin.com/in/priya-mehta",
            instagram_url="https://instagram.com/growthlabs",
            industry="SaaS",
            location="India",
            business_requirement="Customer acquisition and outreach automation",
            company_size=40,
            source="google",
            source_url="https://google.com",
            discovery_reason="Matches the target ICP: SaaS, growth decision-maker, India."
        ),
        DiscoveredLead(
            name="Alex Johnson",
            designation="CEO",
            company_name="MarketPilot",
            company_website="https://marketpilot.example.com",
            linkedin_url="https://linkedin.com/in/alex-johnson",
            instagram_url="https://instagram.com/marketpilot",
            industry="Marketing",
            location="United States",
            business_requirement="AI chatbot and lead qualification",
            company_size=15,
            source="instagram",
            source_url="https://instagram.com/marketpilot",
            discovery_reason="Matches the target ICP through industry, role and AI requirement."
        ),
    ]