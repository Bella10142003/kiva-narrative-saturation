"""
Kiva 叙事饱和提案 —— 模拟数据生成器
=====================================================================
目的：把 100 条真实样本扩充成可试验的合成数据集，用于在提交前
      实际执行一遍提案里的分析流程，检验每一步的必要性与可行性。

设计原则
---------
1. 字段 schema 与真实样本完全一致（27 个字段，同名同类型）。
2. 关键结构特征被刻意植入，使得提案里每一条方法论主张都可被证伪：
   - 已知真值 β1..β6（含随年份演化的 β3/β6）——检验测量矩阵能否分开两条通道
   - 行业-周内生冲击 u[s,w] ——检验「主动池被结果污染」是否真的造成偏误、
     以及「按发布时间构造的镜像池」是否真的能纠正
   - 合作机构（Lending Partner）异质性 ——机构效应同时影响模板化程度与
     募资速度，且 partner_id 不出现在交付数据里（复刻真实数据无 partner
     identifier 的困境），检验 raw/residual 分解能否替代 partner FE
   - 模板化程度随年份上升 ——检验 RQ3 的方向性预测能否被测出
   - 到期未募满（expired）与终止日期缺失 ——检验删失模型与镜像池兜底分支
3. 主动池按时间顺序真实模拟：贷款 i 上架时的池子由此前已抽取的
   贷款端点决定，因此同时性与内生性是「长出来的」，不是事后加的噪音。

输出
-----
  kiva_sim_20k.pkl        与真实样本同构的 list[dict]，交给分析流程
  kiva_sim_truth.csv      真值表（partner_id / 真实 C,H,V,G / 系统性成分 /
                          真实系数），分析时不得使用，只用于对答案
"""

import numpy as np, pandas as pd, hashlib, json, heapq, time
from datetime import datetime, timedelta

# =====================================================================
# 0. 配置
# =====================================================================
CFG = dict(
    SEED           = 20260823,
    N              = 20_000,
    START          = "2016-01-01",
    END            = "2025-12-31",
    FUNDRAISE_CAP_DAYS = 35,      # 平台募资期限上限 → 提案里的 L（对齐真实样本最长 840h）
    LAG_HALFLIFE_DAYS  = 7.0,     # 生成端使用的真实衰减半衰期
    TARGET_MEDIAN_HOURS = 62.0,   # 对齐 100 条真实样本的筹资时长中位数
    MIRROR_WINDOW_DAYS = 14,
    SIGMA_EPS      = 1.60,        # log(1+hours) 残差标准差（对齐真实样本的均值/中位数比）
    EXPIRE_ENABLED = True,
    TERMINAL_DATE_MISSING_RATE = 0.35,  # expired 贷款里终止日期不可重建的比例
)

# ---- 植入的真实系数（作用在“原始尺度”测量上，事后换算为标准化尺度）----
TRUE = dict(
    a1_C  =  0.150,   # 主动池规模 log(1+C)
    a2_H  =  0.900,   # 主动池同质度（余弦，量纲 0~1，故系数较大）
    a3_CH =  0.520,   # 主动饱和 = 交互（2016 基准值）
    a4_V  =  0.060,   # 近期上架量（衰减计数）
    a5_G  =  0.350,   # 近期同质度
    a6_VG =  0.180,   # 近期饱和 = 交互（2016 基准值）—— 刻意设为主动通道的约 1/3
    a3_year_growth = 0.055,   # RQ3 预测一：主动饱和逐年增强
    a6_year_growth = 0.130,   # RQ3 预测二：近期饱和增强更快
    c0 = 3.2, h0 = 0.16, v0 = 3.0, g0 = 0.14,   # 交互项中心化常数
)

rng = np.random.default_rng(CFG["SEED"])

# =====================================================================
# 1. 参照分布（源自 100 条真实样本，按 Kiva 公开构成外推）
# =====================================================================
SECTOR_ACTIVITY = {
    "Agriculture": ["Farming", "Animal Sales", "Agriculture", "Livestock", "Dairy",
                    "Poultry", "Fish Selling", "Pigs", "Cattle"],
    "Food":        ["Food Market", "Food Production/Sales", "Grocery Store",
                    "Restaurant", "Fruits & Vegetables", "Bakery", "Fishing"],
    "Retail":      ["General Store", "Retail", "Clothing Sales", "Shoe Sales",
                    "Used Clothing", "Cosmetics Sales", "Mobile Phones"],
    "Services":    ["Services", "Tailoring", "Hair Salon", "Transportation",
                    "Barber Shop"],
    "Housing":     ["Personal Housing Expenses", "Home Appliances", "Home Products Sales"],
    "Education":   ["Higher education costs", "Primary/secondary school costs",
                    "Education provider"],
    "Health":      ["Personal Medical Expenses", "Health", "Pharmacy"],
    "Clean Energy":["Solar", "Personal Products Sales"],
    "Clothing":    ["Clothing", "Weaving", "Textiles"],
    "Personal Use":["Personal Purchases", "Home Energy"],
    "Arts":        ["Crafts", "Arts", "Embroidery"],
}
SECTOR_W = np.array([.30,.20,.16,.08,.06,.05,.045,.035,.03,.02,.02])

