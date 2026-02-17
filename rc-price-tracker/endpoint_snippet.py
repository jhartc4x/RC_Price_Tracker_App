    @app.get("/api/sailings")
    def api_sailings() -> Any:
        ship_code = request.args.get("ship_code", "").strip()
        if not ship_code:
            return jsonify({"sailings": []})

        url = "https://www.royalcaribbean.com/cruises/graph"
        query = """query cruiseSearch_Cruises($filters: String, $qualifiers: String, $sort: CruiseSearchSort, $pagination: CruiseSearchPagination) {
  cruiseSearch(
    filters: $filters
    qualifiers: $qualifiers
    sort: $sort
    pagination: $pagination
  ) {
    results {
      cruises {
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
                "filters": f"ship:{ship_code}",
                "sort": {"by": "RECOMMENDED"},
                "pagination": {"count": 100, "skip": 0},
            },
            "query": query,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", {}).get("cruiseSearch", {}).get("results", {})
                cruises = results.get("cruises") or []
                
                all_dates = set()
                for cruise in cruises:
                    for sailing in cruise.get("sailings", []):
                        d = sailing.get("sailDate")
                        if d:
                            all_dates.add(str(d))
                
                # Sort dates
                sorted_dates = sorted(list(all_dates))
                return jsonify({"sailings": sorted_dates})
            
            return jsonify({"sailings": [], "error": f"API error: {resp.status_code}"})
            
        except Exception as exc:
            return jsonify({"sailings": [], "error": str(exc)})

