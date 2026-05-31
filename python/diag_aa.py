from collections import Counter
from segmenter.engine import Segmenter
from evalkit.gen_documents import make_dataset
from evalkit.metrics import truth_to_segments

seg = Segmenter()
ds = make_dataset(200, seed=1234)
miss = Counter(); total = 0; ex = []
for b in ds:
    pred, dec = seg.segment(b["pages"])
    starts = {s.start_page for s in pred}
    ts = truth_to_segments(b["truth"])
    for a, c in zip(ts, ts[1:]):
        if a["type"] == c["type"] and a["type"] != "Unknown":
            total += 1
            if c["start"] not in starts:  # missed split
                d = dec[c["start"]]
                pn = "pn" if d.page_number else "nopn"
                miss[(a["type"][:18], pn)] += 1
                if len(ex) < 8:
                    ex.append((a["type"], "pgnum="+str(d.page_number), "score=%.0f"%d.start_score, d.signals))
print("A->A total:", total, "missed:", sum(miss.values()))
print("misses by (type, pagenum-present):")
for k, v in miss.most_common(12):
    print("  ", v, k)
print("--- examples ---")
for e in ex: print(e)
