import json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
D=json.load(open('a6_data.json'))
BG="#fafcfa"; GREEN="#2f8f4e"; PURPLE="#6a4c93"; DARK="#0e3b2b"; GREY="#56655d"; GRID="#e3ece5"
plt.rcParams.update({"font.family":"DejaVu Sans","axes.facecolor":BG,"figure.facecolor":BG,
                     "text.color":GREY,"axes.labelcolor":GREY,"xtick.color":GREY,"ytick.color":GREY})
fig,axes=plt.subplots(2,2,figsize=(21.6,10.62),dpi=100)
fig.subplots_adjust(left=0.058,right=0.985,top=0.945,bottom=0.165,hspace=0.46,wspace=0.16)
days=np.arange(1,32)

def pulse(ax,arr,comp,title,ann):
    ax.bar(days,arr,color=GREEN,width=0.72)
    ax.bar(days,[-c for c in comp],color=PURPLE,width=0.72)
    ax.axhline(0,color="#12211a",lw=2.2)
    ax.set_title(title,color=DARK,fontsize=25,fontweight="bold",loc="left",pad=16)
    ax.set_xlabel("day of month",fontsize=19)
    ax.set_ylabel("index  (month mean = 1.0)",fontsize=17)
    ax.set_xticks([1,7,14,18,21,28]); ax.tick_params(labelsize=19)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_visible(False)
    ax.grid(axis="y",color=GRID,lw=1.2); ax.set_axisbelow(True)
    for txt,xy,xytext,col in ann:
        ax.annotate(txt,xy=xy,xytext=xytext,color=col,fontsize=21,fontweight="bold",
                    va="center",arrowprops=dict(arrowstyle="-",color=col,lw=2,
                    connectionstyle="angle,angleA=0,angleB=90,rad=8"))

p1=D["p1"]; p2=D["p2"]
axes[0,0].set_ylim(-4.3,6.6)
pulse(axes[0,0],p1["arr"],p1["comp"],"2024–2025    both pulses peak on day 18",
      [("arrivals 5.92×",(18.4,5.92),(21.0,5.35),GREEN),
       ("completions 2.75×",(18.4,-2.75),(21.2,-3.55),PURPLE)])
pulse(axes[0,1],p2["arr"],p2["comp"],"2016–2025    the pulse sits on days 17–18",
      [("arrivals peak day 17",(17.4,3.06),(20.0,2.72),GREEN)])

def simple(ax,vals,labels,title,ticks=None):
    x=np.arange(len(vals))
    ax.bar(x,vals,color=GREEN,width=0.66)
    ax.axhline(1.0,color=GREY,lw=2,ls=(0,(6,4)))
    ax.set_title(title,color=DARK,fontsize=25,fontweight="bold",loc="left",pad=16)
    ax.set_ylabel("index",fontsize=17); ax.tick_params(labelsize=19)
    for s in ("top","right"): ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_color(GRID)
    ax.grid(axis="y",color=GRID,lw=1.2); ax.set_axisbelow(True); ax.set_ylim(0,1.8)
    if ticks is None:
        ax.set_xticks(x); ax.set_xticklabels(labels)
    else:
        ax.set_xticks(ticks); ax.set_xticklabels([labels[t] for t in ticks])

# duckdb EXTRACT(DOW): 0=Sunday .. 6=Saturday -> reorder to Mon..Sun
dow=D["dow_code0_is_sunday"]
mon_sun=[dow[1],dow[2],dow[3],dow[4],dow[5],dow[6],dow[0]]
simple(axes[1,0],mon_sun,["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],
       "Day of week    range 0.86–1.08")
axes[1,0].set_xlabel("")
hours=D["hour"]
simple(axes[1,1],hours,[str(i) for i in range(24)],"Hour of day (UTC)    range 0.51–1.70",
       ticks=[0,6,12,18,23])
axes[1,1].set_xlabel("hour",fontsize=19)

fig.text(0.012,0.070,"Green above baseline = new listings (arrivals). Purple below = loans reaching raisedDate (completions), i.e. leaving the current pool.",
         fontsize=16.5,color=GREY)
fig.text(0.012,0.030,f"Day-of-month panels: Pacific calendar days, all {D['n_all']:,} valid loans, normalised so each month's mean = 1.0.  Day-of-week and hour panels: the {D['n_model']:,}-loan model sample, UTC.",
         fontsize=16.5,color=GREY)
fig.savefig("fig_a6_new.png",dpi=100,facecolor=BG)
print("ok")
