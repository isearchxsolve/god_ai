#!/usr/bin/env python3
"""
NIM Agent v2.0 — Safe, Colorful, Dynamic
- Token-bucket RPM enforcement (default 40, configurable)
- Dynamic profiles (any number, user-defined)
- Concurrency cap + jitter + Retry-After respect
- ANSI colors, emoji icons, box-drawing panels
"""

import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    import urllib.request


# Windows ANSI color support
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# Legacy cmd.exe (conhost) has two separate limitations that combine
# to make a Unicode/gradient UI unreadable: its font (raster
# "Terminal" font unless changed) often lacks glyphs for box-drawing
# characters, checkmarks, and emoji, and older builds render 24-bit
# truecolor SGR codes inconsistently. Windows Terminal, ConEmu, and
# every Unix terminal handle both fine. Detect the legacy case up
# front so every glyph/box-drawing constant below can fall back to
# plain ASCII rather than garbled tofu boxes — WT_SESSION is set by
# Windows Terminal, ANSICON/ConEmuANSI by those emulators; ordinary
# cmd.exe/powershell.exe set none of them.
LEGACY_WIN_CONSOLE = (
    sys.platform == "win32"
    and not os.environ.get("WT_SESSION")
    and not os.environ.get("ANSICON")
    and os.environ.get("ConEmuANSI") != "ON"
    and not os.environ.get("TERM_PROGRAM")
)

