import requests
import json

response = requests.post(
  url="https://openrouter.ai/api/v1/chat/completions",
  headers={
    "Authorization": f"Bearer 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"
  },
  data=json.dumps({
    "model": "openai/gpt-3.5-turbo",
    "messages": [
      { "role": "user", "content": "What is the meaning of life?" }
    ]
  })
)
print(response.json())