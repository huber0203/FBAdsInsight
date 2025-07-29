import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

ACCESS_TOKEN = os.environ.get("FB_ACCESS_TOKEN")
API_VERSION = "v23.0"
GRAPH_BASE = f"https://graph.facebook.com/{API_VERSION}"

def get_ad_accounts():
    url = f"{GRAPH_BASE}/me/adaccounts"
    res = requests.get(url, params={"access_token": ACCESS_TOKEN})
    res.raise_for_status()
    return res.json().get("data", [])

def get_ads(account_id, since, until):
    url = f"{GRAPH_BASE}/{account_id}/ads"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "name,insights.fields(spend,actions)",
        "time_range[since]": since,
        "time_range[until]": until,
        "filtering": '[{"field":"delivery_info","operator":"IN","value":["active","completed"]}]',
        "limit": 500
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    return res.json().get("data", [])

def extract_leads(actions):
    for a in actions or []:
        if a.get("action_type") == "lead":
            return int(float(a.get("value", "0")))
    return 0

@app.route("/ads-report", methods=["GET"])
def ads_report():
    since = request.args.get("since")
    until = request.args.get("until")

    if not since or not until:
        return jsonify({"error": "Missing required query params: since, until"}), 400

    accounts = get_ad_accounts()
    results = []

    for account in accounts:
        ads = get_ads(account["id"], since, until)
        for ad in ads:
            insight = (ad.get("insights") or {}).get("data", [{}])[0]
            spend = float(insight.get("spend", "0"))
            if spend <= 1:
                continue
            leads = extract_leads(insight.get("actions"))
            cpl = round(spend / leads, 2) if leads > 0 else None
            results.append({
                "ad_account": account.get("name") or account["id"],
                "ad_name": ad["name"],
                "spend": round(spend, 2),
                "leads": leads,
                "cpl": cpl
            })

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