COUNTRIES = [
    # (name, iso, region, ppp, lat, lon, weight)
    ("Philippines","PH","Asia",4321,13,122,.135),("Kenya","KE","Africa",3010,1,38,.105),
    ("Cambodia","KH","Asia",3352,13,105,.055),("Uganda","UG","Africa",1930,1,32,.055),
    ("Tajikistan","TJ","Asia",2668,39,71,.045),("Pakistan","PK","Asia",4390,30,70,.045),
    ("Senegal","SN","Africa",2790,14,-14,.035),("Nicaragua","NI","Central America",4183,13,-85,.035),
    ("Rwanda","RW","Africa",1290,-2,30,.033),("Ecuador","EC","South America",4498,-2,-78,.032),
    ("Tanzania","TZ","Africa",1650,-6,35,.030),("Nigeria","NG","Africa",2280,10,8,.028),
    ("Ghana","GH","Africa",2450,8,-1,.026),("El Salvador","SV","Central America",4290,14,-89,.026),
    ("Honduras","HN","Central America",2830,15,-86,.025),("Vietnam","VN","Asia",4160,16,108,.024),
    ("Mali","ML","Africa",900,17,-4,.022),("Sierra Leone","SL","Africa",520,8,-11,.021),
    ("Zambia","ZM","Africa",1350,-15,28,.020),("Madagascar","MG","Africa",520,-20,47,.020),
    ("Congo (DRC)","CD","Africa",620,-4,22,.019),("Haiti","HT","North America",1690,19,-72,.018),
    ("Palestine","PS","Middle East",3560,32,35,.017),("Jordan","JO","Middle East",4180,31,36,.016),
    ("Kyrgyzstan","KG","Asia",1970,41,75,.016),("Nepal","NP","Asia",1380,28,84,.015),
    ("Myanmar","MM","Asia",1180,22,96,.014),("Burkina Faso","BF","Africa",840,12,-2,.013),
    ("Togo","TG","Africa",990,8,1,.012),("Benin","BJ","Africa",1370,9,2,.012),
    ("Malawi","MW","Africa",640,-13,34,.011),("Mozambique","MZ","Africa",500,-18,35,.011),
    ("Liberia","LR","Africa",760,6,-9,.010),("Timor-Leste","TL","Oceania",1420,-8,125,.009),
    ("Lebanon","LB","Middle East",4420,33,35,.009),("Samoa","WS","Oceania",4180,-13,-172,.008),
    ("Bolivia","BO","South America",3600,-16,-64,.008),("Guatemala","GT","Central America",4470,15,-90,.008),
    ("Colombia","CO","South America",4390,4,-72,.007),("Peru","PE","South America",4360,-9,-75,.007),
    ("India","IN","Asia",2410,20,77,.007),("Indonesia","ID","Asia",4290,-5,120,.007),
    ("Ethiopia","ET","Africa",1020,8,38,.006),("Cameroon","CM","Africa",1590,6,12,.006),
    ("Cote d'Ivoire","CI","Africa",2380,8,-5,.006),("Zimbabwe","ZW","Africa",1520,-19,29,.005),
    ("Lesotho","LS","Africa",1120,-29,28,.005),("Rwanda-2","RW","Africa",1290,-2,30,.004),
    ("Egypt","EG","Africa",3900,27,30,.004),("Armenia","AM","Asia",4470,40,45,.004),
    ("Moldova","MD","Europe",4260,47,29,.003),("Georgia","GE","Asia",4390,42,43,.003),
    ("Solomon Islands","SB","Oceania",2050,-8,159,.003),("Vanuatu","VU","Oceania",2980,-16,167,.003),
    ("Sri Lanka","LK","Asia",3820,7,81,.003),
]
CTRY_W = np.array([c[6] for c in COUNTRIES]); CTRY_W = CTRY_W/CTRY_W.sum()

CITY_POOL = ["Quezon","Bais","Kalibo","Nakuru","Kisumu","Machakos","Khujand","Bokhtar",
              "Thies","Kaolack","Battambang","Siem Reap","Masaka","Gulu","Lahore","Multan",
              "Kigali","Huye","Tegucigalpa","Choluteca","Managua","Leon","Bukavu","Goma",
              "Port-au-Prince","Cap-Haitien","Hebron","Nablus","Bishkek","Osh","Pokhara",
              "Mandalay","Bamako","Segou","Bo","Kenema","Lusaka","Ndola","Tulear","Tamatave",
              "Arusha","Mbeya","Tamale","Kumasi","Bauchi","Ilorin","Cusco","Trujillo",
              "Sucre","Riobamba","Jinja","Mbale","Kandal","Takeo","Iloilo","Davao"]
