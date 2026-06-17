#!/bin/bash
curl -sN "https://gen.pollinations.ai/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEYY" \
  -d '{
    "model": "deepseek-v4-flash",
    "stream": true,
    "messages": [
      {"role": "system", "content": "You are a helpful assistant. Be concise."},
      {"role": "user", "content": "'"$1"'"}
    ]
  }' | while IFS= read -r line; do
    [[ "$line" == data:* ]] || continue
    data="${line#data: }"
    [[ "$data" == "[DONE]" ]] && echo && break
    python3 -c "
import sys,json
d=json.load(sys.stdin)
delta=d['choices'][0]['delta']
reasoning=delta.get('reasoning') or ''
content=delta.get('content') or ''
if reasoning: print('\033[2m'+reasoning+'\033[0m',end='',flush=True)
if content: print('\033[1m'+content+'\033[0m',end='',flush=True)
" <<< "$data" 2>/dev/null
  done
echo
