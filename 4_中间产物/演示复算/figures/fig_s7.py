import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
BG="#fafcfa"; GREEN="#2f8f4e"; PURPLE="#6a4c93"; MIX="#9fbfac"; DARK="#0e3b2b"; GREY="#56655d"; GRID="#e3ece5"
plt.rcParams.update({"font.family":"DejaVu Sans","axes.facecolor":BG,"figure.facecolor":BG,
                     "text.color":GREY,"axes.labelcolor":GREY,"xtick.color":GREY,"ytick.color":GREY})
rows=[("Construction",104.995,5.12),("Arts",100.659,6.02),("★ Housing",100.381,0.44),
      ("Transportation",98.189,6.47),("Reuse & Recycle",98.104,8.03),("Services",95.566,6.56),
      ("Health",93.264,10.04),("Clothing",89.377,13.30),("Personal Use",76.640,44.70),
      ("Education",75.385,20.28),("Agriculture",68.700,29.33),("Food",60.755,28.17),
      ("Retail",58.431,36.73),("Clean Energy",57.933,39.40),("★ PH × General Store",57.080,57.82)]
labels=[r[0] for r in rows]; vals=[r[1] for r in rows]; bp=[r[2] for r in rows]
cols=[GREEN if v>=90 else (MIX if v>=80 else PURPLE) for v in vals]
fig,ax=plt.subplots(figsize=(21.6,10.62),dpi=100)
fig.subplots_adjust(left=0.205,right=0.905,top=0.955,bottom=0.215)
y=np.arange(len(rows))[::-1]
ax.barh(y,vals,color=cols,height=0.72)
for yy,v in zip(y,vals):
    ax.text(v-1.6,yy,f"{round(v):.0f}%",ha="right",va="center",color="white",
            fontsize=25,fontweight="bold")
for yy,b in zip(y,bp):
    ax.text(112.5,yy,f"{round(b):.0f}%",ha="right",va="center",color=GREY,fontsize=23)
ax.text(112.5,len(rows)+0.05,"boilerplate",ha="right",va="center",color=DARK,fontsize=23,fontweight="bold")
ax.plot([100,100],[-0.7,len(rows)-0.45],color="#12211a",lw=2.4,ls=(0,(6,4)),clip_on=False,zorder=3)
ax.set_yticks(y)
ax.set_yticklabels(labels,fontsize=25)
for t,l in zip(ax.get_yticklabels(),labels):
    if l.startswith("★"): t.set_color(DARK); t.set_fontweight("bold")
    else: t.set_color(GREY)
ax.set_xlim(0,114); ax.set_ylim(-0.7,len(rows)+0.45)
ax.set_xticks([0,25,50,75,100]); ax.set_xticklabels(["0","25","50","75","100%"],fontsize=25)
ax.set_xlabel("share of Homogeneity H that survives when recurring language is removed",
              fontsize=25,color=GREY,labelpad=14)
for s in ("top","right","left"): ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(axis="y",length=0)
ax.grid(axis="x",color=GRID,lw=1.2); ax.set_axisbelow(True)
handles=[Patch(facecolor=GREEN,label="Type A · product sameness"),
         Patch(facecolor=MIX,label="mixed"),
         Patch(facecolor=PURPLE,label="Type B · process sameness")]
leg=ax.legend(handles=handles,loc="upper center",bbox_to_anchor=(0.42,-0.135),ncol=3,
              frameon=False,fontsize=25,handlelength=1.3,handleheight=1.1,columnspacing=3.0)
for t in leg.get_texts(): t.set_color(GREY)
fig.text(0.012,0.016,"Mean focal-to-pool cosine on masked use text, 2016–2024 training sample; 14 sectors with ≥9,000 loans plus one named country×activity market. Platform-wide the share is 75%.",
         fontsize=17,color=GREY)
fig.savefig("fig_s7_new.png",dpi=100,facecolor=BG)
print("ok")
