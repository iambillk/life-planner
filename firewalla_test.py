#!/usr/bin/env python3
"""
Firewalla MSP API Discovery Script
Tests all possible endpoints and dumps results to file
Run: python3 firewalla_test.py
Output: firewalla_api_results.txt
"""

import requests
import json
from datetime import datetime, timedelta
import time

# ==================== CONFIGURATION ====================
FW_API_DOMAIN = "totalchoice.firewalla.net"
FW_TOKEN = "fe7f069d59606cd62b0653a8a417303e"
FW_TARGET_LIST_ID = "TL-8a3af152-551a-4355-b61b-f1e494723b2a"

BASE_URL = f"https://{FW_API_DOMAIN}/v2"
HEADERS = {
    "Authorization": f"Token {FW_TOKEN}",
    "Content-Type": "application/json"
}

# Output file
OUTPUT_FILE = "firewalla_api_results.txt"

# ==================== LOGGING FUNCTIONS ====================

class Logger:
    def __init__(self, filename):
        self.file = open(filename, 'w', encoding='utf-8')
        self.file.write(f"FIREWALLA MSP API DISCOVERY RESULTS\n")
        self.file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.file.write(f"API Domain: {FW_API_DOMAIN}\n")
        self.file.write("="*80 + "\n\n")
    
    def write(self, text):
        """Write to both file and console"""
        print(text)
        self.file.write(text + "\n")
        self.file.flush()  # Ensure immediate write
    
    def write_json(self, data):
        """Write formatted JSON to file"""
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        self.write(json_str)
    
    def close(self):
        self.file.close()

# Initialize logger
log = Logger(OUTPUT_FILE)

# ==================== TEST FUNCTIONS ====================

def print_header(title):
    """Print a formatted section header"""
    log.write("\n" + "="*60)
    log.write(title)
    log.write("="*60)

