import os
from pathlib import Path

uri = Path('https://www.baidu.com')
path = Path('images/1.png')

print(str(uri / path))
