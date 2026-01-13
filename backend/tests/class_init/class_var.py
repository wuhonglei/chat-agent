class TestService:
    _cache = {}


# 第一次实例化
service1 = TestService()
service1._cache["key1"] = "value1"
print("After first instance:", TestService._cache)

# 第二次实例化
service2 = TestService()
service2._cache["key2"] = "value2"
print("After second instance:", TestService._cache)

# 验证共享
print("service1 cache:", service1._cache)
print("service2 cache:", service2._cache)
print("Same object?", service1._cache is service2._cache)
