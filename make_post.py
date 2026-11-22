#!/usr/bin/env python3
"""12:01 / 16:30 post ပုံထုတ် (Auto generate တန်ဖိုး - ကျပန်းဂဏန်း ၃ လုံး + တွဲဂဏန်း)
usage: python3 make_post.py 12:01     |   python3 make_post.py 16:30 [--html-only]"""
import os, sys, random, subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import live                                   # holiday_reason(), MMT ကို ပြန်သုံး

# မြန်မာလို ရက်အမည်များ (Dynamic အတွက်)
myanmar_days = {
    0: "တနင်္လာနေ့",
    1: "အင်္ဂါနေ့",
    2: "ဗုဒ္ဓဟူးနေ့",
    3: "ကြာသပတေးနေ့",
    4: "သောကြာနေ့",
    5: "စနေနေ့",
    6: "တနင်္ဂနွေနေ့"
}

def generate():
    d1, d2, d3 = random.sample(range(10), 3)          # မတူတဲ့ ဂဏန်း ၃ လုံး (ကျပန်း)
    p1, p2 = f"{d1}{d2}", f"{d1}{d3}"                 # တွဲ: 53, 58
    p3 = p2[::-1]                                     # 58 ကို ပြောင်းပြန် -> 85
    return d1, d2, d3, p1, p2, p3

def main():
    slot = sys.argv[1] if len(sys.argv) > 1 else "12:01"
    shown = {"12:01": "12:01", "16:30": "4:30"}.get(slot, slot)
    day = datetime.now(live.MMT)
    
    # နေ့အမည်ကို dynamic ထုတ်ယူရန်
    weekday_name = myanmar_days.get(day.weekday(), "")

    reason = live.holiday_reason(day)
    if reason and "--force" not in sys.argv:
        print(f"{day:%d.%m.%Y} ပိတ်ရက် ({reason}) -> post မထုတ်ပါ"); return
    
    d1, d2, d3, p1, p2, p3 = generate()
    html = open(os.path.join(BASE, "post-template.html"), encoding="utf-8").read()
    
    for k, v in {
        "DATE": f"{day:%d.%m.%Y}", 
        "SLOT": shown, 
        "D1": d1, "D2": d2, "D3": d3,
        "P1": p1, "P2": p2, "P3": p3,
        "WEEKDAY": weekday_name
    }.items():
        html = html.replace("{{" + k + "}}", str(v))
        
    os.makedirs(os.path.join(BASE, "posts"), exist_ok=True)
    stem = os.path.join(BASE, "posts", f"{day:%Y-%m-%d}_{slot.replace(':', '')}")
    
    open(stem + ".html", "w", encoding="utf-8").write(html)
    with open(stem + ".txt", "w", encoding="utf-8") as f:
        f.write(f"{day:%d.%m.%Y} ({shown}) - {d1}.{d2}.{d3} | {p1}*{p2}.{p3}\n"
                "ဤဂဏန်းများသည် Auto generate လုပ်ထားသော တန်ဖိုးများသာ ဖြစ်ပါသည်။ "
                "ခန့်မှန်းချက် မဟုတ်ပါ၊ ထိုးရန် အကြံပြုခြင်း မဟုတ်ပါ။ ပညာပေး၊ ဖျော်ဖြေရေးအတွက်သာ။\n")
                
    print("values:", d1, d2, d3, p1, p2, p3, "weekday:", weekday_name)
    if "--html-only" in sys.argv:
        print("html:", stem + ".html"); return
        
    subprocess.run(["google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    "--window-size=1024,1024", f"--screenshot={stem}.png", "file://" + stem + ".html"], check=True)
    print("image:", stem + ".png")

if __name__ == "__main__":
    main()
