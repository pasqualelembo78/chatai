#!/bin/bash
# Chiude il lavoro di traduzione: attende i worker, ritenta gli scarti, rigenera i prompt
# in italiano, riavvia il backend e ricostruisce l'indice delle griglie.
set -u
cd /opt/aria/backend || exit 1

echo "[finisher] attendo la fine dei worker..."
while pgrep -f "^python3 characters/translate" >/dev/null; do sleep 20; done

echo "[finisher] ritento i personaggi rimasti in inglese (passata singola)"
timeout 14400 python3 characters/translate_identities.py >> /tmp/translate_finale.log 2>&1

echo "[finisher] completo le identità rimaste vuote"
python3 characters/synthesize_identity.py >> /tmp/apply_finale.log 2>&1

echo "[finisher] rigenero i system_prompt in italiano"
python3 characters/apply_categories.py --force > /tmp/apply_finale.log 2>&1
chown -R chatai:chatai characters/data characters/*.py 2>/dev/null

echo "[finisher] riavvio il backend"
systemctl restart chatai.service
sleep 12
systemctl is-active chatai.service

echo "[finisher] ricostruisco l'indice griglie e svuoto le cache"
php -r 'require "/var/www/pornovirtuale/wp-load.php"; aria_grid_index(true); if (function_exists("wp_cache_clean_cache")) { wp_cache_clean_cache(array("file_prefix"=>"supercache","maximum_level"=>0)); } wp_cache_flush(); echo "cache ok\n";' 2>&1 | grep -v "^Character data file"
rm -rf /var/www/pornovirtuale/wp-content/cache/supercache/pornovirtuale.com/* 2>/dev/null
chown -R www-data:www-data /var/www/pornovirtuale/wp-content/cache 2>/dev/null

echo "[finisher] riepilogo"
python3 - <<'PY'
import json, glob
ok = eng = 0
for p in glob.glob('characters/data/*.json'):
    if p.endswith('categories.json'):
        continue
    for c in json.load(open(p)):
        if c.get('identity_it'):
            ok += 1
        t = ' ' + str(c.get('essence') or '').lower() + ' '
        if sum(t.count(w) for w in (' the ', ' is ', ' and ', ' of ', ' his ', ' her ')) >= 3:
            eng += 1
print('biografie tradotte:', ok, '| ancora in inglese:', eng)
PY
echo "[finisher] aggiorno il backup con i dati tradotti"
cd /opt/aria || exit 1
zip -q -d chatai_backup_3b.zip 'backend/characters/data/*' >/dev/null 2>&1
zip -q -r chatai_backup_3b.zip backend/characters/data/

echo "[finisher] DONE"
