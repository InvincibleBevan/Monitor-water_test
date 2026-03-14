import requests
import time
import random
from datetime import datetime

# Configuration
API_URL = "http://localhost:8000/api/telemetry"
INTERVAL_SECONDS = 2
CONTAMINATION_AFTER_SECONDS = 60

def generate_normal_data():
    """Generates normal, safe water telemetry data."""
    return {
        "ph": round(random.uniform(6.8, 7.5), 2),
        "turbidity": round(random.uniform(0.5, 2.0), 2),
        "temperature": round(random.uniform(18.0, 22.0), 2),
        "conductivity": round(random.uniform(300, 450), 2),
        "safety_score": round(random.uniform(90, 100), 1),
        "pathogen_concentration": round(random.uniform(0.0, 10.0), 1)
    }

def generate_contaminated_data():
    """Generates abnormal, dangerous water telemetry data."""
    return {
        "ph": round(random.choice([random.uniform(3.0, 5.0), random.uniform(9.0, 11.0)]), 2), # Too acidic or basic
        "turbidity": round(random.uniform(15.0, 50.0), 2), # Very cloudy
        "temperature": round(random.uniform(25.0, 30.0), 2), # Unusually warm
        "conductivity": round(random.uniform(800, 1500), 2), # High dissolved solids
        "safety_score": round(random.uniform(10, 35), 1), # Dangerously low
        "pathogen_concentration": round(random.uniform(100.0, 500.0), 1)
    }

def main():
    print(f"🌊 Starting Sensor Simulator...")
    print(f"⏱️ Will run normal for {CONTAMINATION_AFTER_SECONDS} seconds, then simulate connection/contamination issues.")
    print("-" * 50)
    
    start_time = time.time()
    forced_contamination = False
    
    while True:
        elapsed = time.time() - start_time
        
        # Decide if we should generate contaminated data based on time OR server response
        if elapsed > CONTAMINATION_AFTER_SECONDS or forced_contamination:
            data = generate_contaminated_data()
            status_text = "🚨 CONTAMINATED"
        else:
            data = generate_normal_data()
            status_text = "✅ NORMAL"

        # Try to send the data to the backend
        try:
            response = requests.post(API_URL, json=data, timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                # Check if the server told us we are in a forced contamination state (e.g. via UI button)
                forced_contamination = result.get("is_contaminated", False)
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {status_text} | pH: {data['ph']} | Tur: {data['turbidity']} | Pathogens: {data['pathogen_concentration']} | Score: {data['safety_score']}")
            else:
                print(f"⚠️ Server returned status code: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("❌ Connection Error: Ensure the FastAPI backend is running on port 8000.")
        except Exception as e:
            print(f"❌ Error sending data: {e}")

        # Wait before sending the next reading
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    # Ensure requests library is installed, if not provide a helpful message
    try:
        import requests
    except ImportError:
        print("The 'requests' library is missing. Please run: pip install requests")
        exit(1)
        
    main()
