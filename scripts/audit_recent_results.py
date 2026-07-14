#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FETCH_SCRIPT = os.path.join(ROOT, 'scripts', 'fetch_race_results.py')


def load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def ymd_to_date(ymd: str) -> dt.date:
    return dt.datetime.strptime(ymd, '%Y%m%d').date()


def date_to_ymd(d: dt.date) -> str:
    return d.strftime('%Y%m%d')


def should_refetch(result_data: Optional[Dict[str, Any]]) -> bool:
    if not result_data:
        return True
    total = int(result_data.get('total_races', 0) or 0)
    unavailable = int(result_data.get('unavailable_count', 0) or 0)
    hit = int(result_data.get('hit_count', 0) or 0)
    miss = int(result_data.get('miss_count', 0) or 0)
    resolved = hit + miss
    if total <= 0:
        return True
    if unavailable > 0:
        return True
    if resolved <= 0 and total > 0:
        return True
    return False


def is_complete_result(result_data: Optional[Dict[str, Any]]) -> bool:
    if not result_data:
        return False
    total = int(result_data.get('total_races', 0) or 0)
    unavailable = int(result_data.get('unavailable_count', 0) or 0)
    hit = int(result_data.get('hit_count', 0) or 0)
    miss = int(result_data.get('miss_count', 0) or 0)
    resolved = hit + miss
    return total > 0 and unavailable == 0 and resolved > 0


def is_partial_result(result_data: Optional[Dict[str, Any]]) -> bool:
    if not result_data:
        return False
    total = int(result_data.get('total_races', 0) or 0)
    unavailable = int(result_data.get('unavailable_count', 0) or 0)
    hit = int(result_data.get('hit_count', 0) or 0)
    miss = int(result_data.get('miss_count', 0) or 0)
    resolved = hit + miss
    return total > 0 and resolved > 0 and unavailable < total


def summarize(result_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not result_data:
        return {
            'ymd': None,
            'total_races': None,
            'hit_count': None,
            'miss_count': None,
            'unavailable_count': None,
            'total_profit': None,
        }
    return {
        'ymd': result_data.get('ymd'),
        'total_races': result_data.get('total_races'),
        'hit_count': result_data.get('hit_count'),
        'miss_count': result_data.get('miss_count'),
        'unavailable_count': result_data.get('unavailable_count'),
        'total_profit': result_data.get('total_profit'),
    }


def run_fetch(ymd: str) -> int:
    print(f'🔁 audit: fetching results for {ymd}')
    return subprocess.run([sys.executable, FETCH_SCRIPT, ymd], cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit and backfill recent race result files.')
    parser.add_argument('--base-ymd', required=True, help='Base date YYYYMMDD')
    parser.add_argument('--lookback-days', type=int, default=14, help='How many past days to inspect, including base date')
    args = parser.parse_args()

    base_date = ymd_to_date(args.base_ymd)
    rows: List[Dict[str, Any]] = []
    latest_results_path = os.path.join(ROOT, 'latest_results.json')
    latest_results_backup: Optional[str] = None
    if os.path.exists(latest_results_path):
        with open(latest_results_path, 'r', encoding='utf-8') as f:
            latest_results_backup = f.read()

    for offset in range(args.lookback_days):
        d = base_date - dt.timedelta(days=offset)
        ymd = date_to_ymd(d)
        pred_path = os.path.join(ROOT, f'final_predictions_{ymd}.json')
        result_path = os.path.join(ROOT, f'race_results_{ymd}.json')

        row: Dict[str, Any] = {
            'ymd': ymd,
            'has_predictions': os.path.exists(pred_path),
            'had_result_before': os.path.exists(result_path),
            'refetched': False,
            'fetch_rc': None,
            'status_before': None,
            'status_after': None,
        }

        if not row['has_predictions']:
            row['status_before'] = 'no_predictions'
            row['status_after'] = 'no_predictions'
            rows.append(row)
            continue

        before = load_json(result_path)
        row['status_before'] = summarize(before)

        if should_refetch(before):
            row['refetched'] = True
            row['fetch_rc'] = run_fetch(ymd)

        after = load_json(result_path)
        row['status_after'] = summarize(after)
        row['is_complete'] = is_complete_result(after)
        row['is_partial'] = is_partial_result(after)
        rows.append(row)

    complete_candidates = [r for r in rows if r.get('is_complete')]
    partial_candidates = [r for r in rows if r.get('is_partial')]

    latest_complete_ymd = None
    latest_complete_path = None
    if complete_candidates:
        latest_complete_ymd = max(r['ymd'] for r in complete_candidates)
        latest_complete_path = os.path.join(ROOT, f'race_results_{latest_complete_ymd}.json')
    elif partial_candidates:
        latest_complete_ymd = max(r['ymd'] for r in partial_candidates)
        latest_complete_path = os.path.join(ROOT, f'race_results_{latest_complete_ymd}.json')

    if latest_complete_path and os.path.exists(latest_complete_path):
        shutil.copyfile(latest_complete_path, os.path.join(ROOT, 'latest_complete_results.json'))
        print(f'✅ latest_complete_results.json <= {os.path.basename(latest_complete_path)}')
    else:
        print('⚠️ latest_complete_results.json を更新できる完全な結果ファイルが見つかりませんでした')

    report = {
        'generated_at': dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'base_ymd': args.base_ymd,
        'lookback_days': args.lookback_days,
        'latest_complete_ymd': latest_complete_ymd,
        'complete_dates': [r['ymd'] for r in complete_candidates],
        'partial_dates': [r['ymd'] for r in partial_candidates],
        'unresolved_dates': [r['ymd'] for r in rows if r.get('has_predictions') and not r.get('is_complete') and not r.get('is_partial')],
        'rows': rows,
    }

    with open(os.path.join(ROOT, 'recent_results_audit.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if latest_results_backup is not None:
        with open(latest_results_path, 'w', encoding='utf-8') as f:
            f.write(latest_results_backup)
        print('♻️ latest_results.json を監査前の状態に復元しました')

    print('📋 audit summary')
    print('  complete_dates =', report['complete_dates'])
    print('  partial_dates  =', report['partial_dates'])
    print('  unresolved     =', report['unresolved_dates'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
