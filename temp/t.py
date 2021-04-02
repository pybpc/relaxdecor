def deco():
    def inner():
        def wr(func):
            def pr():
                print('hi')
            return pr
        return wr
    return inner

@deco().doo()
def foo():
    ...


a = deco()()
