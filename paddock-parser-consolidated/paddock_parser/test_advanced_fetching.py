import asyncio
import pprint
from .fetching import resolve_multi, resilient_get, close_shared_async_client

async def main():
    print("--- Testing DNS Multi-Resolver ---")
    dns_results = await resolve_multi("google.com")
    print("DNS Results for google.com:")
    pprint.pprint(dns_results)

    print("\n--- Testing Resilient Get (triggers content fingerprinting) ---")
    try:
        response = await resilient_get("https://www.google.com")
        print(f"Successfully fetched google.com. Status: {response.status_code}")
        print("Content fingerprinting was triggered internally.")
    except Exception as e:
        print(f"An error occurred during resilient_get: {e}")
    finally:
        await close_shared_async_client()

if __name__ == "__main__":
    asyncio.run(main())
