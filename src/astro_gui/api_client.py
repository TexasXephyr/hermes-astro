"""AstroApiClient — stdlib HTTP client for the astrology GUI API."""

import json
import urllib.request
import urllib.error


class AstroApiError(Exception):
    """Raised on non-2xx HTTP status or API-level errors."""
    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


class AstroApiClient:
    """Wraps the astrology REST API at localhost:8081 using only urllib."""

    def __init__(self, base_url="http://localhost:8081"):
        self.base_url = base_url.rstrip("/")

    def _request(self, method, path, payload=None, headers=None):
        url = f"{self.base_url}{path}"
        req_headers = {"Accept": "application/json"}
        if headers:
            req_headers.update(headers)

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return json.loads(raw.decode("utf-8"))
                return raw.decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            raise AstroApiError(f"HTTP {exc.code}: {exc.reason}", status=exc.code, body=body) from exc
        except urllib.error.URLError as exc:
            raise AstroApiError(f"Connection error: {exc.reason}") from exc

    # ------------------------------------------------------------------
    # People
    # ------------------------------------------------------------------
    def list_people(self):
        """GET /v1/people"""
        return self._request("GET", "/v1/people")

    def get_person(self, person_id):
        """GET /v1/people/{id}"""
        return self._request("GET", f"/v1/people/{person_id}")

    def create_person(self, data):
        """POST /v1/people"""
        return self._request("POST", "/v1/people", payload=data)

    def update_person(self, person_id, data):
        """PUT /v1/people/{id} — falls back to POST equivalent if PUT unavailable."""
        try:
            return self._request("PUT", f"/v1/people/{person_id}", payload=data)
        except AstroApiError as exc:
            if exc.status == 501:
                # Fallback: POST to the same path
                return self._request("POST", f"/v1/people/{person_id}", payload=data)
            raise

    def delete_person(self, person_id):
        """DELETE /v1/people/{id}"""
        return self._request("DELETE", f"/v1/people/{person_id}")

    # ------------------------------------------------------------------
    # Natal Chart Retrieval (persisted)
    # ------------------------------------------------------------------
    def get_natal_chart_for_person(self, person_id):
        """GET /v1/people/{id}/natal-chart — returns persisted natal chart or None."""
        r = self._request("GET", f"/v1/people/{person_id}/natal-chart")
        if r.get("status") == "ok":
            return r.get("natal_chart")
        return None

    # ------------------------------------------------------------------
    # Charts (stateless calculation)
    # ------------------------------------------------------------------
    def calculate_natal(self, person_data, options=None):
        """POST /v1/chart/calculate"""
        payload = {"person": person_data}
        if options is not None:
            payload["options"] = options
        return self._request("POST", "/v1/chart/calculate", payload=payload)

    def get_transit(self, natal_chart_id, date, time, options=None):
        """POST /v1/chart/transit"""
        payload = {
            "natal_chart_id": natal_chart_id,
            "date": date,
            "time": time,
        }
        if options is not None:
            payload["options"] = options
        return self._request("POST", "/v1/chart/transit", payload=payload)

    def get_synastry(self, chart_a_id, chart_b_id, options=None):
        """POST /v1/chart/synastry — API expects chart IDs."""
        payload = {
            "person_a": chart_a_id,
            "person_b": chart_b_id,
        }
        if options is not None:
            payload["options"] = options
        return self._request("POST", "/v1/chart/synastry", payload=payload)

    # ------------------------------------------------------------------
    # Analysis / Export
    # ------------------------------------------------------------------
    def get_period_impact(self, chart_id, date, orb_days):
        """POST /v1/analysis/period-impact — API expects chart_id."""
        payload = {
            "chart_id": chart_id,
            "date": date,
            "orb_days": orb_days,
        }
        return self._request("POST", "/v1/analysis/period-impact", payload=payload)

    def export_ics(self, chart_id, start_date, end_date):
        """POST /v1/export/ics — returns JSON with filepath."""
        payload = {
            "chart_id": chart_id,
            "start_date": start_date,
            "end_date": end_date,
        }
        return self._request("POST", "/v1/export/ics", payload=payload)


# ----------------------------------------------------------------------
# Quick smoke-test when run directly
# ----------------------------------------------------------------------
if __name__ == "__main__":
    client = AstroApiClient()
    try:
        result = client.list_people()
        print("Smoke test PASSED — list_people() returned:", result.get("status"))
    except AstroApiError as exc:
        print("Smoke test FAILED:", exc)