CITY_STUBS = CITY_POOL
REAL_CITIES = {
 "Philippines":["Quezon, Palawan","Bais, Negros Oriental","Kalibo, Aklan","Iloilo City"],
 "Kenya":["Nakuru","Kisumu","Machakos","Eldoret"], "Cambodia":["Battambang","Siem Reap","Kandal","Takeo"],
 "Uganda":["Masaka","Gulu","Jinja","Mbale"], "Tajikistan":["Khujand","Bokhtar","Kulob"],
 "Pakistan":["Lahore","Multan","Faisalabad"], "Senegal":["Thies","Kaolack","Ziguinchor"],
 "Nicaragua":["Managua","Leon","Esteli"], "Rwanda":["Kigali","Huye","Musanze"],
 "Ecuador":["Riobamba","Ambato","Loja"], "Tanzania":["Arusha","Mbeya","Morogoro"],
 "Nigeria":["Bauchi","Ilorin","Abeokuta"], "Ghana":["Tamale","Kumasi","Cape Coast"],
 "El Salvador":["Santa Ana","San Miguel","Sonsonate"], "Honduras":["Tegucigalpa","Choluteca","Comayagua"],
 "Vietnam":["Can Tho","Hue","Vinh"], "Mali":["Bamako","Segou","Sikasso"],
 "Sierra Leone":["Bo","Kenema","Makeni"], "Zambia":["Lusaka","Ndola","Kabwe"],
 "Madagascar":["Tulear","Tamatave","Antsirabe"], "Congo (DRC)":["Bukavu","Goma","Kikwit"],
 "Haiti":["Cap-Haitien","Les Cayes","Jacmel"], "Palestine":["Hebron","Nablus","Jenin"],
 "Kyrgyzstan":["Bishkek","Osh","Jalal-Abad"], "Nepal":["Pokhara","Butwal","Biratnagar"],
 "Peru":["Cusco","Trujillo","Arequipa"], "Bolivia":["Sucre","Tarija","Potosi"],
}
CITY_BY_COUNTRY = {c[0]: REAL_CITIES.get(c[0], [f"{c[0]} Region {k+1}" for k in range(3)])
                   for c in COUNTRIES}

FIRST_F = ["Josephine","Mary","Grace","Amina","Fatima","Rosa","Maria","Ana","Sokha","Srey",
           "Zulfiya","Gulnara","Aissatou","Awa","Nadia","Rita","Beatrice","Esther","Janet",
           "Nyaradzo","Chantal","Immaculee","Thida","Malika","Rosalinda","Jocelyn","Nilda"]
FIRST_M = ["Joseph","Peter","John","Ahmed","Ibrahim","Carlos","Jose","Samnang","Rustam",
           "Mamadou","Ousmane","Emmanuel","Patrick","David","Moses","Tafadzwa","Jean","Kofi"]

REPAY_INTERVAL = (["monthly"]*86 + ["irregularly"]*8 + ["at_end"]*6)

# =====================================================================
# 2. 合作机构（Lending Partner）体系
#    —— 模板族决定文本重复度；机构效应同时影响模板化与募资速度
# =====================================================================
N_PARTNERS = 72
N_TEMPLATE_FAMILIES = 14

BOILER_A = [
    "This loan is part of {P}'s effort to reach clients in remote areas where formal banking is unavailable.",
    "{P} is a microfinance institution that has served low-income households since 2004.",
    "Loans from {P} are disbursed through village banking groups that meet every two weeks.",
    "{P} combines credit with financial literacy training for all of its borrowers.",
    "This borrower is a client of {P}, a social enterprise focused on rural livelihoods.",
    "{P} works with smallholder producers to smooth seasonal cash flow.",
    "As a {P} client, this borrower receives ongoing business mentoring alongside the loan.",
    "{P} prioritises women-led enterprises in underserved districts.",
    "This is a repeat loan; {P} reports full repayment on all previous cycles.",
    "{P} operates a group-guarantee model in which members co-sign one another's loans.",
    "Funds are channelled through {P}'s branch network across the region.",
    "{P} has partnered with Kiva to expand access to affordable working capital.",
    "{P} offers this product to clients who lack the collateral required by commercial banks.",
    "Through {P}, borrowers gain access to markets as well as to credit.",
]
BOILER_B = [
    "Your support helps {P} continue offering responsibly priced credit in this community.",
    "By funding this loan you enable {P} to reach more clients in the coming cycle.",
    "{P} thanks the Kiva lender community for its continued partnership.",
    "Repayments will be recycled by {P} into new loans in the same district.",
    "This loan enables {P} to keep interest rates below the local market average.",
    "With your help, {P} can extend its outreach to neighbouring villages.",
    "{P} monitors each loan through monthly field visits by a dedicated officer.",
]
WHY_SPECIAL = [
    "It empowers women in rural and suburban communities.",
    "It finances smallholder farmers to purchase inputs and equipment.",
    "It helps protect families who are most vulnerable to waterborne diseases.",
    "It supports first-time borrowers who have no access to formal credit.",
    "It funds clean energy products that replace kerosene lighting.",
    "It reaches clients in post-conflict areas with very limited banking infrastructure.",
    "It combines credit with business training for young entrepreneurs.",
    "It serves refugee and host-community households side by side.",
    "It enables households to pay school fees without resorting to informal lenders.",
    "It backs group-guaranteed loans among neighbours who know one another well.",
]

PARTNER_PREFIX = ["Fundacion","Banco","KIT","Rural Trust","MicroCredit","Sowing",
                  "Hope","VisionFund","Alliance","Fondesa"]

def build_partners(rng):
    ps = []
    for k in range(N_PARTNERS):
        home = int(rng.choice(len(COUNTRIES), p=CTRY_W))
        fam  = int(rng.integers(0, N_TEMPLATE_FAMILIES))
        size = float(rng.beta(1.6, 3.0))                 # 机构规模（份额权重）
        # 机构效应：规模大的机构在平台上更知名 → 募资更快（负号 = 更快）
        # 同时规模大的机构模板化程度更高 → 制造 H 的遗漏变量偏误
        tmpl_intensity = float(np.clip(0.20 + 0.75*size + rng.normal(0, 0.10), 0.02, 0.95))
        partner_effect = float(-0.55*size + rng.normal(0, 0.28))
        pname = f"{PARTNER_PREFIX[k % 10]} {CITY_STUBS[k % len(CITY_STUBS)]}"
        ps.append(dict(
            partner_id=f"P{k:03d}", name=pname,
            country_idx=home, family=fam, size=size,
            tmpl_intensity=tmpl_intensity, effect=partner_effect,
            boiler_a=BOILER_A[fam], boiler_b=BOILER_B[fam % len(BOILER_B)],
            why=(WHY_SPECIAL[fam % len(WHY_SPECIAL)][:-1] + " " +
                 ["in the districts where it operates.","through its branch network.",
                  "with support from local field officers.","as part of its core mission.",
                  "in partnership with community groups."][k % 5]),
        ))
    return ps


