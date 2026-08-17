#!/usr/bin/env python3
"""
DES_AI競馬予想 自動レポート生成システム
日次/週次/月次レポートを生成してJSONファイルとして出力
"""

import json
import sys
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from pathlib import Path
import statistics

class RaceAnalyzer:
    """レース展開・脚質分析クラス"""
    
    @staticmethod
    def analyze_pace(horses):
        """
        脚質分布からレース展開を予測
        
        Returns:
            str: 'ハイペース', 'ミドルペース', 'スローペース'
        """
        runstyles = [h.get('推定脚質', '不明') for h in horses]
        counter = Counter(runstyles)
        
        nige_count = counter.get('逃げ', 0)
        senkou_count = counter.get('先行', 0)
        total = len([r for r in runstyles if r != '不明'])
        
        if total == 0:
            return 'ミドルペース'
        
        # 逃げ馬が3頭以上または逃げ+先行が50%以上
        if nige_count >= 3 or (nige_count + senkou_count) / total >= 0.5:
            return 'ハイペース'
        # 逃げ馬が0-1頭
        elif nige_count <= 1:
            return 'スローペース'
        else:
            return 'ミドルペース'
    
    @staticmethod
    def get_favorable_runstyle(pace):
        """
        展開から有利な脚質を返す
        
        Returns:
            list: 有利な脚質のリスト
        """
        if pace == 'ハイペース':
            return ['差し', '追込']
        elif pace == 'スローペース':
            return ['逃げ', '先行']
        else:
            return ['先行', '差し']
    
    @staticmethod
    def count_runstyles(horses):
        """脚質別頭数をカウント"""
        runstyles = [h.get('推定脚質', '不明') for h in horses]
        return dict(Counter(runstyles))


