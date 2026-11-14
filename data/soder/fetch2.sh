#!/bin/zsh
cd "$(dirname "$0")"
for f in spots base extra; do
  for w in 0 30 60 120 180; do
    sleep $w
    for ep in https://overpass-api.de/api/interpreter https://maps.mail.ru/osm/tools/overpass/api/interpreter; do
      curl -s --max-time 280 -A "skatemap-local/1.0" --data-urlencode data@q2_$f.txt $ep -o ${f}2.json
      python3 -c "import json;print('$f',len(json.load(open('${f}2.json'))['elements']))" 2>/dev/null && continue 3
    done
  done
done
