class Test:
    """Test class"""
    shared_state = {
        'count': 0
    }

    def __init__(self):
        self.name = "Test"

    def test(self):
        self.shared_state['count'] += 1


test1 = Test()
test2 = Test()
test1.test()
test2.test()
print(test1.shared_state['count'])
print(test2.shared_state['count'])
