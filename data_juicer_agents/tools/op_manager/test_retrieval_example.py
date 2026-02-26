# -*- coding: utf-8 -*-
"""
Quick smoke test for retrieve_ops.

Tests all four modes (bm25 / vector / hybrid / regex) in one run,
automatically displays the full retrieval list in verbose mode,
and generates a JSON report.

Usage:
    python test_retrieve_ops.py
    python test_retrieve_ops.py --report report.json    # Custom report path
"""

import argparse
import asyncio
import math
import json
import sys
from datetime import datetime
from typing import List, Dict, Any, Optional


ALL_MODES = ["bm25", "vector", "hybrid"]
LIMIT = 20

TEST_CASES = [
    # ── precise: keywords directly from operator names ──────────────────────
    {
        "name": "precise_clean",
        "query": "clean email html ip links",
        "expected": ["clean_email_mapper", "clean_html_mapper",
                     "clean_ip_mapper", "clean_links_mapper"],
        "type": "positive",
    },
    {
        "name": "precise_video_split",
        "query": "video split duration key frame scene",
        "expected": ["video_split_by_duration_mapper",
                     "video_split_by_key_frame_mapper",
                     "video_split_by_scene_mapper"],
        "type": "positive",
    },
    {
        "name": "precise_dialog_detection",
        "query": "dialog intent sentiment topic detection",
        "expected": ["dialog_intent_detection_mapper",
                     "dialog_sentiment_detection_mapper",
                     "dialog_topic_detection_mapper"],
        "type": "positive",
    },

    # ── fuzzy: natural language, no exact name keywords ─────────────────────
    {
        "name": "fuzzy_text_cleaning",
        "query": "I want to strip junk characters and fix encoding issues in my corpus",
        "expected": ["remove_specific_chars_mapper", "fix_unicode_mapper"],
        "type": "positive",
    },
    {
        "name": "fuzzy_image_faces",
        "query": "hide personal identity in photos and describe what is in the picture",
        "expected": ["image_face_blur_mapper", "image_captioning_mapper"],
        "type": "positive",
    },

    # ── negative: non-existent operator, expect empty results ───────────────
    {
        "name": "negative_nonexistent_op",
        "query": "Reverse Word Order",
        "expected": [],
        "type": "negative",
    },
]


# ── Metrics ─────────────────────────────────────────────────────────────────

def compute_metrics_positive(expected: List[str], retrieved: List[str], limit: int) -> Dict[str, Any]:
    """正向用例指标：期望算子被检索到越多越好，排名越靠前越好。"""
    retrieved_index = {name: idx for idx, name in enumerate(retrieved)}

    positions: Dict[str, Optional[int]] = {}
    reciprocal_ranks: List[float] = []

    for op in expected:
        if op in retrieved_index:
            rank = retrieved_index[op] + 1
            positions[op] = rank
            reciprocal_ranks.append(1.0 / rank)
        else:
            positions[op] = None
            reciprocal_ranks.append(0.0)

    # ── Recall ──
    hits = sum(1 for p in positions.values() if p is not None)
    recall = hits / len(expected) if expected else 0.0

    # ── Precision ──
    expected_set = set(expected)
    true_positives = sum(1 for op in retrieved if op in expected_set)
    precision = true_positives / len(retrieved) if retrieved else 0.0

    # ── nDCG ──
    found_ranks = sorted(r for r in positions.values() if r is not None)
    dcg = sum(1.0 / math.log2(r + 1) for r in found_ranks)
    ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(len(expected)))
    ndcg = dcg / ideal_dcg if ideal_dcg > 0 else 0.0

    avg_rank = (sum(found_ranks) / len(found_ranks)) if found_ranks else None

    # ── quality ：recall、precision、ndcg ──
    quality = 0.4 * recall + 0.3 * precision + 0.3 * ndcg

    return {
        "recall": recall,
        "precision": precision,
        "ndcg": ndcg,
        "avg_rank": avg_rank,
        "positions": positions,
        "quality": quality,
    }


