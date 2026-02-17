import requests
import json

url = "https://www.royalcaribbean.com/cruises/graph"

# Query provided by browser capture
query = """query cruiseSearch_Cruises($filters: String, $qualifiers: String, $sort: CruiseSearchSort, $pagination: CruiseSearchPagination) {
  cruiseSearch(
    filters: $filters
    qualifiers: $qualifiers
    sort: $sort
    pagination: $pagination
  ) {
    results {
      cruises {
        id
        sailings {
          sailDate
        }
      }
    }
  }
}"""

headers = {
    "accept": "*/*",
    "content-type": "application/json",
    "brand": "R",
    "country": "USA",
    "language": "en",
    "currency": "USD",
    "office": "MIA",
    "countryalpha2code": "US",
    "apollographql-client-name": "rci-NextGen-Cruise-Search",
    "skip_authentication": "true",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
}

payload = {
  "operationName": "cruiseSearch_Cruises",
  "variables": {
    "filters": "ship:IC",
    "sort": { "by": "RECOMMENDED" },
    "pagination": { "count": 100, "skip": 0 }
  },
  "query": query
}

try:
    print(f"Sending request to {url}...")
    r = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        if "errors" in data:
            print(f"GraphQL Errors: {data.get('errors')}")
        
        results = data.get("data", {}).get("cruiseSearch", {}).get("results", {})
        cruises = results.get("cruises")
        if cruises:
            print(f"SUCCESS! Found {len(cruises)} cruise entries.")
            all_dates = set()
            for cruise in cruises:
                for sailing in cruise.get("sailings", []):
                    d = sailing.get("sailDate")
                    if d: all_dates.add(d)
            print(f"Found {len(all_dates)} unique sail dates.")
            print(f"Sample dates: {sorted(list(all_dates))[:5]}")
        else:
            print("No results found.")
            print(json.dumps(data, indent=2)[:500])
    else:
        print(f"Error {r.status_code}: {r.text[:500]}")
except Exception as e:
    print(f"Exception: {e}")