# ───────────────────────────────────────────
# ANSI COLORS
# ───────────────────────────────────────────
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    BLUE = "\033[34m"; MAGENTA = "\033[35m"; CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRED = "\033[91m"; BGREEN = "\033[92m"; BYELLOW = "\033[93m"
    BBLUE = "\033[94m"; BMAGENTA = "\033[95m"; BCYAN = "\033[96m"
    BWHITE = "\033[97m"
    BG_BLACK = "\033[40m"; BG_RED = "\033[41m"; BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"; BG_BLUE = "\033[44m"; BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"; BG_WHITE = "\033[47m"
    BG_BRED = "\033[101m"; BG_BGREEN = "\033[102m"; BG_BYELLOW = "\033[103m"
    BG_BBLUE = "\033[104m"; BG_BMAGENTA = "\033[105m"; BG_BCYAN = "\033[106m"
    BG_BWHITE = "\033[107m"
    ORANGE = "\033[38;5;208m"; GOLD = "\033[38;5;220m"; PINK = "\033[38;5;205m"
    LIME = "\033[38;5;118m"; TEAL = "\033[38;5;37m"; SALMON = "\033[38;5;203m"
    LAVENDER = "\033[38;5;141m"; SKY = "\033[38;5;75m"; CORAL = "\033[38;5;209m"
    MINT = "\033[38;5;121m"; ROSE = "\033[38;5;204m"; INDIGO = "\033[38;5;63m"
    AMBER = "\033[38;5;214m"; TURQ = "\033[38;5;45m"; CRIMSON = "\033[38;5;161m"

# ───────────────────────────────────────────
# BOX DRAWING + ICONS
# ───────────────────────────────────────────
if LEGACY_WIN_CONSOLE:
    H, V, TL, TR, BL, BR = "-", "|", "+", "+", "+", "+"
    ML, MR, TM, BM = "+", "+", "+", "+"
    DH, DV, DTL, DTR, DBL, DBR = "=", "|", "+", "+", "+", "+"
    ARROW = ">"
else:
    H, V, TL, TR, BL, BR = "─", "│", "┌", "┐", "└", "┘"
    ML, MR, TM, BM = "├", "┤", "┬", "┴"
    DH, DV, DTL, DTR, DBL, DBR = "═", "║", "╔", "╗", "╚", "╝"
    ARROW = "❯"

I = {
    "bot":"🤖","brain":"🧠","code":"💻","bug":"🐛","rocket":"🚀","check":"✅",
    "cross":"❌","warn":"⚠️","info":"ℹ️","sparkle":"✨","gear":"⚙️","file":"📄",
    "folder":"📁","search":"🔍","git":"🔀","test":"🧪","run":"▶️","save":"💾",
    "key":"🔑","star":"⭐","fire":"🔥","clock":"⏱️","target":"🎯","bulb":"💡",
    "lock":"🔒","chart":"📊","memo":"📝","hand":"👉","wave":"👋","crown":"👑",
    "diamond":"💎","zap":"⚡","heart":"❤️","link":"🔗","pin":"📌","tag":"🏷️",
    "bell":"🔔","mag":"🔎","pkg":"📦","send":"📤","recv":"📥","shuffle":"🔀",
    "branch":"🌿","commit":"📌","push":"🚀","pull":"⬇️","diff":"📑","status":"📋",
    "add":"➕","rem":"➖","edit":"✏️","new":"🆕","done":"🏁","wait":"⏳",
    "stop":"🛑","play":"▶️","pause":"⏸️","refresh":"🔄","sync":"🔄","wifi":"📶",
    "battery":"🔋","tools":"🛠️","hammer":"🔨","wrench":"🔧","paint":"🎨",
    "palette":"🎨","music":"🎵","mic":"🎤","camera":"📷","video":"🎬",
    "game":"🎮","trophy":"🏆","medal":"🏅","ribbon":"🎗️","gift":"🎁",
    "party":"🎉","balloon":"🎈","cake":"🎂","coffee":"☕","tea":"🍵",
    "beer":"🍺","wine":"🍷","food":"🍔","apple":"🍎","banana":"🍌",
    "grape":"🍇","melon":"🍉","berry":"🍓","peach":"🍑","cherry":"🍒",
    "lemon":"🍋","pine":"🍍","mango":"🥭","coco":"🥥","kiwi":"🥝",
    "tomato":"🍅","eggplant":"🍆","avo":"🥑","broccoli":"🥦","carrot":"🥕",
    "corn":"🌽","pepper":"🌶️","cuke":"🥒","shroom":"🍄","onion":"🧅",
    "garlic":"🧄","potato":"🥔","yam":"🍠","bread":"🍞","croissant":"🥐",
    "baguette":"🥖","pretzel":"🥨","cheese":"🧀","egg":"🥚","bacon":"🥓",
    "pancake":"🥞","waffle":"🧇","meat":"🥩","chicken":"🍗","bone":"🍖",
    "hotdog":"🌭","pizza":"🍕","taco":"🌮","burrito":"🌯","sandwich":"🥪",
    "falafel":"🧆","dumpling":"🥟","fortune":"🥠","takeout":"🥡",
    "icecream":"🍨","shaved":"🍧","donut":"🍩","cookie":"🍪","choc":"🍫",
    "candy":"🍬","lollipop":"🍭","custard":"🍮","honey":"🍯","bottle":"🍼",
    "milk":"🥛","sake":"🍶","champagne":"🍾","cocktail":"🍸","tropical":"🍹",
    "mug":"🍺","clink":"🥂","tumbler":"🥃","cup":"🥤","bubble":"🧋",
    "juice":"🧃","mate":"🧉","ice":"🧊","sticks":"🥢","plate":"🍽️",
    "cutlery":"🍴","spoon":"🥄","knife":"🔪","amphora":"🏺","earth":"🌍",
    "americas":"🌎","asia":"🌏","globe":"🌐","map":"🗺️","compass":"🧭",
    "mountain":"⛰️","volcano":"🌋","fuji":"🗻","camp":"🏕️","beach":"🏖️",
    "desert":"🏜️","island":"🏝️","park":"🏞️","stadium":"🏟️","classical":"🏛️",
    "construct":"🏗️","house":"🏠","home":"🏡","office":"🏢","post":"🏣",
    "hospital":"🏥","bank":"🏦","hotel":"🏨","store":"🏪","school":"🏫",
    "dept":"🏬","factory":"🏭","jcastle":"🏯","castle":"🏰","wedding":"💒",
    "tokyo":"🗼","liberty":"🗽","church":"⛪","mosque":"🕌","htemple":"🛕",
    "synagogue":"🕍","shinto":"⛩️","kaaba":"🕋","fountain":"⛲","tent":"⛺",
    "foggy":"🌁","night":"🌃","city":"🏙️","sunrise":"🌅","dawn":"🌄",
    "rainbow":"🌈","bridge":"🌉","carousel":"🎠","ferris":"🎡","coaster":"🎢",
    "barber":"💈","circus":"🎪","loco":"🚂","railcar":"🚃","bullet":"🚅",
    "train":"🚆","metro":"🚇","light":"🚈","station":"🚉","tram":"🚊",
    "mono":"🚝","mrail":"🚞","tcar":"🚋","bus":"🚌","obus":"🚍","trolley":"🚎",
    "mini":"🚐","ambulance":"🚑","firetruck":"🚒","police":"🚓","opolice":"🚔",
    "taxi":"🚕","otaxi":"🚖","car":"🚗","ocar":"🚘","suv":"🚙","pickup":"🛻",
    "truck":"🚚","semi":"🚛","tractor":"🚜","race":"🏎️","moto":"🏍️",
    "scooter":"🛵","mwc":"🦽","ewc":"🦼","rickshaw":"🛺","bike":"🚲",
    "kick":"🛴","skate":"🛹","rskate":"🛼","bstop":"🚏","hwy":"🛣️",
    "track":"🛤️","drum":"🛢️","gas":"⛽","siren":"🚨","htlight":"🚥",
    "vtlight":"🚦","stopsign":"🛑","caution":"🚧","anchor":"⚓","sail":"⛵",
    "canoe":"🛶","speed":"🚤","pship":"🛳️","ferry":"⛴️","mboat":"🛥️",
    "ship":"🚢","plane":"✈️","splane":"🛩️","depart":"🛫","arrive":"🛬",
    "chute":"🪂","seat":"💺","heli":"🚁","srail":"🚟","mcable":"🚠",
    "atram":"🚡","sat":"🛰️","rship":"🚀","ufo":"🛸","bellhop":"🛎️",
    "luggage":"🧳","hourglass":"⌛","hglass2":"⏳","watch":"⌚","alarm":"⏰",
    "swatch":"⏱️","timer":"⏲️","mclock":"🕰️","moon":"🌑","wcrescent":"🌒",
    "fq":"🌓","wgibbous":"🌔","fmoon":"🌕","ngibbous":"🌖","lq":"🌗",
    "ncrescent":"🌘","cmoon":"🌙","nmface":"🌚","fqface":"🌛","lqface":"🌜",
    "thermo":"🌡️","sun":"☀️","fmface":"🌝","sface":"🌞","planet":"🪐",
    "star2":"⭐","gstar":"🌟","shooting":"🌠","milky":"🌌","cloud":"☁️",
    "scloud":"⛅","lightning":"🌩️","tornado":"🌪️","fog2":"🌫️","wind":"🌬️",
    "cyclone":"🌀","rainbow2":"🌈","cumbrella":"🌂","umbrella":"☂️","r umbrella":"☔",
    "ground":"⛱️","volt":"⚡","snowflake":"❄️","snowman":"☃️","nsnow":"⛄",
    "comet":"☄️","fire2":"🔥","drop":"💧","wave2":"🌊","pumpkin":"🎃",
    "xmas":"🎄","fireworks":"🎆","sparkler":"🎇","sparkles":"✨","balloon2":"🎈",
    "popper":"🎉","confetti":"🎊","tanabata":"🎋","pine":"🎍","dolls":"🎎",
    "carp":"🎏","chime":"🎐","viewing":"🎑","envelope":"🧧","ribbon2":"🎀",
    "gift2":"🎁","rribbon":"🎗️","tickets":"🎟️","ticket":"🎫","medal2":"🎖️",
    "trophy2":"🏆","smedal":"🏅","gold":"🥇","silver":"🥈","bronze":"🥉",
    "soccer":"⚽","baseball":"⚾","softball":"🥎","basketball":"🏀","volleyball":"🏐",
    "football":"🏈","rugby":"🏉","tennis":"🎾","disc":"🥏","bowling":"🎳",
    "cricket":"🏏","fhockey":"🏑","ihockey":"🏒","lacrosse":"🥍","pingpong":"🏓",
    "badminton":"🏸","boxing":"🥊","martial":"🥋","gnet":"🥅","golf":"⛳",
    "iskate":"⛸️","fish":"🎣","dive":"🤿","rshirt":"🎽","skis":"🎿",
    "sled":"🛷","curling":"🥌","dart":"🎯","yoyo":"🪀","kite":"🪁",
    "gun":"🔫","pool":"🎱","crystal":"🔮","wand":"🪄","nazar":"🧿",
    "vgame":"🎮","joystick":"🕹️","slots":"🎰","die":"🎲","puzzle":"🧩",
    "bear":"🧸","pinata":"🪅","dolls2":"🪆","spade":"♠️","heart":"♥️",
    "diamond":"♦️","club":"♣️","pawn":"♟️","joker":"🃏","mahjong":"🀄",
    "cards":"🎴","arts":"🎭","frame":"🖼️","art2":"🎨","thread":"🧵",
    "needle":"🪡","yarn":"🧶","knot":"🪢","glasses":"👓","shades":"🕶️",
    "goggles":"🥽","labcoat":"🥼","vest":"🦺","tie":"👔","shirt":"👕",
    "jeans":"👖","scarf":"🧣","gloves":"🧤","coat":"🧥","socks":"🧦",
    "dress":"👗","kimono":"👘","sari":"🥻","swimsuit":"🩱","briefs":"🩲",
    "shorts":"🩳","bikini":"👙","blouse":"👚","purse":"👛","handbag":"👜",
    "clutch":"👝","bags":"🛍️","backpack":"🎒","sandal":"🩴","shoe":"👞",
    "sneaker":"👟","boot":"🥾","flat":"🥿","heel":"👠","wsandal":"👡",
    "ballet":"🩰","wboot":"👢","crown2":"👑","what":"👒","tophat":"🎩",
    "grad":"🎓","cap":"🧢","helmet":"🪖","rescue":"⛑️","beads":"📿",
    "lipstick":"💄","ring2":"💍","gem":"💎","mute":"🔇","low":"🔈",
    "med":"🔉","high":"🔊","loud":"📢","mega":"📣","horn":"📯",
    "bell2":"🔔","nbell":"🔕","score":"🎼","note":"🎵","notes":"🎶",
    "smic":"🎙️","slider":"🎚️","knobs":"🎛️","microphone":"🎤","headphones":"🎧",
    "radio":"📻","sax":"🎷","accordion":"🪗","guitar":"🎸","keyboard":"🎹",
    "trumpet":"🎺","violin":"🎻","banjo":"🪕","drum2":"🥁","ldrum":"🪘",
    "phone":"📱","phone2":"📲","telephone":"☎️","receiver":"📞","pager":"📟",
    "fax":"📠","battery2":"🔋","plug":"🔌","laptop":"💻","desktop":"🖥️",
    "printer":"🖨️","kboard":"⌨️","mouse":"🖱️","trackball":"🖲️","disk":"💽",
    "floppy":"💾","cd":"💿","dvd":"📀","abacus":"🧮","mcam":"🎥","fframes":"🎞️",
    "proj":"📽️","clapper":"🎬","tv":"📺","cam":"📷","flash":"📸","vcam":"📹",
    "vhs":"📼","mgl":"🔍","mgr":"🔎","candle":"🕯️","bulb":"💡","flashlight":"🔦",
    "lantern":"🏮","diya":"🪔","nb":"📔","cb":"📕","ob":"📖","gb":"📗",
    "bb":"📘","ob2":"📙","books":"📚","notebook":"📓","ledger":"📒",
    "page":"📃","scroll":"📜","page2":"📄","newspaper":"📰","rnews":"🗞️",
    "btabs":"📑","bookmark":"🔖","label":"🏷️","money":"💰","coin":"🪙",
    "yen":"💴","dollar":"💵","euro":"💶","pound":"💷","wings":"💸",
    "ccard":"💳","receipt":"🧾","upchart":"📈","downchart":"📉","bchart":"📊",
    "clipboard":"📋","pushpin":"📌","rpin":"📍","clip":"📎","lclip":"🖇️",
    "ruler":"📏","truler":"📐","scissors":"✂️","cbox":"🗃️","cabinet":"🗄️",
    "trash":"🗑️","locked":"🔒","unlocked":"🔓","lpen":"🔏","lkey":"🔐",
    "key2":"🔑","okey":"🗝️","hammer2":"🔨","axe":"🪓","pick":"⛏️",
    "hpick":"⚒️","hw":"🛠️","dagger":"🗡️","swords":"⚔️","gun2":"🔫",
    "boomerang":"🪃","bow":"🏹","shield":"🛡️","saw":"🪚","wrench2":"🔧",
    "sdriver":"🪛","nut":"🔩","gear2":"⚙️","clamp":"🗜️","scale":"⚖️",
    "cane":"🦯","link2":"🔗","chains":"⛓️","hook":"🪝","tbox":"🧰",
    "magnet":"🧲","ladder":"🪜","alembic":"⚗️","tube":"🧪","petri":"🧫",
    "dna":"🧬","scope":"🔬","telescope":"🔭","antenna":"📡","syringe":"💉",
    "blood":"🩸","pill":"💊","bandage":"🩹","steth":"🩺","door":"🚪",
    "elevator":"🛗","mirror":"🪞","window":"🪟","bed":"🛏️","couch":"🛋️",
    "chair":"🪑","toilet":"🚽","plunger":"🪠","shower":"🚿","tub":"🛁",
    "trap":"🪤","razor":"🪒","lotion":"🧴","spill":"🧷","broom":"🧹",
    "basket2":"🧺","tpaper":"🧻","bucket":"🪣","soap":"🧼","brush":"🪥",
    "sponge":"🧽","extinguisher":"🧯","cart":"🛒","cig":"🚬","coffin":"⚰️",
    "tomb":"🪦","urn":"⚱️","moai":"🗿","placard":"🪧","idcard":"🪪",
    "atm":"🏧","litter":"🚮","water":"🚰","wc":"♿","men":"🚹","women":"🚺",
    "restroom":"🚻","baby":"🚼","wc2":"🚾","passport":"🛂","customs":"🛃",
    "baggage":"🛄","left":"🛅","warning":"⚠️","kids":"🚸","noentry":"⛔",
    "prohibited":"🚫","nobike":"🚳","nosmoke":"🚭","nolitter":"🚯",
    "nowater":"🚱","noped":"🚷","nophone":"📵","no18":"🔞","radioactive":"☢️",
    "bio":"☣️","up":"⬆️","upr":"↗️","right":"➡️","dnr":"↘️","down":"⬇️",
    "dnl":"↙️","left":"⬅️","upl":"↖️","ud":"↕️","lr":"↔️","rl":"↩️",
    "lr2":"↪️","ru":"⤴️","rd":"⤵️","cw":"🔃","ccw":"🔄","back":"🔙",
    "end":"🔚","on":"🔛","soon":"🔜","top":"🔝","worship":"🛐","atom":"⚛️",
    "om":"🕉️","david":"✡️","dharma":"☸️","yin":"☯️","cross":"✝️",
    "orthodox":"☦️","crescent":"☪️","peace":"☮️","menorah":"🕎","dstar":"🔯",
    "aries":"♈","taurus":"♉","gemini":"♊","cancer":"♋","leo":"♌",
    "virgo":"♍","libra":"♎","scorpio":"♏","sag":"♐","cap":"♑",
    "aqua":"♒","pisces":"♓","oph":"⛎","shuffle2":"🔀","repeat":"🔁",
    "repeat1":"🔂","play2":"▶️","ff":"⏩","next":"⏭️","pp":"⏯️","rev":"◀️",
    "fr":"⏪","prev":"⏮️","upbtn":"🔼","fu":"⏫","dnbtn":"🔽","fd":"⏬",
    "pause2":"⏸️","stop2":"⏹️","rec":"⏺️","eject":"⏏️","cinema":"🎦",
    "dim":"🔅","bright":"🔆","bars":"📶","vibrate":"📳","off":"📴",
    "female":"♀️","male":"♂️","trans":"⚧️","times":"✖️","plus":"➕",
    "minus":"➖","div":"➗","equals":"🟰","inf":"♾️","bangbang":"‼️",
    "qbang":"⁉️","qred":"❓","qwhite":"❔","bwhite":"❕","bred":"❗",
    "dash":"〰️","exchange":"💱","dsign":"💲","medical":"⚕️","recycle":"♻️",
    "fleur":"⚜️","trident":"🔱","badge":"📛","jsym":"🔰","circle":"⭕",
    "cbtn":"✅","cbox2":"☑️","check2":"✔️","x":"❌","xbtn":"❎","loop":"➰",
    "loop2":"➿","part":"〽️","asterisk":"✳️","star3":"✴️","sparkle3":"❇️",
    "copy":"©️","reg":"®️","tm":"™️","khash":"#️⃣","kstar":"*️⃣",
    "k0":"0️⃣","k1":"1️⃣","k2":"2️⃣","k3":"3️⃣","k4":"4️⃣","k5":"5️⃣",
    "k6":"6️⃣","k7":"7️⃣","k8":"8️⃣","k9":"9️⃣","k10":"🔟","upcase":"🔠",
    "lowcase":"🔡","nums":"🔢","syms":"🔣","letters":"🔤","a":"🅰️",
    "ab":"🆎","b":"🅱️","cl":"🆑","cool":"🆒","free":"🆓","id":"🆔",
    "m":"Ⓜ️","new":"🆕","ng":"🆖","o":"🅾️","ok":"🆗","p":"🅿️",
    "sos":"🆘","up2":"🆙","vs":"🆚","here":"🈁","charge":"🈂️",
    "month":"🈷️","notfree":"🈶","reserved":"🈯","bargain":"🉐",
    "discount":"🈹","free2":"🈚","forbidden":"🈲","acceptable":"🉑",
    "apply":"🈸","pass":"🈴","vacancy":"🈳","congrats":"㊗️","secret":"㊙️",
    "open":"🈺","novacancy":"🈵","rc":"🔴","oc":"🟠","yc":"🟡","gc":"🟢",
    "bc":"🔵","pc":"🟣","brc":"🟤","blc":"⚫","wc2":"⚪","rs":"🟥",
    "os":"🟧","ys":"🟨","gs":"🟩","bs":"🟦","ps":"🟪","brs":"🟫",
    "bls":"⬛","wls":"⬜","bms":"◼️","wms":"◻️","bmss":"◾","wmss":"◽",
    "bss":"▪️","wss":"▫️","lod":"🔶","lbd":"🔷","sod":"🔸","sbd":"🔹",
    "rtri":"🔺","rdtri":"🔻","ddot":"💠","radio":"🔘","wsb":"🔳",
    "bsb":"🔲","tree":"🌳","leaf":"🍃","fall":"🍂","seed":"🌱",
    "evergreen":"🌲","palm":"🌴","cactus":"🌵","sheaf":"🌾","herb":"🌿",
    "shamrock":"☘️","clover":"🍀","maple":"🍁","feather":"🪶","shell":"🐚",
    "coral2":"🪸","snail":"🐌","butterfly":"🦋","bug2":"🐛","ant":"🐜",
    "bee":"🐝","beetle":"🪲","ladybug":"🐞","cricket2":"🦗","cockroach":"🪳",
    "spider":"🕷️","web":"🕸️","scorpion":"🦂","mosquito":"🦟","fly":"🪰",
    "worm":"🪱","microbe":"🦠","turtle":"🐢","lizard":"🦎","snake":"🐍",
    "dragon":"🐉","croc":"🐊","saur":"🦕","trex":"🦖","whale":"🐋",
    "whale2":"🐳","dolphin":"🐬","seal":"🦭","fish2":"🐟","fish3":"🐠",
    "fish4":"🐡","shark":"🦈","octopus":"🐙","shell2":"🐚","crab":"🦀",
    "lobster":"🦞","shrimp":"🦐","squid":"🦑","oyster":"🦪","snail2":"🐌",
    "butterfly2":"🦋","bug3":"🐛","ant2":"🐜","bee2":"🐝","beetle2":"🪲",
    "ladybug2":"🐞","cricket3":"🦗","cockroach2":"🪳","spider2":"🕷️",
    "web2":"🕸️","scorpion2":"🦂","mosquito2":"🦟","fly2":"🪰","worm2":"🪱",
    "microbe2":"🦠","turtle2":"🐢","lizard2":"🦎","snake2":"🐍","dragon2":"🐉",
    "croc2":"🐊","saur2":"🦕","trex2":"🦖","whale3":"🐋","whale4":"🐳",
    "dolphin2":"🐬","seal2":"🦭","fish5":"🐟","fish6":"🐠","fish7":"🐡",
    "shark2":"🦈","octopus2":"🐙","shell3":"🐚","crab2":"🦀","lobster2":"🦞",
    "shrimp2":"🦐","squid2":"🦑","oyster2":"🦪","dog":"🐕","dog2":"🐩",
    "guide":"🦮","service":"🐕‍🦺","poodle":"🐩","wolf":"🐺","fox":"🦊",
    "raccoon":"🦝","cat":"🐈","cat2":"🐈‍⬛","lion":"🦁","tiger":"🐯",
    "leopard":"🐆","horse":"🐴","racehorse":"🐎","unicorn":"🦄","zebra":"🦓",
    "deer":"🦌","bison":"🦬","cow":"🐮","ox":"🐂","waterbuff":"🐃",
    "cow2":"🐄","pig":"🐷","pig2":"🐖","boar":"🐗","pig nose":"🐽",
    "ram":"🐏","sheep":"🐑","goat":"🐐","camel":"🐪","camel2":"🐫",
    "llama":"🦙","giraffe":"🦒","elephant":"🐘","mammoth":"🦣","rhino":"🦏",
    "hippo":"🦛","mouse2":"🐁","rat":"🐀","hamster":"🐹","rabbit":"🐰",
    "rabbit2":"🐇","chipmunk":"🐿️","beaver":"🦫","hedgehog":"🦔","bat":"🦇",
    "bear":"🐻","polarbear":"🐻‍❄️","koala":"🐨","panda":"🐼","sloth":"🦥",
    "otter":"🦦","skunk":"🦨","kangaroo":"🦘","badger":"🦡","paw":"🐾",
    "turkey":"🦃","chicken2":"🐔","rooster":"🐓","hatch":"🐣","babychick":"🐤",
    "chick":"🐥","bird":"🐦","penguin":"🐧","dove":"🕊️","eagle":"🦅",
    "duck":"🦆","swan":"🦢","owl":"🦉","dodo":"🦤","feather2":"🪶",
    "flamingo":"🦩","peacock":"🦚","parrot":"🦜","frog":"🐸","croc3":"🐊",
    "turtle3":"🐢","lizard3":"🦎","snake3":"🐍","dragon3":"🐉","saur3":"🦕",
    "trex3":"🦖","whale5":"🐋","whale6":"🐳","dolphin3":"🐬","seal3":"🦭",
    "fish8":"🐟","fish9":"🐠","fish10":"🐡","shark3":"🦈","octopus3":"🐙",
    "crab3":"🦀","lobster3":"🦞","shrimp3":"🦐","squid3":"🦑","snail3":"🐌",
    "butterfly3":"🦋","bug4":"🐛","ant3":"🐜","bee3":"🐝","beetle3":"🪲",
    "ladybug3":"🐞","cricket4":"🦗","cockroach3":"🪳","spider3":"🕷️",
    "web3":"🕸️","scorpion3":"🦂","mosquito3":"🦟","fly3":"🪰","worm3":"🪱",
    "microbe3":"🦠","dog3":"🐕","dog4":"🐩","guide2":"🦮","service2":"🐕‍🦺",
    "poodle2":"🐩","wolf2":"🐺","fox2":"🦊","raccoon2":"🦝","cat3":"🐈",
    "cat4":"🐈‍⬛","lion2":"🦁","tiger2":"🐯","leopard2":"🐆","horse2":"🐴",
    "racehorse2":"🐎","unicorn2":"🦄","zebra2":"🦓","deer2":"🦌","bison2":"🦬",
    "cow3":"🐮","ox2":"🐂","waterbuff2":"🐃","cow4":"🐄","pig3":"🐷",
    "pig4":"🐖","boar2":"🐗","ram2":"🐏","sheep2":"🐑","goat2":"🐐",
    "camel3":"🐪","camel4":"🐫","llama2":"🦙","giraffe2":"🦒","elephant2":"🐘",
    "mammoth2":"🦣","rhino2":"🦏","hippo2":"🦛","mouse3":"🐁","rat2":"🐀",
    "hamster2":"🐹","rabbit3":"🐰","rabbit4":"🐇","chipmunk2":"🐿️",
    "beaver2":"🦫","hedgehog2":"🦔","bat2":"🦇","bear2":"🐻","polarbear2":"🐻‍❄️",
    "koala2":"🐨","panda2":"🐼","sloth2":"🦥","otter2":"🦦","skunk2":"🦨",
    "kangaroo2":"🦘","badger2":"🦡","paw2":"🐾","turkey2":"🦃","chicken3":"🐔",
    "rooster2":"🐓","hatch2":"🐣","babychick2":"🐤","chick2":"🐥","bird2":"🐦",
    "penguin2":"🐧","dove2":"🕊️","eagle2":"🦅","duck2":"🦆","swan2":"🦢",
    "owl2":"🦉","dodo2":"🦤","flamingo2":"🦩","peacock2":"🦚","parrot2":"🦜",
    "frog2":"🐸","monkey":"🐒","gorilla":"🦍","orangutan":"🦧","dogface":"🐶",
    "catface":"🐱","mouseface":"🐭","hamsterface":"🐹","rabbitface":"🐰",
    "foxface":"🦊","bearface":"🐻","pandaface":"🐼","koalaface":"🐨",
    "tigerface":"🐯","lionface":"🦁","cowface":"🐮","pigface":"🐷",
    "frogface":"🐸","monkeyface":"🐵","see":"🙈","hear":"🙉","speak":"🙊",
    "monkey2":"🐒","gorilla2":"🦍","orangutan2":"🦧","dogface2":"🐶",
    "catface2":"🐱","mouseface2":"🐭","hamsterface2":"🐹","rabbitface2":"🐰",
    "foxface2":"🦊","bearface2":"🐻","pandaface2":"🐼","koalaface2":"🐨",
    "tigerface2":"🐯","lionface2":"🦁","cowface2":"🐮","pigface2":"🐷",
    "frogface2":"🐸","monkeyface2":"🐵","see2":"🙈","hear2":"🙉","speak2":"🙊",
}

if LEGACY_WIN_CONSOLE:
    # Legacy conhost renders emoji as tofu boxes regardless of code
    # page. Swap the keys actually used in live UI output (persona
    # icons, thinking/response markers, tool banners, git/run status)
    # for plain ASCII so the interface degrades cleanly instead of
    # looking broken. The rest of the (mostly decorative/unused) icon
    # dict is left as-is since it never reaches the screen.
    I.update({
        "bot":"[bot]","brain":"[think]","code":"[code]","bug":"[bug]","rocket":"[*]",
        "check":"[OK]","cross":"[ERR]","warn":"[!]","info":"[i]","sparkle":"*",
        "gear":"[cfg]","file":"[file]","folder":"[dir]","search":"[find]","git":"[git]",
        "test":"[test]","run":"[run]","save":"[save]","key":"[key]","star":"*",
        "fire":"[!]","clock":"[time]","target":"[target]","bulb":"[hint]","hand":"->",
        "wave":"[bye]","crown":"[*]","zap":"[fast]","link":"[link]","pin":"[pin]",
        "tag":"[tag]","tools":"[tool]","new":"[new]","done":"[done]","wait":"[wait]",
        "stop":"[stop]","memo":"[note]","classical":"[arch]","mag":"[rev]",
    })

# ───────────────────────────────────────────
# PRINT HELPERS
# ───────────────────────────────────────────
_OK, _ERR, _WARN, _INFO = ("[OK]", "[ERR]", "[!]", "[i]") if LEGACY_WIN_CONSOLE else ("✓", "✗", "!", "·")
def ok(msg):   print(f"  {C.BGREEN}{C.BOLD}{_OK}{C.RESET}  {msg}")
def err(msg):  print(f"  {C.BRED}{C.BOLD}{_ERR}{C.RESET}  {msg}")
def warn(msg): print(f"  {C.BYELLOW}{C.BOLD}{_WARN}{C.RESET}  {msg}")
def info(msg): print(f"  {C.BCYAN}{C.BOLD}{_INFO}{C.RESET}  {msg}")
def div(c=C.DIM, w=60): print(f"{c}{H*w}{C.RESET}")
def sec(title, c=C.BCYAN, icon=""):
    i = f"{icon} " if icon else ""
    print(f"\n{c}{H*60}{C.RESET}\n{c}{C.BOLD}{i}{title}{C.RESET}\n{c}{H*60}{C.RESET}\n")
def panel(title, body, c=C.BCYAN, w=60, icon=""):
    ic = f" {icon}" if icon else ""
    print(f"{c}{DTL}{DH*(w-2)}{DTR}{C.RESET}")
    print(f"{c}{DV}{C.RESET} {C.BOLD}{title}{ic}{C.RESET}{' '*(w-4-len(title)-len(icon))}{c}{DV}{C.RESET}")
    print(f"{c}{ML}{DH*(w-2)}{MR}{C.RESET}")
    for line in body.split("\n"):
        print(f"{c}{DV}{C.RESET} {line:<{w-4}}{c}{DV}{C.RESET}")
    print(f"{c}{DBL}{DH*(w-2)}{DBR}{C.RESET}")

def status(label, value, lc=C.BCYAN, vc=C.BWHITE):
    print(f"  {lc}•{C.RESET} {label:<22} {vc}{value}{C.RESET}")

def badge(text, bg=C.BG_BLUE, fg=C.BWHITE):
    print(f"{bg}{fg} {text} {C.RESET}", end=" ")

# ───────────────────────────────────────────
# TRUECOLOR GRADIENTS + BOOT ANIMATION
# ───────────────────────────────────────────
def _lerp(a, b, t): return int(a + (b - a) * t)

# Legacy Windows conhost also can't reliably render 24-bit truecolor
# SGR sequences, so gradients degrade to a single solid color there
# too (see LEGACY_WIN_CONSOLE above).
def gradient(text: str, start=(56, 189, 248), end=(168, 85, 247)) -> str:
    """Render text with a smooth left-to-right truecolor gradient
    (cyan → violet by default). Spaces pass through uncolored so
    word spacing isn't affected. Falls back to a single solid color
    on legacy Windows consoles that can't render 24-bit color reliably."""
    if LEGACY_WIN_CONSOLE:
        return f"{C.BCYAN}{text}{C.RESET}"
    n = max(1, len(text) - 1)
    out = []
    for i, ch in enumerate(text):
        if ch == " ":
            out.append(ch)
            continue
        t = i / n
        r, g, b = _lerp(start[0], end[0], t), _lerp(start[1], end[1], t), _lerp(start[2], end[2], t)
        out.append(f"\033[38;2;{r};{g};{b}m{ch}")
    return "".join(out) + C.RESET

def gradient_rule(width: int = 60, ch: str = "─", start=(56, 189, 248), end=(168, 85, 247)) -> str:
    if LEGACY_WIN_CONSOLE:
        ch = "-"
    return gradient(ch * width, start, end)

def _boot_sequence():
    """Purely cosmetic startup flourish — a couple hundred ms of
    spinner + step labels before the banner lands. Skipped entirely
    on non-interactive/redirected stdout so it never pollutes logs."""
    if not sys.stdout.isatty():
        return
    frames = ["|", "/", "-", "\\"] if LEGACY_WIN_CONSOLE else ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
    steps = ["Loading providers", "Warming rate buckets", "Linking tools"]
    try:
        for step in steps:
            for f in (frames * 2)[:10]:
                sys.stdout.write(f"\r  {C.BCYAN}{f}{C.RESET}  {C.DIM}{step}...{C.RESET}          ")
                sys.stdout.flush()
                time.sleep(0.02)
        sys.stdout.write("\r" + " " * 48 + "\r")
        sys.stdout.flush()
    except Exception:
        pass

# ───────────────────────────────────────────
# PATHS
# ───────────────────────────────────────────
CONFIG_FILE = Path.home() / ".nim_agent_config.json"
SESSIONS_FILE = Path.home() / ".nim_agent_sessions.json"
HISTORY_FILE = Path.home() / ".nim_agent_history.json"
NIM_BASE = "https://integrate.api.nvidia.com/v1"

# ───────────────────────────────────────────
# TOKEN BUCKET RATE LIMITER (RPM ENFORCER)
# ───────────────────────────────────────────
class TokenBucket:
    """Thread-safe, SELF-CORRECTING RPM enforcer with reservation pattern.

    Two things make a naive token bucket still hit 429s in practice:
      1. The real server-side ceiling isn't perfectly stable (shared
         quota, burst windows, other traffic on the same key), so a
         fixed local cap that exactly matches the "advertised" limit
         has zero margin for error.
      2. A limiter that only reacts AFTER a 429 (simple exponential
         backoff on the retry) still spends its next attempt at the
         same aggressive rate that just got rejected.

    This bucket fixes both with an AIMD strategy (the same idea TCP
    congestion control uses):
      - `ceiling_rpm` is the rate you were TOLD you have (e.g. 40).
      - It never targets the ceiling itself — only
        `ceiling_rpm * safety_margin` (default 80%), so normal jitter
        in the server's own accounting doesn't tip you over.
      - The instant a request is rejected (429), the *effective* rate
        is cut in half (multiplicative decrease) and a temporary extra
        gap is added between requests — so the very next attempt is
        already much more conservative, not just delayed once.
      - After a run of consecutive successes, the effective rate creeps
        back up a little at a time (additive increase), capped at the
        safety-margin target. It never overshoots back to the ceiling.

    Key design: tokens are RESERVED before the request, but only
    fully COMMITTED after a successful response. A request that gets
    REJECTED (429) still gets recorded in the usage history — the
    server counted it the moment it processed it, so pretending it
    never happened would just desync the local bucket from reality.
    Only a request that never reached the server at all (timeout,
    connection error) should give its token back via release().
    """
    def __init__(self, rpm: float = 20.0, burst: int = 1, min_gap: float = 2.0,
                 safety_margin: float = 0.8, min_effective_rpm: float = 2.0):
        self.ceiling_rpm = max(1.0, rpm)       # the rate you were told you have
        self.safety_margin = min(1.0, max(0.1, safety_margin))
        self.min_effective_rpm = max(0.5, min_effective_rpm)
        self.rpm = self.ceiling_rpm * self.safety_margin  # current adaptive target
        self.burst = burst
        self.base_min_gap = min_gap
        self.min_gap = min_gap                 # minimum seconds between ANY two requests
        self.penalty_gap_until = 0.0           # monotonic timestamp; extra gap active until then
        self.penalty_gap_extra = 0.0
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self.last_request_time = 0.0
        self.lock = threading.Lock()
        self.history = deque()  # committed AND rejected request timestamps (real usage)
        self._pending = 0  # reserved but not yet committed/counted
        self._consecutive_success = 0
        self._recover_every = 8    # successes needed before nudging rate back up

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_update
        rate = self.rpm / 60.0
        self.tokens = min(self.burst, self.tokens + elapsed * rate)
        self.last_update = now

    def _prune_history(self):
        now = time.monotonic()
        cutoff = now - 60.0
        while self.history and self.history[0] < cutoff:
            self.history.popleft()

    def _current_min_gap(self) -> float:
        if time.monotonic() < self.penalty_gap_until:
            return self.base_min_gap + self.penalty_gap_extra
        return self.base_min_gap

    def _wait_time(self) -> float:
        """Compute how long to wait before next request."""
        self._refill()
        self._prune_history()

        waits = []

        # 1. Token availability
        if self.tokens < 1.0:
            token_wait = (1.0 - self.tokens) / (self.rpm / 60.0)
            waits.append(token_wait)

        # 2. Sliding window ceiling against the ADAPTIVE (not raw) rate,
        #    leaving a 1-slot buffer.
        cap = max(1, int(self.rpm))
        if len(self.history) >= cap:
            if self.history:
                window_wait = 60.0 - (time.monotonic() - self.history[0]) + 0.5
                waits.append(max(0.0, window_wait))

        # 3. Minimum gap between requests (temporarily widened after a 429)
        gap = self._current_min_gap()
        since_last = time.monotonic() - self.last_request_time
        if since_last < gap:
            waits.append(gap - since_last)

        if not waits:
            return 0.0
        return max(waits) + random.uniform(0.0, 0.5)  # jitter

    def reserve(self, timeout: float = 300.0) -> bool:
        """Reserve a token. MUST call commit(), count_rejected(), or
        release() afterwards."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            with self.lock:
                wait = self._wait_time()
                if wait <= 0.01:
                    self.tokens -= 1.0
                    self._pending += 1
                    self.last_request_time = time.monotonic()
                    return True
            time.sleep(wait)
        return False

    def commit(self):
        """Mark the reserved request as successfully completed. Counts
        toward real usage AND slowly earns back rate after enough
        consecutive successes."""
        with self.lock:
            if self._pending > 0:
                self._pending -= 1
                self.history.append(time.monotonic())
                self._consecutive_success += 1
                target = self.ceiling_rpm * self.safety_margin
                if self._consecutive_success >= self._recover_every and self.rpm < target:
                    self._consecutive_success = 0
                    # Additive increase: creep up, never overshoot the target.
                    self.rpm = min(target, self.rpm + max(0.5, target * 0.1))

    def release(self):
        """Release a reservation for a request that never reached the
        server at all (e.g. local timeout, connection error, DNS
        failure). Only use this when you are SURE the server never
        saw/counted the request — otherwise the local bucket and the
        server's real counter drift apart and you'll keep sending
        requests into a limit you've already exceeded."""
        with self.lock:
            if self._pending > 0:
                self._pending -= 1
                self.tokens = min(self.burst, self.tokens + 1.0)

    def count_rejected(self):
        """Record a request that DID reach the server but was rejected
        (429 / rate-limited). The server counted it against your quota
        the moment it processed it, so the local bucket must count it
        too — otherwise stats()/the sliding window under-report real
        usage and reserve() keeps handing out slots the server has
        already used up. Unlike commit(), this does not return the
        token to the pool: the slot is spent either way.

        Also triggers the AIMD back-off: the effective rate is cut in
        half (multiplicative decrease, floored at min_effective_rpm)
        and a temporary extra gap is added between requests, so the
        very next attempt is already more conservative — not just
        delayed once by the caller's own backoff sleep."""
        with self.lock:
            if self._pending > 0:
                self._pending -= 1
                self.history.append(time.monotonic())
            self._consecutive_success = 0
            self.rpm = max(self.min_effective_rpm, self.rpm * 0.5)
            self.penalty_gap_extra = max(self.penalty_gap_extra, self.base_min_gap * 2)
            self.penalty_gap_until = time.monotonic() + 60.0  # widen gap for the next minute

    def set_rpm(self, rpm: float):
        """Set a new ceiling (e.g. from /rpm). Resets the adaptive rate
        back to ceiling*safety_margin so a manual change takes effect
        immediately rather than being capped by a stale lower value."""
        with self.lock:
            self.ceiling_rpm = max(1.0, rpm)
            self.rpm = self.ceiling_rpm * self.safety_margin
            self._consecutive_success = 0

    def set_min_gap(self, gap: float):
        with self.lock:
            self.base_min_gap = max(0.5, gap)

    def stats(self) -> str:
        with self.lock:
            self._prune_history()
            used = len(self.history)
            target = int(self.ceiling_rpm * self.safety_margin)
            cur = round(self.rpm, 1)
            gap = self._current_min_gap()
            return (f"{used}/{int(self.ceiling_rpm)} RPM (ceiling) | "
                    f"adaptive:{cur}/{target} | {max(0, int(self.rpm) - used)} left | gap:{gap:.1f}s")

# ───────────────────────────────────────────
# TOKEN METER (TPM + tok/s + CONTEXT WINDOW)
# ───────────────────────────────────────────
DEFAULT_CONTEXT_WINDOW = 128_000  # fallback if a model doesn't specify one

def estimate_tokens(text: Optional[str]) -> int:
    """Cheap, provider-agnostic estimate (~4 chars/token for English-ish
    text). Good enough for pacing/compaction decisions; real usage
    counts (when the API returns them) are used to correct it."""
    if not text:
        return 0
    return max(1, len(text) // 4)


class TokenMeter:
    """Tracks token throughput the same way TokenBucket tracks request
    counts: a sliding 60s window for TPM, plus a short window for
    instantaneous tokens/sec. RPM alone under-describes real load —
    a single fat request can blow a provider's TPM cap (or your own
    context budget) while never coming close to the RPM ceiling.

    This is purely observational/advisory right now (it doesn't block
    requests the way TokenBucket does), but it's what /limits reports
    and what drives compaction decisions.
    """
    def __init__(self, tpm: Optional[float] = None):
        self.tpm_limit = tpm  # None = unknown/unbounded, just observe
        self.lock = threading.Lock()
        self.window = deque()      # (monotonic_ts, tokens) for the last 60s -> TPM
        self.recent = deque()      # (monotonic_ts, tokens) for the last 5s -> tok/s
        self.total_prompt = 0
        self.total_completion = 0

    def _prune(self):
        now = time.monotonic()
        while self.window and self.window[0][0] < now - 60.0:
            self.window.popleft()
        while self.recent and self.recent[0][0] < now - 5.0:
            self.recent.popleft()

    def record(self, prompt_tokens: int, completion_tokens: int):
        with self.lock:
            now = time.monotonic()
            total = max(0, prompt_tokens) + max(0, completion_tokens)
            self.window.append((now, total))
            self.recent.append((now, total))
            self.total_prompt += max(0, prompt_tokens)
            self.total_completion += max(0, completion_tokens)
            self._prune()

    def tpm(self) -> int:
        with self.lock:
            self._prune()
            return sum(t for _, t in self.window)

    def tokens_per_sec(self) -> float:
        with self.lock:
            self._prune()
            if not self.recent:
                return 0.0
            span = max(0.5, time.monotonic() - self.recent[0][0])
            return sum(t for _, t in self.recent) / span

    def stats(self) -> str:
        tpm = self.tpm()
        tps = self.tokens_per_sec()
        if self.tpm_limit:
            pct = f" ({tpm / self.tpm_limit * 100:.0f}% of {int(self.tpm_limit)})"
        else:
            pct = ""
        return (f"{tpm} TPM{pct} | {tps:.0f} tok/s | "
                f"lifetime: {self.total_prompt}in/{self.total_completion}out")


# ───────────────────────────────────────────
# MULTI-PROVIDER POOL (rotate across free sources)
# ───────────────────────────────────────────
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

# Free OpenRouter models used as fallback capacity when the primary
# provider (NVIDIA) is rate-limited or locked out. GLM-5.2 itself has
# no free tier anywhere (it's ~744B total / ~40B active, $0.76-0.93/M
# in on OpenRouter) — so this pool is built from the largest, most
# capable *frontier-scale* free models that exist today, each on a
# separate provider so a lockout on one says nothing about the rest:
#
#   Provider    Model            Scale            Notes
#   ─────────   ──────────────   ──────────────   ─────────────────────────────
#   NVIDIA      Nemotron 3 Ultra 550B/55B active   1M ctx — closest raw scale to GLM-5.2
#   Moonshot    Kimi K2.6        1T/32B active     256K ctx — SWE-Bench Pro 58.6 (GLM-5.2: 62.1); OpenRouter rates it "Frontier" tier
#   Alibaba     Qwen3-Coder      480B/35B active   ~1M ctx — coding-specialized MoE
#   Tencent     Hy3              295B/21B active   256K ctx — frontier reasoning/agentic, #1 in several OpenRouter category rankings
#   MiniMax     MiniMax M2.5     10B active         205K ctx — small footprint but 80.2% SWE-Bench Verified
#   Poolside    Laguna M.1       (flagship)         256K ctx — Poolside's flagship coding-agent model
#
# Each has its own separate quota, so rotating across them multiplies
# total available daily capacity instead of hammering one source.
# Roughly 18 RPM / 190 RPD per model, kept a hair under OpenRouter's
# published free limits (~20 RPM, ~200 RPD) as a safety margin.
#
# Deliberately left out: GLM-4.5-Air:free and the older Kimi-K2:free
# have both rotated off OpenRouter's free lineup; Nemotron 3 Super
# and other nano/small models are real but a tier below "frontier."
# The free-model lineup rotates without much notice — re-check
# https://openrouter.ai/models?fmt=cards&max_price=0 periodically.
OPENROUTER_FREE_MODELS = [
    ("OpenRouter Nemotron-3-Ultra",   "nvidia/nemotron-3-ultra-550b-a55b:free"),
    ("OpenRouter Kimi-K2.6",          "moonshotai/kimi-k2.6:free"),
    ("OpenRouter Qwen3-Coder",        "qwen/qwen3-coder:free"),
    ("OpenRouter Tencent-Hy3",        "tencent/hy3:free"),
    ("OpenRouter MiniMax-M2.5",       "minimax/minimax-m2.5:free"),
    ("OpenRouter Poolside-Laguna-M1", "poolside/laguna-m.1:free"),
]


class Provider:
    """One OpenAI-compatible endpoint + model, with its own rate
    bucket and daily quota tracking. Providers are independent of each
    other on purpose: a lockout or exhausted quota on one says nothing
    about the others."""
    def __init__(self, name: str, base_url: str, api_key: str, model_id: str,
                 rpm: float = 20.0, daily_limit: Optional[int] = None,
                 min_gap: float = 2.0):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.model_id = model_id
        self.daily_limit = daily_limit
        self.bucket = TokenBucket(rpm=rpm, burst=1, min_gap=min_gap)
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=300) if HAS_OPENAI else None
        self._day = None
        self._daily_count = 0
        self.cooldown_until = 0.0
        self.consecutive_429 = 0

    def _roll_day(self):
        today = datetime.now().date()
        if self._day != today:
            self._day = today
            self._daily_count = 0

    def daily_remaining(self) -> Optional[int]:
        self._roll_day()
        if self.daily_limit is None:
            return None
        return max(0, self.daily_limit - self._daily_count)

    def is_available(self) -> bool:
        self._roll_day()
        if time.monotonic() < self.cooldown_until:
            return False
        if self.daily_limit is not None and self._daily_count >= self.daily_limit:
            return False
        return True

    def record_success(self):
        self._roll_day()
        self._daily_count += 1
        self.consecutive_429 = 0
        self.bucket.commit()

    def record_rejection(self, base_cooldown: float = 120.0):
        """A real 429 from the server. Count it (bucket stays honest)
        and, after a couple of hits in a row, put this provider to
        sleep for a while rather than keep hammering it — the pool
        will use a different provider in the meantime."""
        self._roll_day()
        self.bucket.count_rejected()
        self.consecutive_429 += 1
        if self.consecutive_429 >= 2:
            self.cooldown_until = time.monotonic() + base_cooldown

    def status(self) -> str:
        rem = self.daily_remaining()
        rem_str = "unlimited" if rem is None else f"{rem} left today"
        state = "cooling down" if time.monotonic() < self.cooldown_until else "ready"
        return f"{self.name} [{state}, {rem_str}]"


class ProviderPool:
    """Round-robins across multiple providers so a lockout or
    exhausted quota on one doesn't stop the agent — it just moves to
    the next available free source instead of waiting on the same
    dead end."""
    def __init__(self, providers: List[Provider]):
        if not providers:
            raise ValueError("ProviderPool needs at least one provider")
        self.providers = providers
        self.idx = 0

    def current(self) -> Provider:
        return self.providers[self.idx]

    def rotate(self):
        self.idx = (self.idx + 1) % len(self.providers)

    def next_available(self) -> Optional[Provider]:
        """Return the next usable provider, advancing the pool pointer
        as needed. Returns None only if every provider is currently in
        cooldown or out of daily quota."""
        for _ in range(len(self.providers)):
            p = self.current()
            if p.is_available():
                return p
            self.rotate()
        return None

    def soonest_wait(self) -> float:
        waits = [max(0.0, p.cooldown_until - time.monotonic()) for p in self.providers]
        return max(5.0, min(waits)) if waits else 30.0


def build_provider_pool(profile: Dict) -> ProviderPool:
    """NVIDIA (the configured profile) is always the primary provider.
    If OPENROUTER_API_KEY is set in the environment, a handful of
    OpenRouter's free models are added as fallback capacity — separate
    infrastructure, separate quotas, so they don't share NVIDIA's
    account-level lockout behavior."""
    model = profile["models"][profile["default_model"]]
    providers = [Provider(
        name="NVIDIA NIM",
        base_url=NIM_BASE,
        api_key=profile["key"],
        model_id=model["id"],
        rpm=profile.get("rpm", 20.0),
        daily_limit=None,
    )]

    or_key = os.environ.get("OPENROUTER_API_KEY")
    if or_key:
        for name, model_id in OPENROUTER_FREE_MODELS:
            providers.append(Provider(
                name=name,
                base_url=OPENROUTER_BASE,
                api_key=or_key,
                model_id=model_id,
                rpm=18.0,
                daily_limit=190,
            ))
    return ProviderPool(providers)


# ───────────────────────────────────────────
# CONFIG (DYNAMIC PROFILES)
# ───────────────────────────────────────────
def load_config() -> Dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config: Dict) -> bool:
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        err(f"Failed to save config: {e}")
        return False