def compute_metrics_negative(retrieved: List[str], limit: int) -> Dict[str, Any]:
    """
    Negative case metrics: Expect no operators to be returned. The more operators returned, the worse the score.

    - noise_count:  Actual number of operators returned (noise count)
    - noise_ratio:  noise_count / limit, measures the proportion of noise
    - quality:      1 - noise_ratio, returns 1.0 (full score) when 0 operators are returned
    """
    noise_count = len(retrieved)
    noise_ratio = noise_count / limit if limit > 0 else (0.0 if noise_count == 0 else 1.0)
    quality = max(0.0, 1.0 - noise_ratio)

    return {
        "noise_count": noise_count,
        "noise_ratio": noise_ratio,
        "quality": quality,
        "recall": None,
        "precision": None,
        "ndcg": None,
        "avg_rank": None,
        "positions": {},
    }


def compute_metrics(tc: Dict[str, Any], retrieved: List[str], limit: int) -> Dict[str, Any]:
    case_type = tc.get("type", "positive")
    if case_type == "negative":
        return compute_metrics_negative(retrieved, limit)
    else:
        return compute_metrics_positive(tc["expected"], retrieved, limit)


# ── Display helpers ─────────────────────────────────────────────────────────

def _color(text, code):
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text

def _pass(t):   return _color(t, "32")
def _fail(t):   return _color(t, "31")
def _dim(t):    return _color(t, "90")
def _bold(t):   return _color(t, "1")
def _cyan(t):   return _color(t, "36")
def _yellow(t): return _color(t, "33")


def _rank_tag(pos, total):
    if pos is None:
        return _fail("MISS")
    pct = pos / total
    if pct <= 0.25:
        return _pass(f"#{pos}")
    elif pct <= 0.5:
        return _cyan(f"#{pos}")
    elif pct <= 0.75:
        return _yellow(f"#{pos}")
    else:
        return _fail(f"#{pos}")


def _quality_bar(score, width=20):
    filled = round(score * width)
    bar = "█" * filled + "░" * (width - filled)
    if score >= 0.8:
        return _pass(bar)
    elif score >= 0.5:
        return _yellow(bar)
    else:
        return _fail(bar)


# ── Display per-case ────────────────────────────────────────────────────────

def display_positive_case(tc, retrieved, metrics):
    """Display detailed results for positive cases."""
    ok = metrics["recall"] == 1.0
    status = _pass("PASS") if ok else _fail("FAIL")
    qbar = _quality_bar(metrics["quality"])

    print(f"\n  [{status}] {_bold(tc['name'])}  {_dim('(positive)')}")
    print(f"       query: {_dim(tc['query'])}")
    print(f"       quality: {qbar} {metrics['quality']:.0%}"
          f"   recall={metrics['recall']:.0%}"
          f"  precision={metrics['precision']:.0%}"
          f"  ndcg={metrics['ndcg']:.2f}")

    # expected items with rank
    print(f"       expected ({len(tc['expected'])}):")
    for op in tc["expected"]:
        pos = metrics["positions"][op]
        tag = _rank_tag(pos, LIMIT)
        print(f"         {tag:<8s} {op}")

    # full retrieved list
    print(f"       retrieved ({len(retrieved)}):")
    expected_set = set(tc["expected"])
    for i, op in enumerate(retrieved, 1):
        if op in expected_set:
            print(f"         {_cyan(f'{i:>3}.')} {_cyan(op)} {_pass('◂')}")
        else:
            print(f"         {i:>3}. {op}")

    return ok