# =====================================================================
# 3. 文本生成
#    use          = 活动级模板 + 物品槽（浏览页所见，短）
#    description  = 机构模板句 + 借款人个性化句（点进去才读，长）
#    whySpecial   = 机构级常量（复刻真实数据：几乎无个体变异）
# =====================================================================
ITEMS = {
    "Farming": ["seeds and fertilizers","modern farm inputs such as seeds and fertilizers",
                "improved maize seed","irrigation equipment","pesticide and fertiliser"],
    "Animal Sales": ["sheep","goats","two cows","piglets","a heifer"],
    "Livestock": ["cattle feed","veterinary supplies","a dairy cow"],
    "Dairy": ["a dairy cow","milk cans","feed for her cows"],
    "Poultry": ["day-old chicks","chicken feed","a poultry brooder"],
    "Pigs": ["piglets","pig feed","materials for a pig pen"],
    "Cattle": ["a bull","cattle feed","two heifers"],
    "Agriculture": ["farm inputs","tools and seed","a water pump"],
    "Fish Selling": ["more fresh and dried fish","fish for resale","a cool box and fish"],
    "Fishing": ["fishing nets","a boat engine","fuel and nets"],
    "Food Market": ["more rice, oil, pepper, sugar and other food items to sell",
                    "sacks of rice and cooking oil","assorted foodstuffs for her stall"],
    "Food Production/Sales": ["rice, meat and vegetables for making her food to sell",
                              "flour and cooking gas","ingredients for her cooked-food business"],
    "Grocery Store": ["stock for her grocery","soap, sugar and flour to resell","more groceries"],
    "Restaurant": ["tables and cooking equipment","ingredients for her eatery","a gas cooker"],
    "Fruits & Vegetables": ["fruit and vegetables to resell","a crate of tomatoes and onions"],
    "Bakery": ["flour, sugar and yeast","an oven","baking ingredients"],
    "General Store": ["more stock for her store","goods to resell in her shop","assorted merchandise"],
    "Retail": ["merchandise for resale","stock for her shop"],
    "Clothing Sales": ["clothes to resell","bales of clothing","dresses and shirts for her stall"],
    "Used Clothing": ["a bale of second-hand clothes","used clothing for resale"],
    "Shoe Sales": ["shoes for resale","sandals and school shoes to sell"],
    "Cosmetics Sales": ["cosmetics and beauty products to resell","hair products for her stall"],
    "Mobile Phones": ["phone accessories and airtime","mobile phones for resale"],
    "Services": ["equipment for her business","supplies for her service business"],
    "Tailoring": ["fabric and thread","a sewing machine","cloth for her tailoring business"],
    "Hair Salon": ["hair products and a dryer","salon equipment"],
    "Barber Shop": ["clippers and a mirror","barbering equipment"],
    "Transportation": ["a motorcycle for transport","spare parts and fuel","a tricycle"],
    "Personal Housing Expenses": ["build a sanitary toilet for her family",
                                  "repair the roof of her house","install a concrete floor"],
    "Home Appliances": ["a refrigerator","a water filter","a cooking stove"],
    "Home Products Sales": ["household goods to resell","kitchenware for her stall"],
    "Higher education costs": ["pay her university tuition","cover college fees for her son"],
    "Primary/secondary school costs": ["pay school fees for her children","buy uniforms and books"],
    "Education provider": ["desks and teaching materials","books for her school"],
    "Personal Medical Expenses": ["pay for dental treatment to improve her health",
                                  "cover a medical operation","pay hospital costs"],
    "Health": ["medical supplies","health products to resell"],
    "Pharmacy": ["medicines to stock her pharmacy","pharmaceutical supplies"],
    "Solar": ["a solar home system","a solar lantern and phone charger"],
    "Personal Products Sales": ["personal-care products to resell"],
    "Clothing": ["fabric for making garments","clothing materials"],
    "Weaving": ["yarn and dye","weaving materials"],
    "Textiles": ["cloth and thread","textiles for resale"],
    "Personal Purchases": ["household items for her family","a water tank"],
    "Home Energy": ["a clean cookstove","an energy-efficient stove"],
    "Crafts": ["craft materials","beads and wire for her jewellery"],
    "Arts": ["art supplies","materials for her craft business"],
    "Embroidery": ["embroidery thread and cloth"],
}
USE_FORMS = [
    "to buy {item}.",                      # 模板句（模板化机构固定用这句）
    "to purchase {item} for her business.",
    "to invest in {item} so that she can increase her income.",
    "to pay for {item}.",
]
PERSONA = [
    "{N} is a hardworking microentrepreneur.",
    "{N} is a dedicated parent who has run this business for {yrs} years.",
    "{N} lives in {C} and supports a household of {hh}.",
    "{N} has been trading in the local market since {yr0}.",
]
FAMILY = [
    "She is married and has {kids} children.",
    "He is married and has {kids} children.",
    "She is a widow raising {kids} children on her own.",
    "She lives with her extended family of {hh} people.",
]
ASPIRE = [
    "With the profits she hopes to expand her stock and pay school fees.",
    "Her dream is to grow the business and build a better home for her family.",
    "He plans to reinvest the earnings and increase his working capital.",
    "She hopes to save enough to open a second stall next year.",
]

