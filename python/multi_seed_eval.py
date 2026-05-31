"""Mean of the rigid eval across multiple seeds (mortgage data)."""
import statistics as st
from segmenter.engine import Segmenter
from segmenter.config import get_config
from segmenter.page_splitter import split_pages
from evalkit.gen_documents import make_dataset
from evalkit.metrics import aggregate, evaluate_batch

SEEDS = [1234, 9999, 2026, 777, 555]

def run(seed, n=200):
    seg = Segmenter(config=get_config())
    ds = make_dataset(n, seed=seed)
    rows = []; ok = 0
    for b in ds:
        pages = split_pages(b["ocr"])
        if len(pages) == len(b["truth"]): ok += 1
        else: pages = b["pages"]
        pr, _ = seg.segment(pages)
        rows.append(evaluate_batch(pr, b["truth"]))
    a = aggregate(rows); a["split"] = ok / len(ds); return a

keys = [("aa_split_rate","AA"),("boundary_precision","bP"),("boundary_recall","bR"),
        ("boundary_f1","bF1"),("segment_f1","segF1"),("type_accuracy_matched","type"),
        ("page_type_accuracy","pgTyp"),("unknown_leakage","leak"),
        ("false_unknown_rate","falsU"),("review_recall","revR"),("split","split")]
agg = {k: [] for k,_ in keys}
out = ["seed   " + "".join(f"{lbl:>8}" for _,lbl in keys)]
for s in SEEDS:
    a = run(s)
    for k,_ in keys: agg[k].append(a[k])
    out.append(f"{s:<7}" + "".join(f"{a[k]*100:8.1f}" for k,_ in keys))
out.append("-"*7 + "-"*8*len(keys))
out.append("MEAN   " + "".join(f"{st.mean(agg[k])*100:8.1f}" for k,_ in keys))
print("\n".join(out))
