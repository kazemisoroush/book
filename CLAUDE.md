# Coding Rules

## Testing

**No Useless Tests**: Do not write tests that simply check constructor outputs are not null or verify default values. Tests should verify behavior, not implementation details.

Examples of useless tests to avoid:
```python
# BAD - Just checking a default value
def test_field_default_is_true(self):
    obj = MyClass()
    assert obj.some_field is True

# GOOD - Testing actual behavior
def test_feature_behaves_correctly_when_enabled(self):
    obj = MyClass(feature=True)
    result = obj.do_something()
    assert result == expected_value
```

## TDD (Test-Driven Development)

Write tests before implementation. Follow the Red-Green-Refactor cycle:
1. Write a failing test (Red)
2. Write minimal code to make it pass (Green)
3. Refactor while keeping tests green

## SOLID Principles

- **S**ingle Responsibility: Each class should have one reason to change
- **O**pen/Closed: Open for extension, closed for modification
- **L**iskov Substitution: Subtypes must be substitutable for their base types
- **I**nterface Segregation: Many specific interfaces are better than one general interface
- **D**ependency Inversion: Depend on abstractions, not concretions
