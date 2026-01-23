from toolz.dicttoolz import get_in

person = {
    "name": {
        "first": "John",
    }
}

# get_in 接受一个路径列表，而不是点号分隔的字符串
print(get_in(["name"], person))
