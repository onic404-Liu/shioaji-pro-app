"""Export only reviewed source files for GitHub backup. No account-data discovery."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = (
    '.gitignore', 'trading_service.py', 'web_app.py', 'service.py',
    'credential_store.py', 'launch_web.py', 'requirements.txt',
    '啟動投資簿.cmd', 'web/index.html', 'web/app.css', 'web/app.js',
    'test_web.py', 'test_inventory_v1.py', 'INVENTORY_V1.md',
    'backup_source.py', 'README_INVENTORY.md',
)


def export():
    entries = []
    for name in FILES:
        content = (ROOT / name).read_text(encoding='utf-8')
        entries.append({'path': 'apps/onic-portfolio/' + name, 'mode': '100644',
                        'type': 'blob', 'content': content})
    hashes = {entry['path']: hashlib.sha256(entry['content'].encode('utf-8')).hexdigest()
              for entry in entries}
    entries.append({'path': 'apps/onic-portfolio/SOURCE_MANIFEST.json',
                    'mode': '100644', 'type': 'blob',
                    'content': json.dumps({'version': 1, 'sha256_utf8': hashes}, indent=2) + '\n'})
    return entries


if __name__ == '__main__':
    print(json.dumps(export(), ensure_ascii=False))
