import requests
import json

def trigger_debug():
    url = "http://localhost:8001/api/chat/send"
    
    # Credentials from .env
    db_params = {
        "host": "localhost",
        "port": 3050,
        "database": r"C:\Distrito\OBRAS\Database\JUANDEDI\2021.fdb",
        "user": "SYSDBA",
        "password": "masterkey",
        "charset": "latin1"
    }
    
    payload = {
        "message": "DEBUG_COLUMNS DOCCAB",
        "model_id": "groq-llama-70b",
        "db_params": db_params
    }
    
    print(f"Enviando petición a {url}...")
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            result = data.get('response', 'No response field')
            
            # Save to file
            output_file = "backend/scripts/debug_output.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result)
            
            print(f"\nRespuesta guardada en: {output_file}")
            print(f"Primeros 500 caracteres:\n{result[:500]}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Error conectando al servidor: {str(e)}")

if __name__ == "__main__":
    trigger_debug()
