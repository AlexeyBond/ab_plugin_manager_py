from operations import greet_op

name = 'greeter'
version = '0.1.0'


# Декоратор <op>.implementation не обязателен если имя функции совпадает с именем операции (в т.ч. в этом примере)
@greet_op.implementation
def greet(who: str):
    print(f"Hello {who}!")
