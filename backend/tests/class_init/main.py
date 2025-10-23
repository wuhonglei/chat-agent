class Parent1:
    def __init__(self):
        print("Parent1 init")


class Parent2:
    def __init__(self):
        print("Parent2 init")


class Child(Parent1, Parent2):
    pass


if __name__ == "__main__":
    child = Child()
    print(Child.__mro__)
