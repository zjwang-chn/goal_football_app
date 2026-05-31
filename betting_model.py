#!/usr/bin/env python3
"""
Football Betting Analysis Model (v2 — Asian handicap OU support)
===============================================================
Reusable command-line analysis engine for football betting.

Supports ALL Asian handicap types for Over/Under:
  - Integer (x.0): total>handicap=win, total=handicap=push, total<handicap=lose
  - Half   (x.5): total>handicap=win, total<handicap=lose
  - Quarter (x.25/x.75): split into two halves at +/-0.25, each half follows
    its own rule (integer or half). Results in full win/half win/half loss/full loss.

Usage:  python betting_model.py <data_file>  [--output <file>] [--pretty]
"""

import json, math, sys, os, argparse, re, openpyxl

# ============================================================
# HANDICAP TYPE DETECTION
# ============================================================

class HandicapType:
    INTEGER = "integer"
    HALF = "half"
    QUARTER = "quarter"

def detect_handicap_type(handicap):
    d = handicap - int(handicap)
    if abs(d) < 0.01 or abs(d - 1.0) < 0.01:
        return HandicapType.INTEGER
    elif abs(d - 0.5) < 0.01:
        return HandicapType.HALF
    else:
        return HandicapType.QUARTER

def describe_handicap(handicap):
    t = detect_handicap_type(handicap)
    if t == HandicapType.INTEGER:    return f"{handicap:.0f}球（整数盘）"
    if t == HandicapType.HALF:       return f"{handicap:.1f}球（半数盘）"
    return f"{handicap:.2f}球（四分之一盘 = {handicap-0.25:.1f}+{handicap+0.25:.1f}各半注）"

# ============================================================
# OVER/UNDER PAYOFF CALCULATION (correct Asian handicap rules)
# ============================================================

def compute_ou_payoff(handicap, total_goal_probs, odds, side="over"):
    """
    Compute exact EV and payout structure for an over/under bet.

    Returns dict with: handicap, handicap_type, side, odds,
      p_win, p_half_win, p_push, p_half_lose, p_lose, ev, detail
    """
    htype = detect_handicap_type(handicap)
    def p_total(cond): return sum(p for tg,p in total_goal_probs.items() if cond(tg))
    def p_exact(tg):   return total_goal_probs.get(tg, 0.0)

    res = {"handicap":handicap, "handicap_type":htype, "side":side, "odds":odds,
           "p_win":0.,"p_half_win":0.,"p_push":0.,"p_half_lose":0.,"p_lose":0.,"ev":0.,"detail":""}
    nw = odds-1.0; nhw = 0.5*nw; nhl = -0.5; nl = -1.0; npush = 0.0

    if htype == HandicapType.INTEGER:
        h = int(round(handicap))
        if side == "over":
            res["p_win"]  = p_total(lambda tg: tg > h)
            res["p_push"] = p_exact(h)
        else:
            res["p_win"]  = p_total(lambda tg: tg < h)
            res["p_push"] = p_exact(h)
        res["p_lose"] = 1.0 - res["p_win"] - res["p_push"]
        res["ev"] = nw*res["p_win"] + npush*res["p_push"] + nl*res["p_lose"]
        res["detail"] = f"整数盘 {h}球"

    elif htype == HandicapType.HALF:
        if side == "over":
            res["p_win"] = p_total(lambda tg: tg > handicap)
        else:
            res["p_win"] = p_total(lambda tg: tg < handicap)
        res["p_lose"] = 1.0 - res["p_win"]
        res["ev"] = nw*res["p_win"] + nl*res["p_lose"]
        res["detail"] = f"半数盘 {handicap:.1f}球"

    else:  # QUARTER
        lower = handicap - 0.25
        upper = handicap + 0.25
        ceil_u = int(math.ceil(upper))
        floor_l = int(math.floor(lower))

        if side == "over":
            # For over at x.25 (e.g. 2.25: lower=2.0[int], upper=2.5[half])
            #  Total >= ceil(upper) -> both halves win -> full win
            #  Total == floor(lower)(where lower is integer) -> lower push, upper lose -> half loss
            #  Total < floor(lower) -> both lose -> full loss
            res["p_win"]       = p_total(lambda tg: tg >= ceil_u)
            if detect_handicap_type(lower) == HandicapType.INTEGER:
                res["p_half_lose"] = p_exact(floor_l)      # e.g. 2.25: total=2
            else:
                res["p_half_win"]  = p_exact(ceil_u)       # e.g. 2.75: total=3
        else:  # under
            # For under at x.25 (e.g. 2.25: lower=2.0[int], upper=2.5[half])
            #  Total < lower (i.e. ≤ floor_l-1) -> both halves win -> full win
            #  Total == floor_l (where lower is integer) -> lower push, upper win -> half win
            #  Total >= ceil_u -> both lose -> full loss
            res["p_win"]       = p_total(lambda tg: tg < lower)
            if detect_handicap_type(lower) == HandicapType.INTEGER:
                res["p_half_win"]  = p_exact(floor_l)      # e.g. 2.25: total=2 -> half win
            else:
                res["p_half_lose"] = p_exact(ceil_u)       # e.g. 2.75: total=3 -> half loss

        res["p_lose"] = 1.0 - res["p_win"] - res["p_half_win"] - res["p_half_lose"]
        # Quarter balls have no pure push (the split handles it)
        res["ev"] = (nw*res["p_win"] + nhw*res["p_half_win"] +
                     nhl*res["p_half_lose"] + nl*res["p_lose"])
        res["detail"] = f"四分之一盘 {handicap:.2f}球（{lower:.1f}+{upper:.1f}各半注）"

    return res


