"""Discovery for priority fintech and banking employers.

These employers often use proprietary career platforms, so they are not
represented by the ATS board registry. The utility creates narrow, official
career-page queries for the configured Google Programmable Search connector.
"""
from ats.google_search import fetch_google_jobs


PRIORITY_COMPANIES = {
    "JPMorgan Chase": ("jpmorganchase.com", "jpmorgan.com"),
    "Barclays": ("barclays.com",),
    "Goldman Sachs": ("goldmansachs.com",),
    "Morgan Stanley": ("morganstanley.com",),
    "HSBC": ("hsbc.com",),
    "Visa": ("visa.com",),
    "Mastercard": ("mastercard.com",),
    "American Express": ("americanexpress.com",),
    "Bank of America": ("bankofamerica.com",),
    "Wells Fargo": ("wellsfargo.com",),
    "Citi": ("citigroup.com", "citi.com"),
    "Capital One": ("capitalone.com",),
    "PayPal": ("paypal.com",),
    "Wise": ("wise.com",),
    "Revolut": ("revolut.com",),
    "Stripe": ("stripe.com",),
    "Plaid": ("plaid.com",),
    "Checkout.com": ("checkout.com",),
    "Adyen": ("adyen.com",),
    "Airwallex": ("airwallex.com",),
}


def build_priority_queries(role_terms=None, locations=None):
    role_terms = role_terms or '"software engineer" OR "backend engineer" OR "Java engineer"'
    locations = locations or "India OR Bengaluru OR Bangalore OR Hyderabad OR Pune OR remote"
    return [
        f'site:{domain} (careers OR jobs) ({role_terms}) ({locations})'
        for domains in PRIORITY_COMPANIES.values()
        for domain in domains
    ]


def fetch_priority_jobs(config=None):
    config = config or {}
    priority = config.get("priority_company_discovery", {})
    queries = priority.get("queries") or build_priority_queries(
        priority.get("role_terms"), priority.get("locations")
    )
    return fetch_google_jobs(queries, priority.get("max_results_per_query", 3))
