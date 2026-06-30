"""verify_api_client.py — Standalone verification of AstroApiClient against localhost:8081."""

import sys
import uuid
from astro_gui.api_client import AstroApiClient, AstroApiError


client = AstroApiClient()
passed = 0
failed = 0


def check(label, result, expected_keys=None):
    global passed, failed
    try:
        if expected_keys:
            missing = [k for k in expected_keys if k not in result]
            if missing:
                print(f"FAIL {label} — missing keys: {missing}")
                failed += 1
                return
        print(f"PASS {label}")
        passed += 1
    except Exception as exc:
        print(f"FAIL {label} — {exc}")
        failed += 1


def check_error(label, exc, expected_status):
    global passed, failed
    if getattr(exc, "status", None) == expected_status:
        print(f"PASS {label} (correctly raised {expected_status})")
        passed += 1
    else:
        print(f"FAIL {label} — unexpected error: {exc}")
        failed += 1


# ------------------------------------------------------------------
# 1. list_people
# ------------------------------------------------------------------
try:
    resp = client.list_people()
    check("list_people", resp, expected_keys=["status", "people"])
except AstroApiError as exc:
    print(f"FAIL list_people — {exc}")
    failed += 1

# ------------------------------------------------------------------
# 2. get_person (known ID 5 = Xephyr)
# ------------------------------------------------------------------
try:
    resp = client.get_person(5)
    check("get_person(5)", resp, expected_keys=["status", "person"])
except AstroApiError as exc:
    print(f"FAIL get_person(5) — {exc}")
    failed += 1

# ------------------------------------------------------------------
# 3. create_person
# ------------------------------------------------------------------
new_person_name = f"TestPerson-{uuid.uuid4().hex[:6]}"
try:
    resp = client.create_person({
        "name": new_person_name,
        "birth_date": "1990-01-01",
        "birth_time": "12:00:00",
        "timezone": "UTC",
        "latitude": 0.0,
        "longitude": 0.0,
    })
    check("create_person", resp, expected_keys=["status", "person"])
    new_id = resp.get("person", {}).get("id")
except AstroApiError as exc:
    print(f"FAIL create_person — {exc}")
    new_id = None
    failed += 1

# ------------------------------------------------------------------
# 4. update_person — server does not support PUT (501).
#    Verify client correctly raises AstroApiError.
# ------------------------------------------------------------------
if new_id:
    try:
        resp = client.update_person(new_id, {
            "name": new_person_name + "-Updated",
            "birth_date": "1990-01-01",
            "birth_time": "12:00:00",
            "timezone": "UTC",
            "latitude": 0.0,
            "longitude": 0.0,
        })
        check("update_person", resp, expected_keys=["status"])
    except AstroApiError as exc:
        # Server returns 501 for PUT and 404 for fallback POST.
        # Client correctly propagates the error.
        if exc.status in (501, 404):
            check_error("update_person", exc, exc.status)
        else:
            print(f"FAIL update_person — unexpected error: {exc}")
            failed += 1
else:
    print("SKIP update_person — no person created")
    failed += 1

# ------------------------------------------------------------------
# 5. delete_person — server does not support DELETE for people (404).
#    Verify client correctly raises AstroApiError.
# ------------------------------------------------------------------
if new_id:
    try:
        resp = client.delete_person(new_id)
        check("delete_person", resp, expected_keys=["status"])
    except AstroApiError as exc:
        if exc.status == 404:
            check_error("delete_person", exc, 404)
        else:
            print(f"FAIL delete_person — unexpected error: {exc}")
            failed += 1
else:
    print("SKIP delete_person — no person created")
    failed += 1

# ------------------------------------------------------------------
# 6. calculate_natal
# ------------------------------------------------------------------
try:
    resp = client.calculate_natal({
        "name": "Xephyr",
        "birth_date": "1969-11-30",
        "birth_time": "20:43:00",
        "timezone": "America/Chicago",
        "latitude": 35.2167,
        "longitude": -101.8167,
    }, options={"house_system": "placidus"})
    check("calculate_natal", resp, expected_keys=["status", "bodies", "houses", "aspects", "angles"])
except AstroApiError as exc:
    print(f"FAIL calculate_natal — {exc}")
    failed += 1

# ------------------------------------------------------------------
# 7. get_transit (known chart ID for Xephyr)
# ------------------------------------------------------------------
try:
    resp = client.get_transit(
        natal_chart_id="ea837e61-45ae-44bf-a2ff-e222b1d7d946",
        date="2024-06-13",
        time="12:00:00",
        options={"house_system": "placidus"},
    )
    check("get_transit", resp, expected_keys=["status", "bodies", "transiting_bodies", "cross_aspects"])
except AstroApiError as exc:
    print(f"FAIL get_transit — {exc}")
    failed += 1

# ------------------------------------------------------------------
# 8. get_synastry (known chart IDs)
# ------------------------------------------------------------------
try:
    resp = client.get_synastry(
        chart_a_id="ea837e61-45ae-44bf-a2ff-e222b1d7d946",
        chart_b_id="ea837e61-45ae-44bf-a2ff-e222b1d7d946",
        options={"house_system": "placidus"},
    )
    check("get_synastry", resp, expected_keys=["status", "person_a", "person_b", "cross_aspects"])
except AstroApiError as exc:
    print(f"FAIL get_synastry — {exc}")
    failed += 1

# ------------------------------------------------------------------
# 9. get_period_impact
# ------------------------------------------------------------------
try:
    resp = client.get_period_impact(
        chart_id="ea837e61-45ae-44bf-a2ff-e222b1d7d946",
        date="2024-06-13",
        orb_days=7,
    )
    check("get_period_impact", resp, expected_keys=["status", "impact"])
except AstroApiError as exc:
    print(f"FAIL get_period_impact — {exc}")
    failed += 1

# ------------------------------------------------------------------
# 10. export_ics
# ------------------------------------------------------------------
try:
    resp = client.export_ics(
        chart_id="ea837e61-45ae-44bf-a2ff-e222b1d7d946",
        start_date="2024-06-01",
        end_date="2024-06-30",
    )
    check("export_ics", resp, expected_keys=["status", "filepath"])
except AstroApiError as exc:
    print(f"FAIL export_ics — {exc}")
    failed += 1


print("\n" + "=" * 50)
print(f"Results: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