def ensure_config() -> Dict:
    """Ensure config has a profiles dict. Handles old config migration."""
    config = load_config()
    if "profiles" not in config:
        config["profiles"] = {}
    if "next_id" not in config:
        # Migrate from old format or start fresh
        existing = config.get("profiles", {})
        if existing:
            # Find highest numeric ID
            max_id = 0
            for k in existing.keys():
                try:
                    max_id = max(max_id, int(k))
                except ValueError:
                    pass
            config["next_id"] = max_id + 1
        else:
            config["next_id"] = 1
    return config

def list_profiles(config: Dict) -> Dict:
    return config.get("profiles", {})

def add_profile(config: Dict, name: str, api_key: str, models: Dict, default_model: str, rpm: float = 20.0) -> str:
    """Add a new profile. Returns the profile ID."""
    # Ensure next_id exists
    if "next_id" not in config:
        existing = config.get("profiles", {})
        max_id = 0
        for k in existing.keys():
            try:
                max_id = max(max_id, int(k))
            except ValueError:
                pass
        config["next_id"] = max_id + 1
    pid = str(config["next_id"])
    config["next_id"] += 1
    config["profiles"][pid] = {
        "name": name,
        "key": api_key,
        "models": models,
        "default_model": default_model,
        "rpm": rpm,
    }
    if save_config(config):
        return pid
    else:
        raise RuntimeError("Failed to persist profile to config file")

