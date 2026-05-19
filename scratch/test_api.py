import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "dev-key-123"
STOCKS = ["BBNI.JK", "TLKM.JK", "GOTO.JK"]

def test_endpoint(method, path, data=None, params=None):
    url = f"{BASE_URL}{path}"
    headers = {"X-API-Key": API_KEY}
    print(f"Testing {method} {url}...")
    try:
        if method == "GET":
            response = requests.get(url, params=params, headers=headers)
        else:
            response = requests.post(url, json=data, headers=headers)
        
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  Error: {response.text}")
            return None
    except Exception as e:
        print(f"  Exception: {str(e)}")
        return None

def main():
    print("=== STARTING API COMPREHENSIVE TEST ===")
    
    # 1. Health & Metrics
    test_endpoint("GET", "/")
    test_endpoint("GET", "/metrics")
    
    results = {}
    
    for stock in STOCKS:
        print(f"\n--- Testing Stock: {stock} ---")
        stock_results = {}
        
        # 2. Stock Info
        stock_results['info'] = test_endpoint("GET", f"/stock-info/{stock}")
        
        # 3. Fundamental Analysis
        stock_results['fundamental'] = test_endpoint("GET", f"/fundamental-analysis/{stock}")
        
        # 4. Stock News
        stock_results['news'] = test_endpoint("GET", f"/stock-news/{stock}")
        
        # 5. Full Analyze (The new detailed endpoint)
        stock_results['analyze'] = test_endpoint("GET", f"/analyze/{stock}")
        
        # 6. Predict (Requires loaded model)
        # We try it, but it might return 404 if model not trained/loaded
        stock_results['predict'] = test_endpoint("POST", "/predict", data={"stock_code": stock})
        
        results[stock] = stock_results
        time.sleep(1) # Rate limiting

    # Save summary
    with open("api_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n=== TEST COMPLETED ===")
    print("Full results saved to api_test_results.json")

if __name__ == "__main__":
    main()
