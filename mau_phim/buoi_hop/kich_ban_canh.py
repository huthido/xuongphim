# Kịch bản 12 cảnh "Buổi họp gia đình" -> 4 file đợt viec_1..4.json (mỗi đợt 3 cảnh, 512x288, 81 khung ~5 giây)
import json
from pathlib import Path
D = Path(__file__).resolve().parent
NHAN_VAT = {
    "ong": "the grandfather with gray hair, round glasses and a light blue shirt",
    "ba": "the grandmother with short white hair and a pink cardigan",
    "bo": "the father with short black hair and a navy blue sweater",
    "me": "the mother with a short black bob and a yellow floral blouse",
    "trai": "the ten-year-old son in a white t-shirt",
    "gai": "the seven-year-old daughter with pigtails and a red dress",
}
BOI_CANH = ("in a cozy living room with a wooden table and tea cups, warm afternoon light through the window, "
            "3D animated family film style, vivid colors, smooth motion")
CANH = [
    "Wide shot: {bo}, {me}, {ong} and {ba} sit around the table while {trai} and {gai} run in and sit down",
    "Medium shot: {ba} lifts a green teapot and pours tea into white cups, smiling warmly",
    "Medium shot: {bo} stands up, holds a sheet of paper and speaks, moving his free hand as he explains",
    "Close-up: {me} listens, nods several times and smiles",
    "Medium shot: {trai} raises his hand high and bounces excitedly in his chair",
    "Close-up: {gai} laughs and claps her hands happily",
    "Close-up: {ong} pushes up his glasses, leans forward and points at a map on the table",
    "Over-the-table shot: {bo} and {me} lean over a big paper map and trace a route with their fingers",
    "Medium shot: {trai} and {gai} kneel on their chairs and lean over the map with wide eyes, pointing",
    "Medium shot: {ba} laughs and hugs {gai}, who wraps her arms around her",
    "Wide shot: the whole family raises their tea cups together in a cheerful toast, smiling",
    "Wide shot, camera slowly pulls back: the whole family laughs together around the table as golden sunset light fills the room",
]
viec = []
for i, c in enumerate(CANH, 1):
    viec.append({"prompt": c.format(**NHAN_VAT) + ", " + BOI_CANH, "out": str(D / f"canh_{i:02d}.mp4")})
for k in range(4):
    (D / f"viec_{k + 1}.json").write_text(json.dumps(viec[3 * k:3 * k + 3], ensure_ascii=False, indent=1), encoding="utf-8")
print(len(viec), "canh")