def make_texts(rng, r, partner, year):
    """返回 (use, description, whySpecial)。模板化概率随年份与机构强度上升。"""
    p_tmpl = float(np.clip(partner["tmpl_intensity"] * (0.55 + 0.09*(year-2016)), 0, 0.97))
    templated = rng.random() < p_tmpl

    items = ITEMS.get(r["activity"], ["stock for her business"])
    if templated:
        item, form = items[0], USE_FORMS[0]
    else:
        item = items[int(rng.integers(len(items)))]
        form = USE_FORMS[int(rng.integers(len(USE_FORMS)))]
        # 非模板化文本带借款人特有的数量 / 限定语 —— 拉开 use 字段的差异度
        qty = ["", "", "more ", f"{int(rng.integers(2,40))} ", "additional ",
               "a fresh supply of ", "another batch of "][int(rng.integers(7))]
        tail = ["", "", "", " for the coming season", " to meet rising demand",
                " during the busy months", " for her regular customers",
                " so that she can serve more clients"][int(rng.integers(8))]
        item = qty + item + tail
    use   = form.format(item=item)
    if r["activity"] in ("Personal Housing Expenses","Higher education costs",
                         "Primary/secondary school costs","Personal Medical Expenses"):
        use = f"to {item}." if not templated else f"to {items[0]}."

    N, C = r["name"], r["city"].split(",")[0]
    kids, hh, yrs = int(rng.integers(1,7)), int(rng.integers(2,10)), int(rng.integers(2,20))
    persona = (PERSONA[0] if templated else PERSONA[int(rng.integers(len(PERSONA)))]
               ).format(N=N, C=C, hh=hh, yrs=yrs, yr0=year-yrs)
    fam_pool = [FAMILY[1]] if r["gender"] == "male" else [FAMILY[0], FAMILY[2], FAMILY[3]]
    fam = (fam_pool[0] if templated else fam_pool[int(rng.integers(len(fam_pool)))]
           ).format(kids=kids, hh=hh)
    asp = (ASPIRE[0] if templated else ASPIRE[int(rng.integers(len(ASPIRE)))])
    ba = partner["boiler_a"].format(P=partner["name"])
    bb = partner["boiler_b"].format(P=partner["name"])
    req = (f"She requested a loan of {int(r['loanAmount'])} USD through "
           f"{partner['name']} {use[:-1]}.")
    desc = f"{persona} {fam}<br /><br />{ba} {req}<br /><br />{asp} {bb}"
    return use, desc, partner["why"]


# =====================================================================
# 4. 生成贷款属性与上架时间
# =====================================================================
SECTORS = list(SECTOR_ACTIVITY.keys())

def build_loans(rng, partners, n, start, end):
    t0, t1 = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    days = (t1 - t0).days
    years = np.arange(2016, 2026)
    # 上架量逐年增长（复刻平台扩张），并带周内与季节波动
    yw = 0.55 + 0.11*(years-2016); yw = yw/yw.sum()
    n_by_year = rng.multinomial(n, yw)

    # 活动在行业内的份额（固定，非均匀）
    act_w = {s: rng.dirichlet(np.full(len(a), 1.6)) for s, a in SECTOR_ACTIVITY.items()}
    p_size = np.array([p["size"] for p in partners]); p_size = p_size/p_size.sum()

    rows = []
    for yi, y in enumerate(years):
        k = n_by_year[yi]
        y0 = pd.Timestamp(f"{y}-01-01", tz="UTC")
        # 季节性：年中略多；周内：周末少
        frac = rng.random(k)
        seas = 0.5 + 0.5*np.sin(2*np.pi*frac)             # 用于轻微重加权
        keep = rng.random(k) < (0.75 + 0.25*seas)
        frac = np.where(keep, frac, rng.random(k))
        offs = np.sort(frac) * 365.0
        for j in range(k):
            pi = int(rng.choice(len(partners), p=p_size))
            P  = partners[pi]
            ci = P["country_idx"] if rng.random() < 0.85 else int(rng.choice(len(COUNTRIES), p=CTRY_W))
            cn, iso, reg, ppp, clat, clon, _ = COUNTRIES[ci]
            s  = SECTORS[int(rng.choice(len(SECTORS), p=SECTOR_W))]
            a  = SECTOR_ACTIVITY[s][int(rng.choice(len(SECTOR_ACTIVITY[s]), p=act_w[s]))]
            female = rng.random() < 0.82
            gender = "female" if female else "male"
            name = (FIRST_F if female else FIRST_M)[int(rng.integers(len(FIRST_F if female else FIRST_M)))]
            amt = float(np.round(np.exp(rng.normal(5.75, 0.75)) / 25) * 25)
            amt = float(np.clip(amt, 50, 10000))
            bc  = 1 if rng.random() < 0.90 else int(rng.integers(2, 20))
            if bc > 1: amt = float(np.round(amt * bc * 0.6 / 25) * 25)
            post = y0 + pd.Timedelta(days=float(offs[j])) + pd.Timedelta(
                       hours=float(rng.integers(0, 24)), minutes=float(rng.integers(0, 60)),
                       seconds=float(rng.integers(0, 60)))
            gap = float(rng.normal(18, 12))               # pre-disbursal 为主
            if rng.random() < 0.12: gap = -float(rng.integers(1, 40))   # post-disbursal
            r = dict(
                partner_idx=pi, sector=s, activity=a, gender=gender, name=name,
                loanAmount=amt, borrowerCount=bc,
                lenderRepaymentTerm=int(np.clip(rng.normal(13, 5), 4, 40)),
                repaymentInterval=REPAY_INTERVAL[int(rng.integers(len(REPAY_INTERVAL)))],
                city=f"{CITY_BY_COUNTRY[cn][int(rng.integers(len(CITY_BY_COUNTRY[cn])))]}, {cn}",
                country_iso=iso, country_name=cn, region=reg, country_ppp=float(ppp),
                country_latitude=int(clat), country_longitude=int(clon),
                latitude=float(clat + rng.normal(0, 2.0)),
                longitude=float(clon + rng.normal(0, 2.0)),
                fundsLentInCountry=int(max(1e5, rng.lognormal(17.5, 1.3))),
                post=post, year=int(y),
            )
            r["disbursalDate"] = post - pd.Timedelta(days=gap)
            rows.append(r)
    df = pd.DataFrame(rows).sort_values("post", ignore_index=True)
    df["id"] = 1_000_000 + np.arange(len(df))*7 + rng.integers(0, 7, len(df))
    return df

