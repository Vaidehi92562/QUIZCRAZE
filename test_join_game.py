import requests

url = "http://127.0.0.1:5000/join_game"
data = {
    "gameCode": "884463",  # Change this to your actual game code
    "username": "TestPlayer"  # Change this to your username
}

response = requests.post(url, json=data)

print("Status Code:", response.status_code)
print("Response:", response.json())