# ============================================================
# DATA LOADING
# ============================================================

def load_all_data(filepath):
    wb = openpyxl.load_workbook(filepath)
    ws = wb["Sheet2"]

    # Score odds
    score_odds = {}
    for r in ws.iter_rows(min_row=2, max_row=27, min_col=1, max_col=2, values_only=True):
        s, od = r
        if s is not None and od is not None: score_odds[str(s).strip()] = float(od)

    # HT/FT odds
    htft_odds = {}
    for r in ws.iter_rows(min_row=2, max_row=10, min_col=4, max_col=5, values_only=True):
        lbl, od = r
        if lbl is not None and od is not None: htft_odds[str(lbl).strip()] = float(od)

    # FH 1X2
    fh_odds = {}
    for r in ws.iter_rows(min_row=2, max_row=4, min_col=7, max_col=8, values_only=True):
        lbl, od = r
        if lbl is not None and od is not None: fh_odds[str(lbl).strip()] = float(od)

    # FT 1X2
    ft_odds = {}
    for r in ws.iter_rows(min_row=2, max_row=4, min_col=10, max_col=11, values_only=True):
        lbl, od = r
        if lbl is not None and od is not None: ft_odds[str(lbl).strip()] = float(od)

    # Over/Under (M-N, rows 2-4)
    over_label  = ws.cell(row=2, column=13).value   # "大" or None
    over_odds   = ws.cell(row=2, column=14).value
    hcp_text    = ws.cell(row=3, column=13).value   # "分界 X.XX"
    under_label = ws.cell(row=4, column=13).value   # "小" or None
    under_odds  = ws.cell(row=4, column=14).value

    handicap = None
    if hcp_text:
        m = re.search(r'(\d+\.?\d*)', str(hcp_text))
        if m: handicap = float(m.group(1))

    ou_odds = {}
    if over_odds  is not None: ou_odds["大"] = float(over_odds)
    if under_odds is not None: ou_odds["小"] = float(under_odds)

    # Goal probability distribution (F-H, rows 18-23)
    home_probs, away_probs = {}, {}
    for r in ws.iter_rows(min_row=18, max_row=23, min_col=6, max_col=8, values_only=True):
        g, hp, ap = r
        if g is not None and hp is not None and ap is not None:
            home_probs[int(g)] = float(hp); away_probs[int(g)] = float(ap)

    wb.close()
    return {"score_odds":score_odds, "htft_odds":htft_odds, "fh_odds":fh_odds,
            "ft_odds":ft_odds, "ou_odds":ou_odds, "ou_handicap":handicap,
            "home_probs":home_probs, "away_probs":away_probs}


