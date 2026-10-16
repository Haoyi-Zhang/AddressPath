"""Draw the two retained TPEG measurements directly, without a TeX renderer."""
import argparse
import csv
from pathlib import Path
import tempfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"text.usetex": False, "font.family": "STIXGeneral",
    "mathtext.fontset": "stix", "font.size": 9, "axes.labelsize": 9,
    "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "axes.linewidth": .6,
    "lines.linewidth": .8, "lines.markersize": 4, "pdf.fonttype": 42,
    "ps.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False})


def data():
    tables = Path(__file__).resolve().parents[1] / "tables"
    with (tables / "tpeg-methods.csv").open(newline="", encoding="utf-8") as f:
        methods = list(csv.DictReader(f))
    expected = ["sink-adjacent zero", "uniform zero cut", "cut plus maximal-signature cover"]
    if [r["method"] for r in methods] != expected:
        raise ValueError("method identities changed")
    proved = [int(r["proved"]) for r in methods]
    if proved != [12, 36, 42]:
        raise ValueError("retained method counts changed")
    with (tables / "tpeg-scaling.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    signatures = [int(r["maximal_signatures"]) for r in rows]
    storage = [int(r["certificate_bytes"]) for r in rows]
    if signatures != [2,4,8,16,32,64] or storage != [362,649,1305,2781,6061,13277]:
        raise ValueError("retained signature/storage coordinates changed")
    return proved, signatures, storage


def save(fig, out, name):
    fig.canvas.draw()
    for ax in fig.axes:
        # Constrained layout must keep every axis and tick label inside the canvas.
        renderer = fig.canvas.get_renderer()
        labels = [ax.xaxis.label, ax.yaxis.label]
        for axis, limits in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())):
            lower, upper = sorted(limits)
            labels.extend(tick.label1 for tick in axis.get_major_ticks()
                          if lower <= tick.get_loc() <= upper)
        frame = fig.bbox
        for label in labels:
            if not label.get_text() or not label.get_visible(): continue
            box = label.get_window_extent(renderer)
            if box.x0 < frame.x0-1 or box.x1 > frame.x1+1 or box.y0 < frame.y0-1 or box.y1 > frame.y1+1:
                raise ValueError("clipped label: "+label.get_text())
    fig.savefig(out / (name+".pdf"), metadata={"Creator":"Python Matplotlib",
        "Producer":None,"CreationDate":None,"ModDate":None})
    plt.close(fig)


def figures(out):
    proved, signatures, storage = data()
    fig, ax = plt.subplots(figsize=(4.1,1.9),layout="constrained")
    bars = ax.bar(range(3), proved, width=.72, color=".35",edgecolor="black",linewidth=.5)
    ax.bar_label(bars,labels=[str(v) for v in proved],padding=3,fontsize=8.5)
    ax.set_xticks(range(3),labels=["sink-adjacent\nzero","uniform\nzero cut","cut + signature\ncover"])
    ax.set(ylabel="proved models",ylim=(0,50))
    ax.set_yticks([0,10,20,30,40]);ax.grid(axis="y",alpha=.2,lw=.4);ax.set_axisbelow(True)
    save(fig,out,"methods-bar")
    fig,ax=plt.subplots(figsize=(4.1,2.0),layout="constrained")
    ax.plot(signatures,storage,color="black",marker="o")
    ax.set_xscale("log",base=2);ax.set_yscale("log",base=10)
    ax.set_xticks(signatures,labels=[str(v) for v in signatures])
    ax.set(xlabel="maximal signatures in certificate",ylabel="certificate bytes")
    ax.grid(alpha=.2,lw=.4)
    save(fig,out,"signature-scaling")


def check():
    with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
        for p in (Path(a),Path(b)):figures(p)
        for name in ("methods-bar","signature-scaling"):
            if (Path(a)/(name+".pdf")).read_bytes() != (Path(b)/(name+".pdf")).read_bytes():
                raise ValueError("nondeterministic vector export: "+name)
    print("Retained method counts, signature/storage coordinates, labels and fresh direct-vector exports passed")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    if args.check: check()
    else:
        args.output_dir.mkdir(parents=True,exist_ok=True)
        figures(args.output_dir)
