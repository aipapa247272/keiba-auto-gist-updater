from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / 'data'
OUTPUT_PATH = DATA_DIR / 'strategy_376_lab.json'
JST = timezone(timedelta(hours=9))
UNIT_BET = 100
MIN_HEADCOUNT = 9


def load_json(path: Path) -> Any:
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def to_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(',', '')
    if not s:
        return default
    try:
        return float(s)
    except Exception:
        return default


def norm_horse_no(value: Any) -> str | None:
    i = to_int(value)
    if i is None:
        return None
    return str(i)


def get_des_total(horse: dict[str, Any]) -> float:
    if '新スコア' in horse:
        return to_float(horse.get('新スコア'))
    des = horse.get('des_score') or {}
    if isinstance(des, dict):
        return to_float(des.get('total'))
    return 0.0


def sort_horses_by_popularity(horses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = []
    for horse in horses:
        no = norm_horse_no(horse.get('馬番'))
        pop = to_int(horse.get('人気'))
        if no is None or pop is None:
            continue
        item = dict(horse)
        item['_horse_no'] = no
        item['_pop'] = pop
        valid.append(item)
    return sorted(valid, key=lambda h: (h['_pop'], to_float(h.get('オッズ'), 9999), to_int(h.get('枠番')) or 99, int(h['_horse_no'])))


def sort_horses_by_des(horses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid = []
    for horse in horses:
        no = norm_horse_no(horse.get('馬番'))
        if no is None:
            continue
        score = get_des_total(horse)
        pop = to_int(horse.get('人気')) or 99
        item = dict(horse)
        item['_horse_no'] = no
        item['_des'] = score
        item['_pop'] = pop
        valid.append(item)
    return sorted(valid, key=lambda h: (-h['_des'], h['_pop'], int(h['_horse_no'])))


def build_columns(sorted_horses: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    if len(sorted_horses) < MIN_HEADCOUNT:
        return {'applied': False, 'reason': f'{MIN_HEADCOUNT}頭未満のため対象外'}

    horses = sorted_horses[:9]
    col1 = [h['_horse_no'] for h in horses[:3]]
    col2 = [h['_horse_no'] for h in horses[:7]]
    col3 = [h['_horse_no'] for h in horses[3:9]]

    if len(col1) < 3 or len(col2) < 7 or len(col3) < 6:
        return {'applied': False, 'reason': '必要順位のデータが不足'}

    combos: set[tuple[int, int, int]] = set()
    for a in col1:
        for b in col2:
            for c in col3:
                trio = {a, b, c}
                if len(trio) < 3:
                    continue
                combos.add(tuple(sorted(int(x) for x in trio)))

    combo_strings = ['-'.join(map(str, combo)) for combo in sorted(combos)]
    ranked_preview = []
    for idx, horse in enumerate(horses, start=1):
        ranked_preview.append({
            'rank': idx,
            'horse_no': horse['_horse_no'],
            'horse_name': horse.get('馬名', ''),
            'popularity': horse.get('人気'),
            'odds': horse.get('オッズ', horse.get('単勝オッズ')),
            'des_score': round(get_des_total(horse), 2),
        })

    label = '人気順' if mode == 'popularity' else 'DES順位'
    return {
        'applied': True,
        'reason': f'初期条件クリア（{MIN_HEADCOUNT}頭以上・{label}データ充足）',
        'columns': {
            'A': col1,
            'B': col2,
            'C': col3,
        },
        'bet_count': len(combo_strings),
        'unit_bet': UNIT_BET,
        'total_investment': len(combo_strings) * UNIT_BET,
        'combinations': combo_strings,
        'ranked_preview': ranked_preview,
    }


def extract_actual_combo(result_race: dict[str, Any]) -> str | None:
    actual = result_race.get('actual')
    if isinstance(actual, list) and actual:
        text = str(actual[0]).strip()
        if text:
            parts = [to_int(x) for x in text.split('-')]
            if all(p is not None for p in parts) and len(parts) == 3:
                return '-'.join(map(str, sorted(parts)))
    san = result_race.get('result_sanrenpuku')
    if san:
        parts = [to_int(x) for x in str(san).split('-')]
        if all(p is not None for p in parts) and len(parts) == 3:
            return '-'.join(map(str, sorted(parts)))
    all_results = result_race.get('all_horses_result') or []
    top3 = []
    for horse in all_results:
        rank = to_int(horse.get('着順'))
        no = norm_horse_no(horse.get('馬番'))
        if rank in (1, 2, 3) and no is not None:
            top3.append((rank, int(no)))
    if len(top3) == 3:
        return '-'.join(map(str, sorted(no for _, no in sorted(top3))))
    return None


def extract_payout(result_race: dict[str, Any]) -> int:
    payouts = result_race.get('payouts') or {}
    for key in ['三連複', '3連複', '三連複式']:
        if key in payouts:
            return to_int(payouts.get(key)) or 0
    return to_int(result_race.get('payout_sanrenpuku')) or 0


def race_meta_from_race_data(race: dict[str, Any]) -> dict[str, Any]:
    return {
        'race_id': race.get('race_id'),
        'venue': race.get('競馬場', ''),
        'race_num': str(race.get('レース番号', '')),
        'race_name': race.get('レース名', ''),
        'distance': race.get('距離'),
        'track': race.get('トラック', ''),
        'start_time': race.get('発走時刻', ''),
        'head_count': to_int(race.get('取得頭数')) or len(race.get('horses') or []),
    }


def attach_result(strategy: dict[str, Any], result_race: dict[str, Any]) -> dict[str, Any]:
    actual_combo = extract_actual_combo(result_race)
    hit = actual_combo in set(strategy.get('combinations') or []) if actual_combo else False
    payout = extract_payout(result_race) if hit else 0
    investment = strategy.get('total_investment', 0)
    profit = payout - investment
    out = dict(strategy)
    out.update({
        'actual_combo': actual_combo,
        'hit': hit,
        'payout': payout,
        'profit': profit,
    })
    return out


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    applicable = [r for r in records if r.get('applied')]
    hit_records = [r for r in applicable if r.get('hit')]
    investment = sum(r.get('total_investment', 0) for r in applicable)
    payout = sum(r.get('payout', 0) for r in applicable)
    profit = payout - investment
    avg_points = round(sum(r.get('bet_count', 0) for r in applicable) / len(applicable), 2) if applicable else 0
    trigami_count = sum(1 for r in hit_records if r.get('payout', 0) < r.get('total_investment', 0))
    max_payout = max((r.get('payout', 0) for r in applicable), default=0)
    max_loss = min((r.get('profit', 0) for r in applicable), default=0)
    return {
        'sample_races': len(records),
        'applicable_races': len(applicable),
        'skipped_races': len(records) - len(applicable),
        'hit_count': len(hit_records),
        'hit_rate': round((len(hit_records) / len(applicable) * 100), 1) if applicable else 0,
        'recovery_rate': round((payout / investment * 100), 1) if investment else 0,
        'total_investment': investment,
        'total_payout': payout,
        'total_profit': profit,
        'avg_bet_count': avg_points,
        'trigami_rate': round((trigami_count / len(hit_records) * 100), 1) if hit_records else 0,
        'max_payout': max_payout,
        'max_loss': max_loss,
    }


def build_current_predictions() -> dict[str, Any]:
    latest_predictions = load_json(REPO / 'latest_predictions.json')
    ymd = latest_predictions.get('ymd')
    race_data_path = REPO / f'race_data_{ymd}.json'
    race_data = load_json(race_data_path)
    selected_ids = {r.get('race_id') for r in latest_predictions.get('selected_predictions', [])}
    reference_ids = {r.get('race_id') for r in latest_predictions.get('reference_predictions', [])}

    modes = {'popularity': [], 'desrank': []}
    for race in race_data.get('races', []):
        meta = race_meta_from_race_data(race)
        race_id = meta['race_id']
        meta['des_pick_type'] = '推奨' if race_id in selected_ids else ('参考' if race_id in reference_ids else '未掲載')
        horses = race.get('horses') or []

        pop = build_columns(sort_horses_by_popularity(horses), 'popularity')
        des = build_columns(sort_horses_by_des(horses), 'desrank')

        for mode, strategy in [('popularity', pop), ('desrank', des)]:
            record = dict(meta)
            record.update(strategy)
            modes[mode].append(record)

    for mode in modes:
        modes[mode].sort(key=lambda r: (not r.get('applied'), r.get('start_time') or '', r.get('venue') or '', to_int(r.get('race_num')) or 99))

    return {
        'ymd': ymd,
        'generated_at': latest_predictions.get('generated_at'),
        'apply_rule_note': f'初期版は {MIN_HEADCOUNT}頭以上かつ必要順位データが揃うレースを対象',
        'modes': {mode: {'races': races, 'summary': summarize_records(races)} for mode, races in modes.items()},
    }


def build_history() -> dict[str, Any]:
    result_files = sorted(REPO.glob('race_results_*.json'))
    race_data_cache: dict[str, dict[str, Any]] = {}
    mode_records: dict[str, list[dict[str, Any]]] = {'popularity': [], 'desrank': []}
    daily_buckets: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {'popularity': [], 'desrank': []})

    for result_file in result_files:
        data = load_json(result_file)
        ymd = str(data.get('ymd') or '')
        if not ymd or not ymd.isdigit():
            continue
        race_data_path = REPO / f'race_data_{ymd}.json'
        if not race_data_path.exists():
            continue
        if ymd not in race_data_cache:
            race_data_cache[ymd] = load_json(race_data_path)
        race_map = {race.get('race_id'): race for race in race_data_cache[ymd].get('races', [])}

        for result_race in data.get('races', []):
            race_id = result_race.get('race_id')
            if race_id not in race_map:
                continue
            source_race = race_map[race_id]
            meta = race_meta_from_race_data(source_race)
            meta['ymd'] = ymd
            meta['prediction_type'] = result_race.get('prediction_type', '')
            meta['prediction_label'] = result_race.get('prediction_label', '')
            horses = source_race.get('horses') or []
            pop = attach_result(build_columns(sort_horses_by_popularity(horses), 'popularity'), result_race)
            des = attach_result(build_columns(sort_horses_by_des(horses), 'desrank'), result_race)

            for mode, strategy in [('popularity', pop), ('desrank', des)]:
                record = dict(meta)
                record.update(strategy)
                mode_records[mode].append(record)
                daily_buckets[ymd][mode].append(record)

    daily = []
    for ymd in sorted(daily_buckets.keys()):
        day_item = {'ymd': ymd, 'modes': {}}
        for mode in ['popularity', 'desrank']:
            day_item['modes'][mode] = summarize_records(daily_buckets[ymd][mode])
        daily.append(day_item)

    for mode in mode_records:
        mode_records[mode].sort(key=lambda r: (r.get('ymd') or '', r.get('start_time') or '', r.get('venue') or '', to_int(r.get('race_num')) or 99), reverse=True)

    return {
        'generated_at': datetime.now(JST).isoformat(),
        'unit_bet': UNIT_BET,
        'sample_note': '履歴集計は race_results と race_data の両方が存在するレースを対象',
        'modes': {mode: {'summary': summarize_records(records), 'records': records} for mode, records in mode_records.items()},
        'daily': list(reversed(daily[-60:])),
    }


def main() -> None:
    payload = {
        'generated_at': datetime.now(JST).isoformat(),
        'version': 'strategy_376_lab_v1',
        'unit_bet': UNIT_BET,
        'current': build_current_predictions(),
        'history': build_history(),
    }
    save_json(OUTPUT_PATH, payload)
    print(f'Wrote {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
