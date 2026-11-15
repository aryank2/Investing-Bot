#!/usr/bin/env python3
"""Knowledge-base helper. Usage: kb.py validate | metrics | backup <scratchpad> | restore <scratchpad>"""
import json, re, shutil, sys
from pathlib import Path

KB = Path(__file__).resolve().parent
BACKUP = KB / "backup"
FILES = ["rh_bot_daily_log.jsonl", "rh_bot_open_positions.json", "regime_calc.py", "scan_calc.py"]
D_KINDS = {"trade", "rejected", "stand_aside", "paper"}
K_KINDS = {"lesson", "relationship", "hypothesis", "process", "caveat"}
K_STATUS = {"hypothesis", "observed", "supported", "process", "retired"}
PRIVATE = [(re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "[id]"),
           (re.compile(r"trig_[A-Za-z0-9]+"), "[trigger]"),
           (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[email]"),
           (re.compile(r"(?<![\d.])\d{8,10}(?![\d.])"), "[account]")]


def load(name):
    return [json.loads(l) for l in (KB / name).read_text().splitlines() if l.strip()]


def redact(text):
    for rx, rep in PRIVATE:
        text = rx.sub(rep, text)
    return text


def validate():
    errs = []
    dec, kn = load("decisions.jsonl"), load("knowledge.jsonl")
    for name, rows in (("decisions", dec), ("knowledge", kn)):
        ids = [r.get("id") for r in rows]
        errs += [f"{name}: duplicate id {i}" for i in set(ids) if ids.count(i) > 1]
    for r in dec:
        errs += [f"decision {r.get('id')}: missing {k}" for k in ("id", "date", "kind", "symbol", "status") if k not in r]
        if r.get("kind") not in D_KINDS: errs.append(f"decision {r.get('id')}: bad kind")
        if r.get("status") not in ("open", "closed"): errs.append(f"decision {r.get('id')}: bad status")
    for r in kn:
        errs += [f"knowledge {r.get('id')}: missing {k}" for k in ("id", "date", "kind", "status", "claim", "evidence") if k not in r]
        if r.get("kind") not in K_KINDS: errs.append(f"knowledge {r.get('id')}: bad kind")
        if r.get("status") not in K_STATUS: errs.append(f"knowledge {r.get('id')}: bad status")
    for p in sorted(KB.rglob("*")):
        if p.is_file() and p.suffix in (".jsonl", ".json", ".md", ".py") and p.name != "kb.py":
            t = p.read_text()
            if redact(t) != t: errs.append(f"privacy: {p.relative_to(KB)} contains an id, email or account-like number")
    print("\n".join(errs) if errs else f"valid: {len(dec)} decisions, {len(kn)} knowledge entries")
    return 1 if errs else 0


def trade_stats(rows):
    pnl = [r["outcome"]["pnl"] for r in rows]
    w, l = [p for p in pnl if p > 0], [p for p in pnl if p <= 0]
    out = {"n": len(pnl), "wins": len(w), "losses": len(l)}
    if pnl:
        out.update(win_rate=round(len(w) / len(pnl), 3), total_pnl=round(sum(pnl), 4), expectancy=round(sum(pnl) / len(pnl), 4),
                   avg_win=round(sum(w) / len(w), 4) if w else None, avg_loss=round(sum(l) / len(l), 4) if l else None,
                   mean_pct=round(sum(r["outcome"]["pnl_pct"] for r in rows) / len(rows), 2))
        if w and l and sum(l): out["payoff_ratio"] = round((sum(w) / len(w)) / abs(sum(l) / len(l)), 2)
    return out


def metrics():
    dec = load("decisions.jsonl")
    closed = lambda kind: [r for r in dec if r["kind"] == kind and r["status"] == "closed" and r.get("outcome", {}).get("pnl") is not None]
    real = closed("trade")
    m = {"realized_trades": trade_stats(real), "by_regime": {}, "paper_trades_NOT_realized": trade_stats(closed("paper"))}
    for reg in sorted({r.get("regime") or "unknown" for r in real}):
        m["by_regime"][reg] = trade_stats([r for r in real if (r.get("regime") or "unknown") == reg])
    cal = [(r["expected"]["p_win"], 1.0 if r["outcome"]["pnl"] > 0 else 0.0) for r in real if (r.get("expected") or {}).get("p_win") is not None]
    m["calibration"] = {"n": len(cal), "brier": round(sum((p - o) ** 2 for p, o in cal) / len(cal), 4) if cal else None}
    m["decision_quality"] = {q: sum(1 for r in real if r.get("quality", "unrated") == q) for q in ("good", "bad", "unrated")}
    rej = [r for r in dec if r["kind"] == "rejected" and r["status"] == "closed" and r.get("outcome", {}).get("would_have_pct") is not None]
    m["rejections_resolved"] = {"n": len(rej), "avoided_loss": sum(1 for r in rej if r["outcome"]["would_have_pct"] <= 0)}
    log = BACKUP / "rh_bot_daily_log.jsonl"
    if log.exists():
        eq = [(e["date"], e["account_value"]) for e in map(json.loads, log.read_text().splitlines())
              if e.get("run_type") == "afternoon" and e.get("account_value") is not None]
        if eq:
            peak, dd, months = eq[0][1], 0.0, {}
            for d, v in eq:
                peak = max(peak, v); dd = max(dd, (peak - v) / peak)
                months.setdefault(d[:7], []).append(v)
            keys, mr = sorted(months), {}
            for i, k in enumerate(keys):
                base = months[keys[i - 1]][-1] if i else months[k][0]
                mr[k] = {"return_pct": round((months[k][-1] / base - 1) * 100, 2), "baseline": "prior month close" if i else "first logged close of month (partial)"}
            m["equity"] = {"first": eq[0], "last": eq[-1], "max_drawdown_pct": round(dd * 100, 2), "monthly": mr}
    m["caveat"] = "Sample under 30 closed trades: descriptive only, not evidence of edge." if m["realized_trades"]["n"] < 30 else None
    (KB / "metrics.json").write_text(json.dumps(m, indent=2) + "\n")
    print(json.dumps(m, indent=2))
    return 0


def backup(src):
    BACKUP.mkdir(exist_ok=True)
    for f in FILES:
        p = Path(src) / f
        if p.exists(): (BACKUP / f).write_text(redact(p.read_text())); print("backed up", f)
        else: print("MISSING in scratchpad, not backed up:", f)
    return 0


def restore(dst):
    Path(dst).mkdir(parents=True, exist_ok=True)
    for f in FILES:
        s, d = BACKUP / f, Path(dst) / f
        if d.exists(): print("kept existing", f)
        elif s.exists(): shutil.copy(s, d); print("restored", f)
        else: print("no backup for", f)
    return 0


if __name__ == "__main__":
    cmd, arg = (sys.argv[1:] + [None, None])[:2]
    if cmd in ("backup", "restore") and not arg: sys.exit("usage: kb.py %s <scratchpad dir>" % cmd)
    fn = {"validate": validate, "metrics": metrics, "backup": lambda: backup(arg), "restore": lambda: restore(arg)}.get(cmd)
    sys.exit(fn() if fn else __doc__)
