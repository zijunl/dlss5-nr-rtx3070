"""Summarise PresentMon CSV captures and draw a frame-time comparison chart.

Usage:
    python frametime_report.py capture_a.csv [capture_b.csv ...] [--labels "A" "B"] [--svg out.svg]

For each capture prints: frames, duration, avg ms / fps, median, 1% low, max,
standard deviation, mean frame-to-frame change, odd/even averages (exposes the
10 ms / 23 ms sawtooth of alternating-frame NR) and per-5-second fps.
With --svg, writes a 2-second window of each capture as stacked frame-time plots
(a dashed line marks 16.7 ms = 60 fps).

Capture command (Intel PresentMon 2.x CLI, no admin needed for a process you own):
    PresentMon-2.5.1-x64.exe --process_name Game.exe --output_file run.csv \
        --timed 30 --terminate_after_timed --no_console_stats --stop_existing_session
"""
import argparse
import csv
import statistics as st


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    ft = [float(r["MsBetweenPresents"]) for r in rows if r.get("MsBetweenPresents") not in (None, "", "NA")]
    meta = rows[0] if rows else {}
    return ft, meta


def summarise(label, ft, meta):
    s = sorted(ft)
    n = len(s)
    if n < 10:
        print(f"{label}: only {n} frames - was the game in focus and rendering?")
        return
    d = [abs(ft[i] - ft[i - 1]) for i in range(1, n)]
    p99 = s[int(n * 0.99)]
    print(f"== {label}")
    print(f"  frames {n}, duration {sum(ft) / 1000:.1f} s")
    print(f"  avg {st.mean(ft):.2f} ms ({1000 / st.mean(ft):.1f} fps), median {st.median(ft):.2f} ms")
    print(f"  1% low {1000 / p99:.1f} fps (p99 {p99:.1f} ms), max {s[-1]:.1f} ms")
    print(f"  stdev {st.pstdev(ft):.2f} ms, mean frame-to-frame change {st.mean(d):.2f} ms")
    print(f"  odd/even frame avg {st.mean(ft[1::2]):.1f} / {st.mean(ft[0::2]):.1f} ms")
    print(f"  frames <= 16.7 ms: {100 * sum(1 for x in ft if x <= 16.7) / n:.0f}%")
    print(f"  present mode: {meta.get('PresentMode')}, sync interval: {meta.get('SyncInterval')}")
    t, cur, win = 0.0, [], []
    for x in ft:
        cur.append(x)
        t += x
        if t >= 5000:
            win.append(1000 / st.mean(cur))
            cur, t = [], 0.0
    if win:
        print("  fps per 5 s:", " ".join(f"{v:.1f}" for v in win))


def svg_chart(series, out):
    colors = ["#f0a030", "#4aa3ff", "#6fcf97", "#eb5757"]
    W, H, L, R, T, B = 1200, 300, 70, 20, 40, 40
    ymax = 35.0
    pw, ph = W - L - R, H - T - B
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{len(series) * H + 50}" '
             'font-family="Segoe UI, Microsoft YaHei, sans-serif">',
             '<rect width="100%" height="100%" fill="#1b1b1f"/>',
             f'<text x="{L}" y="28" font-size="20" font-weight="bold" fill="#fff">Frame time (ms), 2 s window</text>']
    for i, (label, ft) in enumerate(series):
        y0 = 40 + i * H
        mean = st.mean(ft)
        parts.append(f'<text x="{L}" y="{y0 + 24}" font-size="18" font-weight="bold" fill="#e8e8e8">{label}</text>')
        parts.append(f'<text x="{W - R}" y="{y0 + 24}" font-size="15" fill="#bbb" text-anchor="end">'
                     f'avg {1000 / mean:.1f} fps | stdev {st.pstdev(ft):.2f} ms</text>')
        for v in (0, 10, 16.7, 20, 25, 30):
            y = y0 + T + ph - (v / ymax) * ph
            col = "#6a6" if v == 16.7 else "#555"
            dash = "" if v == 0 else ' stroke-dasharray="4 4"'
            parts.append(f'<line x1="{L}" x2="{W - R}" y1="{y:.1f}" y2="{y:.1f}" stroke="{col}"{dash}/>')
            parts.append(f'<text x="{L - 6}" y="{y + 5:.1f}" font-size="13" fill="#aaa" text-anchor="end">{v:g}</text>')
        start = min(300, max(0, len(ft) - 200))
        t, pts = 0.0, []
        for v in ft[start:]:
            if t > 2000:
                break
            x = L + (t / 2000) * pw
            y = y0 + T + ph - (min(v, ymax) / ymax) * ph
            pts.append(f"{x:.1f},{y:.1f}")
            t += v
        c = colors[i % len(colors)]
        parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{c}" stroke-width="2"/>')
    parts.append("</svg>")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"chart written to {out}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--labels", nargs="*")
    ap.add_argument("--svg")
    a = ap.parse_args()
    labels = a.labels if a.labels and len(a.labels) == len(a.csv) else a.csv
    series = []
    for path, label in zip(a.csv, labels):
        ft, meta = load(path)
        summarise(label, ft, meta)
        if len(ft) >= 10:
            series.append((label, ft))
    if a.svg and series:
        svg_chart(series, a.svg)


if __name__ == "__main__":
    main()
