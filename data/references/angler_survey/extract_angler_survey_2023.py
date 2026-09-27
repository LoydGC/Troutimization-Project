import pdfplumber, re, pandas as pd
PDF='data/references/troutanglersurveyreport-2023.pdf'
pdf=pdfplumber.open(PDF)
NUM=re.compile(r'^(\d+(\.\d+)?|\*)$')

def parse_group(words, x_lo, x_hi, label_max, y_lo, y_hi, ncols, centers=None):
    ws=[w for w in words if x_lo<=w['x0']<x_hi and y_lo<=w['top']<y_hi]
    vals=[w for w in ws if w['x0']>=label_max and NUM.match(w['text'])]
    labs=[w for w in ws if w['x0']<label_max]
    # value rows
    rows={}
    for v in vals:
        k=next((r for r in rows if abs(r-v['top'])<3),None)
        if k is None: k=v['top']; rows[k]=[]
        rows[k].append(v)
    ys=sorted(rows)
    lab_by={y:[] for y in ys}
    for l in labs:
        y=min(ys,key=lambda r:abs(r-l['top']))
        lab_by[y].append(l)
    out=[]
    for y in ys:
        vs=sorted(rows[y],key=lambda w:w['x0'])
        if len(vs)!=ncols:
            if centers is None: raise ValueError(f'row at {y}: {len(vs)} vals {[w["text"] for w in vs]} {[w["text"] for w in lab_by[y]]}')
            cells=[None]*ncols
            for w in vs:
                c=(w['x0']+w['x1'])/2
                i=min(range(ncols),key=lambda j:abs(centers[j]-c)); cells[i]=w['text']
        else: cells=[w['text'] for w in vs]
        ls=sorted(lab_by[y],key=lambda w:(round(w['top']),w['x0']))
        label=' '.join(w['text'] for w in ls)
        out.append([label]+cells)
    return out

def words(p): return pdf.pages[p-1].extract_words(keep_blank_chars=False, use_text_flow=False)
def find(ws,text,after=0):
    return [w for w in ws if w['text']==text and w['top']>=after]

def regional(p, ncols):
    ws=words(p)
    nw=[w for w in ws if w['text']=='Northwest'][-1]
    hdr_top=nw['top']
    # header bottom: lowest header word within 25pt below Northwest line
    hw=[w for w in ws if abs(w['top']-hdr_top)<16 and (w['text'].startswith('(n=') or w['text'] in ('Resident','Overall','Resident)','Southeast','Northwest'))]
    hb=max(w['bottom'] for w in hw)
    ns=[w['text'] for w in ws if abs(w['top']-hdr_top)<16 and w['text'].startswith('(n=')]
    return parse_group(ws,0,9999,nw['x0']-8,hb-1.5,780,ncols), ns
import re, os
OUT='data/references/angler_survey_2023'
os.makedirs(OUT,exist_ok=True)
R7=['northwest','northcentral','northeast','southwest','southcentral','southeast','nonresident']
FOOT=re.compile(r'\s*\*\s*Less than 0\.5%\s*')
def num(v):
    if v in (None,'*'): return pd.NA
    return float(v) if '.' in v else int(v)
def lt(v): return v=='*'
def split_county(name):
    m=re.match(r'^(.*?)\s*\((.*)\)$',name)
    if not m: return name,pd.NA
    base,inner=m.groups()
    if inner.lower().startswith('other county'): return base,'other/unsure'
    return base, inner.replace(' County','')

# 1 overall preferred waters p76-77
rows=[]
for p in (76,77):
    ws=words(p)
    pct=sorted([w for w in ws if w['text']=='%'],key=lambda w:w['x0'])
    wb=sorted([w for w in ws if w['text']=='Waterbody'],key=lambda w:w['x0'])
    b=[w['x0']-2 for w in wb]+[9999]
    for g in range(3):
        for lab,v in parse_group(ws,b[g],b[g+1],pct[g]['x0']-3,wb[0]['bottom']+2,760,1):
            rows.append(dict(waterbody=FOOT.sub('',lab).strip(),pct_overall=num(v),lt_0_5_pct=lt(v),source_page=p))
t1=pd.DataFrame(rows); t1.insert(0,'rank_order',range(1,len(t1)+1))
nm=t1.waterbody.map(split_county); t1.insert(2,'name_base',[a for a,b in nm]); t1.insert(3,'county_qualifier',[b for a,b in nm])

# 2 regional preferred waters p78-83
rows=[]
for p in range(78,84):
    r,_=regional(p,8)
    for x in r:
        d=dict(waterbody=x[0]); d.update({c:num(v) for c,v in zip(R7+['overall'],x[1:])}); d['source_page']=p; rows.append(d)
t2=pd.DataFrame(rows)
nm=t2.waterbody.map(split_county); t2.insert(1,'name_base',[a for a,b in nm]); t2.insert(2,'county_qualifier',[b for a,b in nm])

# 3 county overall p84
ws=words(84)
cw=sorted([w for w in ws if w['text']=='County' and w['top']<240],key=lambda w:w['x0'])
wm=[w for w in ws if w['text']=='Westmoreland'][0]
b=[cw[0]['x0']-2,cw[1]['x0']-2,9999]; rows=[]
for g in range(2):
    for lab,v in parse_group(ws,b[g],b[g+1],b[g]+120,wm['top']-2,760,1):
        rows.append(dict(county=FOOT.sub('',lab).strip(),pct_overall=num(v),lt_0_5_pct=lt(v),source_page=84))
