import json, requests, random
BASE = "https://api-sandbox.factus.com.co"
CREDS = {"grant_type": "password", "client_id": "a1e16e08-36ad-4298-9f0c-babe687887ef",
         "client_secret": "9Kaj0xT3RLtvPdXOUUNEG769Pry9Dj0T0tZGrYL6",
         "username": "sandboxv2@factus.com.co", "password": "sandbox2026%"}
tok = requests.post(f"{BASE}/oauth/token", data=CREDS, timeout=30).json()["access_token"]
H = {"Authorization": f"Bearer {tok}", "Accept": "application/json"}
HJ = {**H, "Content-Type": "application/json"}
cust = {"identification": "1234567890", "dv": "", "names": "AC", "address": "C1", "email": "a@a.com", "phone": "3001234567",
        "legal_organization_id": "2", "tribute_id": "21", "identification_document_id": "3", "identification_document_code": "13", "municipality_id": "980"}
items = [{"code_reference": "E1", "name": "Pension", "quantity": 1, "discount_rate": 0, "price": 100000, "tax_rate": "0.00",
          "unit_measure_id": 70, "unit_measure_code": "94", "standard_code_id": 1, "standard_code": "999", "is_excluded": 1, "tribute_id": 1, "taxes": [{"code": "01", "rate": "0.00"}]}]
ref = f"XML-{random.randint(1000,9999)}"
num = requests.post(f"{BASE}/v2/bills/validate", headers=HJ, json={"numbering_range_id": 389, "reference_code": ref, "observation": "x", "payment_form": "1", "payment_due_date": "2026-06-30", "payment_method_code": "10", "operation_type": "10", "payment_details": [{"payment_form": "1", "payment_method_code": "10", "amount": 100000}], "customer": cust, "items": items}).json()["data"]["number"]
print("bill:", num)
for path in [f"/v2/bills/download-pdf/{num}", f"/v2/bills/download-xml/{num}",
             f"/v2/bills/{num}/download-pdf", f"/v2/bills/{num}/download-xml"]:
    r = requests.get(f"{BASE}{path}", headers=H, timeout=30)
    info = ""
    if r.status_code == 200:
        try:
            j = r.json(); d = j.get("data", j)
            info = " keys=" + str(list(d.keys())[:8]) if isinstance(d, dict) else ""
        except: info = " (no json)"
    print(f"GET {path} -> {r.status_code}{info}")