# ============================================================
# CORE MODEL
# ============================================================

def poisson_prob(lam, k):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return (lam**k) * math.exp(-lam) / math.factorial(k)

class BettingModel:
    FIRST_HALF_RATIO = 0.45
    SECOND_HALF_RATIO = 0.55

    def __init__(self, home_goal_probs, away_goal_probs, max_goals=6):
        self.max_goals = max_goals
        self.home_goal_probs = {int(k):float(v) for k,v in home_goal_probs.items()}
        self.away_goal_probs = {int(k):float(v) for k,v in away_goal_probs.items()}
        hs = sum(self.home_goal_probs.values())
        a_s = sum(self.away_goal_probs.values())
        assert abs(hs-1.0)<0.001, f"Home probs sum to {hs}"
        assert abs(a_s-1.0)<0.001, f"Away probs sum to {a_s}"
        self.lambda_home = sum(k*v for k,v in self.home_goal_probs.items())
        self.lambda_away = sum(k*v for k,v in self.away_goal_probs.items())
        self._compute_joint_matrix()
        self._compute_fulltime_outcomes()
        self._compute_firsthalf_outcomes()
        self._compute_total_goals()
        self._compute_htft_outcomes()

    def _compute_joint_matrix(self):
        self.joint_probs = {}
        for hi in range(self.max_goals):
            for aj in range(self.max_goals):
                self.joint_probs[f"{hi}-{aj}"] = (self.home_goal_probs.get(hi,0) *
                                                   self.away_goal_probs.get(aj,0))

    def get_joint_matrix(self):
        return {k:round(v,8) for k,v in self.joint_probs.items()}

    def _compute_fulltime_outcomes(self):
        self.home_win_prob = sum(self.joint_probs[f"{i}-{j}"] for i in range(self.max_goals) for j in range(self.max_goals) if i>j)
        self.draw_prob     = sum(self.joint_probs[f"{i}-{j}"] for i in range(self.max_goals) for j in range(self.max_goals) if i==j)
        self.away_win_prob = sum(self.joint_probs[f"{i}-{j}"] for i in range(self.max_goals) for j in range(self.max_goals) if i<j)

    def get_fulltime_probs(self):
        return {"home_win":round(self.home_win_prob,8),"draw":round(self.draw_prob,8),"away_win":round(self.away_win_prob,8)}

    def _compute_firsthalf_outcomes(self):
        lh = self.lambda_home*self.FIRST_HALF_RATIO; la = self.lambda_away*self.FIRST_HALF_RATIO
        hr = {i:poisson_prob(lh,i) for i in range(self.max_goals)}
        ar = {i:poisson_prob(la,i) for i in range(self.max_goals)}
        hs = sum(hr.values()); a_s = sum(ar.values())
        self.fh_home_probs = {k:v/hs for k,v in hr.items()}
        self.fh_away_probs = {k:v/a_s for k,v in ar.items()}
        self.fh_joint_probs = {}
        for hi in range(self.max_goals):
            for aj in range(self.max_goals):
                self.fh_joint_probs[f"{hi}-{aj}"] = self.fh_home_probs[hi]*self.fh_away_probs[aj]
        self.fh_home_win = sum(self.fh_joint_probs[f"{i}-{j}"] for i in range(self.max_goals) for j in range(self.max_goals) if i>j)
        self.fh_draw     = sum(self.fh_joint_probs[f"{i}-{j}"] for i in range(self.max_goals) for j in range(self.max_goals) if i==j)
        self.fh_away_win = sum(self.fh_joint_probs[f"{i}-{j}"] for i in range(self.max_goals) for j in range(self.max_goals) if i<j)

    def get_firsthalf_probs(self):
        return {"home_win":round(self.fh_home_win,8),"draw":round(self.fh_draw,8),"away_win":round(self.fh_away_win,8)}

    def _compute_total_goals(self):
        self.total_goal_probs = {}
        for hi in range(self.max_goals):
            for aj in range(self.max_goals):
                t = hi+aj
                self.total_goal_probs[t] = self.total_goal_probs.get(t,0) + self.joint_probs[f"{hi}-{aj}"]

    def get_total_goals(self):
        return {str(k):round(v,8) for k,v in sorted(self.total_goal_probs.items())}

    def _compute_htft_outcomes(self):
        lh = self.lambda_home*self.SECOND_HALF_RATIO; la = self.lambda_away*self.SECOND_HALF_RATIO
        hr = {i:poisson_prob(lh,i) for i in range(self.max_goals)}
        ar = {i:poisson_prob(la,i) for i in range(self.max_goals)}
        hs = sum(hr.values()); a_s = sum(ar.values())
        sh_h = {k:v/hs for k,v in hr.items()}; sh_a = {k:v/a_s for k,v in ar.items()}
        def oc(g,h):
            if g>h: return "H"
            if g==h: return "D"
            return "A"
        self.htft_probs = {}
        for fhh in range(self.max_goals):
            for fha in range(self.max_goals):
                ht = oc(fhh,fha); p_ht = self.fh_home_probs[fhh]*self.fh_away_probs[fha]
                for shh in range(self.max_goals):
                    for sha in range(self.max_goals):
                        ft = oc(fhh+shh,fha+sha); p_sh = sh_h[shh]*sh_a[sha]
                        k = f"{ht}/{ft}"; self.htft_probs[k] = self.htft_probs.get(k,0) + p_ht*p_sh
        t = sum(self.htft_probs.values())
        self.htft_probs = {k:v/t for k,v in self.htft_probs.items()}

    def get_htft_probs(self):
        return {k:round(v,8) for k,v in self.htft_probs.items()}

    def get_score_prob(self, s):
        p = s.split("-")
        if len(p)!=2: return 0.0
        try: hi,aj=int(p[0]),int(p[1])
        except: return 0.0
        if hi<self.max_goals and aj<self.max_goals: return self.joint_probs.get(s,0)
        return 0.0


