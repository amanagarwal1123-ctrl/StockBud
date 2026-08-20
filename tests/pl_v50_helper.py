import os, sys, json, requests
from dotenv import dotenv_values
BASE = dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"
tok = requests.post(f"{API}/auth/login", json={"username":"admin","password":"admin123"}, timeout=60).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

cmd = sys.argv[1] if len(sys.argv) > 1 else "state"

if cmd == "state":
    d = requests.get(f"{API}/purchase-list", headers=H, timeout=180).json()
    print("orderers:", d["orderers"])
    cnt = {}
    for r in d["rows"]:
        if r.get("temp_removed") or r.get("perm_removed"): continue
        cnt[r.get("purview")] = cnt.get(r.get("purview"),0)+1
    print("counts(base-ish):", cnt)
    print("total rows:", len(d["rows"]))
    for r in d["rows"]:
        if r.get("purview") != "Admin" or r.get("green") or r.get("seasonal_enabled"):
            print(" special:", r["item_name"], r.get("purview"), "green=",r.get("green"), "season=",r.get("season_months"), "temp=",r.get("temp_removed"), "perm=",r.get("perm_removed"))
elif cmd == "setup":
    for n in ("QA_EMPTY","QA_DEL"):
        print(n, requests.post(f"{API}/purchase-list/orderers", json={"name":n}, headers=H, timeout=60).status_code)
    d = requests.get(f"{API}/purchase-list", headers=H, timeout=180).json()
    # pick an Admin item that is not seasonal-out and not removed
    tgt = next(r for r in d["rows"] if r.get("purview")=="Admin" and not r.get("temp_removed") and not r.get("perm_removed") and not r.get("seasonal_enabled"))
    print("assigning", tgt["item_name"], "to QA_DEL")
    print(requests.post(f"{API}/purchase-list/item-state", json={"item_name":tgt["item_name"],"purview":"QA_DEL"}, headers=H, timeout=60).status_code)
    json.dump({"item": tgt["item_name"]}, open("/tmp/qa_del_item.json","w"))
elif cmd == "cleanup":
    d = requests.get(f"{API}/purchase-list", headers=H, timeout=180).json()
    for o in d["orderers"]:
        if o.startswith("QA_"):
            print("del", o, requests.delete(f"{API}/purchase-list/orderers/{o}", params={"reassign_to":"Admin"}, headers=H, timeout=60).text[:120])
elif cmd == "rename_back":
    print(requests.put(f"{API}/purchase-list/orderers/{sys.argv[2]}", json={"new_name": sys.argv[3]}, headers=H, timeout=60).text[:200])
