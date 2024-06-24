from type_registrar import Type


class TestType(Type):
    TYPE_ID = "test"


a = TestType()
print(a)
