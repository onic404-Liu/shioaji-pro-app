"""Run the web app with the installed Python and existing project dependencies."""
import os
from pathlib import Path
import runpy
import sys

BASE = Path(__file__).resolve().parent


def main():
    if sys.version_info[:2] != (3, 11):
        print('此專案目前需要 Python 3.11，請勿改用不相容的執行環境。')
        return 1
    packages = BASE / '.venv' / 'Lib' / 'site-packages'
    if not packages.is_dir():
        print('找不到專案套件，請先恢復 Python 套件環境。')
        return 1
    # Use libraries only; do not invoke the blocked virtual-environment launcher.
    sys.path.insert(0, str(packages))
    sys.path.insert(0, str(BASE))
    os.environ['SJ_LOG_PATH'] = os.devnull
    try:
        import shioaji
    except Exception as exc:
        print(f'永豐 SDK 無法載入（{type(exc).__name__}）。請檢查套件或系統允許的執行環境。')
        return 1
    if '--check' in sys.argv[1:]:
        import web_app
        print(f'啟動檢查通過：Python {sys.version_info.major}.{sys.version_info.minor}、Shioaji {shioaji.__version__}。沒有登入或下單。')
        return 0
    sys.argv[0] = str(BASE / 'web_app.py')
    runpy.run_path(sys.argv[0], run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