def display_negative_case(tc, retrieved, metrics):
    """Display detailed results for negative cases."""
    ok = metrics["noise_count"] == 0
    status = _pass("PASS") if ok else _fail("FAIL")
    qbar = _quality_bar(metrics["quality"])

    print(f"\n  [{status}] {_bold(tc['name'])}  {_dim('(negative)')}")
    print(f"       query: {_dim(tc['query'])}")
    print(f"       quality: {qbar} {metrics['quality']:.0%}"
          f"   noise={metrics['noise_count']}/{LIMIT}"
          f"  noise_ratio={metrics['noise_ratio']:.0%}")

    print(f"       expected: {_cyan('∅  (empty — no matching operator exists)')}")

    if retrieved:
        print(f"       retrieved ({len(retrieved)})  {_fail('← all are noise')}:")
        for i, op in enumerate(retrieved, 1):
            print(f"         {_fail(f'{i:>3}.')} {_fail(op)} {_fail('✗')}")
    else:
        print(f"       retrieved (0): {_pass('∅  perfect — nothing returned')}")

    return ok


# ── Runner ──────────────────────────────────────────────────────────────────

async def run_mode(mode: str) -> List[Dict[str, Any]]:
    from data_juicer_agents.tools.op_manager.op_retrieval import retrieve_ops

    results = []

    print(f"\n{'━' * 70}")
    print(f"  MODE: {_bold(mode.upper()):<30}  limit={LIMIT}")
    print(f"{'━' * 70}")

    for tc in TEST_CASES:
        retrieved = await retrieve_ops(tc["query"], limit=LIMIT, mode=mode)
        metrics = compute_metrics(tc, retrieved, LIMIT)

        case_type = tc.get("type", "positive")

        if case_type == "negative":
            ok = display_negative_case(tc, retrieved, metrics)
        else:
            ok = display_positive_case(tc, retrieved, metrics)

        results.append({
            "case": tc["name"],
            "query": tc["query"],
            "type": case_type,
            "expected": tc["expected"],
            "retrieved": retrieved,
            "pass": ok,
            **metrics,
        })

    # mode summary
    total = len(results)
    passed = sum(1 for r in results if r["pass"])
    failed = total - passed
    avg_q = sum(r["quality"] for r in results) / total

    pos_results = [r for r in results if r["type"] == "positive"]
    neg_results = [r for r in results if r["type"] == "negative"]

    print(f"\n  {'─' * 50}")
    print(f"  {_bold('Summary')}  mode={mode}")
    print(f"    cases:     {_pass(f'{passed} passed')}  {_fail(f'{failed} failed')}  / {total}")
    print(f"    quality:   {_quality_bar(avg_q)} {avg_q:.0%}")

    if pos_results:
        avg_r = sum(r["recall"] for r in pos_results) / len(pos_results)
        avg_p = sum(r["precision"] for r in pos_results) / len(pos_results)
        avg_n = sum(r["ndcg"] for r in pos_results) / len(pos_results)
        print(f"    positive:  recall={avg_r:.0%}  precision={avg_p:.0%}  ndcg={avg_n:.2f}")

    if neg_results:
        avg_noise = sum(r["noise_ratio"] for r in neg_results) / len(neg_results)
        avg_nq = sum(r["quality"] for r in neg_results) / len(neg_results)
        print(f"    negative:  avg_noise_ratio={avg_noise:.0%}  avg_quality={avg_nq:.0%}")

    return results


