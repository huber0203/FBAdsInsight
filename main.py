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

def fetch_insights(ad_account_id, since, until):
    url = f"{GRAPH_BASE}/{ad_account_id}/insights"
    params = {
        "access_token": ACCESS_TOKEN,
        "fields": "campaign_name,adset_name,ad_name,spend,date_start,date_stop,actions,cost_per_action_type",
        "level": "ad",
        "filtering": '[{"field":"spend","operator":"GREATER_THAN","value":"3"}]',
        "time_range": f'{{"since":"{since}","until":"{until}"}}',
        "action_breakdowns": '["action_type"]',
        "limit": 200
    }
    res = requests.get(url, params=params)
    res.raise_for_status()
    return res.json().get("data", [])

def extract_lead_data(actions, cpa):
    leads = next((int(float(a["value"])) for a in (actions or []) if a.get("action_type") == "lead"), 0)
    cpl = next((float(a["value"]) for a in (cpa or []) if a.get("action_type") == "lead"), None)
    return leads, cpl

@app.route("/ads-report", methods=["GET"])
def ads_report():
    since = request.args.get("since")
    until = request.args.get("until")

    if not since or not until:
        return jsonify({"error": "Missing required query params: since, until"}), 400

    try:
        accounts = get_ad_accounts()
    except Exception as e:
        return jsonify({"error": f"Failed to get ad accounts: {str(e)}"}), 500

    results = []

    for account in accounts:
        try:
            insights = fetch_insights(account["id"], since, until)
        except Exception as e:
            continue  # skip if one account fails

        for row in insights:
            spend = float(row.get("spend", "0"))
            leads, cpl = extract_lead_data(row.get("actions"), row.get("cost_per_action_type"))

            results.append({
                "ad_account": account.get("name") or account["id"],
                "ad_name": row.get("ad_name"),
                "campaign_name": row.get("campaign_name"),
                "adset_name": row.get("adset_name"),
                "spend": round(spend, 2),
                "leads": leads,
                "cpl": round(cpl, 2) if cpl is not None else None,
                "date_start": row.get("date_start"),
                "date_stop": row.get("date_stop")
            })

    return jsonify({
        "count": len(results),
        "data": results
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