# ============================================================
# EV & KELLY
# ============================================================

def calculate_ev(odds, probability):
    return odds*probability-1

def kelly_criterion(odds, probability):
    net = odds-1
    if net<=0 or probability<=0 or probability>=1: return 0.0
    return max(0.0, min((probability*net-(1-probability))/net, 0.25))


# ============================================================
# FULL PIPELINE
# ============================================================

def run_analysis(data_file):
    print(f"[1/2] Loading data from: {data_file}")
    data = load_all_data(data_file)
    home_probs, away_probs = data["home_probs"], data["away_probs"]
    print(f"    Home: {dict(sorted(home_probs.items()))}")
    print(f"    Away: {dict(sorted(away_probs.items()))}")
    hcp = data["ou_handicap"]
    print(f"    OU handicap: {hcp} ({describe_handicap(hcp) if hcp else 'N/A'})")

    print(f"[2/2] Running model...")
    model = BettingModel(home_probs, away_probs)

    # Fixed odds (from the file; could also be parsed dynamically)
    ft_odds_map = {"H":2.26,"D":3.1,"A":2.9}
    fh_odds_map = {"H":2.9,"D":2.0,"A":3.6}
    htft_odds_map = {"H/H":3.25,"H/D":14,"H/A":27,"D/H":5.4,"D/D":5,"D/A":6.6,"A/H":25,"A/D":15,"A/A":4.5}
    score_odds_map = data["score_odds"]
    ou_odds = data["ou_odds"]; over_odds=ou_odds.get("大"); under_odds=ou_odds.get("小")

    ft = model.get_fulltime_probs(); fh = model.get_firsthalf_probs(); htft = model.get_htft_probs()

    # Over/Under
    ou_res = {}
    if hcp and over_odds and under_odds:
        for sn, od in [("over",over_odds),("under",under_odds)]:
            p = compute_ou_payoff(hcp, model.total_goal_probs, od, sn)
            ou_res[sn] = p
            print(f"    OU {sn}: odds={od}, EV={p['ev']*100:+.2f}%  "
                  f"win={p['p_win']*100:.1f}% half_win={p['p_half_win']*100:.1f}% "
                  f"push={p['p_push']*100:.1f}% half_lose={p['p_half_lose']*100:.1f}% lose={p['p_lose']*100:.1f}%")

    # Assemble all bets
    all_bets = []
    ft_map = {"H":"home_win","D":"draw","A":"away_win"}
    for k,pk in ft_map.items():
        pv = ft[pk]; all_bets.append({"cat":"全场胜平负","bet":k,"odds":ft_odds_map[k],"prob":pv,"ev":calculate_ev(ft_odds_map[k],pv)})
    for k,pk in ft_map.items():
        pv = fh[pk]; all_bets.append({"cat":"上半场胜平负","bet":k,"odds":fh_odds_map[k],"prob":pv,"ev":calculate_ev(fh_odds_map[k],pv)})

    # OU
    lbl_o = f"大 {hcp}" if hcp else "Over"
    lbl_u = f"小 {hcp}" if hcp else "Under"
    if hcp and "over" in ou_res and "under" in ou_res:
        ro=ou_res["over"]; ru=ou_res["under"]
        all_bets.append({"cat":"大小球","bet":lbl_o,"odds":over_odds,"prob":ro["p_win"]+ro["p_half_win"],"pd":ro,"ev":ro["ev"]})
        all_bets.append({"cat":"大小球","bet":lbl_u,"odds":under_odds,"prob":ru["p_win"]+ru["p_half_win"],"pd":ru,"ev":ru["ev"]})

    htft_list = ["H/H","H/D","H/A","D/H","D/D","D/A","A/H","A/D","A/A"]
    for c in htft_list:
        pv = htft.get(c,0); all_bets.append({"cat":"半全场","bet":c,"odds":htft_odds_map[c],"prob":pv,"ev":calculate_ev(htft_odds_map[c],pv)})

    total_listed = sum(model.get_score_prob(s) for s in score_odds_map if s!="其他")
    rem = max(0.,1.-total_listed)
    for s,od in score_odds_map.items():
        pv = rem if s=="其他" else model.get_score_prob(s)
        all_bets.append({"cat":"精确比分","bet":s,"odds":od,"prob":pv,"ev":calculate_ev(od,pv)})

    # Rank
    sorted_bets = sorted(all_bets, key=lambda x:x["ev"], reverse=True)
    recs = []
    for rank,b in enumerate(sorted_bets,1):
        kf = kelly_criterion(b["odds"],b["prob"])
        r = {"rank":rank,"bet":b["bet"],"category":b["cat"],"odds":b["odds"],
             "theoretical_probability":round(b["prob"],8),"expected_value":round(b["ev"],8),
             "kelly_fraction":round(kf,8),"is_positive_ev":b["ev"]>0}
        if "pd" in b:
            r["handicap_payout"] = {k:round(v,6) if isinstance(v,float) else v for k,v in b["pd"].items()}
        recs.append(r)

    # OU metadata
    ou_meta = {}
    if hcp:
        ht = detect_handicap_type(hcp)
        ou_meta = {"handicap":hcp,"handicap_type":ht,"handicap_description":describe_handicap(hcp)}
        for s in ["over","under"]:
            if s in ou_res:
                rr = ou_res[s]
                ou_meta[s] = {"odds":rr["odds"],"p_win":round(rr["p_win"],6),
                              "p_half_win":round(rr["p_half_win"],6),"p_push":round(rr["p_push"],6),
                              "p_half_lose":round(rr["p_half_lose"],6),"p_lose":round(rr["p_lose"],6),
                              "ev":round(rr["ev"],6)}

    results = {
        "metadata":{
            "model_type":"Independent goal model (empirical distribution)",
            "expected_goals_home":round(model.lambda_home,4),
            "expected_goals_away":round(model.lambda_away,4),
            "expected_total_goals":round(model.lambda_home+model.lambda_away,4),
            "first_half_goal_ratio":model.FIRST_HALF_RATIO,
            "input_file":os.path.abspath(data_file),
            "over_under":ou_meta},
        "probability_distributions":{
            "home_goals":{str(k):round(v,8) for k,v in model.home_goal_probs.items()},
            "away_goals":{str(k):round(v,8) for k,v in model.away_goal_probs.items()},
            "joint_score_matrix":model.get_joint_matrix(),
            "total_goals":model.get_total_goals()},
        "match_outcomes":{
            "full_time":ft,"first_half":fh,"over_under":ou_meta,"htft":htft},
        "expected_values":{
            "full_time":{k:{"odds":ft_odds_map[k],"probability":ft[pk],"ev":round(calculate_ev(ft_odds_map[k],ft[pk]),8)} for k,pk in ft_map.items()},
            "first_half":{k:{"odds":fh_odds_map[k],"probability":fh[pk],"ev":round(calculate_ev(fh_odds_map[k],fh[pk]),8)} for k,pk in ft_map.items()},
            "over_under":ou_meta,
            "htft":{k:{"odds":htft_odds_map[k],"probability":htft.get(k,0),"ev":round(calculate_ev(htft_odds_map[k],htft.get(k,0)),8)} for k in htft_list},
            "exact_scores":{s:{"odds":od,"probability":round(rem if s=="其他" else model.get_score_prob(s),8),
                               "ev":round(calculate_ev(od,rem if s=="其他" else model.get_score_prob(s)),8)} for s,od in score_odds_map.items()}},
        "value_betting_recommendations":recs}
    return results