class ReportGenerator:
    """レポート生成クラス"""
    
    def __init__(self):
        self.predictions = []
        self.results = []
        self.statistics = {}
    
    def load_data(self, predictions_file, results_file, statistics_file):
        """データファイルを読み込み"""
        try:
            with open(predictions_file, 'r', encoding='utf-8') as f:
                pred_data = json.load(f)
                self.predictions = pred_data.get('selected_predictions', [])
        except FileNotFoundError:
            print(f"⚠️ {predictions_file} が見つかりません")
            self.predictions = []
        
        try:
            with open(results_file, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
                self.results = result_data.get('races', [])
        except FileNotFoundError:
            print(f"⚠️ {results_file} が見つかりません")
            self.results = []
        
        try:
            with open(statistics_file, 'r', encoding='utf-8') as f:
                self.statistics = json.load(f)
        except FileNotFoundError:
            print(f"⚠️ {statistics_file} が見つかりません")
            self.statistics = {}
    
    def generate_daily_report(self, target_date):
        """日次レポート生成"""
        report = {
            "report_type": "daily",
            "target_date": target_date,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": self._generate_daily_summary(),
            "race_analysis": self._analyze_races_detail(),
            "performance_by_segment": self._analyze_by_segment(),
            "pace_analysis": self._analyze_pace_performance(),
            "insights": self._generate_daily_insights(),
            "recommendations": self._generate_recommendations()
        }
        return report
    
    def generate_weekly_report(self, start_date, end_date):
        """週次レポート生成"""
        report = {
            "report_type": "weekly",
            "period": f"{start_date} ~ {end_date}",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": self._generate_weekly_summary(),
            "performance_trends": self._analyze_weekly_trends(),
            "best_worst_races": self._find_best_worst_races(),
            "segment_performance": self._analyze_by_segment(),
            "pace_analysis": self._analyze_pace_performance(),
            "insights": self._generate_weekly_insights(),
            "action_items": self._generate_action_items()
        }
        return report
    
    def generate_monthly_report(self, year_month):
        """月次レポート生成"""
        report = {
            "report_type": "monthly",
            "year_month": year_month,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": self._generate_monthly_summary(),
            "detailed_analysis": self._analyze_monthly_details(),
            "segment_performance": self._analyze_by_segment(),
            "pace_analysis": self._analyze_pace_performance(),
            "trends": self._analyze_monthly_trends(),
            "insights": self._generate_monthly_insights(),
            "optimization_proposals": self._generate_optimization_proposals()
        }
        return report
    
    def _generate_daily_summary(self):
        """日次サマリー"""
        total_races = len(self.results)
        hits = sum(1 for r in self.results if r.get('is_hit', False))
        total_investment = sum(r.get('investment', 0) for r in self.results)
        total_payout = sum(r.get('payout', 0) for r in self.results)
        profit = total_payout - total_investment
        hit_rate = (hits / total_races * 100) if total_races > 0 else 0
        recovery_rate = (total_payout / total_investment * 100) if total_investment > 0 else 0
        
        return {
            "total_races": total_races,
            "hits": hits,
            "misses": total_races - hits,
            "hit_rate": round(hit_rate, 1),
            "total_investment": total_investment,
            "total_payout": total_payout,
            "profit": profit,
            "recovery_rate": round(recovery_rate, 1)
        }
    
    def _analyze_races_detail(self):
        """レース詳細分析"""
        details = []
        for result in self.results:
            race_id = result.get('race_id')
            # 対応する予想を探す
            pred = next((p for p in self.predictions if p.get('race_id') == race_id), None)
            
            if pred:
                detail = {
                    "race_id": race_id,
                    "venue": result.get('venue', '不明'),
                    "race_number": result.get('race_number', ''),
                    "is_hit": result.get('is_hit', False),
                    "investment": result.get('investment', 0),
                    "payout": result.get('payout', 0),
                    "profit": result.get('payout', 0) - result.get('investment', 0),
                    "num_horses": result.get('num_horses', 0),
                    "track": pred.get('track', '不明'),
                    "distance": pred.get('distance', 0),
                    "turbulence": pred.get('turbulence', '不明'),
                    "predicted_pace": result.get('predicted_pace', 'ミドルペース'),
                    "axis_runstyles": self._get_axis_runstyles(pred),
                    "hole_count": len(pred.get('betting_plan', {}).get('相手', []))
                }
                details.append(detail)
        
        return details
    
    def _get_axis_runstyles(self, prediction):
        """軸馬の脚質を取得"""
        axis_horses = prediction.get('betting_plan', {}).get('軸', [])
        return [h.get('脚質', '不明') for h in axis_horses]
    
    def _analyze_by_segment(self):
        """セグメント別分析"""
        segments = {
            "by_num_horses": self._analyze_by_num_horses(),
            "by_track": self._analyze_by_track(),
            "by_distance_category": self._analyze_by_distance(),
            "by_turbulence": self._analyze_by_turbulence(),
            "by_venue": self._analyze_by_venue(),
            "by_hole_count": self._analyze_by_hole_count()
        }
        return segments
    
    def _analyze_by_num_horses(self):
        """出馬数別分析"""
        groups = defaultdict(lambda: {"races": 0, "hits": 0, "investment": 0, "payout": 0})
        
        for result in self.results:
            num = result.get('num_horses', 0)
            groups[num]["races"] += 1
            if result.get('is_hit', False):
                groups[num]["hits"] += 1
            groups[num]["investment"] += result.get('investment', 0)
            groups[num]["payout"] += result.get('payout', 0)
        
        return self._format_segment_stats(groups)
    
    def _analyze_by_track(self):
        """トラック別分析"""
        groups = defaultdict(lambda: {"races": 0, "hits": 0, "investment": 0, "payout": 0})
        
        for result in self.results:
            race_id = result.get('race_id')
            pred = next((p for p in self.predictions if p.get('race_id') == race_id), None)
            if pred:
                track = pred.get('track', '不明')
                groups[track]["races"] += 1
                if result.get('is_hit', False):
                    groups[track]["hits"] += 1
                groups[track]["investment"] += result.get('investment', 0)
                groups[track]["payout"] += result.get('payout', 0)
        
        return self._format_segment_stats(groups)
    
    def _analyze_by_distance(self):
        """距離カテゴリ別分析"""
        groups = defaultdict(lambda: {"races": 0, "hits": 0, "investment": 0, "payout": 0})
        
        for result in self.results:
            race_id = result.get('race_id')
            pred = next((p for p in self.predictions if p.get('race_id') == race_id), None)
            if pred:
                distance = pred.get('distance', 0)
                category = self._categorize_distance(distance)
                groups[category]["races"] += 1
                if result.get('is_hit', False):
                    groups[category]["hits"] += 1
                groups[category]["investment"] += result.get('investment', 0)
                groups[category]["payout"] += result.get('payout', 0)
        
        return self._format_segment_stats(groups)
    
    def _categorize_distance(self, distance):
        """距離をカテゴリ分け"""
        if distance < 1400:
            return "短距離"
        elif distance < 1800:
            return "マイル"
        elif distance < 2200:
            return "中距離"
        else:
            return "長距離"
    
    def _analyze_by_turbulence(self):
        """混沌度別分析"""
        groups = defaultdict(lambda: {"races": 0, "hits": 0, "investment": 0, "payout": 0})
        
        for result in self.results:
            race_id = result.get('race_id')
            pred = next((p for p in self.predictions if p.get('race_id') == race_id), None)
            if pred:
                turb = pred.get('turbulence', '不明')
                groups[turb]["races"] += 1
                if result.get('is_hit', False):
                    groups[turb]["hits"] += 1
                groups[turb]["investment"] += result.get('investment', 0)
                groups[turb]["payout"] += result.get('payout', 0)
        
        return self._format_segment_stats(groups)
    
    def _analyze_by_venue(self):
        """会場別分析"""
        groups = defaultdict(lambda: {"races": 0, "hits": 0, "investment": 0, "payout": 0})
        
        for result in self.results:
            venue = result.get('venue', '不明')
            groups[venue]["races"] += 1
            if result.get('is_hit', False):
                groups[venue]["hits"] += 1
            groups[venue]["investment"] += result.get('investment', 0)
            groups[venue]["payout"] += result.get('payout', 0)
        
        return self._format_segment_stats(groups)
    
    def _analyze_by_hole_count(self):
        """穴候補頭数別分析"""
        groups = defaultdict(lambda: {"races": 0, "hits": 0, "investment": 0, "payout": 0})
        
        for result in self.results:
            race_id = result.get('race_id')
            pred = next((p for p in self.predictions if p.get('race_id') == race_id), None)
            if pred:
                hole_count = len(pred.get('betting_plan', {}).get('相手', []))
                groups[hole_count]["races"] += 1
                if result.get('is_hit', False):
                    groups[hole_count]["hits"] += 1
                groups[hole_count]["investment"] += result.get('investment', 0)
                groups[hole_count]["payout"] += result.get('payout', 0)
        
        return self._format_segment_stats(groups)
    
    def _analyze_pace_performance(self):
        """レース展開別パフォーマンス分析"""
        pace_stats = defaultdict(lambda: {
            "races": 0,
            "hits": 0,
            "investment": 0,
            "payout": 0,
            "by_axis_runstyle": defaultdict(lambda: {"races": 0, "hits": 0})
        })
        
        for result in self.results:
            race_id = result.get('race_id')
            pred = next((p for p in self.predictions if p.get('race_id') == race_id), None)
            if pred:
                pace = result.get('predicted_pace', 'ミドルペース')
                pace_stats[pace]["races"] += 1
                if result.get('is_hit', False):
                    pace_stats[pace]["hits"] += 1
                pace_stats[pace]["investment"] += result.get('investment', 0)
                pace_stats[pace]["payout"] += result.get('payout', 0)
                
                # 軸馬の脚質も記録
                axis_horses = pred.get('betting_plan', {}).get('軸', [])
                for axis in axis_horses:
                    runstyle = axis.get('脚質', '不明')
                    pace_stats[pace]["by_axis_runstyle"][runstyle]["races"] += 1
                    if result.get('is_hit', False):
                        pace_stats[pace]["by_axis_runstyle"][runstyle]["hits"] += 1
        
        # フォーマット
        formatted = {}
        for pace, stats in pace_stats.items():
            hit_rate = (stats["hits"] / stats["races"] * 100) if stats["races"] > 0 else 0
            recovery = (stats["payout"] / stats["investment"] * 100) if stats["investment"] > 0 else 0
            
            # 軸馬脚質別の的中率
            runstyle_stats = {}
            for rs, rs_stats in stats["by_axis_runstyle"].items():
                rs_hit_rate = (rs_stats["hits"] / rs_stats["races"] * 100) if rs_stats["races"] > 0 else 0
                runstyle_stats[rs] = {
                    "races": rs_stats["races"],
                    "hits": rs_stats["hits"],
                    "hit_rate": round(rs_hit_rate, 1)
                }
            
            formatted[pace] = {
                "races": stats["races"],
                "hits": stats["hits"],
                "hit_rate": round(hit_rate, 1),
                "investment": stats["investment"],
                "payout": stats["payout"],
                "profit": stats["payout"] - stats["investment"],
                "recovery_rate": round(recovery, 1),
                "axis_runstyle_performance": runstyle_stats
            }
        
        return formatted
    
    def _format_segment_stats(self, groups):
        """セグメント統計をフォーマット"""
        formatted = {}
        for key, stats in groups.items():
            hit_rate = (stats["hits"] / stats["races"] * 100) if stats["races"] > 0 else 0
            recovery = (stats["payout"] / stats["investment"] * 100) if stats["investment"] > 0 else 0
            formatted[str(key)] = {
                "races": stats["races"],
                "hits": stats["hits"],
                "hit_rate": round(hit_rate, 1),
                "investment": stats["investment"],
                "payout": stats["payout"],
                "profit": stats["payout"] - stats["investment"],
                "recovery_rate": round(recovery, 1)
            }
        return formatted
    
    def _generate_daily_insights(self):
        """日次インサイト生成"""
        insights = []
        
        # 的中率チェック
        summary = self._generate_daily_summary()
        if summary["hit_rate"] >= 20:
            insights.append({
                "type": "positive",
                "message": f"✅ 的中率 {summary['hit_rate']}% - 好調を維持",
                "priority": "high"
            })
        elif summary["hit_rate"] == 0 and summary["total_races"] > 0:
            insights.append({
                "type": "warning",
                "message": "⚠️ 本日は的中なし - 明日の条件を見直し",
                "priority": "high"
            })
        
        # 回収率チェック
        if summary["recovery_rate"] >= 100:
            insights.append({
                "type": "positive",
                "message": f"🎯 回収率 {summary['recovery_rate']}% - プラス収支達成！",
                "priority": "high"
            })
        elif summary["recovery_rate"] < 50:
            insights.append({
                "type": "warning",
                "message": f"📉 回収率 {summary['recovery_rate']}% - 買い目の見直しが必要",
                "priority": "medium"
            })
        
        # セグメント別の傾向
        by_turb = self._analyze_by_turbulence()
        best_turb = max(by_turb.items(), key=lambda x: x[1]["hit_rate"], default=(None, {}))
        if best_turb[0]:
            insights.append({
                "type": "info",
                "message": f"💡 {best_turb[0]}混沌度レースが好調（的中率{best_turb[1]['hit_rate']}%）",
                "priority": "low"
            })
        
        return insights
    
    def _generate_recommendations(self):
        """改善提案"""
        recommendations = []
        
        # 出馬数別の推奨
        by_horses = self._analyze_by_num_horses()
        if by_horses:
            sorted_by_recovery = sorted(
                by_horses.items(),
                key=lambda x: x[1]["recovery_rate"],
                reverse=True
            )
            if sorted_by_recovery:
                best = sorted_by_recovery[0]
                recommendations.append({
                    "category": "出馬数",
                    "suggestion": f"{best[0]}頭レースを重点的に狙う（回収率{best[1]['recovery_rate']}%）",
                    "priority": "high"
                })
        
        # ペース別の推奨
        pace_perf = self._analyze_pace_performance()
        if pace_perf:
            sorted_by_hit = sorted(
                pace_perf.items(),
                key=lambda x: x[1]["hit_rate"],
                reverse=True
            )
            if sorted_by_hit:
                best_pace = sorted_by_hit[0]
                recommendations.append({
                    "category": "レース展開",
                    "suggestion": f"{best_pace[0]}のレースが的中しやすい（的中率{best_pace[1]['hit_rate']}%）",
                    "priority": "medium"
                })
        
        return recommendations
    
    def _generate_weekly_summary(self):
        """週次サマリー（月次サマリーと同じロジック）"""
        return self._generate_daily_summary()
    
    def _generate_monthly_summary(self):
        """月次サマリー"""
        return self._generate_daily_summary()
    
    def _analyze_weekly_trends(self):
        """週次トレンド分析"""
        # TODO: 日別の推移を分析
        return {}
    
    def _analyze_monthly_details(self):
        """月次詳細分析"""
        # TODO: より詳細な月次分析
        return {}
    
    def _analyze_monthly_trends(self):
        """月次トレンド分析"""
        # TODO: 週別の推移を分析
        return {}
    
    def _find_best_worst_races(self):
        """ベスト・ワーストレース"""
        if not self.results:
            return {"best": None, "worst": None}
        
        sorted_by_profit = sorted(
            self.results,
            key=lambda x: x.get('payout', 0) - x.get('investment', 0),
            reverse=True
        )
        
        best = sorted_by_profit[0] if sorted_by_profit else None
        worst = sorted_by_profit[-1] if sorted_by_profit else None
        
        return {"best": best, "worst": worst}
    
    def _generate_weekly_insights(self):
        """週次インサイト"""
        return self._generate_daily_insights()
    
    def _generate_monthly_insights(self):
        """月次インサイト"""
        return self._generate_daily_insights()
    
    def _generate_action_items(self):
        """アクションアイテム"""
        return self._generate_recommendations()
    
    def _generate_optimization_proposals(self):
        """最適化提案"""
        return self._generate_recommendations()


def main():
    """メイン処理"""
    if len(sys.argv) < 4:
        print("Usage: python generate_reports.py <report_type> <predictions_json> <results_json> [statistics_json] [target_date]")
        print("  report_type: daily, weekly, monthly")
        sys.exit(1)
    
    report_type = sys.argv[1]
    predictions_file = sys.argv[2]
    results_file = sys.argv[3]
    statistics_file = sys.argv[4] if len(sys.argv) > 4 else "statistics.json"
    target_date_override = sys.argv[5] if len(sys.argv) > 5 else ""
    
    generator = ReportGenerator()
    generator.load_data(predictions_file, results_file, statistics_file)
    
    if report_type == "daily":
        target_date = target_date_override or datetime.now().strftime("%Y-%m-%d")
        report = generator.generate_daily_report(target_date)
        output_file = f"daily_report_{target_date.replace('-', '')}.json"
    
    elif report_type == "weekly":
        today = datetime.now()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        report = generator.generate_weekly_report(
            start.strftime("%Y-%m-%d"),
            end.strftime("%Y-%m-%d")
        )
        output_file = f"weekly_report_{start.strftime('%Y%m%d')}.json"
    
    elif report_type == "monthly":
        year_month = datetime.now().strftime("%Y-%m")
        report = generator.generate_monthly_report(year_month)
        output_file = f"monthly_report_{datetime.now().strftime('%Y%m')}.json"
    
    else:
        print(f"❌ 不明なレポートタイプ: {report_type}")
        sys.exit(1)
    
    # JSON出力
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, ensure_ascii=False, indent=2, fp=f)
    
    print(f"✅ レポート生成完了: {output_file}")
    
    # 標準出力にもサマリーを表示
    if 'summary' in report:
        s = report['summary']
        print(f"\n【{report_type.upper()} レポート】")
        print(f"  レース数: {s.get('total_races', 0)}")
        print(f"  的中: {s.get('hits', 0)}レース")
        print(f"  的中率: {s.get('hit_rate', 0)}%")
        print(f"  投資額: ¥{s.get('total_investment', 0):,}")
        print(f"  払戻額: ¥{s.get('total_payout', 0):,}")
        print(f"  収支: ¥{s.get('profit', 0):,}")
        print(f"  回収率: {s.get('recovery_rate', 0)}%")


if __name__ == "__main__":
    main()