t3=pd.DataFrame(rows); t3.insert(0,'rank_order',range(1,len(t3)+1))

# 4 county by region p85
r,_=regional(85,8)
t4=pd.DataFrame([dict(county=x[0],**{c:num(v) for c,v in zip(R7+['overall'],x[1:])},source_page=85) for x in r])

# 5-9 7-column regional distributions + statewide from chart (manually read, verified against page image)
statewide={
 93:(2461,[4,3,3,1,2,1,2,6,4,13,24,37,2],{'Mean':(29.8,33.5),'Median':(15,16)}),
 94:(624,[10,12,10,4,3,2,6,9,5,12,12,12,5],{'Mean':(70.3,74.2),'Median':(50,50)}),
 115:(2460,[7,3,4,13,23,24,9,3,5,4,1,4],{'Mean':(None,20.6),'Median':(None,12)}),
 127:(2456,[12,3,6,9,17,48,5],{'Mean':(None,15.5),'Median':(None,5)}),
 174:(2461,[12,23,19,21,22,4],{}),
}
names={93:'travel_distance_typical_trip',94:'travel_distance_farthest',115:'days_fished_stocked_2022',
       127:'stocked_trout_harvest_per_year',174:'support_removing_low_use_waters'}
qs={93:'How far, in miles, do you travel, one-way, on an average stocked trout fishing trip in Pennsylvania?',
    94:"What's the farthest distance you travel to fish for stocked trout in Pennsylvania, one-way?",
    115:'How many days did you fish for stocked trout in Pennsylvania in 2022?',
    127:'On average, how many stocked trout do you harvest each year?',
    174:'Some stocked trout streams receive low angler use. Would you support or oppose removing these waters from the stocking program and moving the stocked trout allocation to other waters that receive higher angler use or creating new stocked trout waters that are likely to have higher angler use?'}
tabs={}
for p in statewide:
    r,ns=regional(p,7)
    n_all,sw,stats=statewide[p]
    rows=[dict(response='n (respondents)',row_type='n',**{c:int(re.sub(r'\D','',v)) for c,v in zip(R7,ns)},statewide_all=n_all,statewide_instate=pd.NA)]
    i=0
    for x in r:
        rt='mean' if x[0]=='Mean' else 'median' if x[0]=='Median' else 'percent'
        d=dict(response=x[0],row_type=rt,**{c:num(v) for c,v in zip(R7,x[1:])})
        if rt=='percent': d['statewide_all']=sw[i]; d['statewide_instate']=pd.NA; i+=1
        else: d['statewide_instate'],d['statewide_all']=stats[x[0]]
        rows.append(d)
    for k,(ins,al) in stats.items():
        if k not in [x[0] for x in r]:
            rows.append(dict(response=k,row_type=k.lower(),statewide_all=al,statewide_instate=ins))
    assert i==len(sw),(p,i,len(sw))
    t=pd.DataFrame(rows); t['question']=qs[p]; t['source_page']=p
    tabs[p]=t

# ---- validation
log=[]
for p,t in tabs.items():
    pc=t[t.row_type=='percent']
    for c in R7+['statewide_all']:
        s=pc[c].sum(); log.append(f'p{p} {c}: column sums to {s}' + ('  <-- CHECK' if not 97<=s<=103 else ''))
m=t2.merge(t1[['waterbody','pct_overall','lt_0_5_pct']],on='waterbody',how='outer',indicator=True)
log.append(f'regional table waters: {len(t2)}, overall table: {len(t1)}')
log.append('only in one table: '+str(m[m._merge!='both'][['waterbody','_merge']].values.tolist()))
bad=m[(m._merge=='both')&(~m.lt_0_5_pct.fillna(False).astype(bool))&(m.overall.astype('Float64')!=m.pct_overall.astype('Float64')).fillna(False)]
log.append(f'overall-column mismatches between p76-77 and p78-83: {len(bad)} {bad[["waterbody","overall","pct_overall"]].values.tolist()}')
m=t4.merge(t3,on='county',how='outer',indicator=True)
log.append('county tables only-in-one: '+str(m[m._merge!='both'].county.tolist()))
bad=m[(m._merge=='both')&(~m.lt_0_5_pct.astype(bool))&(m.overall.astype('Float64')!=m.pct_overall.astype('Float64')).fillna(False)]
log.append(f'county overall mismatches: {bad[["county","overall","pct_overall"]].values.tolist()}')
for c in R7+['overall']: log.append(f'p85 {c} sums to {t4[c].sum()}')
print('\n'.join(log))

t1.to_csv(f'{OUT}/p76-77_preferred_waters_overall.csv',index=False)
t2.to_csv(f'{OUT}/p78-83_preferred_waters_by_region.csv',index=False)
t3.to_csv(f'{OUT}/p84_preferred_water_county_overall.csv',index=False)
t4.to_csv(f'{OUT}/p85_preferred_water_county_by_region.csv',index=False)
for p,t in tabs.items(): t.to_csv(f'{OUT}/p{p}_{names[p]}_by_region.csv',index=False)
open(f'{OUT}/validation_log.txt','w').write('\n'.join(log))