def remove_profile(config: Dict, pid: str) -> bool:
    if pid in config.get("profiles", {}):
        del config["profiles"][pid]
        if save_config(config):
            return True
    return False

def update_profile(config: Dict, pid: str, **kwargs) -> bool:
    if pid not in config.get("profiles", {}):
        return False
    config["profiles"][pid].update(kwargs)
    if save_config(config):
        return True
    return False

def prompt_first_setup() -> Dict:
    print(f"\n  {gradient_rule(58)}")
    print(f"  {C.BOLD}First-Time Setup{C.RESET}  {C.DIM}— create your first profile{C.RESET}")
    print(f"  {C.DIM}You can add more profiles later with /profile add{C.RESET}")
    print(f"  {gradient_rule(58)}\n")

    name = input(f"  {I['tag']} Profile name (e.g. OMEGA): ").strip()
    while not name:
        name = input(f"  {I['warn']} Name required: ").strip()

    key = input(f"  {I['key']} NVIDIA API key: ").strip()
    while not key:
        key = input(f"  {I['warn']} Key required: ").strip()

    print(f"\n  {I['bulb']} {C.DIM}Enter model IDs. Leave blank to use defaults.{C.RESET}")
    glm_id = input(f"  {I['code']} GLM model ID [z-ai/glm-5.2]: ").strip() or "z-ai/glm-5.2"
    nem_id = input(f"  {I['code']} Nemotron model ID [nvidia/nemotron-3-ultra-550b-a55b]: ").strip() or "nvidia/nemotron-3-ultra-550b-a55b"

    rpm_str = input(f"  {I['clock']} RPM limit [20]: ").strip()
    rpm = float(rpm_str) if rpm_str else 20.0

    default = input(f"  {I['star']} Default model (glm/nemotron) [glm]: ").strip() or "glm"

    models = {
        "glm": {"name": f"{name}-GLM", "id": glm_id},
        "nemotron": {"name": f"{name}-Nemotron", "id": nem_id},
    }

    config = ensure_config()
    pid = add_profile(config, name, key, models, default, rpm)
    save_config(config)

    ok(f"Profile '{name}' created with ID [{pid}]")
    info(f"RPM limit set to {rpm}")
    info(f"Config saved to: {CONFIG_FILE}")
    print()
    return config

def get_or_create_config() -> Dict:
    config = ensure_config()
    if not config.get("profiles"):
        config = prompt_first_setup()
    return config

# ───────────────────────────────────────────
# SESSIONS
# ───────────────────────────────────────────
def load_sessions() -> Dict:
    if SESSIONS_FILE.exists():
        try:
            with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_sessions(sessions: Dict):
    with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)

def session_key(profile_name: str, project_dir: str) -> str:
    return f"{profile_name}::{project_dir.replace(chr(92), '/').replace(':', '_')}"

def load_session(profile_name: str, project_dir: str) -> Optional[Dict]:
    return load_sessions().get(session_key(profile_name, project_dir))

def save_session(profile_name: str, project_dir: str, data: Dict):
    sessions = load_sessions()
    key = session_key(profile_name, project_dir)
    sessions[key] = data
    if len(sessions) > 20:
        oldest = sorted(sessions.items(), key=lambda x: x[1].get("timestamp", ""))[:len(sessions)-20]
        for k, _ in oldest:
            del sessions[k]
    save_sessions(sessions)

def delete_session(profile_name: str, project_dir: str):
    sessions = load_sessions()
    key = session_key(profile_name, project_dir)
    if key in sessions:
        del sessions[key]
        save_sessions(sessions)

# ───────────────────────────────────────────
# PERSONAS
# ───────────────────────────────────────────
PERSONAS = {
    "architect": {"name": "Architect", "description": "Design systems and review architecture", "stage": "planning",
        "prompt": "You are a senior software architect. Analyze the project structure, suggest improvements, design patterns, and scalability solutions. Think about maintainability, performance, and clean separation of concerns. Design before building. Always design with testability in mind.",
        "icon": I["classical"], "color": C.BBLUE},
    "coder": {"name": "Coder", "description": "Write, refactor, and debug code", "stage": "implementation",
        "prompt": "You are an expert software engineer. Write clean, efficient, well-documented code. Follow best practices and modern conventions. Always explain your reasoning. Focus on completing features and fixing TODOs. Practice test-driven development.",
        "icon": I["code"], "color": C.BGREEN},
    "debugger": {"name": "Debugger", "description": "Find and fix bugs", "stage": "troubleshooting",
        "prompt": "You are a debugging specialist. Analyze error messages, trace logic, identify root causes, and provide minimal fixes. Focus on correctness. Hunt down bugs and edge cases. After every fix, run the relevant tests.",
        "icon": I["bug"], "color": C.BRED},
    "reviewer": {"name": "Reviewer", "description": "Code review and quality analysis", "stage": "review",
        "prompt": "You are a strict code reviewer. Find bugs, security issues, performance bottlenecks, and style violations. Be thorough and critical. Suggest specific fixes. Ensure code quality before merge.",
        "icon": I["mag"], "color": C.BMAGENTA},
    "optimizer": {"name": "Optimizer", "description": "Performance optimization", "stage": "optimization",
        "prompt": "You are a performance engineer. Profile code, identify bottlenecks, suggest algorithmic improvements, and optimize for speed and memory. Make fast code faster. After each optimization, run benchmarks and tests.",
        "icon": I["zap"], "color": C.BYELLOW},
    "general": {"name": "General", "description": "General purpose assistant", "stage": "general",
        "prompt": "You are a helpful AI assistant. Answer questions, explain concepts, and assist with tasks. When writing or modifying code, follow test-driven development principles.",
        "icon": I["bot"], "color": C.BCYAN},
}