t_start = time.time()
partners = build_partners(rng)
loans = build_loans(rng, partners, CFG["N"], CFG["START"], CFG["END"])
print(f"[1] 属性生成 {len(loans)} 条  {time.time()-t_start:.1f}s")

# 文本
uses, descs, whys = [], [], []
for i, r in loans.iterrows():
    P = partners[r["partner_idx"]]
    u, d, w = make_texts(rng, r, P, r["year"])
    uses.append(u); descs.append(d); whys.append(w)
loans["use"], loans["description"], loans["whySpecial"] = uses, descs, whys
loans["image_url"] = [
    "https://www.kiva.org/img/s100/" + hashlib.md5(str(i).encode()).hexdigest() + ".webp"
    for i in loans["id"]]
print(f"[2] 文本生成完成  {time.time()-t_start:.1f}s")


# =====================================================================
# 5. 真实叙事环境的构造（生成端使用 use 字段的余弦相似度作为“真驱动”）
#    说明：这是模拟的**假设**，不是发现。它让分析端可以检验
#          “扫描阶段文本(use) vs 审议阶段文本(description)”哪一个能还原真值。
# =====================================================================
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy import sparse

vec_u = TfidfVectorizer(ngram_range=(1,2), min_df=3, sublinear_tf=True, norm="l2")
U = vec_u.fit_transform(loans["use"].tolist()).astype(np.float64).tocsr()
print(f"[3] use 向量 {U.shape}  {time.time()-t_start:.1f}s")

post_h = (loans["post"].values.astype("datetime64[s]").astype(np.int64) / 3600.0)   # 小时
sector_code = pd.Categorical(loans["sector"]).codes.astype(int)
NS = sector_code.max() + 1
L_HOURS   = CFG["FUNDRAISE_CAP_DAYS"] * 24.0
WIN_HOURS = 30 * 24.0
LAM = np.log(2) / (CFG["LAG_HALFLIFE_DAYS"] * 24.0)

# ---- 滞后池（status-agnostic，只依赖发布时间，可预先计算）----
idx_by_sector = [np.where(sector_code == s)[0] for s in range(NS)]
V_true = np.zeros(len(loans)); G_true = np.zeros(len(loans)); Nlag = np.zeros(len(loans), int)
for s in range(NS):
    ids = idx_by_sector[s]; ts = post_h[ids]
    lo = np.searchsorted(ts, ts - L_HOURS - WIN_HOURS)
    hi = np.searchsorted(ts, ts - L_HOURS)
    Us = U[ids]
    for k in range(len(ids)):
        if hi[k] <= lo[k]: continue
        sl = slice(lo[k], hi[k])
        w = np.exp(-LAM * (ts[k] - ts[sl] - L_HOURS))
        Vk = w.sum()
        if Vk <= 0: continue
        pool = Us[sl]
        wmean = sparse.csr_matrix(w.reshape(1,-1)) @ pool          # 加权和向量
        V_true[ids[k]] = Vk
        G_true[ids[k]] = float(Us[k].multiply(wmean).sum() / Vk)
        Nlag[ids[k]] = hi[k] - lo[k]
print(f"[4] 滞后池完成  {time.time()-t_start:.1f}s")

# ---- 镜像池（前 14 天发布的全部同行业贷款，不论后续状态）----
MIR_H = CFG["MIRROR_WINDOW_DAYS"] * 24.0
Cm = np.zeros(len(loans)); Hm = np.zeros(len(loans))
for s in range(NS):
    ids = idx_by_sector[s]; ts = post_h[ids]; Us = U[ids]
    lo = np.searchsorted(ts, ts - MIR_H); hi = np.arange(len(ids))
    for k in range(len(ids)):
        if hi[k] <= lo[k]: continue
        pool = Us[lo[k]:hi[k]]
        Cm[ids[k]] = hi[k]-lo[k]
        Hm[ids[k]] = float(Us[k].multiply(pool.sum(axis=0)).sum() / (hi[k]-lo[k]))