def test_endpoint(endpoint, method="GET", data=None, show_full=False):
    """Test a single endpoint and log results"""
    url = f"{BASE_URL}{endpoint}"
    log.write(f"\nTesting: {method} {endpoint}")
    log.write(f"URL: {url}")
    
    try:
        start_time = time.time()
        
        if method == "GET":
            response = requests.get(url, headers=HEADERS, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=HEADERS, json=data, timeout=10)
        elif method == "PATCH":
            response = requests.patch(url, headers=HEADERS, json=data, timeout=10)
        else:
            log.write(f"   Unsupported method: {method}")
            return None
        
        elapsed = time.time() - start_time
        log.write(f"Response Time: {elapsed:.2f}s")
        log.write(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            # First check if it's JSON
            try:
                json_data = response.json()
                log.write("✅ SUCCESS - Valid JSON Response")
                
                # Always write full response to file
                log.write("\n--- RESPONSE DATA ---")
                log.write_json(json_data)
                
                # Analyze response structure
                if isinstance(json_data, dict):
                    log.write(f"\nResponse Type: Object")
                    log.write(f"Keys: {', '.join(json_data.keys())}")
                    
                    # Log nested structure
                    for key, value in json_data.items():
                        if isinstance(value, list):
                            log.write(f"  {key}: List with {len(value)} items")
                        elif isinstance(value, dict):
                            log.write(f"  {key}: Object with keys: {', '.join(value.keys())}")
                        else:
                            log.write(f"  {key}: {type(value).__name__}")
                            
                elif isinstance(json_data, list):
                    log.write(f"\nResponse Type: Array with {len(json_data)} items")
                    if json_data and isinstance(json_data[0], dict):
                        log.write(f"First item keys: {', '.join(json_data[0].keys())}")
                
                log.write("-" * 40)
                return json_data
                
            except json.JSONDecodeError:
                # Check if it's HTML
                if response.text.strip().startswith('<!DOCTYPE') or response.text.strip().startswith('<html'):
                    log.write("❌ FAILED - Received HTML instead of JSON (likely login page)")
                    log.write("Response preview (first 500 chars):")
                    log.write(response.text[:500])
                else:
                    log.write("❌ FAILED - Response is not valid JSON")
                    log.write("Response preview (first 1000 chars):")
                    log.write(response.text[:1000])
                return None  # Return None for failed endpoints
                
        elif response.status_code == 401:
            log.write(f"❌ UNAUTHORIZED - Check API token")
            log.write(f"Error Response: {response.text[:500]}")
            return None
        elif response.status_code == 403:
            log.write(f"❌ FORBIDDEN - No access to this endpoint")
            log.write(f"Error Response: {response.text[:500]}")
            return None
        elif response.status_code == 404:
            log.write(f"❌ NOT FOUND - Endpoint doesn't exist")
            return None
        else:
            log.write(f"❌ FAILED - Status: {response.status_code}")
            log.write(f"Error Response: {response.text[:500]}")
            return None
            
    except requests.exceptions.Timeout:
        log.write("❌ TIMEOUT - Request timed out after 10 seconds")
        return None
    except requests.exceptions.ConnectionError as e:
        log.write(f"❌ CONNECTION ERROR: {str(e)[:200]}")
        return None
    except Exception as e:
        log.write(f"❌ EXCEPTION: {str(e)[:200]}")
        return None

# ==================== MAIN TEST SUITE ====================

def main():
    log.write("╔══════════════════════════════════════════════════════════╗")
    log.write("║         FIREWALLA MSP API DISCOVERY TOOL                ║")
    log.write("║         Testing: totalchoice.firewalla.net              ║")
    log.write("╚══════════════════════════════════════════════════════════╝")
    
    results = {}
    working_endpoints = []
    
    # ========== KNOWN WORKING ENDPOINT ==========
    print_header("1. TESTING KNOWN WORKING ENDPOINT")
    known = test_endpoint(f"/target-lists/{FW_TARGET_LIST_ID}")
    if known:
        results['target_list'] = known
        working_endpoints.append(f"/target-lists/{FW_TARGET_LIST_ID}")
        log.write("\n✓ API connection confirmed working!")
    else:
        log.write("\n✗ Known endpoint failed - check token/connection")
        log.close()
        return
    
    # ========== DISCOVER ROOT/INFO ENDPOINTS ==========
    print_header("2. DISCOVERING API STRUCTURE")
    endpoints_to_test = [
        "/",
        "/info",
        "/version",
        "/status",
        "/health",
        "/api",
        "/docs",
        "/openapi",
        "/swagger"
    ]
    
    for endpoint in endpoints_to_test:
        result = test_endpoint(endpoint)
        if result:
            results[endpoint] = result
            working_endpoints.append(endpoint)
    
    # ========== MSP MANAGEMENT ENDPOINTS ==========
    print_header("3. MSP MANAGEMENT ENDPOINTS")
    msp_endpoints = [
        "/boxes",
        "/devices", 
        "/networks",
        "/organization",
        "/account",
        "/users",
        "/groups",
        "/customers",
        "/sites"
    ]
    
    for endpoint in msp_endpoints:
        result = test_endpoint(endpoint)
        if result:
            results[endpoint] = result
            working_endpoints.append(endpoint)
    
    # ========== SECURITY & MONITORING ENDPOINTS ==========
    print_header("4. SECURITY & MONITORING ENDPOINTS")
    security_endpoints = [
        "/alarms",
        "/alerts",
        "/events",
        "/security",
        "/threats",
        "/incidents",
        "/logs",
        "/audit",
        "/activities",
        "/notifications",
        "/vulnerabilities"
    ]
    
    for endpoint in security_endpoints:
        result = test_endpoint(endpoint)
        if result:
            results[endpoint] = result
            working_endpoints.append(endpoint)
    
    # ========== NETWORK ANALYTICS ENDPOINTS ==========
    print_header("5. NETWORK ANALYTICS ENDPOINTS")
    network_endpoints = [
        "/flows",
        "/traffic",
        "/bandwidth",
        "/stats",
        "/statistics",
        "/metrics",
        "/analytics",
        "/usage",
        "/top-talkers",
        "/connections",
        "/sessions"
    ]
    
    for endpoint in network_endpoints:
        result = test_endpoint(endpoint)
        if result:
            results[endpoint] = result
            working_endpoints.append(endpoint)
    
    # ========== RULES & POLICIES ENDPOINTS ==========
    print_header("6. RULES & POLICIES ENDPOINTS")
    rules_endpoints = [
        "/rules",
        "/policies",
        "/target-lists",  # We know this works
        "/blocklists",
        "/allowlists",
        "/acl",
        "/firewall",
        "/filters"
    ]
    
    for endpoint in rules_endpoints:
        result = test_endpoint(endpoint)
        if result:
            results[endpoint] = result
            working_endpoints.append(endpoint)
    
    # ========== IF WE FOUND BOXES, TEST BOX-SPECIFIC ==========
    if "/boxes" in [e for e in working_endpoints]:
        print_header("7. BOX-SPECIFIC ENDPOINTS")
        boxes_data = results.get("/boxes")
        if boxes_data:
            # Handle both list and object responses
            if isinstance(boxes_data, list) and len(boxes_data) > 0:
                box_id = boxes_data[0].get('id') or boxes_data[0].get('box_id')
            elif isinstance(boxes_data, dict):
                # Maybe boxes are in a 'data' or 'boxes' key
                if 'data' in boxes_data and isinstance(boxes_data['data'], list):
                    box_id = boxes_data['data'][0].get('id') if boxes_data['data'] else None
                elif 'boxes' in boxes_data and isinstance(boxes_data['boxes'], list):
                    box_id = boxes_data['boxes'][0].get('id') if boxes_data['boxes'] else None
                else:
                    box_id = boxes_data.get('id')
            else:
                box_id = None
                
            if box_id:
                log.write(f"\nFound Box ID: {box_id}")
                box_endpoints = [
                    f"/boxes/{box_id}",
                    f"/boxes/{box_id}/status",
                    f"/boxes/{box_id}/alarms",
                    f"/boxes/{box_id}/flows",
                    f"/boxes/{box_id}/devices",
                    f"/boxes/{box_id}/stats",
                    f"/boxes/{box_id}/rules",
                    f"/boxes/{box_id}/alerts",
                    f"/boxes/{box_id}/config"
                ]
                for endpoint in box_endpoints:
                    result = test_endpoint(endpoint)
                    if result:
                        results[endpoint] = result
                        working_endpoints.append(endpoint)
    
    # ========== TIME-BASED QUERIES ==========
    print_header("8. TIME-BASED QUERIES (Last 24 Hours)")
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    
    time_params = f"?start={yesterday.isoformat()}Z&end={now.isoformat()}Z"
    time_endpoints = [
        f"/alarms{time_params}",
        f"/alerts{time_params}",
        f"/events{time_params}",
        f"/flows{time_params}",
        f"/stats{time_params}"
    ]
    
    for endpoint in time_endpoints:
        result = test_endpoint(endpoint)
        if result:
            results[endpoint] = result
            working_endpoints.append(endpoint)
    
    # ========== ADDITIONAL DISCOVERY ==========
    print_header("9. ADDITIONAL ENDPOINT DISCOVERY")
    
    # Test pagination and limits
    if "/alarms" in [e.split('?')[0] for e in working_endpoints]:
        test_endpoint("/alarms?limit=10")
        test_endpoint("/alarms?offset=0&limit=5")
    
    # Test different target list endpoints
    test_endpoint("/target-lists")  # Get all lists
    
    # ========== FINAL SUMMARY ==========
    print_header("DISCOVERY COMPLETE - SUMMARY")
    
    log.write(f"\n✅ WORKING ENDPOINTS FOUND: {len(working_endpoints)}")
    log.write("\nWorking Endpoints List:")
    for endpoint in sorted(working_endpoints):
        log.write(f"   • {endpoint}")
    
    log.write(f"\n📊 Statistics:")
    log.write(f"   Total endpoints tested: ~60")
    log.write(f"   Working endpoints: {len(working_endpoints)}")
    log.write(f"   Success rate: {(len(working_endpoints)/60)*100:.1f}%")
    
    # ========== SAVE RESULTS SUMMARY ==========
    print_header("RESULTS SAVED")
    log.write(f"\nFull results have been saved to: {OUTPUT_FILE}")
    log.write("\n✨ Discovery complete! Ready to build the Firewalla integration module!")
    
    # Save a JSON summary for easy parsing
    summary_file = "firewalla_api_summary.json"
    with open(summary_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "api_domain": FW_API_DOMAIN,
            "working_endpoints": working_endpoints,
            "endpoint_count": len(working_endpoints),
            "full_results": {k: ("DATA_FOUND" if v else "NO_DATA") for k, v in results.items()}
        }, f, indent=2)
    
    log.write(f"JSON summary saved to: {summary_file}")
    
    log.close()
    print(f"\n📄 Results saved to: {OUTPUT_FILE}")
    print(f"📊 Summary saved to: {summary_file}")

if __name__ == "__main__":
    main()