# ───────────────────────────────────────────
# FILE TOOLS (COLORFUL)
# ───────────────────────────────────────────
class FileTools:
    def __init__(self, base_path: str):
        self.base = Path(base_path).resolve()

    def _safe(self, path: str) -> Path:
        target = (self.base / path).resolve()
        if not str(target).startswith(str(self.base)):
            raise ValueError(f"Path '{path}' escapes project directory")
        return target

    def _fcolor(self, p: Path) -> str:
        e = p.suffix.lower()
        cmap = {'.py':C.BGREEN,'.js':C.BYELLOW,'.ts':C.BBLUE,'.java':C.BRED,
                '.cpp':C.BCYAN,'.c':C.BCYAN,'.go':C.BCYAN,'.rs':C.ORANGE,
                '.json':C.BYELLOW,'.yaml':C.BYELLOW,'.yml':C.BYELLOW,
                '.toml':C.ORANGE,'.xml':C.BYELLOW,'.md':C.BCYAN,'.txt':C.BWHITE,
                '.rst':C.BCYAN,'.html':C.BMAGENTA,'.css':C.BBLUE,'.scss':C.PINK,
                '.sql':C.BGREEN,'.sh':C.BGREEN,'.bash':C.BGREEN,'.zsh':C.BGREEN,
                '.ps1':C.BBLUE,'.rb':C.BRED,'.php':C.BMAGENTA,'.swift':C.ORANGE,
                '.kt':C.BMAGENTA,'.scala':C.BRED,'.r':C.BBLUE,'.m':C.BGREEN,
                '.mm':C.BGREEN,'.dart':C.BCYAN,'.lua':C.BBLUE,'.vim':C.BGREEN,
                '.dockerfile':C.BBLUE}
        return cmap.get(e, C.BWHITE)

    def read(self, path: str) -> str:
        try:
            target = self._safe(path)
            if not target.exists(): return f"{I['cross']} {C.BRED}[ERR]{C.RESET} File not found: {path}"
            if target.is_dir(): return f"{I['cross']} {C.BRED}[ERR]{C.RESET} '{path}' is a directory"
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            lines = content.splitlines()
            c = self._fcolor(target)
            b = f"{C.BCYAN}{DTL}{DH*58}{DTR}{C.RESET}"
            h = f"{C.BCYAN}{DV}{C.RESET} {c}{I['file']} {path}{C.RESET} {C.DIM}({len(content)} chars, {len(lines)} lines){C.RESET}"
            ftr = f"{C.BCYAN}{DBL}{DH*58}{DBR}{C.RESET}"
            return f"{b}\n{h}\n{b}\n{content}\n{ftr}"
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def list_dir(self, path: str = ".") -> str:
        try:
            target = self._safe(path)
            if not target.exists(): return f"{I['cross']} {C.BRED}[ERR]{C.RESET} Directory not found: {path}"
            if not target.is_dir(): return f"{I['cross']} {C.BRED}[ERR]{C.RESET} '{path}' is not a directory"
            dirs, files = [], []
            for item in sorted(target.iterdir()):
                (dirs if item.is_dir() else files).append(item)
            out = [f"{C.BOLD}{C.BBLUE}{I['folder']} {path}{C.RESET} {C.DIM}({len(dirs)} dirs, {len(files)} files){C.RESET}",
                   C.BBLUE + H*50 + C.RESET]
            for d in dirs:
                out.append(f"  {C.BBLUE}{I['folder']}{C.RESET} {C.BOLD}{C.BWHITE}{d.name}{C.RESET}/")
            for f in files:
                sz = f.stat().st_size
                szs = f"{sz} B" if sz < 1024 else f"{sz/1024:.1f} KB" if sz < 1024*1024 else f"{sz/(1024*1024):.1f} MB"
                out.append(f"  {C.DIM}{I['file']}{C.RESET} {self._fcolor(f)}{f.name}{C.RESET} {C.DIM}({szs}){C.RESET}")
            return "\n".join(out)
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def search(self, pattern: str, path: str = ".", ext: str = "") -> str:
        try:
            target = self._safe(path)
            matches = []
            rx = re.compile(pattern, re.IGNORECASE)
            for root, _, files in os.walk(target):
                for fn in files:
                    if ext and not fn.endswith(ext): continue
                    fp = Path(root) / fn
                    rel = fp.relative_to(self.base)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as f:
                            for i, line in enumerate(f, 1):
                                if rx.search(line):
                                    matches.append(f"  {C.BYELLOW}{rel}:{i}{C.RESET} {line.strip()}")
                                    if len(matches) >= 50: break
                    except: pass
                    if len(matches) >= 50: break
                if len(matches) >= 50: break
            if not matches:
                return f"{I['info']} {C.BYELLOW}[INFO]{C.RESET} No matches for '{C.BOLD}{pattern}{C.RESET}'"
            b = f"{C.BMAGENTA}{DTL}{DH*58}{DTR}{C.RESET}"
            h = f"{C.BMAGENTA}{DV}{C.RESET} {C.BOLD}{I['search']} Search: '{pattern}'{C.RESET} {C.DIM}({len(matches)} matches){C.RESET}"
            ftr = f"{C.BMAGENTA}{DBL}{DH*58}{DBR}{C.RESET}"
            return f"{b}\n{h}\n{b}\n" + "\n".join(matches[:50]) + f"\n{ftr}"
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def tree(self, path: str = ".", max_depth: int = 3) -> str:
        try:
            target = self._safe(path)
            lines = [f"{C.BOLD}{C.BGREEN}{I['tree']} Tree: {path}{C.RESET}", C.BGREEN + H*50 + C.RESET]
            def _tree(cur: Path, prefix: str = "", depth: int = 0):
                if depth > max_depth: return
                try:
                    items = sorted(cur.iterdir(), key=lambda x: (not x.is_dir(), x.name))
                    for i, item in enumerate(items):
                        last = i == len(items) - 1
                        br = f"{C.BYELLOW}└──{C.RESET}" if last else f"{C.BYELLOW}├──{C.RESET}"
                        if item.is_dir():
                            lines.append(f"{prefix}{br} {C.BBLUE}{I['folder']} {item.name}{C.RESET}/")
                            _tree(item, prefix + ("    " if last else f"{C.BYELLOW}│{C.RESET}   "), depth + 1)
                        else:
                            lines.append(f"{prefix}{br} {self._fcolor(item)}{item.name}{C.RESET}")
                except PermissionError: pass
            _tree(target)
            return "\n".join(lines)
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def write(self, path: str, content: str) -> str:
        try:
            target = self._safe(path)
            if target.exists() and target.is_dir():
                return (f"{I['cross']} {C.BRED}[ERR]{C.RESET} '{path}' is an existing "
                         f"directory, not a file — pick a file name inside it, e.g. "
                         f"'{path.rstrip('/')}/{Path(path).name or 'file.txt'}'")
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return f"{I['check']} {C.BGREEN}[OK]{C.RESET} Written: {C.BOLD}{C.BWHITE}{path}{C.RESET} {C.DIM}({len(content)} chars){C.RESET}"
        except PermissionError as e:
            return (f"{I['cross']} {C.BRED}[ERR]{C.RESET} Permission denied writing '{path}': {e}. "
                     f"Common causes: the path points to a directory, the file is open/locked "
                     f"in another program, or the process lacks write access to this location.")
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def modify(self, path: str, old_string: str, new_string: str) -> str:
        try:
            target = self._safe(path)
            if not target.exists(): return f"{I['cross']} {C.BRED}[ERR]{C.RESET} File not found: {path}"
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if old_string not in content:
                return f"{I['warn']} {C.BYELLOW}[ERR]{C.RESET} old_string not found in {path}. Use search_files to find exact text."
            new_content = content.replace(old_string, new_string, 1)
            if new_content == content:
                return f"{I['info']} {C.BYELLOW}[INFO]{C.RESET} No changes made."
            with open(target, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"{I['check']} {C.BGREEN}[OK]{C.RESET} Modified: {C.BOLD}{C.BWHITE}{path}{C.RESET}"
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def modify_lines(self, path: str, start_line: int, end_line: int, new_content: str) -> str:
        try:
            target = self._safe(path)
            if not target.exists(): return f"{I['cross']} {C.BRED}[ERR]{C.RESET} File not found: {path}"
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            if start_line < 1 or end_line > len(lines) or start_line > end_line:
                return f"{I['cross']} {C.BRED}[ERR]{C.RESET} Invalid line range. File has {len(lines)} lines."
            new_lines = new_content.split("\n")
            if lines and lines[-1].endswith("\n"):
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines[-1] += "\n"
            result = lines[:start_line-1] + new_lines + lines[end_line:]
            with open(target, "w", encoding="utf-8") as f:
                f.writelines(result)
            return f"{I['check']} {C.BGREEN}[OK]{C.RESET} Modified lines {C.BOLD}{start_line}-{end_line}{C.RESET} in {C.BWHITE}{path}{C.RESET}"
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def run_command(self, command: str, timeout: int = 60) -> str:
        try:
            r = subprocess.run(command, cwd=self.base, capture_output=True, text=True, shell=True, timeout=timeout)
            out = ""
            if r.stdout:
                out += f"{C.BOLD}{C.BGREEN}═══ STDOUT ═══{C.RESET}\n{C.BWHITE}{r.stdout}{C.RESET}\n"
            if r.stderr:
                out += f"{C.BOLD}{C.BRED}═══ STDERR ═══{C.RESET}\n{C.BYELLOW}{r.stderr}{C.RESET}\n"
            ec = C.BGREEN if r.returncode == 0 else C.BRED
            out += f"{C.BOLD}{ec}═══ EXIT CODE: {r.returncode} ═══{C.RESET}"
            return out
        except subprocess.TimeoutExpired:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} Command timed out after {timeout}s: {command}"
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def run_python(self, script: str, args: str = "") -> str:
        try:
            target = self._safe(script)
            if not target.exists():
                return f"{I['cross']} {C.BRED}[ERR]{C.RESET} Script not found: {script}"
            cmd = f'python "{target}"'
            if args: cmd += f" {args}"
            return self.run_command(cmd, timeout=120)
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def run_tests(self, test_path: str = "", runner: str = "pytest") -> str:
        try:
            if test_path:
                target = self._safe(test_path)
                cmd = f'{runner} "{target}"'
            else:
                cmd = runner
            return self.run_command(cmd, timeout=300)
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def git_status(self) -> str:
        try:
            r = subprocess.run(["git", "status", "--short"], cwd=self.base, capture_output=True, text=True, shell=True)
            if r.returncode != 0: return f"{I['cross']} {C.BRED}[ERR]{C.RESET} Not a git repository"
            if not r.stdout.strip(): return f"{I['check']} {C.BGREEN}[INFO]{C.RESET} Working tree clean"
            lines = r.stdout.strip().split("\n")
            out = [f"{C.BOLD}{C.BMAGENTA}{I['git']} Git Status{C.RESET} {C.DIM}({len(lines)} changes){C.RESET}",
                   C.BMAGENTA + H*50 + C.RESET]
            for line in lines:
                st, fn = line[:2], line[3:]
                sc = ""
                for ch in st:
                    if ch == "M": sc += f"{C.BYELLOW}M{C.RESET}"
                    elif ch == "A": sc += f"{C.BGREEN}A{C.RESET}"
                    elif ch == "D": sc += f"{C.BRED}D{C.RESET}"
                    elif ch == "?": sc += f"{C.BCYAN}?{C.RESET}"
                    elif ch == " ": sc += " "
                    else: sc += ch
                out.append(f"  {sc} {C.BWHITE}{fn}{C.RESET}")
            return "\n".join(out)
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def git_diff(self) -> str:
        try:
            r = subprocess.run(["git", "diff"], cwd=self.base, capture_output=True, text=True, shell=True)
            if r.returncode != 0: return f"{I['cross']} {C.BRED}[ERR]{C.RESET} Git diff failed"
            if not r.stdout.strip(): return f"{I['info']} {C.BYELLOW}[INFO]{C.RESET} No changes"
            lines = r.stdout[:5000].split("\n")
            colored = []
            for line in lines:
                if line.startswith("+") and not line.startswith("+++"):
                    colored.append(f"{C.BGREEN}{line}{C.RESET}")
                elif line.startswith("-") and not line.startswith("---"):
                    colored.append(f"{C.BRED}{line}{C.RESET}")
                elif line.startswith("@@"):
                    colored.append(f"{C.BCYAN}{line}{C.RESET}")
                else:
                    colored.append(line)
            return f"{C.BOLD}{C.BMAGENTA}═══ Git Diff ═══{C.RESET}\n" + "\n".join(colored)
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def git_add(self, path: str = ".") -> str:
        try:
            target = self._safe(path)
            r = subprocess.run(["git", "add", str(target)], cwd=self.base, capture_output=True, text=True, shell=True)
            if r.returncode != 0: return f"{I['cross']} {C.BRED}[ERR]{C.RESET} git add failed: {r.stderr}"
            return f"{I['check']} {C.BGREEN}[OK]{C.RESET} Staged: {C.BWHITE}{path}{C.RESET}"
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def git_commit(self, message: str) -> str:
        try:
            r = subprocess.run(["git", "commit", "-m", message], cwd=self.base, capture_output=True, text=True, shell=True)
            if r.returncode != 0: return f"{I['cross']} {C.BRED}[ERR]{C.RESET} git commit failed: {r.stderr}"
            return f"{I['check']} {C.BGREEN}[OK]{C.RESET} Committed: {C.BOLD}{C.BWHITE}{message}{C.RESET}\n{C.DIM}{r.stdout}{C.RESET}"
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

    def git_push(self, remote: str = "origin", branch: str = "") -> str:
        try:
            cmd = ["git", "push", remote]
            if branch: cmd.append(branch)
            r = subprocess.run(cmd, cwd=self.base, capture_output=True, text=True, shell=True)
            if r.returncode != 0: return f"{I['cross']} {C.BRED}[ERR]{C.RESET} git push failed: {r.stderr}"
            return f"{I['rocket']} {C.BGREEN}[OK]{C.RESET} Pushed to {C.BWHITE}{remote}{' ' + branch if branch else ''}{C.RESET}\n{C.DIM}{r.stdout}{C.RESET}"
        except Exception as e:
            return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

