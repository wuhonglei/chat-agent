from .models import IPLocatorResponse


def format_results(response: IPLocatorResponse) -> str:
    """
    Format the response to a human-readable string
    """
    return f"""
Status: {response.status}
Country: {response.country}
Country Code: {response.countryCode}
Region: {response.region}
Region Name: {response.regionName}
City: {response.city}
Latitude: {response.lat:.6f}
Longitude: {response.lon:.6f}
Timezone: {response.timezone}
""".strip()
