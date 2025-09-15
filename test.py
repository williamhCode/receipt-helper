import base64, os

def gen_slug(n: int = 12) -> str:
    s = base64.b32encode(os.urandom(8)).decode().lower().strip("=")
    return s.replace("o", "8").replace("l", "9")[:n]

for _ in range(10):
    print(gen_slug())

