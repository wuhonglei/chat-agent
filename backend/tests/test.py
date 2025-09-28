
class Test():
    def __init__(self):
        self.initialize()

    def initialize(self):
        self.name = 'whl'

    def say_hello(self):
        print(f"Hello, {self.name}!")


test = Test()
print(test.name)
