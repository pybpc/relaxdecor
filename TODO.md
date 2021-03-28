- [ ] bug report to `parso` for missing invalid decorator syntax

```python
@foo()()
def func1(): ...


@foo().bar()
def func2(): ...
```