# ───────────────────────────────────────────
# TOOL SCHEMAS
# ───────────────────────────────────────────
TOOLS_SCHEMA = [
    {"type":"function","function":{"name":"read_file","description":"Read the full contents of a file in the project.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Relative path to the file"}},"required":["path"]}}},
    {"type":"function","function":{"name":"list_directory","description":"List contents of a directory.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Relative path to directory (default: current)","default":"."}},"required":[]}}},
    {"type":"function","function":{"name":"search_files","description":"Search for text patterns in files using regex.","parameters":{"type":"object","properties":{"pattern":{"type":"string","description":"Regex pattern to search for"},"path":{"type":"string","description":"Directory to search in","default":"."},"ext":{"type":"string","description":"File extension filter (e.g. .py)","default":""}},"required":["pattern"]}}},
    {"type":"function","function":{"name":"directory_tree","description":"Show directory tree structure.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Root path","default":"."},"max_depth":{"type":"integer","description":"Max depth to traverse","default":3}},"required":[]}}},
    {"type":"function","function":{"name":"write_file","description":"Create a new file or overwrite an existing file entirely.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Relative file path"},"content":{"type":"string","description":"Full content to write"}},"required":["path","content"]}}},
    {"type":"function","function":{"name":"modify_file","description":"Replace a specific string/block in an existing file. Use read_file first to get exact text.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Relative file path"},"old_string":{"type":"string","description":"Exact text to replace (must match exactly, including whitespace)"},"new_string":{"type":"string","description":"Replacement text"}},"required":["path","old_string","new_string"]}}},
    {"type":"function","function":{"name":"modify_lines","description":"Replace specific line range in a file (1-indexed, inclusive). Use read_file to check line numbers.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Relative file path"},"start_line":{"type":"integer","description":"First line to replace (1-indexed)"},"end_line":{"type":"integer","description":"Last line to replace (inclusive)"},"new_content":{"type":"string","description":"New content to insert (can be multi-line)"}},"required":["path","start_line","end_line","new_content"]}}},
    {"type":"function","function":{"name":"run_command","description":"Execute any shell command in the project directory. Use for running build scripts, pip install, npm, make, etc.","parameters":{"type":"object","properties":{"command":{"type":"string","description":"Shell command to execute"},"timeout":{"type":"integer","description":"Timeout in seconds (default: 60)","default":60}},"required":["command"]}}},
    {"type":"function","function":{"name":"run_python","description":"Run a Python script in the project directory. Use for running individual scripts or modules.","parameters":{"type":"object","properties":{"script":{"type":"string","description":"Relative path to the Python script"},"args":{"type":"string","description":"Command-line arguments to pass to the script","default":""}},"required":["script"]}}},
    {"type":"function","function":{"name":"run_tests","description":"Run test suite using pytest or unittest. Use after making changes to verify correctness.","parameters":{"type":"object","properties":{"test_path":{"type":"string","description":"Path to test file or directory (default: all tests)","default":""},"runner":{"type":"string","description":"Test runner: pytest or unittest (default: pytest)","default":"pytest"}},"required":[]}}},
    {"type":"function","function":{"name":"git_status","description":"Show git working tree status.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"git_diff","description":"Show git diff of current changes.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"git_add","description":"Stage files for commit. Use '.' to stage all changes.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"File or directory to stage (default: .)","default":"."}},"required":[]}}},
    {"type":"function","function":{"name":"git_commit","description":"Commit staged changes with a message.","parameters":{"type":"object","properties":{"message":{"type":"string","description":"Commit message"}},"required":["message"]}}},
    {"type":"function","function":{"name":"git_push","description":"Push commits to remote repository.","parameters":{"type":"object","properties":{"remote":{"type":"string","description":"Remote name (default: origin)","default":"origin"},"branch":{"type":"string","description":"Branch name (default: current branch)","default":""}},"required":[]}}},
]

def execute_tool(tools: FileTools, name: str, args: Dict) -> str:
    try:
        if name == "read_file": return tools.read(args.get("path", ""))
        elif name == "list_directory": return tools.list_dir(args.get("path", "."))
        elif name == "search_files": return tools.search(args.get("pattern", ""), args.get("path", "."), args.get("ext", ""))
        elif name == "directory_tree": return tools.tree(args.get("path", "."), args.get("max_depth", 3))
        elif name == "write_file": return tools.write(args.get("path", ""), args.get("content", ""))
        elif name == "modify_file": return tools.modify(args.get("path", ""), args.get("old_string", ""), args.get("new_string", ""))
        elif name == "modify_lines": return tools.modify_lines(args.get("path", ""), args.get("start_line", 1), args.get("end_line", 1), args.get("new_content", ""))
        elif name == "run_command": return tools.run_command(args.get("command", ""), args.get("timeout", 60))
        elif name == "run_python": return tools.run_python(args.get("script", ""), args.get("args", ""))
        elif name == "run_tests": return tools.run_tests(args.get("test_path", ""), args.get("runner", "pytest"))
        elif name == "git_status": return tools.git_status()
        elif name == "git_diff": return tools.git_diff()
        elif name == "git_add": return tools.git_add(args.get("path", "."))
        elif name == "git_commit": return tools.git_commit(args.get("message", ""))
        elif name == "git_push": return tools.git_push(args.get("remote", "origin"), args.get("branch", ""))
        else: return f"{I['cross']} {C.BRED}[ERR]{C.RESET} Unknown tool: {name}"
    except Exception as e:
        return f"{I['cross']} {C.BRED}[ERR]{C.RESET} {e}"

# ───────────────────────────────────────────
# STAGE DETECTOR
# ───────────────────────────────────────────
class StageDetector:
    def __init__(self, tools: FileTools):
        self.tools = tools
        self.base = tools.base

    def detect(self) -> Tuple[str, str]:
        checks = [
            ("debugger", self._check_debugger),
            ("optimizer", self._check_optimizer),
            ("reviewer", self._check_reviewer),
            ("coder", self._check_coder),
            ("architect", self._check_architect),
        ]
        for key, fn in checks:
            result = fn()
            if result: return key, result
        return "general", "No specific stage detected."

    def _check_debugger(self) -> Optional[str]:
        patterns = [r"error\.log", r"debug\.log", r"traceback", r"crash", r"\.err$", r"failures\.txt", r"pytest_cache"]
        error_files = []
        try:
            for root, _, files in os.walk(self.base):
                for f in files:
                    if any(re.search(p, f, re.I) for p in patterns):
                        error_files.append(f)
                    elif f.endswith(".log"):
                        try:
                            with open(Path(root)/f, "r", errors="replace") as fh:
                                if any(s in fh.read(2000).lower() for s in ["traceback", "exception", "error:", "failed"]):
                                    error_files.append(f)
                        except: pass
                if error_files: break
        except: pass
        if error_files:
            return f"Found error signals: {', '.join(error_files[:3])}. Switching to Debugger."
        try:
            r = self.tools.search(r"BUG|HACK|FIXME|XXX", ".")
            if not r.startswith(f"{I['info']}") and r.count(":") > 3:
                return f"Found {r.count(':')} bug markers. Switching to Debugger."
        except: pass
        return None

    def _check_optimizer(self) -> Optional[str]:
        large = []
        try:
            for root, _, files in os.walk(self.base):
                for f in files:
                    if f.endswith((".py", ".js", ".ts", ".java", ".cpp", ".c")):
                        sz = (Path(root)/f).stat().st_size
                        if sz > 500*1024: large.append(f)
        except: pass
        if len(large) >= 2:
            return f"Large files detected: {', '.join(large[:3])}. Switching to Optimizer."
        return None

    def _check_reviewer(self) -> Optional[str]:
        try:
            r = subprocess.run(["git", "status", "--short"], cwd=self.base, capture_output=True, text=True, shell=True)
            if r.returncode == 0 and r.stdout.strip():
                n = len(r.stdout.strip().split("\n"))
                if n >= 3: return f"Git shows {n} changed files. Switching to Reviewer."
        except: pass
        try:
            py = list(self.base.rglob("*.py"))
            if len(py) > 10 and any(d.is_dir() for d in self.base.rglob("*test*")):
                return f"Project has {len(py)} files + tests. Switching to Reviewer."
        except: pass
        return None

    def _check_coder(self) -> Optional[str]:
        try:
            r = self.tools.search(r"TODO|FIXME|pass\s*$|NotImplementedError|raise.*implement", ".")
            if not r.startswith(f"{I['info']}") and r.count(":") >= 3:
                return f"Found {r.count(':')} TODOs/stubs. Switching to Coder."
        except: pass
        try:
            cfg = list(self.base.glob("*.json")) + list(self.base.glob("*.yaml")) + list(self.base.glob("*.yml")) + list(self.base.glob("*.toml"))
            py = list(self.base.rglob("*.py"))
            if len(cfg) >= 1 and len(py) <= 3:
                return f"Config exists but only {len(py)} code files. Switching to Coder."
        except: pass
        return None

    def _check_architect(self) -> Optional[str]:
        try:
            items = list(self.base.iterdir())
            files = [i for i in items if i.is_file()]
            dirs = [i for i in items if i.is_dir()]
            if len(files) == 0 and len(dirs) == 0:
                return "Empty project. Switching to Architect."
            if len(files) <= 2 and len(dirs) <= 1:
                return f"Nearly empty ({len(files)} files, {len(dirs)} dirs). Switching to Architect."
            md = list(self.base.glob("*.md"))
            py = list(self.base.rglob("*.py"))
            if len(md) >= 1 and len(py) == 0:
                return "Design docs but no code. Switching to Architect."
        except: pass
        return None

# ───────────────────────────────────────────
# NIM CLIENT (with Token Bucket RPM enforcement)
# ───────────────────────────────────────────
class NIMClient:
    def __init__(self, profile: Dict, project_dir: str, restore: bool = True):
        self.profile = profile
        self.active_model_key = profile["default_model"]
        self.messages: List[Dict] = []
        self.goal: Optional[str] = None
        self.persona = PERSONAS["general"]
        self.tools = FileTools(project_dir)
        self.stage_detector = StageDetector(self.tools)
        self.auto_stage = True
        self.last_stage = None
        self.project_dir = project_dir
        self.max_tool_rounds = 300
        self.max_auto_continues = 2  # how many times to auto-continue past a round-limit cutoff before stopping and asking the user

        # Token/context tracking — separate from the RPM bucket above.
        # RPM tells you if you're sending too many *requests*; this
        # tells you if you're sending too many *tokens* (TPM ceilings
        # are commonly tighter than RPM ones) and how full the
        # conversation's context window is getting.
        self.token_meter = TokenMeter(tpm=profile.get("tpm"))
        self.context_window = profile.get("context_window", DEFAULT_CONTEXT_WINDOW)
        self.compact_threshold = 0.5    # compact once context is this full
        self.compact_keep_recent = 8    # always keep this many recent messages verbatim

        # Provider pool: NVIDIA is always primary; OpenRouter's free
        # models join automatically as fallback capacity if
        # OPENROUTER_API_KEY is set in the environment. Each provider
        # has its own rate bucket and daily quota, independent of the
        # others.
        self.pool = build_provider_pool(profile)

        # Retry config
        self.max_retries = 5
        self.base_delay = 2.0
        self.max_delay = 60.0

        if restore:
            self._try_restore()
        else:
            self._auto_detect()
            self._rebuild_system()

    def _try_restore(self):
        session = load_session(self.profile["name"], self.project_dir)
        if session:
            print(f"\n  {gradient_rule(58)}")
            print(f"  {C.BOLD}Session Found{C.RESET}: {C.BWHITE}{self.profile['name']}{C.RESET}  {C.DIM}{session.get('timestamp', 'unknown')}{C.RESET}")
            print(f"  {C.DIM}Messages: {len(session.get('messages', []))} · Goal: {session.get('goal', 'None')} · Persona: {session.get('persona', 'General')}{C.RESET}")
            print(f"  {gradient_rule(58)}")
            resp = input(f"  {C.BOLD}Resume?{C.RESET} {C.DIM}[Y/n]:{C.RESET} ").strip().lower()
            if resp in ("", "y", "yes"):
                self.messages = session.get("messages", [])
                self.goal = session.get("goal")
                self.active_model_key = session.get("model_key", self.active_model_key)
                self.auto_stage = session.get("auto_stage", True)
                pk = session.get("persona_key", "general")
                if pk in PERSONAS: self.persona = PERSONAS[pk]
                self.last_stage = session.get("last_detected_stage")
                print(f"  {C.BGREEN}✓ Restored{C.RESET}\n")
                self._rebuild_system()
                # A resumed session can carry a large message history.
                # Check compaction immediately instead of waiting for
                # the in-loop threshold check on round 1 — otherwise
                # the very first request after resume sends the full
                # uncompacted history, which is slow and timeout-prone.
                self.maybe_compact()
                return
            else:
                delete_session(self.profile["name"], self.project_dir)
                print(f"  {C.BCYAN}✓ New session{C.RESET}\n")
        self._auto_detect()
        self._rebuild_system()

    @property
    def bucket(self) -> TokenBucket:
        """The currently active provider's rate bucket. Kept as a
        property (rather than a plain attribute) so existing status
        display and /rpm commands keep working without change, but
        now reflect whichever provider the pool is actually using."""
        return self.pool.current().bucket

    def get_model(self) -> Dict:
        return self.profile["models"][self.active_model_key]

    def switch_model(self, key: str) -> bool:
        if key in self.profile["models"]:
            self.active_model_key = key
            self._rebuild_system()
            return True
        return False

    def _auto_detect(self):
        if not self.auto_stage: return
        pk, reason = self.stage_detector.detect()
        if pk != self.last_stage:
            self.last_stage = pk
            self.persona = PERSONAS[pk]
            p = self.persona
            print(f"\n{C.BCYAN}{H*60}{C.RESET}")
            print(f"{C.BCYAN}{I['target']} [Auto-Stage]{C.RESET} {C.BWHITE}{reason}{C.RESET}")
            print(f"{p['color']}{p['icon']} [Persona]{C.RESET} {C.BOLD}{p['name']}{C.RESET} {C.DIM}- {p['description']}{C.RESET}")
            print(f"{C.BCYAN}{H*60}{C.RESET}\n")

    def _rebuild_system(self):
        parts = [self.persona["prompt"]]
        if self.goal: parts.append(f"\nCURRENT GOAL: {self.goal}")
        parts.append(f"\nYou are working in project: {self.project_dir}")
        parts.append("\nYou have access to file system tools. Use them proactively to explore, read, write, modify, search, analyze, run commands, execute scripts, and run tests. Do not just describe what you would do — actually do it by calling tools. Continue working autonomously until the task is complete.")
        parts.append("\nYou can also use git tools: git_status, git_diff, git_add, git_commit, git_push. Stage, commit, and push changes when appropriate.")
        parts.append("\nYou can run shell commands, Python scripts, and test suites. Run tests after making changes to verify correctness. Use run_command for build scripts, pip install, npm, etc. Use run_python for Python scripts. Use run_tests for pytest/unittest.")
        parts.append("\n=== TEST-DRIVEN DEVELOPMENT (TDD) ===")
        parts.append("You MUST follow TDD principles:")
        parts.append("1. Before writing new code, check if tests exist. If not, write tests first.")
        parts.append("2. After every code change, run the relevant tests to verify correctness.")
        parts.append("3. If tests fail, fix the code (not the tests) until they pass.")
        parts.append("4. Only commit code when all tests pass.")
        parts.append("5. When fixing bugs, first write a test that reproduces the bug, then fix it.")
        self.messages = [m for m in self.messages if m.get("role") != "system"]
        self.messages.insert(0, {"role": "system", "content": "\n".join(parts)})

    def context_tokens(self) -> int:
        """Estimated token size of the full message history right now."""
        return sum(estimate_tokens(self._msg_text(m)) for m in self.messages)

    def context_pct(self) -> float:
        return self.context_tokens() / max(1, self.context_window)

    @staticmethod
    def _msg_text(m: Dict) -> str:
        parts = [m.get("content") or ""]
        for tc in (m.get("tool_calls") or []):
            fn = tc.get("function", {})
            parts.append(fn.get("name", "") + (fn.get("arguments") or ""))
        return " ".join(parts)

    def maybe_compact(self):
        """Compact the conversation once it crosses compact_threshold of
        the model's context window, instead of waiting to hit a hard
        context-length error mid-task. Keeps the system prompt and the
        most recent `compact_keep_recent` messages verbatim; folds
        everything older into a single summary message.

        This is deliberately cheap (no extra API call): it's a
        structural compaction, not an LLM-generated summary. Good
        enough to keep a long-running agent loop alive; swap in a
        real summarization call here later if you want higher-fidelity
        compaction.
        """
        if self.context_pct() < self.compact_threshold:
            return False

        system_msgs = [m for m in self.messages if m.get("role") == "system"]
        rest = [m for m in self.messages if m.get("role") != "system"]

        if len(rest) <= self.compact_keep_recent:
            return False  # nothing meaningful to fold away

        old, recent = rest[:-self.compact_keep_recent], rest[-self.compact_keep_recent:]

        # Summarize what's being dropped well enough to keep the agent
        # oriented (who said what, which tools ran) without the full
        # verbatim payload weighing down the context.
        lines = []
        for m in old:
            role = m.get("role", "?")
            if role == "tool":
                snippet = (m.get("content") or "")[:150].replace("\n", " ")
                lines.append(f"- tool[{m.get('name','?')}] -> {snippet}")
            else:
                snippet = (m.get("content") or "")[:150].replace("\n", " ")
                if snippet:
                    lines.append(f"- {role}: {snippet}")
        summary = (
            f"[Compacted {len(old)} earlier messages to stay under the "
            f"context budget.]\n" + "\n".join(lines[-60:])  # cap summary size too
        )

        before = self.context_tokens()
        self.messages = system_msgs + [{"role": "system", "content": summary}] + recent
        after = self.context_tokens()
        print(f"\n  {C.BYELLOW}{I['pkg']} [Compact]{C.RESET} {C.DIM}"
              f"{len(old)} messages folded — context ~{before} -> ~{after} tokens "
              f"({self.context_pct()*100:.0f}% of {self.context_window}){C.RESET}\n")
        return True

    def set_goal(self, goal: str):
        self.goal = goal
        self._rebuild_system()

    def set_persona(self, key: str):
        if key in PERSONAS:
            self.persona = PERSONAS[key]
            self.auto_stage = False
            self._rebuild_system()
            return True
        return False

    def enable_auto(self):
        self.auto_stage = True
        self._auto_detect()
        self._rebuild_system()

    def _call_with_backoff(self, make_call):
        """Call the API via the provider pool, rotating to the next
        available free provider on repeated 429s instead of retrying
        the same one that just told us no.

        make_call(provider) must perform the actual request using
        that provider's client/model and return the result.
        """
        delay = self.base_delay
        max_attempts = self.max_retries * max(1, len(self.pool.providers))
        for attempt in range(max_attempts):
            provider = self.pool.next_available()
            if provider is None:
                # Every provider is either cooling down or out of
                # daily quota. Nothing to do but wait for the soonest
                # one to free up, then try the pool again.
                wait = min(self.pool.soonest_wait(), 60.0)
                print(f"\n{C.BRED}{I['stop']} [ALL PROVIDERS BUSY]{C.RESET} Every free provider is rate-limited or out of quota. Waiting {wait:.0f}s...", flush=True)
                time.sleep(wait)
                continue

            # ENFORCE RPM: reserve a token from THIS provider's bucket.
            if not provider.bucket.reserve(timeout=60.0):
                # Purely a local pacing issue, not a server rejection —
                # just try the next provider instead of waiting here.
                self.pool.rotate()
                continue

            try:
                result = make_call(provider)
                provider.record_success()
                return result
            except Exception as e:
                err_str = str(e).lower()
                # Not every provider/proxy returns a plain HTTP 429.
                # gRPC-style backends (Vertex, some local worker pools)
                # raise "ResourceExhausted" with a "local total request
                # limit reached (N/M)" message instead — same meaning
                # (too much concurrent/queued load), different words.
                # Treat both as the same signal so we back off and
                # rotate providers instead of raising a raw traceback.
                is_429 = (
                    "429" in err_str or "too many requests" in err_str
                    or "rate limit" in err_str or "rate_limit" in err_str
                    or "resourceexhausted" in err_str.replace(" ", "")
                    or "resource exhausted" in err_str
                    or "quota" in err_str
                    or "worker local total request limit" in err_str
                )

                if is_429:
                    # The server received and counted this request
                    # before rejecting it — count it locally too, and
                    # after repeated hits put this provider to sleep
                    # and let the pool use a different free source.
                    provider.record_rejection()
                    if time.monotonic() < provider.cooldown_until:
                        print(f"\n{C.BRED}{I['stop']} [RATE LIMIT] {provider.name} is rate-limited — switching to the next free provider...{C.RESET}", flush=True)
                        self.pool.rotate()
                    else:
                        wait = min(delay + random.uniform(0.5, 1.5), self.max_delay)
                        print(f"\n{C.BRED}{I['stop']} [RATE LIMIT] 429 from {provider.name}! Backing off {wait:.1f}s. Attempt {attempt+1}/{max_attempts}...{C.RESET}", flush=True)
                        delay = min(delay * 2, self.max_delay)
                        time.sleep(wait)
                else:
                    provider.bucket.release()  # other error: not a server rejection
                    raise
        raise Exception(f"All providers exhausted after {max_attempts} attempts across the pool.")

    def run(self, user_message: str, thinking: bool = True):
        if self.auto_stage:
            old = self.persona["name"]
            self._auto_detect()
            if self.persona["name"] != old:
                self._rebuild_system()

        self.messages.append({"role": "user", "content": user_message})
        model = self.get_model()  # profile's selected model — only used to decide default thinking behavior below; the actual model id used on the wire comes from whichever provider serves each attempt

        continuations_left = self.max_auto_continues
        while True:
            finished = self._run_rounds(thinking)
            if finished or continuations_left <= 0:
                if not finished:
                    print(f"\n{C.BRED}{I['stop']} [ROUND LIMIT]{C.RESET} Hit {self.max_tool_rounds} tool-call "
                          f"rounds without finishing, and auto-continue is exhausted for this task. "
                          f"State is saved — send another message (e.g. 'continue') to keep going.\n", flush=True)
                    self.save_state()
                return
            # Silent death was the actual bug users hit: the loop just
            # stopped with no explanation. Instead: tell the user, then
            # automatically feed the model a "continue" turn so a task
            # that's genuinely still in progress doesn't just die.
            continuations_left -= 1
            print(f"\n{C.BYELLOW}{I['refresh']} [AUTO-CONTINUE]{C.RESET} Hit {self.max_tool_rounds} rounds — "
                  f"continuing automatically ({continuations_left} auto-continue(s) left)...\n", flush=True)
            self.save_state()
            self.messages.append({"role": "user", "content": "Continue exactly where you left off."})

    def _run_rounds(self, thinking: bool = True) -> bool:
        """Runs up to max_tool_rounds of the tool-calling loop. Returns
        True if the model produced a final (non-tool-call) answer,
        False if the round budget ran out mid-task."""
        for round_num in range(self.max_tool_rounds):
            self.maybe_compact()

            prompt_tokens_est = self.context_tokens()
            # Don't blindly ask for a fixed 4096 completion tokens —
            # if the context is already most of the way to the model's
            # window, that request can push a call over the edge and
            # trigger a hard context-length error instead of a clean
            # response. Cap the ask to what's actually left, with a
            # sane floor so short completions never get starved.
            remaining_ctx = self.context_window - prompt_tokens_est
            dynamic_max_tokens = max(512, min(4096, remaining_ctx - 512))

            print(f"{C.DIM}  [round {round_num+1}/{self.max_tool_rounds}]{C.RESET}", flush=True)

            base_payload = {
                "messages": self.messages,
                "max_tokens": dynamic_max_tokens,
                "temperature": 0.2,
                "stream": True,
                "tools": TOOLS_SCHEMA,
                "tool_choice": "auto",
            }

            full_content = ""
            full_reasoning = ""
            tool_calls = []
            in_thinking = False
            got_content = False

            try:
                if HAS_OPENAI:
                    def do_stream(provider):
                        payload = dict(base_payload)
                        payload["model"] = provider.model_id
                        if thinking and "glm" in provider.model_id:
                            payload["extra_body"] = {
                                "chat_template_kwargs": {
                                    "enable_thinking": True,
                                    "clear_thinking": False,
                                    "thinking_effort": "max",
                                }
                            }
                        return provider.client.chat.completions.create(**payload)

                    resp = self._call_with_backoff(do_stream)
                    for chunk in resp:
                        delta = chunk.choices[0].delta

                        reasoning = getattr(delta, "reasoning_content", None)
                        if reasoning:
                            if not in_thinking:
                                print(f"\n{C.BMAGENTA}{H*30}{C.RESET}")
                                print(f"{C.BMAGENTA}{I['brain']} [Thinking]{C.RESET}", end="", flush=True)
                                in_thinking = True
                            print(reasoning, end="", flush=True)
                            full_reasoning += reasoning

                        content = delta.content or ""
                        if content:
                            if in_thinking:
                                print(f"\n{C.BMAGENTA}{H*30}{C.RESET}")
                                in_thinking = False
                            if not got_content:
                                print(f"\n{C.BGREEN}{I['bot']} [Response]{C.RESET}", end="", flush=True)
                                got_content = True
                            print(content, end="", flush=True)
                            full_content += content

                        tc_list = getattr(delta, "tool_calls", None)
                        if tc_list:
                            for tc in tc_list:
                                idx = tc.index
                                while len(tool_calls) <= idx:
                                    tool_calls.append({"id": "", "name": "", "arguments": ""})
                                if tc.id: tool_calls[idx]["id"] += tc.id
                                if tc.function:
                                    if tc.function.name: tool_calls[idx]["name"] += tc.function.name
                                    if tc.function.arguments: tool_calls[idx]["arguments"] += tc.function.arguments
                else:
                    def do_http(provider):
                        payload = {k: v for k, v in base_payload.items() if k != "stream"}
                        payload["model"] = provider.model_id
                        if thinking and "glm" in provider.model_id:
                            payload["chat_template_kwargs"] = {
                                "enable_thinking": True,
                                "clear_thinking": False,
                                "thinking_effort": "max",
                            }
                        return self._http_chat(payload, provider)
                    content, reasoning = self._call_with_backoff(do_http)
                    if reasoning:
                        print(f"\n{C.BMAGENTA}{H*30}{C.RESET}")
                        print(f"{C.BMAGENTA}{I['brain']} [Thinking]{C.RESET}\n{reasoning}\n{C.BMAGENTA}{H*30}{C.RESET}", flush=True)
                    print(f"\n{C.BGREEN}{I['bot']} [Response]{C.RESET}\n{content}", flush=True)
                    full_content = content
                    full_reasoning = reasoning or ""

            except Exception as e:
                print(f"\n{I['cross']} {C.BRED}[ERR]{C.RESET} {e}", flush=True)
                return True  # don't auto-continue into a repeat of a hard error

            print("", flush=True)

            completion_tokens_est = estimate_tokens(full_content) + estimate_tokens(full_reasoning)
            for tc in tool_calls:
                completion_tokens_est += estimate_tokens(tc.get("arguments", ""))
            self.token_meter.record(prompt_tokens_est, completion_tokens_est)

            if tool_calls:
                assistant_msg = {"role": "assistant", "content": full_content or None}
                formatted_tc = []
                for tc in tool_calls:
                    formatted_tc.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]}
                    })
                assistant_msg["tool_calls"] = formatted_tc
                self.messages.append(assistant_msg)

                for tc in tool_calls:
                    name = tc["name"]
                    try:
                        args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except:
                        args = {}
                    print(f"\n{C.BYELLOW}{H*50}{C.RESET}")
                    print(f"{C.BYELLOW}{I['tools']} [Tool]{C.RESET} {C.BOLD}{C.BWHITE}{name}{C.RESET}({C.DIM}{json.dumps(args)}{C.RESET})")
                    print(f"{C.BYELLOW}{H*50}{C.RESET}\n", flush=True)
                    result = execute_tool(self.tools, name, args)
                    result = self._truncate_tool_result(result)
                    print(result[:500] + ("\n..." if len(result) > 500 else ""), flush=True)

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": name,
                        "content": result,
                    })

                # Checkpoint after every round, not just at REPL exit —
                # a crash or Ctrl-C mid-task otherwise loses everything
                # this round's tool calls just did, even though it's
                # already sitting in self.messages in memory.
                self.save_state()
                continue
            else:
                self.messages.append({"role": "assistant", "content": full_content})
                return True
        return False  # ran out of rounds without a final answer

    def _truncate_tool_result(self, result: str) -> str:
        """Cap a tool result's size against how much context budget is
        actually left, instead of a fixed char count. A fixed cap
        either wastes headroom on a near-empty context or, on a
        nearly-full one, still leaves too little room for the model's
        own next response — this scales with what's really available.
        """
        remaining_tokens = max(0, self.context_window - self.context_tokens())
        # Never let one tool result eat more than ~40% of what's left,
        # and keep sane absolute floor/ceiling so tiny or huge windows
        # both behave reasonably.
        budget_chars = int(max(2000, min(16000, remaining_tokens * 0.4 * 4)))
        if len(result) > budget_chars:
            half = budget_chars // 2
            result = result[:half] + f"\n... [truncated {len(result) - budget_chars} chars] ...\n" + result[-half:]
        return result

    def _http_chat(self, payload: Dict, provider: "Provider") -> tuple:
        req = urllib.request.Request(
            f"{provider.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            content = msg.get("content", "")
            reasoning = msg.get("reasoning_content")
            return content, reasoning

    def clear(self):
        self.messages = []
        self._rebuild_system()

    def save_state(self):
        pk = "general"
        for k, v in PERSONAS.items():
            if v["name"] == self.persona["name"]: pk = k; break
        save_session(self.profile["name"], self.project_dir, {
            "profile": self.profile["name"],
            "model_key": self.active_model_key,
            "persona_key": pk,
            "persona": self.persona["name"],
            "goal": self.goal,
            "auto_stage": self.auto_stage,
            "last_detected_stage": self.last_stage,
            "timestamp": datetime.now().isoformat(),
            "messages": self.messages,
        })

    def save_history(self):
        data = {
            "profile": self.profile["name"],
            "model": self.get_model()["name"],
            "persona": self.persona["name"],
            "goal": self.goal,
            "timestamp": datetime.now().isoformat(),
            "messages": self.messages,
        }
        histories = []
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                histories = json.load(f)
        histories.append(data)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(histories[-10:], f, indent=2, ensure_ascii=False)

# ───────────────────────────────────────────
# UI
# ───────────────────────────────────────────
def banner():
    _boot_sequence()
    width = 60
    title = "N I M   A G E N T"
    tagline = "Autonomous Coding Agent"
    subline = "Multi-Provider Pool  ·  Token-Bucket RPM  ·  Persistent Profiles"

    print()
    print(f"  {gradient_rule(width)}")
    print(f"  {' '*max(0,(width-len(title))//2)}{C.BOLD}{gradient(title)}{C.RESET}")
    print(f"  {' '*max(0,(width-len(tagline))//2)}{C.DIM}{tagline}{C.RESET}")
    print(f"  {gradient_rule(width)}")
    print(f"  {' '*max(0,(width-len(subline))//2)}{C.DIM}{subline}{C.RESET}")
    print()

def print_profiles(config: Dict):
    profiles = list_profiles(config)
    if not profiles:
        warn("No profiles configured — use /profile add to create one.")
        return
    print(f"  {C.BOLD}Profiles{C.RESET}")
    print(f"  {gradient_rule(58)}")
    for pid, p in profiles.items():
        has = f"{C.BGREEN}●{C.RESET} key set" if p.get("key") else f"{C.BRED}●{C.RESET} no key"
        rpm = p.get("rpm", 20.0)
        print(f"  {C.BOLD}[{pid}]{C.RESET} {C.BWHITE}{p['name']:<18}{C.RESET} {has}  {C.DIM}{rpm} rpm{C.RESET}")
        for mk, mv in p.get("models", {}).items():
            marker = f" {C.GREEN}(default){C.RESET}" if mk == p.get("default_model") else ""
            print(f"        {C.DIM}{mk:<9}{C.RESET}{C.CYAN}{mv['id']}{C.RESET}{marker}")
    print()

def print_personas():
    print(f"  {C.BOLD}Personas{C.RESET}  {C.DIM}(auto-detected — switch manually with /agent <name>){C.RESET}")
    for k, p in PERSONAS.items():
        print(f"    {C.DIM}/agent{C.RESET} {C.CYAN}{k:<12}{C.RESET} {p['color']}{p['icon']}{C.RESET}  {p['description']} {C.DIM}[{p['stage']}]{C.RESET}")
    print()

def help_text():
    print(f"""
  {gradient_rule(58)}
  {C.BOLD}COMMANDS{C.RESET}
  {gradient_rule(58)}
  {C.BYELLOW}/goal <text>{C.RESET}        {C.DIM}Set project goal{C.RESET}
  {C.BYELLOW}/agent <name>{C.RESET}       {C.DIM}Manual persona (disables auto){C.RESET}
  {C.BYELLOW}/agent auto{C.RESET}         {C.DIM}Re-enable auto stage detection{C.RESET}
  {C.BYELLOW}/model{C.RESET}              {C.DIM}Show current model{C.RESET}
  {C.BYELLOW}/model <key>{C.RESET}        {C.DIM}Switch model in current profile{C.RESET}
  {C.BYELLOW}/read <path>{C.RESET}        {C.DIM}Read file{C.RESET}
  {C.BYELLOW}/ls [path]{C.RESET}          {C.DIM}List directory{C.RESET}
  {C.BYELLOW}/tree [path]{C.RESET}        {C.DIM}Directory tree{C.RESET}
  {C.BYELLOW}/search <pat> [-e .py]{C.RESET} {C.DIM}Search files{C.RESET}
  {C.BYELLOW}/write <path>{C.RESET}       {C.DIM}Interactive file writer{C.RESET}
  {C.BYELLOW}/run <command>{C.RESET}      {C.DIM}Run shell command in project dir{C.RESET}
  {C.BYELLOW}/python <script> [args]{C.RESET} {C.DIM}Run Python script{C.RESET}
  {C.BYELLOW}/test [path] [runner]{C.RESET}   {C.DIM}Run tests (pytest/unittest){C.RESET}
  {C.BYELLOW}/clear{C.RESET}              {C.DIM}Clear history{C.RESET}
  {C.BYELLOW}/forget{C.RESET}             {C.DIM}Delete saved session{C.RESET}
  {C.BYELLOW}/history{C.RESET}            {C.DIM}Show message history{C.RESET}
  {C.BYELLOW}/save{C.RESET}               {C.DIM}Save to history file{C.RESET}
  {C.BYELLOW}/switch <id>{C.RESET}        {C.DIM}Switch profile{C.RESET}
  {C.BYELLOW}/profile list{C.RESET}       {C.DIM}List all profiles{C.RESET}
  {C.BYELLOW}/profile add{C.RESET}        {C.DIM}Add a new profile interactively{C.RESET}
  {C.BYELLOW}/profile remove <id>{C.RESET}  {C.DIM}Remove a profile{C.RESET}
  {C.BYELLOW}/rpm [value]{C.RESET}        {C.DIM}Show or set RPM limit for current profile{C.RESET}
  {C.BYELLOW}/limits{C.RESET}             {C.DIM}Show RPM, TPM, tok/s, and context window usage{C.RESET}
  {C.BYELLOW}/keys{C.RESET}               {C.DIM}Show key status for all profiles{C.RESET}
  {C.BYELLOW}/help{C.RESET}               {C.DIM}This help{C.RESET}
  {C.BYELLOW}/exit{C.RESET}               {C.DIM}Exit (auto-saves){C.RESET}
  {gradient_rule(58)}

{C.DIM}Just type your message — the agent will think, use tools, modify files,
run tests/scripts, commit and push changes, working autonomously until done.
Everything streams live. TDD is enforced by default.{C.RESET}
""")

def prompt_multiline() -> str:
    print(f"{C.BCYAN}{I['edit']} Enter content (empty line to finish):{C.RESET}")
    lines = []
    while True:
        line = input(f"  {C.DIM}>{C.RESET} ")
        if line == "": break
        lines.append(line)
    return "\n".join(lines)

def prompt_add_profile(config: Dict) -> str:
    """Interactive profile creation. Returns new profile ID."""
    print(f"\n  {gradient_rule(58)}")
    print(f"  {C.BOLD}Add New Profile{C.RESET}")
    print(f"  {gradient_rule(58)}\n")

    name = input(f"  {I['tag']} Profile name: ").strip()
    while not name:
        name = input(f"  {I['warn']} Name required: ").strip()

    key = input(f"  {I['key']} NVIDIA API key: ").strip()
    while not key:
        key = input(f"  {I['warn']} Key required: ").strip()

    print(f"\n  {I['bulb']} {C.DIM}Enter model IDs for this profile. Leave blank for defaults.{C.RESET}")
    glm_id = input(f"  {I['code']} GLM model ID [z-ai/glm-5.2]: ").strip() or "z-ai/glm-5.2"
    nem_id = input(f"  {I['code']} Nemotron model ID [nvidia/nemotron-3-ultra-550b-a55b]: ").strip() or "nvidia/nemotron-3-ultra-550b-a55b"

    rpm_str = input(f"  {I['clock']} RPM limit [20]: ").strip()
    rpm = float(rpm_str) if rpm_str else 20.0

    default = input(f"  {I['star']} Default model key (glm/nemotron) [glm]: ").strip() or "glm"

    models = {
        "glm": {"name": f"{name}-GLM", "id": glm_id},
        "nemotron": {"name": f"{name}-Nemotron", "id": nem_id},
    }

    pid = add_profile(config, name, key, models, default, rpm)
    # Double-save to be absolutely sure
    save_config(config)
    ok(f"Profile '{name}' created with ID [{pid}]")
    info(f"RPM limit: {rpm} | Default: {default}")
    info(f"Config saved to: {CONFIG_FILE}")
    return pid

def main():
    banner()
    config = get_or_create_config()
    print_profiles(config)

    profiles = list_profiles(config)
    if not profiles:
        err("No profiles available. Exiting.")
        sys.exit(1)

    # Profile selection — always offer creating new
    pids = list(profiles.keys())
    default_pid = pids[0]

    print(f"{C.DIM}  Type a profile ID to use it, or 'new' to create one.{C.RESET}")
    choice = input(f"{C.BYELLOW}• Select profile [{', '.join(pids)}] or 'new' (default: {default_pid}): {C.RESET}").strip() or default_pid

    if choice.lower() == "new":
        new_pid = prompt_add_profile(config)
        profiles = list_profiles(config)
        choice = new_pid
    elif choice not in profiles:
        warn(f"Invalid profile '{choice}'. Using {default_pid}.")
        choice = default_pid

    profile = profiles[choice]
    project_dir = os.getcwd()
    agent = NIMClient(profile, project_dir, restore=True)
    model = agent.get_model()
    rpm = profile.get("rpm", 20.0)

    print(f"  {C.BGREEN}●{C.RESET} {C.BOLD}{profile['name']}{C.RESET}  {C.DIM}active{C.RESET}   {C.CYAN}{model['name']}{C.RESET} {C.DIM}({model['id']}){C.RESET}")
    print(f"  {C.DIM}Project{C.RESET}   {C.BWHITE}{project_dir}{C.RESET}")
    print(f"  {C.DIM}RPM{C.RESET}       {C.BWHITE}{rpm}{C.RESET} {C.DIM}(token bucket enforced){C.RESET}")
    print(f"  {C.DIM}Models{C.RESET}    {C.DIM}/model glm · /model nemotron{C.RESET}")
    print()
    print_personas()
    print(f"  {C.DIM}Type /help for commands, or just type your message to start.{C.RESET}\n")

    try:
        while True:
            try:
                # Show rate limit status in prompt
                rl_status = f"{agent.pool.current().name} · {agent.bucket.stats()}"
                prompt_prefix = f"{C.DIM}{rl_status}{C.RESET}\n"
                user_input = input(f"{prompt_prefix}{gradient(ARROW)} ").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n  {C.DIM}Exiting...{C.RESET}")
                break

            if not user_input: continue

            if user_input.startswith("/exit"):
                print(f"  {C.BGREEN}✓{C.RESET} Goodbye!")
                break
            elif user_input.startswith("/help"):
                help_text()
            elif user_input.startswith("/switch "):
                new = user_input[7:].strip()
                profiles = list_profiles(config)
                if new in profiles:
                    agent.save_state()
                    agent = NIMClient(profiles[new], project_dir, restore=True)
                    m = agent.get_model()
                    rpm = profiles[new].get("rpm", 20.0)
                    print(f"\n  {C.BGREEN}✓{C.RESET} Switched to {C.BOLD}{profiles[new]['name']}{C.RESET}  {C.CYAN}{m['name']}{C.RESET}")
                    print(f"  {C.DIM}RPM limit:{C.RESET} {C.BWHITE}{rpm}{C.RESET}\n")
                else:
                    err(f"Invalid profile ID '{new}'.")
            elif user_input.startswith("/profile "):
                sub = user_input[9:].strip()
                if sub == "list":
                    print_profiles(config)
                elif sub == "add":
                    prompt_add_profile(config)
                    profiles = list_profiles(config)
                elif sub.startswith("remove "):
                    pid = sub[7:].strip()
                    if pid in list_profiles(config):
                        if input(f"{C.BYELLOW}• Really remove profile [{pid}]? [y/N]: {C.RESET}").strip().lower() == "y":
                            remove_profile(config, pid)
                            ok(f"Profile [{pid}] removed.")
                            profiles = list_profiles(config)
                        else:
                            info("Cancelled.")
                    else:
                        err(f"Profile [{pid}] not found.")
                else:
                    warn("Usage: /profile list | /profile add | /profile remove <id>")
            elif user_input.startswith("/limits"):
                ctx_pct = agent.context_pct() * 100
                ctx_color = C.BGREEN if ctx_pct < 60 else C.BYELLOW if ctx_pct < agent.compact_threshold*100 else C.BRED
                print(f"\n  {C.BOLD}Rate & Resource Limits{C.RESET}")
                print(f"  {C.DIM}RPM      {C.RESET}{agent.bucket.stats()}")
                print(f"  {C.DIM}Tokens   {C.RESET}{agent.token_meter.stats()}")
                print(f"  {C.DIM}Context  {C.RESET}{ctx_color}{agent.context_tokens()} / {agent.context_window} tokens "
                      f"({ctx_pct:.0f}%){C.RESET} {C.DIM}(compacts at {int(agent.compact_threshold*100)}%){C.RESET}\n")
            elif user_input.startswith("/rpm"):
                parts = user_input.split()
                if len(parts) >= 2:
                    try:
                        new_rpm = float(parts[1])
                        agent.pool.providers[0].bucket.set_rpm(new_rpm)
                        # Also save to config
                        for pid, p in list_profiles(config).items():
                            if p["name"] == agent.profile["name"]:
                                update_profile(config, pid, rpm=new_rpm)
                                break
                        ok(f"RPM limit set to {new_rpm} (NVIDIA/primary provider)")
                    except ValueError:
                        err("Invalid RPM value.")
                else:
                    info(f"Current: {agent.pool.current().name} | {agent.bucket.rpm} RPM | {agent.bucket.stats()}")
            elif user_input.startswith("/goal "):
                agent.set_goal(user_input[6:].strip())
                ok(f"Goal set: {agent.goal}")
            elif user_input == "/goal":
                info(f"Goal: {agent.goal or 'None'}")
            elif user_input.startswith("/agent "):
                pk = user_input[7:].strip()
                if pk == "auto":
                    agent.enable_auto()
                    ok(f"Auto-Stage ON: {agent.persona['name']}")
                elif agent.set_persona(pk):
                    p = agent.persona
                    print(f"  {C.BGREEN}✓{C.RESET} {p['color']}{p['icon']}{C.RESET} {C.BOLD}{p['name']}{C.RESET} {C.DIM}(manual){C.RESET}")
                    warn("Auto-stage off — use '/agent auto' to re-enable.")
                else:
                    err("Invalid persona.")
            elif user_input == "/persona":
                mode = f"{C.BGREEN}[AUTO]{C.RESET}" if agent.auto_stage else f"{C.BYELLOW}[MANUAL]{C.RESET}"
                p = agent.persona
                print(f"{mode} {p['color']}{p['icon']}{C.RESET} {C.BOLD}{p['name']}{C.RESET} - {p['description']}")
            elif user_input.startswith("/model "):
                if agent.switch_model(user_input[7:].strip()):
                    m = agent.get_model()
                    ok(f"Model: {m['name']}")
                else:
                    err("Invalid model.")
            elif user_input == "/model":
                m = agent.get_model()
                print(f"{C.BCYAN}[Current]{C.RESET} {C.BOLD}{m['name']}{C.RESET} {C.DIM}({m['id']}){C.RESET}")
                for k, v in agent.profile["models"].items():
                    marker = f" {C.BGREEN}{I['check']} active{C.RESET}" if k == agent.active_model_key else ""
                    print(f"  {C.BYELLOW}/model {k:<10}{C.RESET} {C.DIM}-{C.RESET} {v['name']}{marker}")
            elif user_input.startswith("/read "):
                print(agent.tools.read(user_input[6:].strip().strip('"')))
            elif user_input.startswith("/ls"):
                print(agent.tools.list_dir(user_input[3:].strip().strip('"') or "."))
            elif user_input.startswith("/tree"):
                print(agent.tools.tree(user_input[5:].strip().strip('"') or "."))
            elif user_input.startswith("/search "):
                parts = user_input[8:].strip().split(" -e ")
                print(agent.tools.search(parts[0].strip('"'), ext=parts[1] if len(parts) > 1 else ""))
            elif user_input.startswith("/write "):
                path = user_input[7:].strip().strip('"')
                content = prompt_multiline()
                if content:
                    print(f"\n{C.BCYAN}Preview ({len(content)} chars):{C.RESET}")
                    print(content[:200] + "..." if len(content) > 200 else content)
                    if input(f"\n{C.BYELLOW}Write? [y/N]: {C.RESET}").strip().lower() == "y":
                        print(agent.tools.write(path, content))
                    else:
                        warn("Cancelled")
                else:
                    warn("No content")
            elif user_input.startswith("/run "):
                cmd = user_input[5:].strip()
                print(f"  {C.CYAN}{ARROW}{C.RESET} {C.BWHITE}{cmd}{C.RESET}\n")
                print(agent.tools.run_command(cmd, timeout=120))
            elif user_input.startswith("/python "):
                parts = user_input[8:].strip().split(None, 1)
                script = parts[0]
                args = parts[1] if len(parts) > 1 else ""
                print(f"  {C.CYAN}{ARROW}{C.RESET} python {C.BWHITE}{script} {args}{C.RESET}\n")
                print(agent.tools.run_python(script, args))
            elif user_input.startswith("/test"):
                parts = user_input[5:].strip().split()
                test_path = parts[0] if parts else ""
                runner = parts[1] if len(parts) > 1 else "pytest"
                print(f"  {C.MAGENTA}{ARROW}{C.RESET} {runner} {C.BWHITE}{test_path}{C.RESET}\n")
                print(agent.tools.run_tests(test_path, runner))
            elif user_input.startswith("/git "):
                sub = user_input[5:].strip()
                if sub == "status": print(agent.tools.git_status())
                elif sub == "diff": print(agent.tools.git_diff())
                elif sub.startswith("add "): print(agent.tools.git_add(sub[4:].strip()))
                elif sub.startswith("commit "): print(agent.tools.git_commit(sub[7:].strip()))
                elif sub.startswith("push"):
                    parts = sub.split()
                    remote = parts[1] if len(parts) > 1 else "origin"
                    branch = parts[2] if len(parts) > 2 else ""
                    print(agent.tools.git_push(remote, branch))
                else: warn("Use: /git status, /git diff, /git add <path>, /git commit <msg>, /git push [remote] [branch]")
            elif user_input.startswith("/clear"):
                agent.clear()
                ok("Cleared")
            elif user_input.startswith("/forget"):
                delete_session(agent.profile["name"], agent.project_dir)
                ok("Session deleted")
            elif user_input.startswith("/history"):
                for i, msg in enumerate(agent.messages):
                    if msg.get("role") == "system": continue
                    rc = C.BGREEN if msg["role"] == "user" else C.BCYAN if msg["role"] == "assistant" else C.BYELLOW
                    print(f"  {C.DIM}[{i}]{C.RESET} {rc}{msg['role']}{C.RESET}: {msg.get('content','')[:80].replace(chr(10), ' ')}...")
            elif user_input.startswith("/save"):
                agent.save_history()
                ok(f"Saved to {HISTORY_FILE}")
            elif user_input == "/keys":
                for pid, p in list_profiles(config).items():
                    status = f"{C.BGREEN}● set{C.RESET}" if p.get("key") else f"{C.BRED}● not set{C.RESET}"
                    print(f"  [{C.BOLD}{pid}{C.RESET}] {C.BWHITE}{p['name']:<18}{C.RESET} {status}")
            else:
                print(f"\n{C.BCYAN}{H*60}{C.RESET}")
                agent.run(user_input)
                print(f"{C.BCYAN}{H*60}{C.RESET}\n")
    finally:
        agent.save_state()
        print(f"  {C.BGREEN}✓{C.RESET} {C.DIM}Session saved{C.RESET}")

if __name__ == "__main__":
    main()