async def main(report_path: str):
    all_results: Dict[str, List[Dict[str, Any]]] = {}

    for mode in ALL_MODES:
        all_results[mode] = await run_mode(mode)

    # ── Cross-mode comparison ───────────────────────────────────────────
    print(f"\n{'━' * 70}")
    print(f"  {_bold('CROSS-MODE COMPARISON')}")
    print(f"{'━' * 70}")

    header_modes = "".join(f"{m:>12s}" for m in ALL_MODES)
    print(f"\n  {'case':<35s}{header_modes}")
    print(f"  {'─' * 35}{'─' * 12 * len(ALL_MODES)}")

    for i, tc in enumerate(TEST_CASES):
        case_type = tc.get("type", "positive")
        label = tc["name"]
        if case_type == "negative":
            label += " ⊘"
        row = f"  {label:<35s}"
        for mode in ALL_MODES:
            q = all_results[mode][i]["quality"]
            cell = f"{q:.0%}"
            if q >= 0.8:
                cell = _pass(f"{cell:>12s}")
            elif q >= 0.5:
                cell = _yellow(f"{cell:>12s}")
            else:
                cell = _fail(f"{cell:>12s}")
            row += cell
        print(row)

    print(f"  {'─' * 35}{'─' * 12 * len(ALL_MODES)}")

    # Overall quality
    row = f"  {_bold('avg quality'):<35s}"
    for mode in ALL_MODES:
        avg = sum(r["quality"] for r in all_results[mode]) / len(all_results[mode])
        fmt = f"{avg:.0%}"
        if avg >= 0.8:
            row += _pass(f"{fmt:>12s}")
        elif avg >= 0.5:
            row += _yellow(f"{fmt:>12s}")
        else:
            row += _fail(f"{fmt:>12s}")
    print(row)

    # Summary rows by category
    for label, filter_type, keys in [
        ("pos recall",    "positive", "recall"),
        ("pos precision", "positive", "precision"),
        ("pos ndcg",      "positive", "ndcg"),
        ("neg noise_ratio", "negative", "noise_ratio"),
    ]:
        row = f"  {_bold(label):<35s}"
        for mode in ALL_MODES:
            subset = [r for r in all_results[mode] if r["type"] == filter_type]
            if not subset:
                row += f"{'n/a':>12s}"
                continue
            avg = sum(r[keys] for r in subset) / len(subset)
            if keys in ("recall", "precision", "noise_ratio"):
                fmt = f"{avg:.0%}"
            else:
                fmt = f"{avg:.2f}"
            row += f"{fmt:>12s}"
        print(row)

    # ── JSON report ─────────────────────────────────────────────────────
    report = {
        "timestamp": datetime.now().isoformat(),
        "limit": LIMIT,
        "modes": {},
    }
    for mode, results in all_results.items():
        serializable = []
        for r in results:
            sr = {k: v for k, v in r.items() if k != "positions"}
            sr["positions"] = {op: pos for op, pos in r["positions"].items()}
            sr["quality"] = round(sr["quality"], 4)
            if sr["recall"] is not None:
                sr["recall"] = round(sr["recall"], 4)
            if sr["precision"] is not None:
                sr["precision"] = round(sr["precision"], 4)
            if sr["ndcg"] is not None:
                sr["ndcg"] = round(sr["ndcg"], 4)
            if "noise_ratio" in sr:
                sr["noise_ratio"] = round(sr["noise_ratio"], 4)
            serializable.append(sr)

        avg_q = sum(r["quality"] for r in results) / len(results)
        passed = sum(1 for r in results if r["pass"])

        pos_results = [r for r in results if r["type"] == "positive"]
        neg_results = [r for r in results if r["type"] == "negative"]

        summary: Dict[str, Any] = {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "avg_quality": round(avg_q, 4),
        }

        if pos_results:
            summary["positive"] = {
                "count": len(pos_results),
                "avg_recall": round(sum(r["recall"] for r in pos_results) / len(pos_results), 4),
                "avg_precision": round(sum(r["precision"] for r in pos_results) / len(pos_results), 4),
                "avg_ndcg": round(sum(r["ndcg"] for r in pos_results) / len(pos_results), 4),
            }

        if neg_results:
            summary["negative"] = {
                "count": len(neg_results),
                "avg_noise_count": round(sum(r["noise_count"] for r in neg_results) / len(neg_results), 2),
                "avg_noise_ratio": round(sum(r["noise_ratio"] for r in neg_results) / len(neg_results), 4),
                "avg_quality": round(sum(r["quality"] for r in neg_results) / len(neg_results), 4),
            }

        report["modes"][mode] = {
            "summary": summary,
            "cases": serializable,
        }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  📄 Report saved to: {_cyan(report_path)}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieval quality test for retrieve_ops")
    parser.add_argument("--report", type=str, default="retrieval_report.json",
                        metavar="PATH", help="JSON report output path (default: retrieval_report.json)")
    args = parser.parse_args()

    asyncio.run(main(args.report))