def main():
    parser = argparse.ArgumentParser(description="Football Betting Analysis Model v2")
    parser.add_argument("data_file", help="Path to odds Excel file (xlsx, Sheet2)")
    parser.add_argument("--output","-o",default="analysis_results.json")
    parser.add_argument("--pretty","-p",action="store_true")
    args = parser.parse_args()
    if not os.path.exists(args.data_file):
        print(f"ERROR: File not found: {args.data_file}",file=sys.stderr); sys.exit(1)
    results = run_analysis(args.data_file)
    with open(args.output,"w",encoding="utf-8") as f:
        json.dump(results,f,ensure_ascii=False,indent=(2 if args.pretty else None))
    pos = [r for r in results["value_betting_recommendations"] if r["is_positive_ev"]]
    print(f"\n{'='*60}\nComplete! -> {os.path.abspath(args.output)}")
    print(f"Options: {len(results['value_betting_recommendations'])} | +EV: {len(pos)}")
    print(f"Expected total goals: {results['metadata']['expected_total_goals']}")
    ou = results["metadata"].get("over_under",{})
    if ou:
        print(f"\nOver/Under: {ou.get('handicap_description','')}")
        for s in ["over","under"]:
            if s in ou:
                r=ou[s]; print(f"  {s}: odds={r['odds']}, EV={r['ev']*100:+.2f}%  "
                               f"win={r['p_win']*100:.1f}% hw={r['p_half_win']*100:.1f}% "
                               f"push={r['p_push']*100:.1f}% hl={r['p_half_lose']*100:.1f}% lose={r['p_lose']*100:.1f}%")
    if pos:
        print(f"\nTop Value Bets:")
        for r in pos[:5]:
            print(f"  #{r['rank']}: {r['bet']:>10} ({r['category']}) EV={r['expected_value']*100:+6.2f}%")
    print('='*60)

if __name__=="__main__":
    main()