print(f"[5] 镜像池完成  {time.time()-t_start:.1f}s")




# =====================================================================
# 6. 按时间顺序模拟主动池 + 用已知真值反向生成筹资时长
#    主动池由此前贷款的**实现端点**决定 → 同时性/内生性自然产生
#    交互项的中心化常数与截距通过三轮自校准确定（对齐真实样本的时长分布）
# =====================================================================
n = len(loans)
country_code  = pd.Categorical(loans["country_name"]).codes.astype(int)
activity_code = pd.Categorical(loans["activity"]).codes.astype(int)
week_idx = ((post_h - post_h.min()) // (24*7)).astype(int)
NW = week_idx.max() + 1
year_arr = loans["year"].values

fe_country  = rng.normal(0, 0.30, country_code.max()+1)
fe_activity = rng.normal(0, 0.20, activity_code.max()+1)
fe_week = (0.10*np.sin(2*np.pi*np.arange(NW)/52.0) + rng.normal(0, 0.08, NW))
# 行业-周冲击：分析端观察不到，week FE 吸收不了 —— 内生性引擎
shock = np.zeros((NS, NW))
for s in range(NS):
    e = rng.normal(0, 0.45, NW)
    for w in range(1, NW): e[w] = 0.55*e[w-1] + e[w]*np.sqrt(1-0.55**2)
    shock[s] = e

a = dict(TRUE)
partner_eff = np.array([partners[i]["effect"] for i in loans["partner_idx"]])
ctrl = (0.35*np.log(loans["loanAmount"].values/300.0)
        + 0.12*(loans["borrowerCount"].values > 1)
        + 0.10*(loans["gender"].values == "male")
        + 0.008*(loans["lenderRepaymentTerm"].values - 12)
        + 0.15*(loans["repaymentInterval"].values == "at_end"))

fixed_part = (ctrl + partner_eff + fe_country[country_code] + fe_activity[activity_code]
              + fe_week[week_idx] + shock[sector_code, week_idx])
lV_all = np.log1p(V_true)
Uarr = U.tocsr()
Udense = {i: None for i in ()}    # 占位；逐行取用
vocab = U.shape[1]

def simulate(base, cons, use_inter, seed):
    """按发布顺序模拟。use_inter=False 时关闭两个交互项（用于自校准第一轮）。"""
    r = np.random.default_rng(seed)
    eps = r.normal(0, CFG["SIGMA_EPS"], n)
    C = np.zeros(n); H = np.zeros(n); mu = np.zeros(n); hrs = np.zeros(n)
    st = np.empty(n, dtype=object)
    pool_sum = np.zeros((NS, vocab)); pool_cnt = np.zeros(NS, int); heap = []
    A3, A6 = (a["a3_CH"], a["a6_VG"]) if use_inter else (0.0, 0.0)
    for i in range(n):
        ti, s = post_h[i], sector_code[i]
        while heap and heap[0][0] <= ti:
            _, j, sj = heapq.heappop(heap)
            pool_sum[sj] -= Uarr[j].toarray()[0]; pool_cnt[sj] -= 1
        c = pool_cnt[s]
        h_ = float(Uarr[i].multiply(pool_sum[s].reshape(1,-1)).sum()/c) if c > 0 else 0.0
        C[i], H[i] = c, h_
        lc, lv = np.log1p(c), lV_all[i]
        y3 = 1.0 + a["a3_year_growth"]*(year_arr[i]-2016)
        y6 = 1.0 + a["a6_year_growth"]*(year_arr[i]-2016)
        m = (base + a["a1_C"]*lc + a["a2_H"]*h_
             + A3*y3*(lc-cons["c0"])*(h_-cons["h0"])
             + a["a4_V"]*lv + a["a5_G"]*G_true[i]
             + A6*y6*(lv-cons["v0"])*(G_true[i]-cons["g0"])
             + fixed_part[i])
        mu[i] = m
        hv = max(float(np.expm1(m + eps[i])), 0.05)
        if CFG["EXPIRE_ENABLED"] and hv > L_HOURS:
            hrs[i] = np.nan; st[i] = "unfunded"; end = ti + L_HOURS
        else:
            hrs[i] = hv; st[i] = "funded"; end = ti + hv
        pool_sum[s] += Uarr[i].toarray()[0]; pool_cnt[s] += 1
        heapq.heappush(heap, (end, i, s))
    return C, H, mu, hrs, st

# ---- 三轮自校准：中心化常数取实现均值，截距对齐目标中位数 ----
cons = dict(c0=1.0, h0=0.10, v0=3.0, g0=0.14)
base = 3.0
for it in range(3):
    C_t, H_t, mu_t, hrs_t, st_t = simulate(base, cons, use_inter=(it > 0), seed=CFG["SEED"]+it)
    cons = dict(c0=float(np.log1p(C_t).mean()), h0=float(H_t.mean()),
                v0=float(lV_all.mean()),       g0=float(G_true.mean()))
    med = np.nanmedian(hrs_t)
    base += float(np.log1p(CFG["TARGET_MEDIAN_HOURS"]) - np.log1p(med))
    print(f"    校准轮 {it}: 池均值={C_t.mean():.1f} H均值={H_t.mean():.3f} "
          f"中位时长={med:.1f}h 未募满={np.mean(st_t=='unfunded'):.1%} → base={base:.3f}")
C_true, H_true, mu_sys, hours, status = simulate(base, cons, use_inter=True, seed=CFG["SEED"]+99)
a.update({k: cons[k] for k in ("c0","h0","v0","g0")}); a["BASE"] = base
Npool = C_true.astype(int); print(f"[6] 序贯模拟完成  {time.time()-t_start:.1f}s")


# =====================================================================
# 7. 组装输出（字段 schema 与真实样本一致）+ 真值表
# =====================================================================
status = np.array(status, dtype=object)
rs = rng.random(n)
# 未募满的贷款：一部分终止状态明确（expired，终止日 = 上架 + 30 天），
# 一部分状态模糊（refunded，终止日不可重建）—— 用于检验镜像池兜底分支
status_out = np.where(status == "funded", "funded",
              np.where(rs < 1-CFG["TERMINAL_DATE_MISSING_RATE"], "expired", "refunded"))
raised = np.where(status == "funded", post_h + np.nan_to_num(hours), np.nan)

def iso(h):
    if not np.isfinite(h): return None
    return pd.Timestamp(h*3600, unit="s", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

records = []
for i in range(n):
    r = loans.iloc[i]
    records.append(dict(
        id=int(r["id"]), status=str(status_out[i]), borrowerCount=int(r["borrowerCount"]),
        name=r["name"], gender=r["gender"], loanAmount=float(r["loanAmount"]),
        lenderRepaymentTerm=int(r["lenderRepaymentTerm"]), repaymentInterval=r["repaymentInterval"],
        sector=r["sector"], activity=r["activity"], use=r["use"], city=r["city"],
        latitude=float(r["latitude"]), longitude=float(r["longitude"]),
        country_iso=r["country_iso"], country_name=r["country_name"], region=r["region"],
        country_ppp=float(r["country_ppp"]), fundsLentInCountry=int(r["fundsLentInCountry"]),
        country_latitude=int(r["country_latitude"]), country_longitude=int(r["country_longitude"]),
        description=r["description"], whySpecial=r["whySpecial"], image_url=r["image_url"],
        disbursalDate=pd.Timestamp(r["disbursalDate"]).strftime("%Y-%m-%dT%H:%M:%SZ"),
        fundraisingDate=iso(post_h[i]), raisedDate=iso(raised[i]),
    ))
pd.to_pickle(records, "kiva_sim_20k.pkl")
pd.DataFrame(records).to_csv("kiva_sim_20k.csv", index=False)

# ---- 真实标准化系数（分析端应当还原的基准）----
lC, lV = np.log1p(C_true), np.log1p(V_true)
mC, sC = lC.mean(), lC.std(); mH, sH = H_true.mean(), H_true.std()
mV, sV = lV.mean(), lV.std(); mG, sG = G_true.mean(), G_true.std()
ym3 = (1 + a["a3_year_growth"]*(year_arr-2016)).mean()
ym6 = (1 + a["a6_year_growth"]*(year_arr-2016)).mean()
A3, A6 = a["a3_CH"]*ym3, a["a6_VG"]*ym6
true_std = {
    "b1_C":  a["a1_C"]*sC + A3*(mH-a["h0"])*sC,
    "b2_H":  a["a2_H"]*sH + A3*(mC-a["c0"])*sH,
    "b3_CH": A3*sC*sH,
    "b4_V":  a["a4_V"]*sV + A6*(mG-a["g0"])*sV,
    "b5_G":  a["a5_G"]*sG + A6*(mV-a["v0"])*sG,
    "b6_VG": A6*sV*sG,
}
truth = pd.DataFrame(dict(
    id=[r["id"] for r in records],
    partner_id=[partners[i]["partner_id"] for i in loans["partner_idx"]],
    partner_effect=partner_eff,
    tmpl_intensity=[partners[i]["tmpl_intensity"] for i in loans["partner_idx"]],
    C_true=C_true, H_true=H_true, V_true=V_true, G_true=G_true,
    Npool=Npool, Nlag=Nlag, Cmirror=Cm, Hmirror=Hm,
    sector_week_shock=shock[sector_code, week_idx], mu_systematic=mu_sys,
    hours=hours, year=year_arr, week=week_idx, status_latent=status,
))
truth.to_csv("kiva_sim_truth.csv", index=False)

meta = dict(CFG=CFG, TRUE_RAW={k: (float(v) if isinstance(v,(int,float,np.floating)) else v)
                               for k,v in a.items()},
            TRUE_STANDARDISED={k: float(v) for k,v in true_std.items()},
            n=n, n_partners=N_PARTNERS, n_template_families=N_TEMPLATE_FAMILIES,
            pct_unfunded=float((status!="funded").mean()),
            median_hours=float(np.nanmedian(hours)), mean_hours=float(np.nanmean(hours)),
            mean_active_pool=float(C_true.mean()), p90_active_pool=float(np.percentile(C_true,90)),
            share_pool_ge10=float((C_true>=10).mean()),
            mean_H=float(H_true.mean()), sd_H=float(H_true.std()),
            mean_Nlag=float(Nlag.mean()), mean_mirror_pool=float(Cm.mean()))
json.dump(meta, open("kiva_sim_meta.json","w"), indent=2, ensure_ascii=False)
print(json.dumps({k:v for k,v in meta.items() if k!="CFG"}, indent=2, ensure_ascii=False))
print(f"[7] 全部完成  {time.time()-t_start:.1f}s")
